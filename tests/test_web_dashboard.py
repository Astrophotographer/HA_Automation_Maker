"""Tests for Lovelace web inbox dashboard config."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "custom_components" / "automation_advisor"))

from web_dashboard import build_inbox_config


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


if __name__ == "__main__":
    unittest.main()
