"""Ask in the Home Assistant Companion app first; persistent notification is fallback."""

from __future__ import annotations

from homeassistant.core import HomeAssistant

from .actions import KIND_DEPLOY, KIND_DISMISS, KIND_LATER, KIND_RUN, encode_action


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
        blocking=False,
    )


async def ask_run_once(hass: HomeAssistant, suggestion: dict) -> None:
    sid = str(suggestion["id"])
    title = "실행하시겠습니까?"
    body = (
        f"{suggestion.get('title')}\n{suggestion.get('explanation')}\n\n"
        "지금 한 번만 실행합니다. 자동화는 아직 등록하지 않습니다."
    )
    payload = {
        "title": title,
        "message": body,
        "data": {
            "tag": f"advisor_run_{sid}",
            "actions": [
                {"action": encode_action(KIND_RUN, sid), "title": "실행"},
                {"action": encode_action(KIND_LATER, sid), "title": "나중에"},
                {"action": encode_action(KIND_DISMISS, sid), "title": "기각"},
            ],
        },
    }
    sent = await _fanout_mobile(hass, payload)
    extra = ""
    if sent == 0:
        extra = (
            f"\n\nCompanion 앱이 없으면 개발자 도구에서 "
            f"`automation_advisor.run_once` → `{sid}`"
        )
    await _persistent(hass, title, body + extra, f"advisor_run_{sid}")


async def ask_automate(hass: HomeAssistant, suggestion: dict) -> None:
    sid = str(suggestion["id"])
    title = "자동화하시겠습니까?"
    body = (
        f"{suggestion.get('title')}\n방금 한 번 실행해 봤습니다. "
        "조건이 맞을 때마다 반복할까요?\n\n"
        "등록하면 시험 모드(꺼진 상태)로 들어갑니다."
    )
    payload = {
        "title": title,
        "message": body,
        "data": {
            "tag": f"advisor_auto_{sid}",
            "actions": [
                {"action": encode_action(KIND_DEPLOY, sid), "title": "자동화"},
                {"action": encode_action(KIND_DISMISS, sid), "title": "아니요"},
            ],
        },
    }
    sent = await _fanout_mobile(hass, payload)
    extra = ""
    if sent == 0:
        extra = (
            f"\n\n개발자 도구에서 `automation_advisor.deploy` → `{sid}`"
        )
    await _persistent(hass, title, body + extra, f"advisor_auto_{sid}")
