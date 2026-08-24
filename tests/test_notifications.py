"""Notification payload helpers."""

from __future__ import annotations

import unittest

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "custom_components" / "automation_advisor"))

from push_format import (
    clear_notification_payload,
    flatten_actions_for_fcm,
    mobile_card_payload,
    suggestion_card_tag,
    suggestion_card_tags,
)


class FlattenActionsTests(unittest.TestCase):
    def test_flattens_up_to_three_actions(self) -> None:
        flat = flatten_actions_for_fcm(
            [
                {"action": "AR_abc", "title": "실행"},
                {"action": "AN_abc", "title": "나중에"},
                {"action": "AX_abc", "title": "기각"},
                {"action": "EXTRA", "title": "ignored"},
            ]
        )
        self.assertEqual(
            flat,
            {
                "action_1_key": "AR_abc",
                "action_1_title": "실행",
                "action_2_key": "AN_abc",
                "action_2_title": "나중에",
                "action_3_key": "AX_abc",
                "action_3_title": "기각",
            },
        )

    def test_includes_optional_action_fields(self) -> None:
        flat = flatten_actions_for_fcm(
            [
                {
                    "action": "URI",
                    "title": "열기",
                    "uri": "/lovelace/home",
                    "behavior": "textInput",
                    "authenticationRequired": True,
                }
            ]
        )
        self.assertEqual(flat["action_1_key"], "URI")
        self.assertEqual(flat["action_1_uri"], "/lovelace/home")
        self.assertEqual(flat["action_1_behavior"], "textInput")
        self.assertEqual(flat["action_1_authenticationRequired"], "True")


class SuggestionCardTests(unittest.TestCase):
    def test_run_and_automate_share_the_same_tag(self) -> None:
        sid = "f1cfa7dc"
        run = mobile_card_payload(
            title="실행하시겠습니까?",
            body="켜기",
            suggestion_id=sid,
            actions=[{"action": f"AR_{sid}", "title": "실행"}],
        )
        auto = mobile_card_payload(
            title="자동화하시겠습니까?",
            body="반복할까요?",
            suggestion_id=sid,
            actions=[{"action": f"AD_{sid}", "title": "자동화"}],
        )
        tag = suggestion_card_tag(sid)
        self.assertEqual(run["data"]["tag"], tag)
        self.assertEqual(auto["data"]["tag"], tag)
        self.assertEqual(run["data"]["group"], tag)
        self.assertEqual(auto["data"]["group"], tag)
        self.assertEqual(auto["data"]["action_3_key"], "")
        self.assertEqual(auto["data"]["action_3_title"], "")

    def test_later_and_dismiss_clear_that_card_and_legacy_tags(self) -> None:
        sid = "f1cfa7dc"
        tags = suggestion_card_tags(sid)
        self.assertEqual(tags[0], suggestion_card_tag(sid))
        self.assertIn(f"advisor_auto_{sid}", tags)
        self.assertEqual(tags[0], f"advisor_run_{sid}")
        payload = clear_notification_payload(tags[0])
        self.assertEqual(payload["message"], "clear_notification")
        self.assertEqual(payload["data"]["tag"], tags[0])


if __name__ == "__main__":
    unittest.main()
