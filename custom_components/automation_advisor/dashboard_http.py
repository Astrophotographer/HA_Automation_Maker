"""HTTP views for the Dashboard web panel."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from aiohttp import web
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant

from .const import (
    DOMAIN,
    MIN_PATTERN_CONFIDENCE,
    MIN_PATTERN_LIFT,
    MIN_PATTERN_SUPPORT,
    OBSERVE_SKIP_DOMAINS,
)
from .dashboard_api import (
    build_device_row,
    build_log_lines,
    build_reasons,
    build_summary,
    group_devices,
    list_automations,
    normalize_action,
)
from .inventory import build_entity_display_names, snapshot_inventory

_LOGGER = logging.getLogger(__name__)

_DATA_KEY = "dashboard_runtime"
_VIEWS_FLAG = "dashboard_views_registered"

_DEVICE_DOMAINS = frozenset(
    {
        "light",
        "switch",
        "climate",
        "cover",
        "fan",
        "media_player",
        "binary_sensor",
        "lock",
    }
)


class DashboardRuntime:
    def __init__(self, coordinator: Any) -> None:
        self.coordinator = coordinator
        self.hass: HomeAssistant = coordinator.hass

    def _entity_link_counts(self) -> tuple[dict[str, int], dict[str, int]]:
        auto_counts: dict[str, int] = {}
        sug_counts: dict[str, int] = {}
        for s in self.coordinator.suggestions:
            status = str(s.get("status") or "")
            entities = list(s.get("entities") or [])
            if not entities:
                continue
            if status == "deployed":
                bucket = auto_counts
            elif status in {"pending", "previewed"}:
                bucket = sug_counts
            else:
                continue
            for eid in entities:
                bucket[eid] = bucket.get(eid, 0) + 1
        return auto_counts, sug_counts

    async def summary(self) -> dict[str, Any]:
        snaps = snapshot_inventory(self.hass)
        auto_c, sug_c = self._entity_link_counts()
        entity_rows: list[dict[str, Any]] = []
        for snap in snaps:
            if snap.domain in OBSERVE_SKIP_DOMAINS:
                continue
            if snap.domain not in _DEVICE_DOMAINS:
                continue
            entity_rows.append(
                build_device_row(
                    snap.entity_id,
                    snap.display_name or snap.friendly_name or snap.entity_id,
                    snap.area_name or "기타",
                    snap.state,
                    auto_c.get(snap.entity_id, 0),
                    sug_c.get(snap.entity_id, 0),
                    device_id=snap.device_id,
                    device_name=snap.device_name,
                )
            )
        devices = group_devices(entity_rows)
        devices.sort(key=lambda d: (d["area"], d["name"]))
        return build_summary(
            synced_at=datetime.now(timezone.utc).isoformat(),
            devices=devices,
            pending_count=len(self.coordinator.pending_suggestions),
        )

    def automations(self, *, include_dismissed: bool) -> list[dict[str, Any]]:
        return list_automations(
            list(self.coordinator.suggestions),
            include_dismissed=include_dismissed,
        )

    async def logs(self, limit: int = 80) -> dict[str, Any]:
        limit = max(1, min(int(limit), 200))
        store = self.coordinator.event_store
        events = await self.hass.async_add_executor_job(
            store.fetch_recent, limit
        )
        # Newest first from store → reverse for terminal (oldest→newest ascending n)
        events = list(reversed(events))
        total = await self.hass.async_add_executor_job(store.count)
        start_n = max(1, total - len(events) + 1)
        names = build_entity_display_names(self.hass)
        lines = build_log_lines(events, names=names, start_n=start_n)
        return {
            "total": total,
            "span_days": self.coordinator.habit_stats.get("span_days", 0),
            "lines": lines,
        }

    def reasons(self) -> dict[str, Any]:
        coord = self.coordinator
        return build_reasons(
            list(coord.suggestions),
            min_confidence=MIN_PATTERN_CONFIDENCE,
            min_support=MIN_PATTERN_SUPPORT,
            min_lift=MIN_PATTERN_LIFT,
            habit=dict(coord.habit_stats or {}),
            preview=list(getattr(coord, "habit_preview", None) or []),
        )

    async def action(self, kind: str, suggestion_id: str | None) -> dict[str, Any]:
        kind = normalize_action(kind)
        coord = self.coordinator

        if kind == "scan":
            count = await coord.async_scan()
            prompted = await coord.async_prompt_new()
            return {"ok": True, "scanned": count, "prompted": prompted}

        if kind == "resend_all":
            prompted = await coord.async_reprompt(limit=10)
            return {"ok": True, "prompted": prompted}

        if not suggestion_id:
            return {"ok": False, "error": "suggestion_id required"}

        suggestion = coord.find_suggestion_any(str(suggestion_id))
        if kind == "resend":
            if not suggestion:
                return {"ok": False, "error": "not found"}
            from .notifications import ask_run_once

            suggestion["snoozed"] = False
            await ask_run_once(self.hass, suggestion)
            suggestion["asked_run"] = True
            await coord._save()
            return {"ok": True, "prompted": 1}

        if not suggestion:
            return {"ok": False, "error": "not found"}

        status = str(suggestion.get("status") or "")
        sid = str(suggestion.get("id") or suggestion_id)

        if kind == "approve":
            if status == "pending":
                ok = await coord.async_run_once(sid)
                return {"ok": bool(ok)}
            if status == "previewed":
                await coord.async_deploy(sid)
                return {"ok": True}
            return {"ok": False, "error": f"cannot approve status={status}"}

        if kind == "deploy":
            await coord.async_deploy(sid)
            return {"ok": True}
        if kind == "later":
            await coord.async_later(sid)
            return {"ok": True}
        if kind == "dismiss":
            await coord.async_dismiss(sid)
            return {"ok": True}
        if kind == "delete":
            await coord.async_delete(sid)
            return {"ok": True}

        return {"ok": False, "error": "unhandled"}


def _runtime(hass: HomeAssistant) -> DashboardRuntime:
    return hass.data[DOMAIN][_DATA_KEY]


class DashboardSummaryView(HomeAssistantView):
    url = "/api/automation_advisor/dashboard/summary"
    name = "api:automation_advisor:dashboard:summary"
    requires_auth = True

    async def get(self, request: web.Request) -> web.Response:
        hass: HomeAssistant = request.app["hass"]
        return self.json(await _runtime(hass).summary())


class DashboardAutomationsView(HomeAssistantView):
    url = "/api/automation_advisor/dashboard/automations"
    name = "api:automation_advisor:dashboard:automations"
    requires_auth = True

    async def get(self, request: web.Request) -> web.Response:
        hass: HomeAssistant = request.app["hass"]
        raw = str(request.query.get("include_dismissed") or "0")
        include = raw in {"1", "true", "yes"}
        return self.json({"items": _runtime(hass).automations(include_dismissed=include)})


class DashboardLogsView(HomeAssistantView):
    url = "/api/automation_advisor/dashboard/logs"
    name = "api:automation_advisor:dashboard:logs"
    requires_auth = True

    async def get(self, request: web.Request) -> web.Response:
        hass: HomeAssistant = request.app["hass"]
        limit = int(request.query.get("limit") or 80)
        return self.json(await _runtime(hass).logs(limit=limit))


class DashboardReasonsView(HomeAssistantView):
    url = "/api/automation_advisor/dashboard/reasons"
    name = "api:automation_advisor:dashboard:reasons"
    requires_auth = True

    async def get(self, request: web.Request) -> web.Response:
        hass: HomeAssistant = request.app["hass"]
        return self.json(_runtime(hass).reasons())


class DashboardActionView(HomeAssistantView):
    url = "/api/automation_advisor/dashboard/action"
    name = "api:automation_advisor:dashboard:action"
    requires_auth = True

    async def post(self, request: web.Request) -> web.Response:
        hass: HomeAssistant = request.app["hass"]
        try:
            body = await request.json()
        except Exception:  # noqa: BLE001
            return self.json({"ok": False, "error": "invalid json"}, status_code=400)
        kind = body.get("kind") or ""
        sid = body.get("suggestion_id")
        try:
            result = await _runtime(hass).action(str(kind), sid)
        except ValueError as err:
            return self.json({"ok": False, "error": str(err)}, status_code=400)
        except Exception as err:  # noqa: BLE001
            _LOGGER.exception("dashboard action failed")
            return self.json({"ok": False, "error": str(err)}, status_code=500)
        status = 200 if result.get("ok") else 400
        return self.json(result, status_code=status)


async def async_setup_dashboard(hass: HomeAssistant, coordinator: Any) -> None:
    domain_data = hass.data.setdefault(DOMAIN, {})
    domain_data[_DATA_KEY] = DashboardRuntime(coordinator)
    if domain_data.get(_VIEWS_FLAG):
        return
    hass.http.register_view(DashboardSummaryView)
    hass.http.register_view(DashboardAutomationsView)
    hass.http.register_view(DashboardLogsView)
    hass.http.register_view(DashboardReasonsView)
    hass.http.register_view(DashboardActionView)
    domain_data[_VIEWS_FLAG] = True
