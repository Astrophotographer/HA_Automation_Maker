"""Validate chatbot-authored Home Assistant automation YAML."""

from __future__ import annotations

from typing import Any

import yaml

from .safety import is_blocked


def parse_automation_yaml(text: str) -> dict[str, Any]:
    """Parse a single automation mapping. Raises ValueError on bad input."""
    raw = (text or "").strip()
    if not raw:
        raise ValueError("YAML이 비어 있습니다.")
    if raw.startswith("```"):
        lines = raw.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        raw = "\n".join(lines).strip()
    try:
        data = yaml.safe_load(raw)
    except yaml.YAMLError as err:
        raise ValueError(f"YAML 파싱 실패: {err}") from err
    if isinstance(data, list):
        if len(data) != 1 or not isinstance(data[0], dict):
            raise ValueError("자동화는 하나의 매핑이어야 합니다.")
        data = data[0]
    if not isinstance(data, dict):
        raise ValueError("자동화 YAML은 객체여야 합니다.")
    triggers = data.get("trigger", data.get("triggers"))
    actions = data.get("action", data.get("actions"))
    if not triggers:
        raise ValueError("trigger(또는 triggers)가 필요합니다.")
    if not actions:
        raise ValueError("action(또는 actions)가 필요합니다.")
    return data


def collect_entity_ids(obj: Any) -> list[str]:
    found: list[str] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            for key, val in node.items():
                if key == "entity_id":
                    if isinstance(val, str) and "." in val:
                        found.append(val)
                    elif isinstance(val, list):
                        for item in val:
                            if isinstance(item, str) and "." in item:
                                found.append(item)
                else:
                    walk(val)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(obj)
    seen: set[str] = set()
    out: list[str] = []
    for eid in found:
        if eid not in seen:
            seen.add(eid)
            out.append(eid)
    return out


def action_entity_ids(automation: dict[str, Any]) -> list[str]:
    steps = automation.get("action", automation.get("actions")) or []
    if isinstance(steps, dict):
        steps = [steps]
    return collect_entity_ids(steps)


def apply_chat_defaults(automation: dict[str, Any], suggestion_id: str) -> dict[str, Any]:
    auto = dict(automation)
    if not auto.get("id"):
        auto["id"] = f"advisor_chat_{suggestion_id}"
    if "initial_state" not in auto:
        auto["initial_state"] = False
    alias = auto.get("alias") or auto.get("id")
    auto["alias"] = str(alias)
    desc = auto.get("description") or ""
    if f"[Advisor:{suggestion_id}]" not in str(desc):
        auto["description"] = f"[Advisor:{suggestion_id}] {desc}".strip()
    return auto


def assert_automation_safe(automation: dict[str, Any]) -> None:
    blocked = action_entity_ids(automation)
    if is_blocked(blocked):
        raise ValueError(
            "잠금·알람·카메라·공조 등 고위험 장비는 챗봇으로 등록할 수 없습니다."
        )
