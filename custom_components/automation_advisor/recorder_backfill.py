"""Backfill learnable events from Home Assistant Recorder into the local store."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any, Iterable

from .actor import SENSOR_DOMAINS, classify_actor, is_learnable
from .const import OBSERVE_SKIP_DOMAINS
from .event_store import EventStore

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

# Re-fetch a little overlap so incremental backfills stay contiguous.
_BACKFILL_OVERLAP = timedelta(hours=1)


def entity_ids_for_backfill(entity_ids: Iterable[str]) -> list[str]:
    """Entity ids worth querying from Recorder (learnable domains only)."""
    selected: list[str] = []
    for entity_id in entity_ids:
        if "." not in entity_id:
            continue
        domain = entity_id.split(".", 1)[0]
        if domain in OBSERVE_SKIP_DOMAINS or domain in SENSOR_DOMAINS:
            continue
        selected.append(entity_id)
    return sorted(set(selected))


def iter_learnable_changes(
    entity_id: str,
    states: list[Any],
    *,
    area_id: str | None,
) -> list[dict[str, Any]]:
    """Turn Recorder state rows into learnable event payloads."""
    if "." not in entity_id:
        return []
    domain = entity_id.split(".", 1)[0]
    events: list[dict[str, Any]] = []

    for index, state in enumerate(states):
        if index == 0:
            continue
        new_val = getattr(state, "state", None)
        if new_val is None:
            continue
        old_val = getattr(states[index - 1], "state", None) if index > 0 else None
        if new_val == old_val:
            continue

        context = getattr(state, "context", None)
        actor = classify_actor(
            entity_domain=domain,
            user_id=getattr(context, "user_id", None) if context else None,
            parent_id=getattr(context, "parent_id", None) if context else None,
            context_id=getattr(context, "id", None) if context else None,
        )
        if not is_learnable(actor):
            continue

        changed = getattr(state, "last_changed", None) or getattr(
            state, "last_updated", None
        )
        if changed is None:
            continue
        if changed.tzinfo is None:
            changed = changed.replace(tzinfo=timezone.utc)
        else:
            changed = changed.astimezone(timezone.utc)

        events.append(
            {
                "ts": changed.timestamp(),
                "entity_id": entity_id,
                "domain": domain,
                "old_state": old_val,
                "new_state": new_val,
                "actor": actor,
                "area_id": area_id,
            }
        )
    return events


def _area_map(hass: HomeAssistant) -> dict[str, str | None]:
    mapping: dict[str, str | None] = {}
    try:
        from homeassistant.helpers import device_registry as dr
        from homeassistant.helpers import entity_registry as er

        ent_reg = er.async_get(hass)
        dev_reg = dr.async_get(hass)
        for entry in ent_reg.entities.values():
            area_id = entry.area_id
            if not area_id and entry.device_id:
                device = dev_reg.async_get(entry.device_id)
                if device:
                    area_id = device.area_id
            mapping[entry.entity_id] = area_id
    except Exception:  # noqa: BLE001
        return mapping
    return mapping


async def backfill_from_recorder(
    hass: HomeAssistant,
    store: EventStore,
    *,
    days: int,
) -> int:
    """Import learnable Recorder history; dedupe against existing SQLite rows."""
    try:
        from homeassistant.components.recorder import get_instance
        from homeassistant.components.recorder.history import state_changes_during_period
        from homeassistant.util import dt as dt_util
    except ImportError:
        _LOGGER.debug("Recorder component unavailable — skipping backfill")
        return 0

    recorder = get_instance(hass)
    if recorder is None:
        _LOGGER.debug("Recorder not loaded — skipping backfill")
        return 0

    entity_ids = entity_ids_for_backfill(hass.states.async_entity_ids())
    if not entity_ids:
        return 0

    end_time = dt_util.utcnow()
    max_ts = await hass.async_add_executor_job(store.max_ts)
    if max_ts:
        start_time = datetime.fromtimestamp(max_ts, tz=timezone.utc) - _BACKFILL_OVERLAP
    else:
        start_time = end_time - timedelta(days=days)

    areas = _area_map(hass)
    inserted = 0

    try:
        history = await hass.async_add_executor_job(
            state_changes_during_period,
            hass,
            start_time,
            end_time,
            entity_ids,
            False,
            True,
        )
    except Exception as err:  # noqa: BLE001
        _LOGGER.warning("Recorder backfill failed: %s", err)
        return 0

    for entity_id, states in (history or {}).items():
        for payload in iter_learnable_changes(
            entity_id,
            states or [],
            area_id=areas.get(entity_id),
        ):
            added = await hass.async_add_executor_job(
                store.insert_if_new,
                **payload,
            )
            if added:
                inserted += 1

    if inserted:
        _LOGGER.info(
            "Automation Advisor: recorder backfill added %d learnable events", inserted
        )
    return inserted
