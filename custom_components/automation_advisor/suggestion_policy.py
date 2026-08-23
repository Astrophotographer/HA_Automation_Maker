"""Suggestion lifecycle rules (no Home Assistant import)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from .const import DISMISS_COOLDOWN_DAYS

_ACTIVE = frozenset({"pending", "previewed", "deployed", "killed"})


def suggestion_key(suggestion: dict) -> tuple:
    return (
        suggestion.get("recipe_id"),
        suggestion.get("area_id"),
        tuple(suggestion.get("entities") or []),
    )


def _parse_when(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def blocks_resuggestion(
    suggestion: dict,
    *,
    now: datetime | None = None,
    cooldown_days: int = DISMISS_COOLDOWN_DAYS,
) -> bool:
    """True if this stored suggestion should stop the same key from being added again."""
    status = suggestion.get("status")
    if status in _ACTIVE:
        return True
    if status != "dismissed":
        return False

    when = _parse_when(suggestion.get("dismissed_at"))
    if when is None:
        # Legacy dismiss without timestamp: allow re-suggest on next scan.
        return False

    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return now < when + timedelta(days=cooldown_days)
