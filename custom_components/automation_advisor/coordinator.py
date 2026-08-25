"""Coordinator — catalog + habit scan/deploy UX."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .compiler import action_to_service_call
from .community import load_community_rates
from .config_setup import ensure_configuration_include
from .const import (
    AUTOMATIONS_FILENAME,
    CONF_COMMUNITY_STUB,
    CONF_HABIT_LEARNING,
    CONF_LLM_API_KEY,
    CONF_LLM_BASE_URL,
    CONF_LLM_MODEL,
    CONF_MIN_OBSERVE_DAYS,
    CONF_TRIAL_MODE,
    DEFAULT_COMMUNITY_STUB,
    DEFAULT_HABIT_LEARNING,
    DEFAULT_MIN_OBSERVE_DAYS,
    DEFAULT_TRIAL_MODE,
    EVENT_DB_FILENAME,
    EVENT_RETENTION_DAYS,
    SUGGESTIONS_FILENAME,
)
from .event_store import EventStore
from .inventory import existing_automation_entity_sets, snapshot_inventory
from .notifications import (
    ask_automate,
    clear_suggestion_card,
    confirm_deployed,
    sync_web_inbox,
)
from .observe import Observer
from .pattern import discover_patterns
from .recorder_backfill import backfill_from_recorder
from .recommender import recommend
from .chat_yaml import apply_chat_defaults, assert_automation_safe, collect_entity_ids
from .safety import is_blocked
from .suggestion_policy import blocks_resuggestion, suggestion_key

_LOGGER = logging.getLogger(__name__)


class AdvisorCoordinator:
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.status = "idle"
        self.matches: list[dict] = []
        self.suggestions: list[dict] = []
        self.last_scan: str | None = None
        self.habit_stats: dict = {
            "events": 0,
            "span_days": 0.0,
            "patterns": 0,
            "ready": False,
            "recorder_backfilled": 0,
        }
        # Patterns found before observe-days gate; shown on threshold tab only.
        self.habit_preview: list[dict] = []
        self._suggestions_file = Path(hass.config.path(SUGGESTIONS_FILENAME))
        self._automations_file = Path(hass.config.path(AUTOMATIONS_FILENAME))
        self._event_store = EventStore(hass.config.path(EVENT_DB_FILENAME))
        self.observer = Observer(hass, self._event_store)
        self._listeners: list = []

    def async_add_listener(self, cb) -> None:
        self._listeners.append(cb)

    def _notify(self) -> None:
        for cb in self._listeners:
            cb()

    def _opt(self, key: str, default):
        opts = self.entry.options
        data = self.entry.data
        return opts.get(key, data.get(key, default))

    async def _write_text(self, path: Path, text: str) -> None:
        await self.hass.async_add_executor_job(path.write_text, text, "utf-8")

    async def async_load(self) -> None:
        if not self._automations_file.exists():
            await self._rewrite_automations_file()
        if await ensure_configuration_include(self.hass):
            await self.hass.services.async_call(
                "persistent_notification",
                "create",
                {
                    "title": "Automation Advisor — 설정 한 줄 추가됨",
                    "message": (
                        "`configuration.yaml`에 "
                        "`automation advisor: !include automation_advisor.yaml` "
                        "를 넣었습니다.\n\n"
                        "Home Assistant를 한 번 재시작하면 배포된 자동화가 로드됩니다."
                    ),
                    "notification_id": "advisor_config_include",
                },
                blocking=False,
            )
        try:
            text = await self.hass.async_add_executor_job(
                self._suggestions_file.read_text, "utf-8"
            )
            data = json.loads(text)
            self.suggestions = data.get("suggestions", [])
            self.last_scan = data.get("last_scan")
            self.matches = data.get("matches", [])
        except Exception:
            self.suggestions = []
        await self._refresh_habit_stats()
        if self._opt(CONF_HABIT_LEARNING, DEFAULT_HABIT_LEARNING):
            await self.observer.async_start()

    async def async_unload(self) -> None:
        self.observer.async_stop()

    async def _save(self) -> None:
        data = json.dumps(
            {
                "last_scan": self.last_scan,
                "matches": self.matches,
                "suggestions": self.suggestions,
            },
            ensure_ascii=False,
            indent=2,
        )
        await self._write_text(self._suggestions_file, data)

    def _trial(self) -> bool:
        return bool(self._opt(CONF_TRIAL_MODE, DEFAULT_TRIAL_MODE))

    async def _refresh_habit_stats(self, pattern_count: int | None = None) -> None:
        events = await self.hass.async_add_executor_job(self._event_store.count)
        span = await self.hass.async_add_executor_job(self._event_store.span_days)
        min_days = int(self._opt(CONF_MIN_OBSERVE_DAYS, DEFAULT_MIN_OBSERVE_DAYS))
        self.habit_stats = {
            "events": events,
            "span_days": round(span, 2),
            "patterns": pattern_count if pattern_count is not None else self.habit_stats.get("patterns", 0),
            "ready": span >= min_days and events > 0,
            "min_observe_days": min_days,
            "preview_count": len(getattr(self, "habit_preview", None) or []),
        }

    async def async_ensure_habit_preview(self) -> None:
        """Rebuild threshold-tab preview from the local event store if empty."""
        if not self._opt(CONF_HABIT_LEARNING, DEFAULT_HABIT_LEARNING):
            self.habit_preview = []
            return
        if self.habit_preview:
            return
        min_days = int(self._opt(CONF_MIN_OBSERVE_DAYS, DEFAULT_MIN_OBSERVE_DAYS))
        lookback = max(min_days, EVENT_RETENTION_DAYS)
        events = await self.hass.async_add_executor_job(
            self._event_store.fetch_since, lookback
        )
        patterns = await self.hass.async_add_executor_job(discover_patterns, events)
        ranked = sorted(
            patterns,
            key=lambda p: (p.lift, p.confidence, p.support),
            reverse=True,
        )[:20]
        self.habit_preview = [
            {
                "title": p.title,
                "explanation": p.explanation,
                "support": p.support,
                "confidence": p.confidence,
                "lift": p.lift,
                "source": "habit_preview",
                "status": "preview",
                "above_threshold": True,
            }
            for p in ranked
        ]
        await self._refresh_habit_stats(len(patterns))
        self.habit_stats["preview_count"] = len(self.habit_preview)

    async def async_scan(self) -> int:
        self.status = "scanning"
        self._notify()

        inventory = snapshot_inventory(self.hass)
        existing = existing_automation_entity_sets(self.hass)

        community_rates = None
        if self._opt(CONF_COMMUNITY_STUB, DEFAULT_COMMUNITY_STUB):
            community_rates = await self.hass.async_add_executor_job(load_community_rates)

        habit_patterns = []
        backfilled = 0
        min_days = int(self._opt(CONF_MIN_OBSERVE_DAYS, DEFAULT_MIN_OBSERVE_DAYS))
        if self._opt(CONF_HABIT_LEARNING, DEFAULT_HABIT_LEARNING):
            await self.hass.async_add_executor_job(
                self._event_store.purge_older_than, EVENT_RETENTION_DAYS
            )
            lookback = max(min_days, EVENT_RETENTION_DAYS)
            backfilled = await backfill_from_recorder(
                self.hass, self._event_store, days=lookback
            )
            events = await self.hass.async_add_executor_job(
                self._event_store.fetch_since, lookback
            )
            span = await self.hass.async_add_executor_job(self._event_store.span_days)
            # Always discover so the threshold tab can visualize metrics even
            # before the observe-days gate promotes habits to suggestions.
            habit_patterns = await self.hass.async_add_executor_job(
                discover_patterns, events
            )
            # Cap dashboard preview — full discovery can be thousands of pairs.
            ranked = sorted(
                habit_patterns,
                key=lambda p: (p.lift, p.confidence, p.support),
                reverse=True,
            )[:20]
            self.habit_preview = [
                {
                    "title": p.title,
                    "explanation": p.explanation,
                    "support": p.support,
                    "confidence": p.confidence,
                    "lift": p.lift,
                    "source": "habit_preview",
                    "status": "preview",
                    "above_threshold": True,
                }
                for p in ranked
            ]
            pattern_count = len(habit_patterns)
            # Observe-days gate only blocks promoting habits into suggestions.
            # Keep habit_preview so the thresholds tab can always visualize metrics.
            if span < min_days:
                habit_patterns = []
            await self._refresh_habit_stats(pattern_count)
            self.habit_stats["recorder_backfilled"] = backfilled
            self.habit_stats["preview_count"] = len(self.habit_preview)
        else:
            self.habit_preview = []
            await self._refresh_habit_stats(0)
            self.habit_stats["recorder_backfilled"] = 0

        llm_base = (self._opt(CONF_LLM_BASE_URL, "") or "").strip() or None
        llm_model = (self._opt(CONF_LLM_MODEL, "") or "").strip() or None
        llm_key = (self._opt(CONF_LLM_API_KEY, "") or "").strip() or None
        new_suggestions = recommend(
            inventory,
            existing_entity_sets=existing,
            trial=self._trial(),
            community_rates=community_rates or {},
            habit_patterns=habit_patterns,
            llm_base_url=llm_base,
            llm_model=llm_model,
            llm_api_key=llm_key,
        )

        self.matches = [
            {
                "recipe_id": s["recipe_id"],
                "title": s["title"],
                "area_name": s.get("area_name"),
                "source": s["source"],
            }
            for s in new_suggestions
        ]

        blocked_keys = {
            suggestion_key(s) for s in self.suggestions if blocks_resuggestion(s)
        }

        new_count = 0
        for suggestion in new_suggestions:
            key = suggestion_key(suggestion)
            existing = next(
                (
                    s
                    for s in self.suggestions
                    if suggestion_key(s) == key and s.get("status") == "pending"
                ),
                None,
            )
            if existing is not None:
                # Keep the same id; refresh concrete copy + compiled automation.
                sid = existing["id"]
                existing["behavior"] = suggestion.get("behavior")
                existing["explanation"] = suggestion.get("explanation")
                existing["entity_names"] = suggestion.get("entity_names") or {}
                existing["title"] = suggestion.get("title")
                auto = dict(suggestion.get("automation") or {})
                if auto:
                    auto["id"] = f"advisor_{suggestion.get('recipe_id')}_{sid}"
                    desc = str(auto.get("description") or "")
                    if "]" in desc:
                        auto["description"] = f"[Advisor:{sid}]" + desc.split("]", 1)[1]
                    existing["automation"] = auto
                existing["asked_run"] = False
                continue
            if key in blocked_keys:
                continue
            self.suggestions.insert(0, suggestion)
            blocked_keys.add(key)
            new_count += 1

        self.last_scan = datetime.now().strftime("%Y-%m-%d %H:%M")
        self.status = "idle"
        self._refresh_behaviors(inventory)
        await self._save()
        self._notify()
        _LOGGER.info(
            "Automation Advisor: scan complete — %d new (habit patterns=%d)",
            new_count,
            len(habit_patterns),
        )
        return new_count

    def _refresh_behaviors(self, inventory: list | None = None) -> None:
        """Fill concrete condition/action text on pending/previewed suggestions."""
        from .behavior import describe_automation_behavior
        from .inventory import build_entity_display_names, snapshot_inventory

        if inventory is None:
            inventory = snapshot_inventory(self.hass)
        names = build_entity_display_names(self.hass)
        for entity in inventory:
            label = entity.display_name or entity.friendly_name
            if label and label != entity.entity_id:
                names[entity.entity_id] = label
        for suggestion in self.suggestions:
            if suggestion.get("status") not in {"pending", "previewed"}:
                continue
            stored_names = dict(suggestion.get("entity_names") or {})
            # Fresh registry names win over stale stored romanized labels
            merged = {**stored_names, **names}
            derived = describe_automation_behavior(
                suggestion.get("automation") or {},
                merged,
                context_area=suggestion.get("area_name"),
            )
            if derived:
                suggestion["behavior"] = derived
            elif not suggestion.get("behavior"):
                continue
            behavior = str(suggestion["behavior"])
            old = str(suggestion.get("explanation") or "")
            stub = ""
            marker = "(비슷한 환경"
            idx = old.find(marker)
            if idx >= 0:
                stub = "\n\n" + old[idx:].strip()
            suggestion["explanation"] = behavior + stub
            suggestion["entity_names"] = {
                eid: merged[eid]
                for eid in (suggestion.get("entities") or [])
                if eid in merged and merged[eid] != eid
            }

    async def async_prompt_new(self) -> int:
        from .notifications import ask_run_once, sync_web_inbox

        self._refresh_behaviors()
        prompted = 0
        for suggestion in self.pending_suggestions:
            if suggestion.get("asked_run") or suggestion.get("snoozed"):
                continue
            await ask_run_once(self.hass, suggestion)
            suggestion["asked_run"] = True
            prompted += 1
            if prompted >= 3:
                break
        if prompted:
            await self._save()
        await sync_web_inbox(
            self.hass, self.pending_suggestions, self.previewed_suggestions
        )
        return prompted

    async def async_reprompt(self, limit: int = 3) -> int:
        from .notifications import ask_run_once, sync_web_inbox

        self._refresh_behaviors()
        prompted = 0
        for suggestion in self.pending_suggestions:
            suggestion["snoozed"] = False
            await ask_run_once(self.hass, suggestion)
            suggestion["asked_run"] = True
            prompted += 1
            if prompted >= limit:
                break
        if prompted:
            await self._save()
        await sync_web_inbox(
            self.hass, self.pending_suggestions, self.previewed_suggestions
        )
        return prompted

    async def async_run_once(
        self, suggestion_id: str, *, prompt_automate: bool = True
    ) -> bool:
        suggestion = self._get_suggestion(suggestion_id)
        if not suggestion or suggestion.get("status") != "pending":
            return False
        auto = suggestion.get("automation") or {}
        domain, service, data = action_to_service_call(auto)
        entity_ids = data.get("entity_id")
        if isinstance(entity_ids, str):
            entity_ids = [entity_ids]
        if is_blocked(list(entity_ids or [])):
            _LOGGER.warning("Automation Advisor: blocked one-shot %s", suggestion_id)
            return False
        from homeassistant.core import Context

        ctx = Context()
        self.observer.remember_advisor_context(ctx.id)
        await self.hass.services.async_call(
            domain, service, data, blocking=True, context=ctx
        )
        suggestion["status"] = "previewed"
        suggestion["previewed_at"] = datetime.now().isoformat()
        await self._save()
        self._notify()
        if prompt_automate:
            await ask_automate(self.hass, suggestion)
        await sync_web_inbox(
            self.hass, self.pending_suggestions, self.previewed_suggestions
        )
        return True

    async def async_deploy(self, suggestion_id: str) -> None:
        suggestion = self._get_suggestion(suggestion_id)
        if not suggestion:
            return
        suggestion["status"] = "deployed"
        suggestion["deployed_at"] = datetime.now().isoformat()
        await self._rewrite_automations_file()
        await self._save()
        await self.hass.services.async_call("automation", "reload")
        auto = suggestion.get("automation") or {}
        trial_note = (
            "시험 모드라 비활성으로 등록했습니다. 자동화를 켠 뒤에 Home Assistant가 실행합니다."
            if suggestion.get("trial") or auto.get("initial_state") is False
            else "조건이 맞으면 Home Assistant가 실행합니다."
        )
        await confirm_deployed(self.hass, suggestion, trial_note)
        await sync_web_inbox(
            self.hass, self.pending_suggestions, self.previewed_suggestions
        )
        self._notify()

    async def _rewrite_automations_file(self) -> None:
        import yaml

        automations = []
        for suggestion in self.suggestions:
            if suggestion.get("status") == "deployed" and suggestion.get("automation"):
                auto = dict(suggestion["automation"])
                automations.append(auto)

        content = (
            "# Automation Advisor — compiler output. Do not hand-edit.\n"
            "# Trial automations use initial_state: false until you enable them.\n\n"
        )
        if automations:
            content += yaml.dump(
                automations,
                allow_unicode=True,
                default_flow_style=False,
                sort_keys=False,
            )
        else:
            content += "[]\n"

        await self._write_text(self._automations_file, content)

    async def async_dismiss(self, suggestion_id: str) -> None:
        suggestion = self._get_suggestion(suggestion_id)
        if suggestion:
            suggestion["status"] = "dismissed"
            suggestion["dismissed_at"] = datetime.now(timezone.utc).isoformat()
            await self._save()
            await clear_suggestion_card(self.hass, suggestion_id)
            await sync_web_inbox(
                self.hass, self.pending_suggestions, self.previewed_suggestions
            )
            self._notify()

    async def async_later(self, suggestion_id: str) -> None:
        suggestion = self._get_suggestion(suggestion_id)
        if not suggestion:
            return
        suggestion["snoozed"] = True
        await self._save()
        await clear_suggestion_card(self.hass, suggestion_id)
        await sync_web_inbox(
            self.hass, self.pending_suggestions, self.previewed_suggestions
        )

    async def async_feedback(self, suggestion_id: str, rating: str) -> None:
        suggestion = self._get_suggestion(suggestion_id)
        if suggestion:
            suggestion["feedback"] = rating
            await self._save()
            self._notify()

    async def async_delete(self, suggestion_id: str) -> None:
        self.suggestions = [s for s in self.suggestions if s.get("id") != suggestion_id]
        await self._save()
        await self._rewrite_automations_file()
        await self.hass.services.async_call("automation", "reload")
        self._notify()

    async def async_kill_switch(self) -> int:
        count = 0
        for suggestion in self.suggestions:
            if suggestion.get("status") == "deployed":
                suggestion["status"] = "killed"
                count += 1
        await self._rewrite_automations_file()
        await self._save()
        await self.hass.services.async_call("automation", "reload")
        self._notify()
        return count

    async def async_clear_habit_data(self) -> int:
        before = await self.hass.async_add_executor_job(self._event_store.count)
        await self.hass.async_add_executor_job(self._event_store.clear)
        await self._refresh_habit_stats(0)
        self._notify()
        return before

    def _get_suggestion(self, sid: str) -> dict | None:
        return next((s for s in self.suggestions if s.get("id") == sid), None)

    @property
    def event_store(self) -> EventStore:
        return self._event_store

    def llm_options(self) -> tuple[str | None, str | None, str | None]:
        base = (self._opt(CONF_LLM_BASE_URL, "") or "").strip() or None
        model = (self._opt(CONF_LLM_MODEL, "") or "").strip() or None
        key = (self._opt(CONF_LLM_API_KEY, "") or "").strip() or None
        return base, model, key

    def find_suggestion_any(self, target_id: str) -> dict | None:
        """Match suggestion id or compiled automation id."""
        for suggestion in self.suggestions:
            if suggestion.get("id") == target_id:
                return suggestion
            auto = suggestion.get("automation") or {}
            if auto.get("id") == target_id:
                return suggestion
        return None

    async def async_chat_create(self, automation: dict, *, title: str) -> str:
        suggestion_id = f"chat_{uuid.uuid4().hex[:10]}"
        auto = apply_chat_defaults(dict(automation), suggestion_id)
        assert_automation_safe(auto)
        entities = collect_entity_ids(auto)
        self.suggestions.append(
            {
                "id": suggestion_id,
                "recipe_id": "chat",
                "source": "chat",
                "title": title or auto.get("alias") or suggestion_id,
                "explanation": auto.get("description") or title,
                "entities": entities,
                "status": "deployed",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "deployed_at": datetime.now(timezone.utc).isoformat(),
                "feedback": None,
                "trial": auto.get("initial_state") is False,
                "automation": auto,
            }
        )
        await self._save()
        await self._rewrite_automations_file()
        await self.hass.services.async_call("automation", "reload")
        self._notify()
        return suggestion_id

    async def async_chat_update(
        self, target_id: str, automation: dict, *, title: str
    ) -> None:
        suggestion = self.find_suggestion_any(target_id)
        if not suggestion:
            raise ValueError(f"자동화를 찾지 못했습니다: {target_id}")
        suggestion_id = str(suggestion.get("id"))
        auto = apply_chat_defaults(dict(automation), suggestion_id)
        assert_automation_safe(auto)
        suggestion["automation"] = auto
        suggestion["title"] = title or auto.get("alias") or suggestion.get("title")
        suggestion["entities"] = collect_entity_ids(auto)
        suggestion["status"] = "deployed"
        suggestion["deployed_at"] = datetime.now(timezone.utc).isoformat()
        suggestion["source"] = suggestion.get("source") or "chat"
        await self._save()
        await self._rewrite_automations_file()
        await self.hass.services.async_call("automation", "reload")
        self._notify()

    @property
    def pending_suggestions(self) -> list[dict]:
        return [s for s in self.suggestions if s.get("status") == "pending"]

    @property
    def previewed_suggestions(self) -> list[dict]:
        return [s for s in self.suggestions if s.get("status") == "previewed"]

    @property
    def deployed_suggestions(self) -> list[dict]:
        return [s for s in self.suggestions if s.get("status") == "deployed"]
