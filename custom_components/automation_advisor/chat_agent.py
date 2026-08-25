"""Tool-using chat agent for Automation Advisor."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol

import yaml

from .chat_pending import PendingStore, PendingWrite
from .chat_yaml import assert_automation_safe, parse_automation_yaml

_LOGGER = logging.getLogger(__name__)

SYSTEM_PROMPT = """당신은 Home Assistant Automation Advisor 한국어 챗봇입니다.
도구로 추천·자동화·장비 상태·로그를 조회합니다.
자동화를 만들거나 바꾸거나 지울 때는 propose_* 도구만 쓰고, 사용자에게 확인 버튼이 뜬다고 안내하세요.
확인 전에는 HA에 반영되지 않았다고 말하세요.
YAML은 Home Assistant 자동화 형식(trigger/action)으로 작성하세요.
잠금·알람·카메라·공조·온수기·청소기는 액션으로 쓰지 마세요.
짧고 명확하게 답하세요."""

TOOL_SPECS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "list_suggestions",
            "description": "자동화 추천(대기/미리보기/기각 등) 목록",
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "description": "pending|previewed|deployed|dismissed|killed 또는 비움(전체)",
                    }
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_automations",
            "description": "Advisor가 배포한 자동화 목록",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_states",
            "description": "장비/엔티티 현재 상태 조회",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "이름·entity_id·영역 검색어",
                    },
                    "limit": {"type": "integer"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_logs",
            "description": "최근 장비 이벤트 로그",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer"},
                    "entity_id": {"type": "string"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "propose_create_automation",
            "description": "새 자동화 YAML 제안(확인 전 미등록)",
            "parameters": {
                "type": "object",
                "properties": {
                    "summary": {"type": "string"},
                    "yaml": {"type": "string"},
                },
                "required": ["yaml"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "propose_update_automation",
            "description": "기존 자동화 수정 YAML 제안",
            "parameters": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "summary": {"type": "string"},
                    "yaml": {"type": "string"},
                },
                "required": ["id", "yaml"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "propose_delete_automation",
            "description": "자동화 삭제 제안",
            "parameters": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "summary": {"type": "string"},
                },
                "required": ["id"],
            },
        },
    },
]


class ChatToolkit(Protocol):
    def list_suggestions(self, status: str | None = None) -> list[dict[str, Any]]: ...

    def list_automations(self) -> list[dict[str, Any]]: ...

    def get_states(self, query: str | None = None, limit: int = 40) -> list[dict[str, Any]]: ...

    def get_logs(
        self, limit: int = 40, entity_id: str | None = None
    ) -> list[dict[str, Any]]: ...

    def find_suggestion(self, target_id: str) -> dict[str, Any] | None: ...


@dataclass
class AgentResult:
    text: str
    pending: PendingWrite | None = None
    messages: list[dict[str, Any]] = field(default_factory=list)


_TOOL_JSON_RE = re.compile(
    r"```(?:json|tool)?\s*(\{.*?\})\s*```|"
    r"<tool_call>\s*(\{.*?\})\s*</tool_call>|"
    r"\{\s*\"(?:name|tool)\"\s*:\s*\"[a-z_]+\"[\s\S]*?\}",
    re.DOTALL,
)


def parse_fallback_tool_calls(content: str) -> list[dict[str, Any]]:
    """Best-effort tool calls when the model ignores OpenAI tools."""
    if not content:
        return []
    calls: list[dict[str, Any]] = []
    for match in _TOOL_JSON_RE.finditer(content):
        blob = next((g for g in match.groups() if g), match.group(0))
        try:
            data = json.loads(blob)
        except json.JSONDecodeError:
            continue
        name = data.get("name") or data.get("tool")
        if not name:
            continue
        args = data.get("arguments") or data.get("parameters") or data.get("args") or {}
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except json.JSONDecodeError:
                args = {}
        calls.append(
            {
                "id": f"fallback_{len(calls)}",
                "type": "function",
                "function": {
                    "name": str(name),
                    "arguments": json.dumps(args, ensure_ascii=False),
                },
            }
        )
    return calls


def _args(call: dict[str, Any]) -> dict[str, Any]:
    raw = (call.get("function") or {}).get("arguments") or "{}"
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


class ChatAgent:
    def __init__(
        self,
        toolkit: ChatToolkit,
        pending: PendingStore,
        llm_call: Callable[..., dict[str, Any]],
        *,
        max_rounds: int = 6,
    ) -> None:
        self.toolkit = toolkit
        self.pending = pending
        self.llm_call = llm_call
        self.max_rounds = max_rounds

    def run(self, history: list[dict[str, Any]], user_text: str) -> AgentResult:
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages.extend(history)
        messages.append({"role": "user", "content": user_text})

        pending: PendingWrite | None = None
        final_text = ""

        for _ in range(self.max_rounds):
            message = self.llm_call(messages=messages, tools=TOOL_SPECS)
            tool_calls = message.get("tool_calls") or []
            content = (message.get("content") or "").strip()
            if not tool_calls and content:
                tool_calls = parse_fallback_tool_calls(content)

            if not tool_calls:
                final_text = content or "요청을 처리했습니다."
                messages.append({"role": "assistant", "content": final_text})
                break

            messages.append(
                {
                    "role": "assistant",
                    "content": content or None,
                    "tool_calls": tool_calls,
                }
            )
            stop_after = False
            for call in tool_calls:
                name = (call.get("function") or {}).get("name") or ""
                result, maybe_pending = self._dispatch(name, _args(call))
                if maybe_pending is not None:
                    pending = maybe_pending
                    stop_after = True
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.get("id") or name,
                        "content": json.dumps(result, ensure_ascii=False),
                    }
                )
            if stop_after:
                final_text = (
                    content
                    or "아래 내용을 확인한 뒤 버튼을 눌러 주세요. 확인 전에는 Home Assistant에 반영되지 않습니다."
                )
                messages.append({"role": "assistant", "content": final_text})
                break
        else:
            final_text = final_text or "도구 호출이 너무 많아 중단했습니다."

        # history without system
        trimmed = [m for m in messages if m.get("role") != "system"]
        return AgentResult(text=final_text, pending=pending, messages=trimmed)

    def _dispatch(
        self, name: str, args: dict[str, Any]
    ) -> tuple[Any, PendingWrite | None]:
        try:
            if name == "list_suggestions":
                status = (args.get("status") or "").strip() or None
                return self.toolkit.list_suggestions(status), None
            if name == "list_automations":
                return self.toolkit.list_automations(), None
            if name == "get_states":
                return (
                    self.toolkit.get_states(
                        query=(args.get("query") or None),
                        limit=int(args.get("limit") or 40),
                    ),
                    None,
                )
            if name == "get_logs":
                return (
                    self.toolkit.get_logs(
                        limit=int(args.get("limit") or 40),
                        entity_id=(args.get("entity_id") or None),
                    ),
                    None,
                )
            if name == "propose_create_automation":
                return self._propose_create(args)
            if name == "propose_update_automation":
                return self._propose_update(args)
            if name == "propose_delete_automation":
                return self._propose_delete(args)
            return {"error": f"unknown tool: {name}"}, None
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("chat tool %s failed: %s", name, err)
            return {"error": str(err)}, None

    def _propose_create(
        self, args: dict[str, Any]
    ) -> tuple[dict[str, Any], PendingWrite | None]:
        yaml_text = str(args.get("yaml") or "")
        auto = parse_automation_yaml(yaml_text)
        assert_automation_safe(auto)
        summary = str(args.get("summary") or auto.get("alias") or "새 자동화")
        yaml_dump = yaml.safe_dump(auto, allow_unicode=True, sort_keys=False)
        item = self.pending.create(
            kind="create",
            summary=summary,
            yaml_text=yaml_dump,
            automation=auto,
        )
        return {"ok": True, "pending": True, "summary": summary}, item

    def _propose_update(
        self, args: dict[str, Any]
    ) -> tuple[dict[str, Any], PendingWrite | None]:
        target_id = str(args.get("id") or "").strip()
        if not target_id:
            return {"error": "id가 필요합니다."}, None
        if not self.toolkit.find_suggestion(target_id):
            return {"error": f"자동화를 찾지 못했습니다: {target_id}"}, None
        yaml_text = str(args.get("yaml") or "")
        auto = parse_automation_yaml(yaml_text)
        assert_automation_safe(auto)
        summary = str(args.get("summary") or auto.get("alias") or f"수정 {target_id}")
        yaml_dump = yaml.safe_dump(auto, allow_unicode=True, sort_keys=False)
        item = self.pending.create(
            kind="update",
            summary=summary,
            yaml_text=yaml_dump,
            automation=auto,
            target_id=target_id,
        )
        return {"ok": True, "pending": True, "summary": summary}, item

    def _propose_delete(
        self, args: dict[str, Any]
    ) -> tuple[dict[str, Any], PendingWrite | None]:
        target_id = str(args.get("id") or "").strip()
        if not target_id:
            return {"error": "id가 필요합니다."}, None
        found = self.toolkit.find_suggestion(target_id)
        if not found:
            return {"error": f"자동화를 찾지 못했습니다: {target_id}"}, None
        summary = str(
            args.get("summary")
            or f"삭제: {found.get('title') or found.get('id')}"
        )
        item = self.pending.create(
            kind="delete",
            summary=summary,
            yaml_text="",
            automation=None,
            target_id=found.get("id"),
        )
        return {"ok": True, "pending": True, "summary": summary}, item
