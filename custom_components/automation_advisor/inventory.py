"""Read Home Assistant registries into a local snapshot. Does not interpret patterns."""

from __future__ import annotations

import logging

from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
)

from .models import EntitySnap

from .labels import resolve_display_name

_LOGGER = logging.getLogger(__name__)


def build_entity_names(hass: HomeAssistant) -> dict[str, str]:
    """Map entity_id → Korean/UI label (same idea as the HA frontend)."""
    ent_reg = er.async_get(hass)
    dev_reg = dr.async_get(hass)
    names: dict[str, str] = {}

    for entity_id, entry in ent_reg.entities.items():
        device = None
        if entry.device_id:
            device = dev_reg.devices.get(entry.device_id)
        state = hass.states.get(entity_id)
        names[entity_id] = _resolve_name(hass, entity_id, entry, device, state)

    # Also cover any state that might not be in the registry yet
    for state in hass.states.async_all():
        if state.entity_id not in names:
            names[state.entity_id] = _resolve_name(
                hass, state.entity_id, None, None, state
            )
    return names


def build_entity_display_names(hass: HomeAssistant) -> dict[str, str]:
    """Map entity_id → concise area · device label for notifications."""
    ent_reg = er.async_get(hass)
    dev_reg = dr.async_get(hass)
    area_reg = ar.async_get(hass)
    full_names = build_entity_names(hass)
    display: dict[str, str] = {}

    for entity_id, entry in ent_reg.entities.items():
        device = dev_reg.devices.get(entry.device_id) if entry.device_id else None
        area_id = entry.area_id or (device.area_id if device else None)
        area_name = None
        if area_id:
            area = area_reg.async_get_area(area_id)
            if area:
                area_name = area.name
        display[entity_id] = resolve_display_name(
            entity_id,
            entry=entry,
            device=device,
            area_name=area_name,
            full_name=full_names.get(entity_id),
        )

    for entity_id, full_name in full_names.items():
        if entity_id not in display:
            display[entity_id] = full_name if full_name != entity_id else entity_id
    return display


def _resolve_name(
    hass: HomeAssistant,
    entity_id: str,
    entry: er.RegistryEntry | None,
    device: dr.DeviceEntry | None,
    state: State | None,
) -> str:
    if entry is not None and entry.name and str(entry.name).strip():
        return str(entry.name).strip()

    device_name = None
    if device is not None:
        device_name = device.name_by_user or device.name
        if device_name:
            device_name = str(device_name).strip()

    original = None
    if entry is not None and entry.original_name:
        original = str(entry.original_name).strip()

    # Compose like HA UI for has_entity_name devices
    if entry is not None and getattr(entry, "has_entity_name", False):
        if device_name and original:
            return f"{device_name} {original}"
        if device_name:
            return device_name
        if original:
            return original

    if device_name and original:
        return f"{device_name} {original}"
    if device_name:
        return device_name
    if original:
        return original

    if state is not None:
        attr_name = state.attributes.get("friendly_name")
        if (
            isinstance(attr_name, str)
            and attr_name.strip()
            and attr_name != entity_id
        ):
            return attr_name.strip()

    if entry is not None:
        try:
            full = er.async_get_full_entity_name(hass, entry)
            if isinstance(full, str) and full.strip() and full != entity_id:
                return full.strip()
        except Exception:  # noqa: BLE001
            _LOGGER.debug("async_get_full_entity_name failed for %s", entity_id)

    return entity_id


def snapshot_inventory(hass: HomeAssistant) -> list[EntitySnap]:
    ent_reg = er.async_get(hass)
    area_reg = ar.async_get(hass)
    dev_reg = dr.async_get(hass)
    names = build_entity_names(hass)
    snaps: list[EntitySnap] = []

    for state in hass.states.async_all():
        entry = ent_reg.async_get(state.entity_id)
        device = None
        area_id = None
        if entry:
            area_id = entry.area_id
            if entry.device_id:
                device = dev_reg.devices.get(entry.device_id)
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

        full_name = names.get(state.entity_id) or state.entity_id
        snaps.append(
            EntitySnap(
                entity_id=state.entity_id,
                domain=state.domain,
                device_class=device_class,
                area_id=area_id,
                area_name=area_name,
                state=state.state,
                friendly_name=full_name,
                display_name=resolve_display_name(
                    state.entity_id,
                    entry=entry,
                    device=device,
                    area_name=area_name,
                    full_name=full_name,
                ),
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
