"""Automation Advisor — HACS custom integration.

Home Assistant-import-free at module load so engine tests can run without Core.
"""
from __future__ import annotations

from .const import DOMAIN

__all__ = ["DOMAIN"]


async def async_setup_entry(hass, entry):
    from .integration import async_setup_entry as _setup

    return await _setup(hass, entry)


async def async_unload_entry(hass, entry):
    from .integration import async_unload_entry as _unload

    return await _unload(hass, entry)


async def async_reload_entry(hass, entry):
    await async_unload_entry(hass, entry)
    return await async_setup_entry(hass, entry)
