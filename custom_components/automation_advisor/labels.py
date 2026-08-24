"""Concise user-facing entity labels (no Home Assistant imports)."""

from __future__ import annotations

import re
from typing import Any

_CONFIGURE_SUFFIX = re.compile(r"\s*\(configure!\)\s*", re.IGNORECASE)
_GENERIC_ORIGINALS = frozenset(
    {"움직임", "motion", "occupancy", "상태", "state", "battery", "배터리"}
)


def short_area_name(area_name: str | None) -> str | None:
    """UI area label without romanized ids or trailing noise."""
    if not area_name:
        return None
    name = str(area_name).strip()
    if name.endswith(" 사용"):
        return name[:-3].strip()
    return name


def _clean_device_label(name: str) -> str:
    cleaned = _CONFIGURE_SUFFIX.sub("", name).strip()
    return cleaned or name.strip()


def resolve_display_name(
    entity_id: str,
    *,
    entry: Any | None,
    device: Any | None,
    area_name: str | None,
    full_name: str | None = None,
) -> str:
    """Short user-facing label: optional area + brief device/entity name."""
    short_area = short_area_name(area_name)
    device_label = None
    if device is not None:
        raw_device = getattr(device, "name_by_user", None) or getattr(device, "name", None)
        if raw_device:
            device_label = _clean_device_label(str(raw_device).strip())

    original = None
    if entry is not None and getattr(entry, "original_name", None):
        original = str(entry.original_name).strip()

    if device_label and original and original.casefold() in _GENERIC_ORIGINALS:
        short_name = device_label
    elif original:
        short_name = original
    elif device_label:
        short_name = device_label
    elif full_name and full_name != entity_id:
        short_name = str(full_name).strip()
    else:
        short_name = entity_id

    if short_area:
        if short_name.startswith(f"{short_area} "):
            return short_name
        return f"{short_area} · {short_name}"
    return short_name


def display_name_in_area(label: str, area_name: str | None) -> str:
    """Drop a leading area prefix when the suggestion is already scoped to that area."""
    short_area = short_area_name(area_name)
    if not short_area:
        return label
    prefix = f"{short_area} · "
    if label.startswith(prefix):
        return label[len(prefix) :]
    return label
