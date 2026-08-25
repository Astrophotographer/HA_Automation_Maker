"""Lovelace dashboard with real [실행]/[기각] buttons for the HA web UI.

HA persistent notifications only support dismiss — they cannot show action
buttons. This dashboard is the web equivalent of Companion push actions.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .event_store import StoredEvent

_LOGGER = logging.getLogger(__name__)

DASHBOARD_URL = "automation-advisor"
DASHBOARD_TITLE = "Automation Advisor"
DASHBOARD_ICON = "mdi:lightbulb-on"
VIEW_PATH = "inbox"
LOGS_VIEW_PATH = "logs"

_ACTOR_LABEL = {
    "human_ui": "사람",
    "physical": "직접",
    "automation": "자동화",
    "advisor": "Advisor",
    "sensor": "센서",
    "unknown": "?",
}


def build_inbox_config(
    pending: list[dict],
    previewed: list[dict] | None = None,
    *,
    log_events: list | None = None,
    log_names: dict[str, str] | None = None,
    log_areas: dict[str, str] | None = None,
    log_count: int = 0,
    log_span_days: float = 0.0,
) -> dict[str, Any]:
    """Build a Lovelace storage config with logs + approval views."""
    return {
        "views": [
            _logs_view(
                log_events or [],
                names=log_names or {},
                areas=log_areas or {},
                count=log_count,
                span_days=log_span_days,
            ),
            _inbox_view(pending, previewed or []),
        ]
    }


def _inbox_view(pending: list[dict], previewed: list[dict]) -> dict[str, Any]:
    cards: list[dict[str, Any]] = [
        {
            "type": "markdown",
            "content": (
                "## 승인 대기\n\n"
                "사이드바 알림(종)에는 해제만 있습니다.\n"
                "웹에서 승인하려면 아래 버튼을 누르세요.\n\n"
                "폰 Companion 푸시의 [실행] [나중에] [기각]과 같습니다."
            ),
        }
    ]

    if not pending and not previewed:
        cards.append(
            {
                "type": "markdown",
                "content": (
                    "_대기 중인 추천이 없습니다._\n\n"
                    "`automation_advisor.scan` 또는 아래 다시 스캔을 누르세요."
                ),
            }
        )
    else:
        for suggestion in pending:
            cards.append(_suggestion_card(suggestion, stage="run"))
        for suggestion in previewed:
            cards.append(_suggestion_card(suggestion, stage="deploy"))

    cards.append(_scan_actions())
    return {
        "title": "승인",
        "path": VIEW_PATH,
        "icon": "mdi:clipboard-check",
        "cards": cards,
    }


def _logs_view(
    events: list,
    *,
    names: dict[str, str],
    areas: dict[str, str],
    count: int,
    span_days: float,
) -> dict[str, Any]:
    cards: list[dict[str, Any]] = [
        {
            "type": "markdown",
            "content": (
                "## 기기 로그\n\n"
                "집 안 장비들의 상태 변화를 모읍니다.\n"
                "반복되는 손길이 보이면 **스캔**이 자동화 초안으로 바꿉니다."
            ),
        },
        {
            "type": "markdown",
            "content": (
                f"**수집** `{count}`건 · "
                f"**기간** `{span_days:.1f}`일 · "
                f"**표시** 최근 `{len(events)}`건"
            ),
        },
        {
            "type": "markdown",
            "content": _logs_markdown(events, names=names, areas=areas),
        },
        _scan_actions(),
    ]
    return {
        "title": "기기 로그",
        "path": LOGS_VIEW_PATH,
        "icon": "mdi:text-box-search-outline",
        "cards": cards,
    }


def _scan_actions() -> dict[str, Any]:
    return {
        "type": "horizontal-stack",
        "cards": [
            {
                "type": "button",
                "name": "로그 분석 · 스캔",
                "icon": "mdi:magnify-scan",
                "tap_action": {
                    "action": "perform-action",
                    "perform_action": "automation_advisor.scan",
                },
            },
            {
                "type": "button",
                "name": "알림 다시 보내기",
                "icon": "mdi:bell-ring",
                "tap_action": {
                    "action": "perform-action",
                    "perform_action": "automation_advisor.reprompt",
                    "data": {"limit": 3},
                },
            },
        ],
    }


def _logs_markdown(
    events: list,
    *,
    names: dict[str, str],
    areas: dict[str, str],
) -> str:
    if not events:
        return (
            "_아직 수집된 로그가 없습니다._\n\n"
            "조명을 켜거나 센서를 움직이면 여기에 쌓입니다.\n"
            "이미 Recorder에 기록이 있으면 **로그 분석 · 스캔**으로 채울 수 있습니다."
        )

    lines = [
        "| 시각 | 공간 | 기기 | 변화 | 주체 |",
        "| --- | --- | --- | --- | --- |",
    ]
    for ev in events:
        lines.append(_format_log_row(ev, names=names, areas=areas))
    lines.append("")
    lines.append(
        "_같은 공간에서 반복되는 `모션 → 조명` 같은 쌍을 찾으면 승인 탭으로 제안합니다._"
    )
    return "\n".join(lines)


def _format_log_row(
    ev: "StoredEvent",
    *,
    names: dict[str, str],
    areas: dict[str, str],
) -> str:
    when = _fmt_ts(ev.ts)
    area = areas.get(ev.area_id or "", "") or (ev.area_id or "—")
    label = names.get(ev.entity_id) or ev.entity_id
    old = ev.old_state if ev.old_state is not None else "—"
    change = f"`{old}` → `{ev.new_state}`"
    actor = _ACTOR_LABEL.get(ev.actor, ev.actor)
    return (
        f"| {_md_cell(when)} | {_md_cell(area)} | {_md_cell(label)} "
        f"| {change} | {_md_cell(actor)} |"
    )


def _md_cell(value: object) -> str:
    return str(value).replace("|", "\\|")


def _fmt_ts(ts: float) -> str:
    try:
        from zoneinfo import ZoneInfo

        tz = ZoneInfo("Asia/Seoul")
    except Exception:  # noqa: BLE001
        tz = timezone.utc
    return datetime.fromtimestamp(ts, tz=tz).strftime("%m/%d %H:%M:%S")


def _suggestion_card(suggestion: dict, *, stage: str) -> dict[str, Any]:
    sid = str(suggestion["id"])
    title = suggestion.get("title") or sid
    detail = (
        suggestion.get("behavior")
        or suggestion.get("explanation")
        or ""
    )
    if stage == "deploy":
        heading = "자동화하시겠습니까?"
        buttons = [
            {
                "type": "button",
                "name": "자동화",
                "icon": "mdi:robot",
                "tap_action": {
                    "action": "perform-action",
                    "perform_action": "automation_advisor.deploy",
                    "data": {"suggestion_id": sid},
                },
            },
            {
                "type": "button",
                "name": "아니요",
                "icon": "mdi:close",
                "tap_action": {
                    "action": "perform-action",
                    "perform_action": "automation_advisor.dismiss",
                    "data": {"suggestion_id": sid},
                },
            },
        ]
    else:
        heading = "실행하시겠습니까?"
        buttons = [
            {
                "type": "button",
                "name": "실행",
                "icon": "mdi:play",
                "tap_action": {
                    "action": "perform-action",
                    "perform_action": "automation_advisor.run_once",
                    "data": {"suggestion_id": sid},
                },
            },
            {
                "type": "button",
                "name": "나중에",
                "icon": "mdi:clock-outline",
                "tap_action": {
                    "action": "perform-action",
                    "perform_action": "automation_advisor.later",
                    "data": {"suggestion_id": sid},
                },
            },
            {
                "type": "button",
                "name": "기각",
                "icon": "mdi:close",
                "tap_action": {
                    "action": "perform-action",
                    "perform_action": "automation_advisor.dismiss",
                    "data": {"suggestion_id": sid},
                },
            },
        ]

    return {
        "type": "vertical-stack",
        "cards": [
            {
                "type": "markdown",
                "content": (
                    f"### {heading}\n"
                    f"{title}\n\n"
                    f"{detail}\n\n"
                    f"`{sid}`"
                ),
            },
            {"type": "horizontal-stack", "cards": buttons},
        ],
    }


async def _log_context(hass: "HomeAssistant") -> dict[str, Any]:
    """Pull recent events + friendly labels from the running coordinator."""
    from homeassistant.helpers import area_registry as ar

    from .const import DOMAIN
    from .inventory import build_entity_display_names

    events: list = []
    count = 0
    span_days = 0.0
    for coord in (hass.data.get(DOMAIN) or {}).values():
        store = getattr(coord, "_event_store", None)
        if store is None:
            continue
        events = await hass.async_add_executor_job(store.fetch_recent, 50)
        count = await hass.async_add_executor_job(store.count)
        span_days = await hass.async_add_executor_job(store.span_days)
        break

    names: dict[str, str] = {}
    areas: dict[str, str] = {}
    try:
        names = build_entity_display_names(hass)
        area_reg = ar.async_get(hass)
        for ev in events:
            aid = ev.area_id
            if not aid or aid in areas:
                continue
            area = area_reg.async_get_area(aid)
            if area:
                areas[aid] = area.name
    except Exception:  # noqa: BLE001
        _LOGGER.debug("Could not resolve entity/area labels for log view", exc_info=True)

    return {
        "events": events,
        "names": names,
        "areas": areas,
        "count": count,
        "span_days": span_days,
    }


async def ensure_web_dashboard(
    hass: "HomeAssistant",
    pending: list[dict],
    previewed: list[dict] | None = None,
) -> bool:
    """Create/update the Automation Advisor sidebar dashboard. Returns True if saved."""
    from homeassistant.components.lovelace.const import (
        CONF_ICON,
        CONF_REQUIRE_ADMIN,
        CONF_SHOW_IN_SIDEBAR,
        CONF_TITLE,
        CONF_URL_PATH,
        LOVELACE_DATA,
    )
    from homeassistant.components.lovelace.dashboard import (
        DashboardsCollection,
        LovelaceStorage,
    )

    lovelace = hass.data.get(LOVELACE_DATA)
    if lovelace is None:
        _LOGGER.debug("Lovelace not ready; skip dashboard update")
        return False

    logs = await _log_context(hass)
    config = build_inbox_config(
        pending,
        previewed,
        log_events=logs["events"],
        log_names=logs["names"],
        log_areas=logs["areas"],
        log_count=logs["count"],
        log_span_days=logs["span_days"],
    )
    dash = lovelace.dashboards.get(DASHBOARD_URL)

    if dash is None:
        try:
            collection = DashboardsCollection(hass)
            await collection.async_load()
            existing = next(
                (
                    item
                    for item in collection.async_items()
                    if item.get(CONF_URL_PATH) == DASHBOARD_URL
                ),
                None,
            )
            if existing is None:
                await collection.async_create_item(
                    {
                        CONF_URL_PATH: DASHBOARD_URL,
                        CONF_TITLE: DASHBOARD_TITLE,
                        CONF_ICON: DASHBOARD_ICON,
                        CONF_SHOW_IN_SIDEBAR: True,
                        CONF_REQUIRE_ADMIN: False,
                    }
                )
            # Official listener may own registration; fall back to local map.
            dash = lovelace.dashboards.get(DASHBOARD_URL)
            if dash is None:
                item = next(
                    (
                        i
                        for i in collection.async_items()
                        if i.get(CONF_URL_PATH) == DASHBOARD_URL
                    ),
                    None,
                )
                if item is None:
                    _LOGGER.warning("Dashboard create did not persist %s", DASHBOARD_URL)
                    return False
                dash = LovelaceStorage(hass, item)
                lovelace.dashboards[DASHBOARD_URL] = dash
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Failed to create Automation Advisor dashboard")
            return False

    try:
        await dash.async_save(config)
        _LOGGER.info(
            "Updated Automation Advisor web inbox (%d pending, %d log rows)",
            len(pending),
            len(logs["events"]),
        )
        return True
    except Exception:  # noqa: BLE001
        _LOGGER.exception("Failed to save Automation Advisor dashboard")
        return False
