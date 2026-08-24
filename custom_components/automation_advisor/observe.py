"""Observe layer — listen for state changes and store learnable events."""

from __future__ import annotations

import logging
from collections import deque

from homeassistant.const import EVENT_STATE_CHANGED
from homeassistant.core import Event, HomeAssistant, callback

from .actor import classify_actor, is_learnable
from .const import EVENT_RETENTION_DAYS, OBSERVE_SKIP_DOMAINS
from .event_store import EventStore

_LOGGER = logging.getLogger(__name__)

_SKIP_DOMAINS = OBSERVE_SKIP_DOMAINS


class Observer:
    def __init__(self, hass: HomeAssistant, store: EventStore) -> None:
        self.hass = hass
        self.store = store
        self._unsub = None
        self.advisor_context_ids: deque[str] = deque(maxlen=200)

    def remember_advisor_context(self, context_id: str | None) -> None:
        if context_id:
            self.advisor_context_ids.append(context_id)

    async def async_start(self) -> None:
        if self._unsub:
            return

        @callback
        def _on_state(event: Event) -> None:
            self._handle(event)

        self._unsub = self.hass.bus.async_listen(EVENT_STATE_CHANGED, _on_state)
        await self.hass.async_add_executor_job(
            self.store.purge_older_than, EVENT_RETENTION_DAYS
        )
        _LOGGER.info("Automation Advisor: habit observer started")

    def async_stop(self) -> None:
        if self._unsub:
            self._unsub()
            self._unsub = None

    def _handle(self, event: Event) -> None:
        entity_id = event.data.get("entity_id")
        if not entity_id or "." not in entity_id:
            return
        domain = entity_id.split(".", 1)[0]
        if domain in _SKIP_DOMAINS:
            return

        new_state = event.data.get("new_state")
        old_state = event.data.get("old_state")
        if new_state is None:
            return
        new_val = new_state.state
        old_val = old_state.state if old_state is not None else None
        if new_val == old_val:
            return

        ctx = event.context
        actor = classify_actor(
            entity_domain=domain,
            user_id=getattr(ctx, "user_id", None),
            parent_id=getattr(ctx, "parent_id", None),
            context_id=getattr(ctx, "id", None),
            advisor_context_ids=set(self.advisor_context_ids),
        )
        if not is_learnable(actor):
            return

        area_id = None
        try:
            from homeassistant.helpers import device_registry as dr
            from homeassistant.helpers import entity_registry as er

            ent_reg = er.async_get(self.hass)
            entry = ent_reg.async_get(entity_id)
            if entry:
                area_id = entry.area_id
                if not area_id and entry.device_id:
                    dev = dr.async_get(self.hass).async_get(entry.device_id)
                    if dev:
                        area_id = dev.area_id
        except Exception:  # noqa: BLE001
            area_id = None

        try:
            self.store.insert(
                entity_id=entity_id,
                domain=domain,
                old_state=old_val,
                new_state=new_val,
                actor=actor,
                area_id=area_id,
            )
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("event insert failed: %s", err)
