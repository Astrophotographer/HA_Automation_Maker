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
    group_devices,
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


class GroupDevicesTests(unittest.TestCase):
    def test_groups_by_device_id(self) -> None:
        rows = [
            build_device_row(
                "switch.plug",
                "플러그",
                "거실",
                "on",
                1,
                0,
                device_id="dev1",
                device_name="스마트플러그",
            ),
            build_device_row(
                "sensor.plug_power",
                "전력",
                "거실",
                "12",
                0,
                1,
                device_id="dev1",
                device_name="스마트플러그",
            ),
            build_device_row("light.other", "다른등", "침실", "off", 0, 0),
        ]
        # sensor domain is not in primary list — still groups; switch preferred as state
        grouped = group_devices(rows)
        self.assertEqual(len(grouped), 2)
        plug = next(d for d in grouped if d["device_id"] == "dev1")
        self.assertEqual(plug["name"], "스마트플러그")
        self.assertEqual(plug["entity_count"], 2)
        self.assertEqual(plug["automation_count"], 1)
        self.assertEqual(plug["suggestion_count"], 1)
        self.assertEqual(len(plug["entities"]), 2)
        solo = next(d for d in grouped if d["device_id"] is None)
        self.assertEqual(solo["entity_count"], 1)
        self.assertEqual(solo["name"], "다른등")

    def test_group_ok_false_if_any_entity_bad(self) -> None:
        rows = [
            build_device_row(
                "light.a", "A", "거실", "on", 0, 0, device_id="d", device_name="램프"
            ),
            build_device_row(
                "switch.a",
                "B",
                "거실",
                "unavailable",
                0,
                0,
                device_id="d",
                device_name="램프",
            ),
        ]
        grouped = group_devices(rows)
        self.assertEqual(len(grouped), 1)
        self.assertIs(grouped[0]["ok"], False)
        self.assertEqual(grouped[0]["state"], "unavailable")


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
                    "lift": 1.5,
                    "explanation": "반복",
                }
            ],
            min_confidence=0.75,
            min_support=3,
            min_lift=1.2,
        )
        self.assertEqual(r["thresholds"]["min_confidence"], 0.75)
        self.assertEqual(r["thresholds"]["min_lift"], 1.2)
        self.assertEqual(r["items"][0]["score"], 0.82)
        self.assertEqual(r["items"][0]["confidence"], 0.82)
        self.assertEqual(r["items"][0]["support"], 5)
        self.assertEqual(r["items"][0]["lift"], 1.5)
        self.assertIs(r["items"][0]["above_threshold"], True)
        self.assertIs(r["items"][0]["has_metrics"], True)

    def test_preview_and_habit(self) -> None:
        r = build_reasons(
            [
                {
                    "id": "c1",
                    "title": "Catalog",
                    "status": "pending",
                    "source": "catalog",
                }
            ],
            min_confidence=0.5,
            min_support=3,
            min_lift=1.2,
            habit={"ready": False, "span_days": 1.5, "min_observe_days": 3, "patterns": 1},
            preview=[
                {
                    "title": "문 열림 → 조명 on",
                    "explanation": "반복",
                    "support": 4,
                    "confidence": 0.7,
                    "lift": 1.8,
                }
            ],
        )
        self.assertFalse(r["habit"]["ready"])
        titles = [x["title"] for x in r["items"]]
        self.assertIn("Catalog", titles)
        self.assertIn("문 열림 → 조명 on", titles)
        preview = next(x for x in r["items"] if x["title"] == "문 열림 → 조명 on")
        self.assertTrue(preview["has_metrics"])
        self.assertEqual(preview["support"], 4)
        catalog = next(x for x in r["items"] if x["title"] == "Catalog")
        self.assertFalse(catalog["has_metrics"])

    def test_below_lift(self) -> None:
        r = build_reasons(
            [
                {
                    "id": "1",
                    "title": "T",
                    "status": "pending",
                    "confidence": 0.9,
                    "support": 10,
                    "lift": 1.0,
                }
            ],
            min_confidence=0.5,
            min_support=3,
            min_lift=1.2,
        )
        self.assertIs(r["items"][0]["above_threshold"], False)

    def test_demo_when_no_metrics(self) -> None:
        r = build_reasons(
            [
                {
                    "id": "1",
                    "title": "일몰이면 조명 켜기",
                    "status": "pending",
                    "source": "catalog",
                }
            ],
            min_confidence=0.5,
            min_support=3,
            min_lift=1.2,
        )
        demo = [x for x in r["items"] if x.get("source") == "demo"]
        self.assertEqual(len(demo), 3)
        self.assertTrue(all(x["has_metrics"] for x in demo))
        self.assertTrue(demo[0]["above_threshold"])
        self.assertFalse(demo[1]["above_threshold"])  # lift 1.05 < 1.2


class ActionNormalizeTests(unittest.TestCase):
    def test_ok(self) -> None:
        self.assertEqual(normalize_action("approve"), "approve")
        self.assertEqual(normalize_action("resend"), "resend")

    def test_bad(self) -> None:
        with self.assertRaises(ValueError):
            normalize_action("nope")


if __name__ == "__main__":
    unittest.main()
