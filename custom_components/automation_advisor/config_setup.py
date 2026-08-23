"""One-time Home Assistant configuration helpers."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from .const import AUTOMATIONS_FILENAME

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

INCLUDE_MARKER = "# automation-advisor-include"
INCLUDE_LINE = f"automation advisor: !include {AUTOMATIONS_FILENAME}"


def _patch_configuration_yaml(path: Path) -> bool:
    """Append the advisor include line if missing. Returns True when file changed."""
    if path.exists():
        text = path.read_text(encoding="utf-8")
        lowered = text.lower()
        if "automation_advisor.yaml" in lowered or "automation advisor:" in lowered:
            return False
        if not text.endswith("\n"):
            text += "\n"
        text += f"\n{INCLUDE_MARKER}\n{INCLUDE_LINE}\n"
        path.write_text(text, encoding="utf-8")
        return True

    path.write_text(
        "\n".join(
            [
                "default_config:",
                "",
                INCLUDE_MARKER,
                INCLUDE_LINE,
                "",
            ]
        ),
        encoding="utf-8",
    )
    return True


async def ensure_configuration_include(hass: HomeAssistant) -> bool:
    """Ensure configuration.yaml loads automation_advisor.yaml."""
    config_path = Path(hass.config.path("configuration.yaml"))
    return await hass.async_add_executor_job(_patch_configuration_yaml, config_path)
