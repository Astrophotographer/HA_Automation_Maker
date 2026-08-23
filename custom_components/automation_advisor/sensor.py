"""Automation Advisor sensors — same four-entity shape as HA Rhythm."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, VERSION
from .coordinator import AdvisorCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: AdvisorCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            AdvisorStatusSensor(coordinator, entry),
            AdvisorMatchesSensor(coordinator, entry),
            AdvisorPendingSensor(coordinator, entry),
            AdvisorDeployedSensor(coordinator, entry),
        ]
    )


class _AdvisorBase(SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator: AdvisorCoordinator, entry: ConfigEntry) -> None:
        self._coordinator = coordinator
        self._entry = entry
        coordinator.async_add_listener(self._on_update)

    def _on_update(self) -> None:
        self.schedule_update_ha_state()

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": "Automation Advisor",
            "manufacturer": "Automation Advisor",
            "model": "Catalog + habit + compiler",
            "sw_version": VERSION,
        }

    async def async_will_remove_from_hass(self) -> None:
        if self._on_update in self._coordinator._listeners:
            self._coordinator._listeners.remove(self._on_update)


class AdvisorStatusSensor(_AdvisorBase):
    _attr_icon = "mdi:lightbulb-on"

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_status"
        self._attr_name = "Status"

    @property
    def native_value(self):
        return self._coordinator.status

    @property
    def extra_state_attributes(self):
        return {
            "last_scan": self._coordinator.last_scan,
            "catalog_matches": len(self._coordinator.matches),
            "pending_suggestions": len(self._coordinator.pending_suggestions),
            "previewed_suggestions": len(self._coordinator.previewed_suggestions),
            "deployed_suggestions": len(self._coordinator.deployed_suggestions),
            "habit": self._coordinator.habit_stats,
            "source": "catalog+habit",
        }


class AdvisorMatchesSensor(_AdvisorBase):
    _attr_icon = "mdi:book-open-variant"
    _attr_native_unit_of_measurement = "matches"

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_matches"
        self._attr_name = "Catalog Matches"

    @property
    def native_value(self):
        return len(self._coordinator.matches)

    @property
    def extra_state_attributes(self):
        return {"matches": self._coordinator.matches}


class AdvisorPendingSensor(_AdvisorBase):
    _attr_icon = "mdi:lightbulb-on-outline"
    _attr_native_unit_of_measurement = "suggestions"

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_pending"
        self._attr_name = "Pending Suggestions"

    @property
    def native_value(self):
        return len(self._coordinator.pending_suggestions)

    @property
    def extra_state_attributes(self):
        public = []
        for suggestion in self._coordinator.pending_suggestions:
            public.append(
                {
                    "id": suggestion.get("id"),
                    "title": suggestion.get("title"),
                    "explanation": suggestion.get("explanation"),
                    "source": suggestion.get("source"),
                    "area_name": suggestion.get("area_name"),
                    "trial": suggestion.get("trial"),
                }
            )
        return {"suggestions": public}


class AdvisorDeployedSensor(_AdvisorBase):
    _attr_icon = "mdi:check-circle-outline"
    _attr_native_unit_of_measurement = "automations"

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_deployed"
        self._attr_name = "Deployed Automations"

    @property
    def native_value(self):
        return len(self._coordinator.deployed_suggestions)

    @property
    def extra_state_attributes(self):
        return {
            "automations": [
                {
                    "id": s.get("id"),
                    "title": s.get("title"),
                    "automation_id": (s.get("automation") or {}).get("id"),
                    "trial": s.get("trial"),
                }
                for s in self._coordinator.deployed_suggestions
            ]
        }
