"""Tests for Advisor chatbot helpers (no Home Assistant / Spark)."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "custom_components"))

from automation_advisor.chat_agent import (  # noqa: E402
    ChatAgent,
    parse_fallback_tool_calls,
)
from automation_advisor.chat_llm import llm_origin  # noqa: E402
from automation_advisor.chat_pending import PendingStore  # noqa: E402
from automation_advisor.chat_yaml import (  # noqa: E402
    action_entity_ids,
    apply_chat_defaults,
    assert_automation_safe,
    parse_automation_yaml,
)


GOOD_YAML = """
alias: 거실 모션 시 조명
trigger:
  - platform: state
    entity_id: binary_sensor.living_motion
    to: "on"
action:
  - action: light.turn_on
    target:
      entity_id: light.living_lamp
"""


class YamlTests(unittest.TestCase):
    def test_parse_and_defaults(self) -> None:
        auto = parse_automation_yaml(GOOD_YAML)
        self.assertIn("trigger", auto)
        out = apply_chat_defaults(auto, "chat_abc")
        self.assertEqual(out["id"], "advisor_chat_chat_abc")
        self.assertIs(out["initial_state"], False)
        self.assertEqual(action_entity_ids(out), ["light.living_lamp"])

    def test_fence_stripped(self) -> None:
        fenced = "```yaml\n" + GOOD_YAML + "\n```"
        auto = parse_automation_yaml(fenced)
        self.assertEqual(auto["alias"], "거실 모션 시 조명")

    def test_blocked_action(self) -> None:
        auto = parse_automation_yaml(
            """
alias: bad
trigger:
  - platform: state
    entity_id: binary_sensor.x
    to: "on"
action:
  - action: lock.unlock
    target:
      entity_id: lock.front
"""
        )
        with self.assertRaises(ValueError):
            assert_automation_safe(auto)


class LlmOriginTests(unittest.TestCase):
    def test_strips_v1(self) -> None:
        self.assertEqual(llm_origin("http://spark:8000/v1"), "http://spark:8000")
        self.assertEqual(llm_origin("http://spark:8000/v1/"), "http://spark:8000")

    def test_keeps_plain(self) -> None:
        self.assertEqual(llm_origin("http://spark:8000"), "http://spark:8000")


class PendingTests(unittest.TestCase):
    def test_create_and_pop(self) -> None:
        store = PendingStore(ttl_seconds=60)
        item = store.create(kind="create", summary="s", yaml_text="a: 1")
        self.assertIsNotNone(store.get(item.token))
        popped = store.pop(item.token)
        self.assertEqual(popped.summary, "s")
        self.assertIsNone(store.get(item.token))


class FallbackParserTests(unittest.TestCase):
    def test_json_fence(self) -> None:
        text = '말해줄게\n```json\n{"name":"list_automations","arguments":{}}\n```'
        calls = parse_fallback_tool_calls(text)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["function"]["name"], "list_automations")


class FakeToolkit:
    def __init__(self) -> None:
        self.suggestions = [
            {
                "id": "s1",
                "title": "거실",
                "source": "catalog",
                "status": "pending",
                "explanation": "x",
            }
        ]

    def list_suggestions(self, status=None):
        return [s for s in self.suggestions if not status or s["status"] == status]

    def list_automations(self):
        return []

    def get_states(self, query=None, limit=40):
        return [{"entity_id": "light.a", "name": "A", "state": "on", "domain": "light"}]

    def get_logs(self, limit=40, entity_id=None):
        return []

    def find_suggestion(self, target_id: str):
        return next((s for s in self.suggestions if s["id"] == target_id), None)


class AgentTests(unittest.TestCase):
    def test_propose_create_stops_with_pending(self) -> None:
        store = PendingStore()
        toolkit = FakeToolkit()
        calls = [
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "1",
                        "type": "function",
                        "function": {
                            "name": "propose_create_automation",
                            "arguments": json.dumps(
                                {"summary": "거실 조명", "yaml": GOOD_YAML},
                                ensure_ascii=False,
                            ),
                        },
                    }
                ],
            }
        ]
        idx = {"n": 0}

        def llm_call(*, messages, tools):
            msg = calls[idx["n"]]
            idx["n"] += 1
            return msg

        agent = ChatAgent(toolkit, store, llm_call)
        result = agent.run([], "만들어줘")
        self.assertIsNotNone(result.pending)
        self.assertEqual(result.pending.kind, "create")
        self.assertIn("확인", result.text)


if __name__ == "__main__":
    unittest.main()
