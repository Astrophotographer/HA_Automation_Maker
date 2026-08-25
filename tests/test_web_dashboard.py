"""Tests for Lovelace web inbox dashboard config."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "custom_components" / "automation_advisor"))

from web_dashboard import LOGS_VIEW_PATH, VIEW_PATH, build_inbox_config


class WebDashboardTests(unittest.TestCase):
    def test_pending_has_run_and_dismiss_buttons(self) -> None:
        config = build_inbox_config(
            [
                {
                    "id": "abc12345",
                    "title": "조명 끄기",
                    "explanation": "테스트",
                }
            ]
        )
        blob = str(config)
        self.assertIn("automation_advisor.run_once", blob)
        self.assertIn("automation_advisor.later", blob)
        self.assertIn("automation_advisor.dismiss", blob)
        self.assertIn("abc12345", blob)
        self.assertIn("실행", blob)
        self.assertIn("나중에", blob)

    def test_previewed_has_deploy_button(self) -> None:
        config = build_inbox_config(
            [],
            [{"id": "def67890", "title": "자동화", "explanation": "ok"}],
        )
        blob = str(config)
        self.assertIn("automation_advisor.deploy", blob)
        self.assertIn("자동화", blob)
        self.assertIn("아니요", blob)
        self.assertNotIn("automation_advisor.later", blob)

    def test_logs_view_is_first_and_lists_events(self) -> None:
        ev = SimpleNamespace(
            ts=1_700_000_000.0,
            entity_id="light.entry",
            domain="light",
            old_state="off",
            new_state="on",
            actor="human_ui",
            area_id="entry",
            hour=12,
            weekday=0,
        )
        config = build_inbox_config(
            [],
            log_events=[ev],
            log_names={"light.entry": "현관 조명"},
            log_areas={"entry": "현관"},
            log_count=12,
            log_span_days=3.2,
        )
        self.assertEqual(config["views"][0]["path"], LOGS_VIEW_PATH)
        self.assertEqual(config["views"][1]["path"], VIEW_PATH)
        blob = str(config)
        self.assertIn("기기 로그", blob)
        self.assertIn("현관 조명", blob)
        self.assertIn("로그 분석 · 스캔", blob)
        self.assertIn("automation_advisor.scan", blob)


if __name__ == "__main__":
    unittest.main()
