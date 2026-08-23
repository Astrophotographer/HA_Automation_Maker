"""Home Assistant wiring — services and sensors."""

from __future__ import annotations

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
import homeassistant.helpers.config_validation as cv

from .actions import KIND_DEPLOY, KIND_DISMISS, KIND_RUN, parse_action
from .const import DOMAIN
from .coordinator import AdvisorCoordinator

PLATFORMS = ["sensor"]


async def _notify(hass: HomeAssistant, title: str, message: str, notification_id: str) -> None:
    await hass.services.async_call(
        "persistent_notification",
        "create",
        {"title": title, "message": message, "notification_id": notification_id},
    )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})
    coordinator = AdvisorCoordinator(hass, entry)
    await coordinator.async_load()
    hass.data[DOMAIN][entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_reload))

    if not coordinator.suggestions and not coordinator.last_scan:
        await _notify(
            hass,
            title="Automation Advisor 설치됨",
            message=(
                "v1: 장비×카탈로그 즉시 추천. v2: 수동 조작만 로컬에 모아 습관 패턴을 만듭니다.\n"
                "승인 전에는 Home Assistant에 넣지 않습니다.\n\n"
                "**1.** `automation_advisor.scan`\n"
                "**2.** Companion에서 **실행하시겠습니까?** → 한 번 실행\n"
                "**3.** **자동화하시겠습니까?** → 시험 등록\n\n"
                "`configuration.yaml`:\n"
                "`automation advisor: !include automation_advisor.yaml`"
            ),
            notification_id="advisor_welcome",
        )

    async def handle_scan(_call: ServiceCall) -> None:
        count = await coordinator.async_scan()
        stats = coordinator.habit_stats
        habit_line = (
            f"습관 로그: 이벤트 {stats.get('events', 0)}개, "
            f"관찰 {stats.get('span_days', 0)}일 "
            f"(필요 {stats.get('min_observe_days', 7)}일), "
            f"패턴 {stats.get('patterns', 0)}개."
        )
        if count == 0:
            await _notify(
                hass,
                "Automation Advisor — 스캔 완료",
                (
                    "새 추천이 없습니다.\n\n"
                    f"{habit_line}\n\n"
                    "움직임 센서와 조명을 같은 방에 두었는지, "
                    "이미 같은 자동화가 있는지는 스캔이 걸러냅니다."
                ),
                "advisor_scan_done",
            )
            return
        await coordinator.async_prompt_new()
        pending = coordinator.pending_suggestions
        lines = "\n".join(
            f"• **{s.get('title')}** [{s.get('source')}] — {s.get('explanation')} (ID: `{s['id']}`)"
            for s in pending[:12]
        )
        await _notify(
            hass,
            title=f"Automation Advisor — 추천 {count}개",
            message=(
                f"카탈로그·습관 후보 {count}개. YAML은 컴파일러가 만듭니다.\n\n"
                f"{habit_line}\n\n"
                f"{lines}\n\n"
                "Companion: **실행하시겠습니까?** → 그다음 **자동화하시겠습니까?**"
            ),
            notification_id="advisor_scan_done",
        )

    async def handle_run_once(call: ServiceCall) -> None:
        ok = await coordinator.async_run_once(call.data["suggestion_id"])
        if not ok:
            await _notify(
                hass,
                "Automation Advisor — 실행하지 않음",
                "추천을 찾을 수 없거나, 차단된 동작입니다.",
                "advisor_run_failed",
            )

    async def handle_mobile_action(event) -> None:
        parsed = parse_action(
            event.data.get("action") or event.data.get("actionName")
        )
        if not parsed:
            return
        kind, suggestion_id = parsed
        if kind == KIND_RUN:
            await coordinator.async_run_once(suggestion_id)
        elif kind == KIND_DEPLOY:
            await coordinator.async_deploy(suggestion_id)
        elif kind == KIND_DISMISS:
            await coordinator.async_dismiss(suggestion_id)

    async def handle_deploy(call: ServiceCall) -> None:
        await coordinator.async_deploy(call.data["suggestion_id"])

    async def handle_dismiss(call: ServiceCall) -> None:
        await coordinator.async_dismiss(call.data["suggestion_id"])

    async def handle_feedback(call: ServiceCall) -> None:
        await coordinator.async_feedback(call.data["suggestion_id"], call.data["rating"])

    async def handle_delete(call: ServiceCall) -> None:
        await coordinator.async_delete(call.data["suggestion_id"])

    async def handle_kill(_call: ServiceCall) -> None:
        count = await coordinator.async_kill_switch()
        await _notify(
            hass,
            "Automation Advisor — kill switch",
            f"이 시스템이 등록한 자동화 {count}개를 비활성·제거했습니다.",
            "advisor_kill",
        )

    async def handle_clear_habit(_call: ServiceCall) -> None:
        n = await coordinator.async_clear_habit_data()
        await _notify(
            hass,
            "Automation Advisor — 습관 로그 삭제",
            f"로컬 이벤트 {n}개를 지웠습니다. 관찰이 다시 시작됩니다.",
            "advisor_habit_cleared",
        )

    async def handle_habit_status(_call: ServiceCall) -> None:
        await coordinator._refresh_habit_stats()
        stats = coordinator.habit_stats
        await _notify(
            hass,
            "Automation Advisor — 습관 상태",
            (
                f"이벤트 {stats.get('events')} · 관찰 {stats.get('span_days')}일 "
                f"(최소 {stats.get('min_observe_days')}일) · "
                f"준비됨={stats.get('ready')} · 최근 패턴 {stats.get('patterns')}"
            ),
            "advisor_habit_status",
        )

    hass.services.async_register(DOMAIN, "scan", handle_scan)
    hass.services.async_register(
        DOMAIN,
        "run_once",
        handle_run_once,
        schema=vol.Schema({vol.Required("suggestion_id"): cv.string}),
    )
    hass.services.async_register(
        DOMAIN,
        "deploy",
        handle_deploy,
        schema=vol.Schema({vol.Required("suggestion_id"): cv.string}),
    )
    hass.services.async_register(
        DOMAIN,
        "dismiss",
        handle_dismiss,
        schema=vol.Schema({vol.Required("suggestion_id"): cv.string}),
    )
    hass.services.async_register(
        DOMAIN,
        "feedback",
        handle_feedback,
        schema=vol.Schema(
            {
                vol.Required("suggestion_id"): cv.string,
                vol.Required("rating"): vol.In(["good", "bad"]),
            }
        ),
    )
    hass.services.async_register(
        DOMAIN,
        "delete",
        handle_delete,
        schema=vol.Schema({vol.Required("suggestion_id"): cv.string}),
    )
    hass.services.async_register(DOMAIN, "kill_switch", handle_kill)
    hass.services.async_register(DOMAIN, "clear_habit_data", handle_clear_habit)
    hass.services.async_register(DOMAIN, "habit_status", handle_habit_status)
    entry.async_on_unload(
        hass.bus.async_listen("mobile_app_notification_action", handle_mobile_action)
    )
    entry.async_on_unload(
        hass.bus.async_listen("ios.notification_action_fired", handle_mobile_action)
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    coordinator: AdvisorCoordinator | None = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if coordinator:
        await coordinator.async_unload()
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        for service in (
            "scan",
            "run_once",
            "deploy",
            "dismiss",
            "feedback",
            "delete",
            "kill_switch",
            "clear_habit_data",
            "habit_status",
        ):
            if hass.services.has_service(DOMAIN, service):
                hass.services.async_remove(DOMAIN, service)
    return unload_ok


async def _reload(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
