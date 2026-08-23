"""Pure helpers for Companion push payloads (no Home Assistant imports)."""

from __future__ import annotations

_ACTION_EXTRA_KEYS = ("uri", "behavior", "authenticationRequired")


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
