"""Companion-app action ids. Pure Python so tests do not import Home Assistant."""

from __future__ import annotations

# AR run once, AN later, AD deploy, AX dismiss. iOS action ids stay short.
KIND_RUN = "AR"
KIND_LATER = "AN"
KIND_DEPLOY = "AD"
KIND_DISMISS = "AX"


def encode_action(kind: str, suggestion_id: str) -> str:
    return f"{kind}_{suggestion_id}"


def parse_action(action: str | None) -> tuple[str, str] | None:
    if not action or "_" not in action:
        return None
    kind, _, suggestion_id = action.partition("_")
    if kind not in {KIND_RUN, KIND_LATER, KIND_DEPLOY, KIND_DISMISS}:
        return None
    if not suggestion_id:
        return None
    return kind, suggestion_id
