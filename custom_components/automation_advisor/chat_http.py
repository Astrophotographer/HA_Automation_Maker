"""HTTP views + iframe panel for the Advisor Channel Talk chatbot."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from aiohttp import web
from homeassistant.components.frontend import async_remove_panel
from homeassistant.components.http import HomeAssistantView, StaticPathConfig
from homeassistant.components.panel_custom import async_register_panel
from homeassistant.core import HomeAssistant

from .chat_agent import ChatAgent
from .chat_llm import chat_completions, probe_llm_status, resolve_llm_endpoint
from .chat_pending import PendingStore
from .chat_yaml import assert_automation_safe
from .const import DOMAIN
from .inventory import build_entity_display_names

_LOGGER = logging.getLogger(__name__)

WWW_DIR = Path(__file__).parent / "chat_www"
STATIC_URL = "/api/automation_advisor/static"
PANEL_URL_PATH = "dashboard"
_OLD_PANEL_URL_PATH = "automation-advisor-ui"
PANEL_TITLE = "Dashboard"
PANEL_ICON = "mdi:view-dashboard-outline"
_DATA_KEY = "chat_runtime"
_STATIC_FLAG = "chat_static_registered"
_VIEWS_FLAG = "chat_views_registered"


class CoordinatorToolkit:
    def __init__(self, coordinator: Any) -> None:
        self.coordinator = coordinator
        self.hass: HomeAssistant = coordinator.hass

    def list_suggestions(self, status: str | None = None) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for s in self.coordinator.suggestions:
            if status and s.get("status") != status:
                continue
            out.append(
                {
                    "id": s.get("id"),
                    "title": s.get("title"),
                    "source": s.get("source"),
                    "status": s.get("status"),
                    "explanation": (s.get("behavior") or s.get("explanation") or "")[
                        :240
                    ],
                }
            )
        return out[:50]

    def list_automations(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for s in self.coordinator.suggestions:
            if s.get("status") != "deployed":
                continue
            auto = s.get("automation") or {}
            out.append(
                {
                    "id": s.get("id"),
                    "automation_id": auto.get("id"),
                    "alias": auto.get("alias") or s.get("title"),
                    "source": s.get("source"),
                    "initial_state": auto.get("initial_state"),
                }
            )
        return out

    def find_suggestion(self, target_id: str) -> dict[str, Any] | None:
        return self.coordinator.find_suggestion_any(target_id)

    def get_states(
        self, query: str | None = None, limit: int = 40
    ) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit), 80))
        names = build_entity_display_names(self.hass)
        q = (query or "").strip().lower()
        rows: list[dict[str, Any]] = []
        for state in self.hass.states.async_all():
            eid = state.entity_id
            label = names.get(eid, eid)
            hay = f"{eid} {label}".lower()
            if q and q not in hay:
                continue
            rows.append(
                {
                    "entity_id": eid,
                    "name": label,
                    "state": state.state,
                    "domain": eid.split(".", 1)[0],
                }
            )
            if len(rows) >= limit:
                break
        return rows

    def get_logs(
        self, limit: int = 40, entity_id: str | None = None
    ) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit), 100))
        events = self.coordinator.event_store.fetch_recent(limit=limit)
        names = build_entity_display_names(self.hass)
        out: list[dict[str, Any]] = []
        for ev in events:
            if entity_id and ev.entity_id != entity_id:
                continue
            out.append(
                {
                    "ts": datetime.fromtimestamp(ev.ts, tz=timezone.utc).isoformat(),
                    "entity_id": ev.entity_id,
                    "name": names.get(ev.entity_id, ev.entity_id),
                    "old": ev.old_state,
                    "new": ev.new_state,
                    "actor": ev.actor,
                    "area_id": ev.area_id,
                }
            )
        return out


class ChatRuntime:
    def __init__(self, coordinator: Any) -> None:
        self.coordinator = coordinator
        self.pending = PendingStore()
        self.sessions: dict[str, list[dict[str, Any]]] = {}
        self.toolkit = CoordinatorToolkit(coordinator)

    def history(self, session_id: str) -> list[dict[str, Any]]:
        return list(self.sessions.get(session_id) or [])

    def save_history(self, session_id: str, messages: list[dict[str, Any]]) -> None:
        # Keep last user/assistant turns only for compactness
        kept: list[dict[str, Any]] = []
        for msg in messages:
            role = msg.get("role")
            if role in {"user", "assistant"} and msg.get("content"):
                kept.append({"role": role, "content": msg["content"]})
        self.sessions[session_id] = kept[-24:]

    async def handle_chat(self, session_id: str, message: str) -> dict[str, Any]:
        base, model, key = self.coordinator.llm_options()
        endpoint = resolve_llm_endpoint(base, model, key)
        if not endpoint:
            return {
                "reply": (
                    "LLM이 설정되지 않았습니다. 통합 옵션에서 Spark vLLM "
                    "`llm_base_url`과 `llm_model`을 넣어 주세요."
                ),
                "pending": None,
            }

        llm_base, llm_model, llm_key = endpoint

        def llm_call(*, messages, tools):
            return chat_completions(
                base_url=llm_base,
                model=llm_model,
                api_key=llm_key,
                messages=messages,
                tools=tools,
            )

        agent = ChatAgent(self.toolkit, self.pending, llm_call)
        history = self.history(session_id)
        try:
            result = await self.coordinator.hass.async_add_executor_job(
                agent.run, history, message
            )
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("chat agent failed: %s", err)
            return {
                "reply": f"챗봇 처리 중 오류가 났습니다: {err}",
                "pending": None,
            }

        self.save_history(session_id, result.messages)
        return {
            "reply": result.text,
            "pending": result.pending.as_dict() if result.pending else None,
        }

    async def handle_status(self) -> dict[str, Any]:
        base, model, key = self.coordinator.llm_options()
        return await self.coordinator.hass.async_add_executor_job(
            lambda: probe_llm_status(base_url=base, model=model, api_key=key)
        )

    async def handle_confirm(self, token: str, accept: bool) -> dict[str, Any]:
        item = self.pending.pop(token)
        if item is None:
            return {"ok": False, "message": "확인 토큰이 없거나 만료되었습니다."}
        if not accept:
            return {"ok": True, "message": "취소했습니다. Home Assistant에는 반영되지 않았습니다."}
        try:
            if item.kind == "create":
                assert item.automation is not None
                assert_automation_safe(item.automation)
                sid = await self.coordinator.async_chat_create(
                    item.automation, title=item.summary
                )
                return {"ok": True, "message": f"등록했습니다. (ID: {sid})"}
            if item.kind == "update":
                assert item.automation is not None and item.target_id
                assert_automation_safe(item.automation)
                await self.coordinator.async_chat_update(
                    item.target_id, item.automation, title=item.summary
                )
                return {"ok": True, "message": "수정을 적용했습니다."}
            if item.kind == "delete":
                assert item.target_id
                await self.coordinator.async_delete(item.target_id)
                return {"ok": True, "message": "삭제했습니다."}
            return {"ok": False, "message": f"알 수 없는 작업: {item.kind}"}
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("chat confirm failed: %s", err)
            return {"ok": False, "message": str(err)}


class AdvisorChatView(HomeAssistantView):
    url = "/api/automation_advisor/chat"
    name = "api:automation_advisor:chat"
    requires_auth = True

    async def post(self, request: web.Request) -> web.Response:
        hass: HomeAssistant = request.app["hass"]
        runtime: ChatRuntime | None = hass.data.get(DOMAIN, {}).get(_DATA_KEY)
        if runtime is None:
            return self.json({"error": "chat not ready"}, status_code=503)
        try:
            body = await request.json()
        except Exception:  # noqa: BLE001
            return self.json({"error": "invalid json"}, status_code=400)
        message = str(body.get("message") or "").strip()
        session_id = str(body.get("session_id") or "default").strip() or "default"
        if not message:
            return self.json({"error": "message required"}, status_code=400)
        result = await runtime.handle_chat(session_id, message)
        return self.json(result)


class AdvisorChatConfirmView(HomeAssistantView):
    url = "/api/automation_advisor/chat/confirm"
    name = "api:automation_advisor:chat_confirm"
    requires_auth = True

    async def post(self, request: web.Request) -> web.Response:
        hass: HomeAssistant = request.app["hass"]
        runtime: ChatRuntime | None = hass.data.get(DOMAIN, {}).get(_DATA_KEY)
        if runtime is None:
            return self.json({"error": "chat not ready"}, status_code=503)
        try:
            body = await request.json()
        except Exception:  # noqa: BLE001
            return self.json({"error": "invalid json"}, status_code=400)
        token = str(body.get("token") or "").strip()
        accept = bool(body.get("accept"))
        if not token:
            return self.json({"error": "token required"}, status_code=400)
        result = await runtime.handle_confirm(token, accept)
        return self.json(result)


class AdvisorChatStatusView(HomeAssistantView):
    url = "/api/automation_advisor/chat/status"
    name = "api:automation_advisor:chat_status"
    requires_auth = True

    async def get(self, request: web.Request) -> web.Response:
        hass: HomeAssistant = request.app["hass"]
        runtime: ChatRuntime | None = hass.data.get(DOMAIN, {}).get(_DATA_KEY)
        if runtime is None:
            return self.json({"error": "chat not ready"}, status_code=503)
        return self.json(await runtime.handle_status())


class AdvisorUiView(HomeAssistantView):
    """Serve chat HTML with no-store caching (avoids HA service-worker stale JS)."""

    url = "/api/automation_advisor/ui"
    name = "api:automation_advisor:ui"
    requires_auth = False

    async def get(self, request: web.Request) -> web.Response:
        hass: HomeAssistant = request.app["hass"]
        index = WWW_DIR / "index.html"

        def _read() -> str:
            return index.read_text(encoding="utf-8")

        body = await hass.async_add_executor_job(_read)
        return web.Response(
            text=body,
            content_type="text/html",
            charset="utf-8",
            headers={
                "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                "Pragma": "no-cache",
                "Expires": "0",
            },
        )


async def async_setup_chat(hass: HomeAssistant, coordinator: Any) -> None:
    domain_data = hass.data.setdefault(DOMAIN, {})
    domain_data[_DATA_KEY] = ChatRuntime(coordinator)

    if not domain_data.get(_STATIC_FLAG):
        await hass.http.async_register_static_paths(
            [StaticPathConfig(STATIC_URL, str(WWW_DIR), False)]
        )
        domain_data[_STATIC_FLAG] = True

    if not domain_data.get(_VIEWS_FLAG):
        hass.http.register_view(AdvisorChatView)
        hass.http.register_view(AdvisorChatConfirmView)
        hass.http.register_view(AdvisorChatStatusView)
        hass.http.register_view(AdvisorUiView)
        domain_data[_VIEWS_FLAG] = True

    try:
        async_remove_panel(hass, _OLD_PANEL_URL_PATH, warn_if_unknown=False)
    except Exception:  # noqa: BLE001
        pass
    try:
        # Replace previous iframe panel at /dashboard if present
        async_remove_panel(hass, PANEL_URL_PATH, warn_if_unknown=False)
    except Exception:  # noqa: BLE001
        pass

    # Custom panel (not bare iframe): HA injects `.hass` so we can pass a live
    # access token into the chat UI and avoid "로그인 필요" from storage/cache.
    await async_register_panel(
        hass,
        frontend_url_path=PANEL_URL_PATH,
        webcomponent_name="automation-advisor-panel",
        sidebar_title=PANEL_TITLE,
        sidebar_icon=PANEL_ICON,
        module_url=f"{STATIC_URL}/panel.js?v=0.2.29",
        embed_iframe=False,
        require_admin=True,
        config={"version": "0.2.29"},
    )

    from .dashboard_http import async_setup_dashboard

    await async_setup_dashboard(hass, coordinator)


async def async_unload_chat(hass: HomeAssistant) -> None:
    domain_data = hass.data.get(DOMAIN) or {}
    domain_data.pop(_DATA_KEY, None)
    for path in (PANEL_URL_PATH, _OLD_PANEL_URL_PATH):
        try:
            async_remove_panel(hass, path, warn_if_unknown=False)
        except Exception:  # noqa: BLE001
            pass
