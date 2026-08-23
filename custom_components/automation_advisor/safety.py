"""Safety gate. High-risk domains never become actions."""

from __future__ import annotations

BLOCKED_ACTION_DOMAINS = {
    "lock",
    "alarm_control_panel",
    "camera",
    "climate",
    "water_heater",
    "vacuum",
    "alarm",
}


def is_blocked(entity_ids: list[str] | None) -> bool:
    for entity_id in entity_ids or []:
        domain = entity_id.split(".", 1)[0]
        if domain in BLOCKED_ACTION_DOMAINS:
            return True
    return False
