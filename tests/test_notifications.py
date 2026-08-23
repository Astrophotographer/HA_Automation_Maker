"""Notification payload helpers."""

from __future__ import annotations

import unittest

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "custom_components" / "automation_advisor"))

from push_format import flatten_actions_for_fcm


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


if __name__ == "__main__":
    unittest.main()
