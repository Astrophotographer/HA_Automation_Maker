"""Read Home Assistant registries into a local snapshot. Does not interpret patterns."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
)

from .models import EntitySnap


def snapshot_inventory(hass: HomeAssistant) -> list[EntitySnap]:
    ent_reg = er.async_get(hass)
    area_reg = ar.async_get(hass)
    dev_reg = dr.async_get(hass)
    snaps: list[EntitySnap] = []

    for state in hass.states.async_all():
        entry = ent_reg.async_get(state.entity_id)
        area_id = None
        if entry:
            area_id = entry.area_id
            if not area_id and entry.device_id:
                device = dev_reg.async_get(entry.device_id)
                if device:
                    area_id = device.area_id
        area_name = None
        if area_id:
            area = area_reg.async_get_area(area_id)
            if area:
                area_name = area.name
        device_class = None
        if entry is not None:
            device_class = entry.device_class or entry.original_device_class
        if not device_class:
            device_class = state.attributes.get("device_class")

        snaps.append(
            EntitySnap(
                entity_id=state.entity_id,
                domain=state.domain,
                device_class=device_class,
                area_id=area_id,
                area_name=area_name,
                state=state.state,
                friendly_name=str(state.attributes.get("friendly_name") or state.entity_id),
                attributes=dict(state.attributes),
            )
        )
    return snaps


def existing_automation_entity_sets(hass: HomeAssistant) -> list[set[str]]:
    sets: list[set[str]] = []
    for state in hass.states.async_all("automation"):
        raw = state.attributes.get("entity_id")
        if isinstance(raw, str):
            raw = [raw]
        if raw:
            sets.append(set(raw))
    return sets
