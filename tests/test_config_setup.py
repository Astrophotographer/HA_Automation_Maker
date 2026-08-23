"""Tests for config include helper."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from automation_advisor.config_setup import _patch_configuration_yaml, INCLUDE_LINE


class ConfigSetupTests(unittest.TestCase):
    def test_appends_include_when_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "configuration.yaml"
            path.write_text("default_config:\n", encoding="utf-8")
            changed = _patch_configuration_yaml(path)
            self.assertTrue(changed)
            text = path.read_text(encoding="utf-8")
            self.assertIn(INCLUDE_LINE, text)

    def test_skips_when_already_present(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "configuration.yaml"
            path.write_text(f"default_config:\n{INCLUDE_LINE}\n", encoding="utf-8")
            changed = _patch_configuration_yaml(path)
            self.assertFalse(changed)


if __name__ == "__main__":
    unittest.main()
