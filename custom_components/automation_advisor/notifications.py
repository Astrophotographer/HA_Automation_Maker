"""Ask in the Home Assistant Companion app first; persistent notification is fallback."""

from __future__ import annotations

from homeassistant.core import HomeAssistant

from .behavior import suggestion_detail_text
from .actions import KIND_DEPLOY, KIND_DISMISS, KIND_LATER, KIND_RUN, encode_action
from .push_format import (
    clear_notification_payload,
    mobile_card_payload,
    suggestion_card_tag,
    suggestion_card_tags,
)


async def _fanout_mobile(hass: HomeAssistant, payload: dict) -> int:
    notify = hass.services.async_services().get("notify", {})
    sent = 0
    for name in notify:
        if not str(name).startswith("mobile_app_"):
            continue
        await hass.services.async_call("notify", name, payload, blocking=False)
        sent += 1
    return sent


async def _persistent(hass: HomeAssistant, title: str, message: str, notification_id: str) -> None:
    await hass.services.async_call(
        "persistent_notification",
        "create",
        {"title": title, "message": message, "notification_id": notification_id},
        blocking=True,
    )


async def clear_suggestion_card(hass: HomeAssistant, suggestion_id: str) -> None:
    """Remove this suggestion's Companion card and matching web inbox entries."""
    for tag in suggestion_card_tags(suggestion_id):
        await hass.services.async_call(
            "persistent_notification",
            "dismiss",
            {"notification_id": tag},
            blocking=False,
        )
        await _fanout_mobile(hass, clear_notification_payload(tag))


def _web_run_message(suggestion: dict) -> str:
    sid = str(suggestion["id"])
    detail = suggestion_detail_text(suggestion)
    return (
        f"{suggestion.get('title')}\n\n"
        f"{detail}\n\n"
        "【실행】을 누르면 조건을 기다리지 않고 지금 동작만 한 번 실행합니다.\n"
        "같은 알림에서 자동화 여부를 이어서 묻습니다.\n\n"
        "폰: Companion 푸시를 펼친 뒤 [실행] [나중에] [기각]\n\n"
        "웹: 사이드바 Automation Advisor 대시보드에서 버튼을 누르세요.\n\n"
        f"직접: `automation_advisor.run_once` → `{sid}`"
    )


def _web_auto_message(suggestion: dict) -> str:
    sid = str(suggestion["id"])
    detail = suggestion_detail_text(suggestion)
    return (
        f"{suggestion.get('title')}\n\n"
        f"{detail}\n\n"
        "방금 한 번 실행해 봤습니다. 위 조건이 맞을 때마다 반복할까요?\n\n"
        "등록하면 시험 모드(꺼진 상태)로 들어갑니다.\n\n"
        "폰: [자동화] [아니요]\n\n"
        "웹: 사이드바 Automation Advisor 대시보드에서 버튼을 누르세요.\n\n"
        f"직접: `automation_advisor.deploy` → `{sid}`"
    )


async def sync_web_inbox(
    hass: HomeAssistant,
    pending: list[dict],
    previewed: list[dict] | None = None,
) -> None:
    """Refresh HA web inbox notification + Lovelace dashboard with buttons."""
    from .web_dashboard import DASHBOARD_URL, VIEW_PATH, ensure_web_dashboard

    pending = [s for s in pending if not s.get("snoozed")]
    await ensure_web_dashboard(hass, pending, previewed)

    if not pending and not (previewed or []):
        await hass.services.async_call(
            "persistent_notification",
            "dismiss",
            {"notification_id": "advisor_inbox"},
            blocking=False,
        )
        return

    lines = [
        "사이드바 알림(종)은 해제만 됩니다.\n\n"
        f"웹에서 승인: [Automation Advisor 대시보드 열기]"
        f"(/{DASHBOARD_URL}/{VIEW_PATH})\n\n"
        "거기에 [실행] [기각] 버튼이 있습니다.\n"
    ]
    for suggestion in pending[:8]:
        sid = str(suggestion["id"])
        lines.append(f"- {suggestion.get('title')} (`{sid}`)")
    await _persistent(
        hass,
        f"Automation Advisor — 대기 {len(pending)}건 (웹은 대시보드에서 승인)",
        "\n".join(lines),
        "advisor_inbox",
    )


async def ask_run_once(hass: HomeAssistant, suggestion: dict) -> None:
    sid = str(suggestion["id"])
    title = "실행하시겠습니까?"
    detail = suggestion_detail_text(suggestion)
    body = (
        f"{suggestion.get('title')}\n{detail}\n\n"
        "[실행]=지금 동작만 1회. 같은 알림에서 자동화할지 이어서 묻습니다."
    )
    payload = mobile_card_payload(
        title=title,
        body=body,
        suggestion_id=sid,
        actions=[
            {"action": encode_action(KIND_RUN, sid), "title": "실행"},
            {"action": encode_action(KIND_LATER, sid), "title": "나중에"},
            {"action": encode_action(KIND_DISMISS, sid), "title": "기각"},
        ],
    )
    await _persistent(hass, title, _web_run_message(suggestion), suggestion_card_tag(sid))
    await _fanout_mobile(hass, payload)


async def ask_automate(hass: HomeAssistant, suggestion: dict) -> None:
    sid = str(suggestion["id"])
    # Kill any legacy second-card tags from older builds before replacing.
    for tag in suggestion_card_tags(sid):
        if tag == suggestion_card_tag(sid):
            continue
        await hass.services.async_call(
            "persistent_notification",
            "dismiss",
            {"notification_id": tag},
            blocking=False,
        )
        await _fanout_mobile(hass, clear_notification_payload(tag))
    title = "자동화하시겠습니까?"
    detail = suggestion_detail_text(suggestion)
    body = (
        f"{suggestion.get('title')}\n{detail}\n\n"
        "방금 한 번 실행해 봤습니다. 위 조건이 맞을 때마다 반복할까요?\n"
        "등록하면 시험 모드(꺼진 상태)로 들어갑니다."
    )
    payload = mobile_card_payload(
        title=title,
        body=body,
        suggestion_id=sid,
        actions=[
            {"action": encode_action(KIND_DEPLOY, sid), "title": "자동화"},
            {"action": encode_action(KIND_DISMISS, sid), "title": "아니요"},
        ],
    )
    await _persistent(hass, title, _web_auto_message(suggestion), suggestion_card_tag(sid))
    await _fanout_mobile(hass, payload)


async def confirm_deployed(hass: HomeAssistant, suggestion: dict, trial_note: str) -> None:
    sid = str(suggestion["id"])
    auto = suggestion.get("automation") or {}
    title = f"등록했습니다: {auto.get('alias', suggestion.get('title'))}"
    body = f"{suggestion.get('explanation')}\n\n{trial_note}\n\n이 알림은 닫으시면 됩니다."
    payload = mobile_card_payload(
        title=title, body=body, suggestion_id=sid, actions=[]
    )
    await _persistent(hass, title, body, suggestion_card_tag(sid))
    await _fanout_mobile(hass, payload)
