"""Tests for concise area · device display labels."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "custom_components"))

from automation_advisor.labels import (  # noqa: E402
    display_name_in_area,
    resolve_display_name,
    short_area_name,
)


class DisplayNameTests(unittest.TestCase):
    def test_short_area_name_trims_usage_suffix(self) -> None:
        self.assertEqual(short_area_name("어디서나 사용"), "어디서나")
        self.assertEqual(short_area_name("거실"), "거실")

    def test_motion_sensor_uses_device_not_romanized_slug(self) -> None:
        entry = SimpleNamespace(
            has_entity_name=True,
            original_name="움직임",
        )
        device = SimpleNamespace(name="동작감지 센서", name_by_user=None)
        label = resolve_display_name(
            "binary_sensor.eodiseona_sayong_dongjaggamji_senseo_motion",
            entry=entry,
            device=device,
            area_name="어디서나 사용",
        )
        self.assertEqual(label, "어디서나 · 동작감지 센서")
        self.assertNotIn("eodiseona", label)

    def test_light_uses_device_name_and_short_area(self) -> None:
        entry = SimpleNamespace(has_entity_name=True, original_name=None)
        device = SimpleNamespace(name="선반 조명", name_by_user=None)
        label = resolve_display_name(
            "light.eodiseona_sayong_seonban_jomyeong",
            entry=entry,
            device=device,
            area_name="어디서나 사용",
        )
        self.assertEqual(label, "어디서나 · 선반 조명")

    def test_ipcam_strips_configure_suffix(self) -> None:
        entry = SimpleNamespace(has_entity_name=True, original_name="움직임")
        device = SimpleNamespace(name="IPCam #1 (configure!)", name_by_user=None)
        label = resolve_display_name(
            "binary_sensor.geosil_ipcam_1_configure_motion",
            entry=entry,
            device=device,
            area_name="거실",
        )
        self.assertEqual(label, "거실 · IPCam #1")

    def test_display_name_in_area_drops_redundant_prefix(self) -> None:
        self.assertEqual(
            display_name_in_area("어디서나 · 선반 조명", "어디서나 사용"),
            "선반 조명",
        )


if __name__ == "__main__":
    unittest.main()
