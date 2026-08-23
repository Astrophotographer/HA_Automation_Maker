"""Ask in the Home Assistant Companion app first; persistent notification is fallback."""

from __future__ import annotations

from homeassistant.core import HomeAssistant

from .actions import KIND_DEPLOY, KIND_DISMISS, KIND_LATER, KIND_RUN, encode_action
from .push_format import flatten_actions_for_fcm


def _mobile_payload(*, title: str, body: str, tag: str, actions: list[dict]) -> dict:
    return {
        "title": title,
        "message": body,
        "data": {
            "tag": tag,
            "group": tag,
            "channel": "Automation Advisor",
            "importance": "high",
            "priority": "high",
            "sticky": True,
            "actions": actions,
            **flatten_actions_for_fcm(actions),
        },
    }


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


def _web_run_message(suggestion: dict) -> str:
    sid = str(suggestion["id"])
    return (
        f"**{suggestion.get('title')}**\n\n"
        f"{suggestion.get('explanation')}\n\n"
        "지금 한 번만 실행합니다. 자동화는 아직 등록하지 않습니다.\n\n"
        "**폰:** Companion 푸시 알림을 펼친 뒤 [실행] [나중에] [기각]\n\n"
        "**웹(개발자 도구 → 서비스):**\n"
        f"- 실행: `automation_advisor.run_once` → suggestion_id `{sid}`\n"
        f"- 기각: `automation_advisor.dismiss` → suggestion_id `{sid}`"
    )


def _web_auto_message(suggestion: dict) -> str:
    sid = str(suggestion["id"])
    return (
        f"**{suggestion.get('title')}**\n\n"
        "방금 한 번 실행해 봤습니다. 조건이 맞을 때마다 반복할까요?\n\n"
        "등록하면 시험 모드(꺼진 상태)로 들어갑니다.\n\n"
        "**폰:** [자동화] [아니요]\n\n"
        "**웹(개발자 도구 → 서비스):**\n"
        f"- 자동화: `automation_advisor.deploy` → suggestion_id `{sid}`\n"
        f"- 거절: `automation_advisor.dismiss` → suggestion_id `{sid}`"
    )


async def sync_web_inbox(hass: HomeAssistant, pending: list[dict]) -> None:
    """One sidebar notification listing all pending suggestions for the HA web UI."""
    if not pending:
        await hass.services.async_call(
            "persistent_notification",
            "dismiss",
            {"notification_id": "advisor_inbox"},
            blocking=False,
        )
        return
    lines = [
        "HA 웹 **알림(왼쪽 사이드바 종 아이콘)** 에서 확인하세요. "
        "Companion 푸시와 같은 추천입니다.\n"
    ]
    for suggestion in pending[:8]:
        sid = str(suggestion["id"])
        lines.append(
            f"### {suggestion.get('title')}\n"
            f"{suggestion.get('explanation')}\n\n"
            f"- 실행: `automation_advisor.run_once` / `{sid}`\n"
            f"- 기각: `automation_advisor.dismiss` / `{sid}`\n"
        )
    await _persistent(
        hass,
        f"Automation Advisor — 대기 {len(pending)}건",
        "\n".join(lines),
        "advisor_inbox",
    )


async def ask_run_once(hass: HomeAssistant, suggestion: dict) -> None:
    sid = str(suggestion["id"])
    title = "실행하시겠습니까?"
    body = (
        f"{suggestion.get('title')}\n{suggestion.get('explanation')}\n\n"
        "지금 한 번만 실행합니다. 자동화는 아직 등록하지 않습니다."
    )
    payload = _mobile_payload(
        title=title,
        body=body,
        tag=f"advisor_run_{sid}",
        actions=[
            {"action": encode_action(KIND_RUN, sid), "title": "실행"},
            {"action": encode_action(KIND_LATER, sid), "title": "나중에"},
            {"action": encode_action(KIND_DISMISS, sid), "title": "기각"},
        ],
    )
    await _persistent(hass, title, _web_run_message(suggestion), f"advisor_run_{sid}")
    await _fanout_mobile(hass, payload)


async def ask_automate(hass: HomeAssistant, suggestion: dict) -> None:
    sid = str(suggestion["id"])
    title = "자동화하시겠습니까?"
    body = (
        f"{suggestion.get('title')}\n방금 한 번 실행해 봤습니다. "
        "조건이 맞을 때마다 반복할까요?\n\n"
        "등록하면 시험 모드(꺼진 상태)로 들어갑니다."
    )
    payload = _mobile_payload(
        title=title,
        body=body,
        tag=f"advisor_auto_{sid}",
        actions=[
            {"action": encode_action(KIND_DEPLOY, sid), "title": "자동화"},
            {"action": encode_action(KIND_DISMISS, sid), "title": "아니요"},
        ],
    )
    await _persistent(hass, title, _web_auto_message(suggestion), f"advisor_auto_{sid}")
    await _fanout_mobile(hass, payload)
