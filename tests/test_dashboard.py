"""Tests for Dashboard API builders (no Home Assistant)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "custom_components"))

from automation_advisor.dashboard_api import (  # noqa: E402
    build_device_row,
    build_log_lines,
    build_reasons,
    build_summary,
    list_automations,
    normalize_action,
)


class DeviceRowTests(unittest.TestCase):
    def test_ok_false_when_unavailable(self) -> None:
        row = build_device_row("light.x", "X", "거실", "unavailable", 0, 0)
        self.assertIs(row["ok"], False)
        self.assertEqual(row["area"], "거실")
        self.assertEqual(row["entity_id"], "light.x")

    def test_ok_true_when_on(self) -> None:
        row = build_device_row("light.x", "X", "거실", "on", 2, 1)
        self.assertIs(row["ok"], True)
        self.assertEqual(row["automation_count"], 2)
        self.assertEqual(row["suggestion_count"], 1)


class SummaryTests(unittest.TestCase):
    def test_counts(self) -> None:
        s = build_summary(
            synced_at="2026-08-25T00:00:00+00:00",
            devices=[
                build_device_row("light.a", "A", "거실", "on", 1, 0),
                build_device_row("light.b", "B", "침실", "unavailable", 0, 1),
            ],
            pending_count=2,
        )
        self.assertEqual(s["device_count"], 2)
        self.assertEqual(s["anomaly_count"], 1)
        self.assertEqual(s["pending_count"], 2)
        self.assertEqual(s["synced_at"], "2026-08-25T00:00:00+00:00")


class AutomationsListTests(unittest.TestCase):
    def test_hides_dismissed_by_default(self) -> None:
        sug = [
            {"id": "1", "title": "A", "status": "pending", "source": "habit"},
            {"id": "2", "title": "B", "status": "dismissed", "source": "habit"},
            {
                "id": "3",
                "title": "C",
                "status": "deployed",
                "source": "catalog",
                "automation": {"id": "auto_c", "alias": "C"},
            },
        ]
        out = list_automations(sug, include_dismissed=False)
        self.assertEqual([x["id"] for x in out], ["1", "3"])
        out2 = list_automations(sug, include_dismissed=True)
        self.assertEqual([x["id"] for x in out2], ["1", "2", "3"])


class LogLineTests(unittest.TestCase):
    def test_numbering(self) -> None:
        class Ev:
            ts = 1700000000.0
            entity_id = "light.a"
            old_state = "off"
            new_state = "on"
            actor = "human_ui"

        lines = build_log_lines([Ev()], names={"light.a": "거실등"}, start_n=100)
        self.assertEqual(lines[0]["n"], 100)
        self.assertEqual(lines[0]["entity_id"], "light.a")
        self.assertIn("on", lines[0]["msg"])


class ReasonsTests(unittest.TestCase):
    def test_thresholds(self) -> None:
        r = build_reasons(
            [
                {
                    "id": "1",
                    "title": "T",
                    "status": "pending",
                    "source": "habit",
                    "confidence": 0.82,
                    "support": 5,
                    "explanation": "반복",
                }
            ],
            min_confidence=0.75,
            min_support=3,
        )
        self.assertEqual(r["thresholds"]["min_confidence"], 0.75)
        self.assertEqual(r["items"][0]["score"], 0.82)
        self.assertIs(r["items"][0]["above_threshold"], True)


class ActionNormalizeTests(unittest.TestCase):
    def test_ok(self) -> None:
        self.assertEqual(normalize_action("approve"), "approve")
        self.assertEqual(normalize_action("resend"), "resend")

    def test_bad(self) -> None:
        with self.assertRaises(ValueError):
            normalize_action("nope")


if __name__ == "__main__":
    unittest.main()
