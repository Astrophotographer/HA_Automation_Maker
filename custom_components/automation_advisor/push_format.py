"""Pure helpers for Companion push payloads (no Home Assistant imports)."""

from __future__ import annotations

_ACTION_EXTRA_KEYS = ("uri", "behavior", "authenticationRequired")


def suggestion_card_tag(suggestion_id: str) -> str:
    """One Android/iOS notification tag per suggestion so the card is reused.

    Uses the original run-stage tag so already-visible Companion cards are
    updated in place instead of spawning a second notification.
    """
    return f"advisor_run_{suggestion_id}"


def suggestion_card_tags(suggestion_id: str) -> tuple[str, ...]:
    """Current tag plus legacy tags from when run/auto used different cards."""
    sid = str(suggestion_id)
    tag = suggestion_card_tag(sid)
    return (tag, f"advisor_run_{sid}", f"advisor_auto_{sid}")


def clear_notification_payload(tag: str) -> dict:
    return {"message": "clear_notification", "data": {"tag": tag}}


def flatten_actions_for_fcm(actions: list[dict]) -> dict[str, str]:
    """Mirror Android WebsocketManager action flattening for FCM cloud push."""
    flat: dict[str, str] = {}
    for index, action in enumerate(actions[:3], start=1):
        flat[f"action_{index}_key"] = str(action["action"])
        flat[f"action_{index}_title"] = str(action["title"])
        for extra in _ACTION_EXTRA_KEYS:
            if extra in action:
                flat[f"action_{index}_{extra}"] = str(action[extra])
    return flat


def mobile_card_payload(
    *, title: str, body: str, suggestion_id: str, actions: list[dict]
) -> dict:
    """Companion payload. Same suggestion_id always replaces the same card."""
    tag = suggestion_card_tag(str(suggestion_id))
    flat = flatten_actions_for_fcm(actions)
    for index in range(1, 4):
        flat.setdefault(f"action_{index}_key", "")
        flat.setdefault(f"action_{index}_title", "")
    return {
        "title": title,
        "message": body,
        "data": {
            "tag": tag,
            "group": tag,
            "channel": "Automation Advisor",
            "importance": "high",
            "priority": "high",
            # Keep the same Android/iOS row so title/actions can be replaced.
            "sticky": True,
            "alert_once": True,
            "actions": actions,
            **flat,
        },
    }
