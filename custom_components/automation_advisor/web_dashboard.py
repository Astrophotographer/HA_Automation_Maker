"""Lovelace dashboard with real [실행]/[기각] buttons for the HA web UI.

HA persistent notifications only support dismiss — they cannot show action
buttons. This dashboard is the web equivalent of Companion push actions.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

DASHBOARD_URL = "automation-advisor"
DASHBOARD_TITLE = "Automation Advisor"
DASHBOARD_ICON = "mdi:lightbulb-on"
VIEW_PATH = "inbox"


def build_inbox_config(
    pending: list[dict], previewed: list[dict] | None = None
) -> dict[str, Any]:
    """Build a Lovelace storage config with action buttons per suggestion."""
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

    previewed = previewed or []
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

    cards.append(
        {
            "type": "horizontal-stack",
            "cards": [
                {
                    "type": "button",
                    "name": "다시 스캔",
                    "icon": "mdi:magnify",
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
    )

    return {
        "views": [
            {
                "title": "승인",
                "path": VIEW_PATH,
                "icon": "mdi:clipboard-check",
                "cards": cards,
            }
        ]
    }


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

    config = build_inbox_config(pending, previewed)
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
            "Updated Automation Advisor web inbox (%d pending)", len(pending)
        )
        return True
    except Exception:  # noqa: BLE001
        _LOGGER.exception("Failed to save Automation Advisor dashboard")
        return False
