"""Read Home Assistant registries into a local snapshot. Does not interpret patterns."""

from __future__ import annotations

from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
)

from .models import EntitySnap


def _display_name(
    hass: HomeAssistant,
    state: State,
    entry: er.RegistryEntry | None,
    device: dr.DeviceEntry | None,
) -> str:
    """Resolve the same Korean/UI name users see in Home Assistant."""
    attr_name = state.attributes.get("friendly_name")
    if isinstance(attr_name, str) and attr_name.strip() and attr_name != state.entity_id:
        return attr_name.strip()

    if entry is not None:
        try:
            full = er.async_get_full_entity_name(hass, entry)
            if isinstance(full, str) and full.strip():
                return full.strip()
        except Exception:  # noqa: BLE001 — fall through to simpler fields
            pass
        if entry.name and str(entry.name).strip():
            return str(entry.name).strip()
        parts: list[str] = []
        if device is not None:
            device_name = device.name_by_user or device.name
            if device_name:
                parts.append(str(device_name))
        if entry.original_name:
            parts.append(str(entry.original_name))
        if parts:
            return " ".join(parts)

    if device is not None:
        device_name = device.name_by_user or device.name
        if device_name:
            return str(device_name)

    return state.entity_id


def snapshot_inventory(hass: HomeAssistant) -> list[EntitySnap]:
    ent_reg = er.async_get(hass)
    area_reg = ar.async_get(hass)
    dev_reg = dr.async_get(hass)
    snaps: list[EntitySnap] = []

    for state in hass.states.async_all():
        entry = ent_reg.async_get(state.entity_id)
        device = None
        area_id = None
        if entry:
            area_id = entry.area_id
            if entry.device_id:
                device = dev_reg.async_get(entry.device_id)
                if not area_id and device:
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
                friendly_name=_display_name(hass, state, entry, device),
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
