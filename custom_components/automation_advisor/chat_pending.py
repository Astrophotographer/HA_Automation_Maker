"""In-memory pending write tokens for confirm-gated chatbot actions."""

from __future__ import annotations

import secrets
import time
from dataclasses import dataclass
from typing import Any


@dataclass
class PendingWrite:
    token: str
    kind: str  # create | update | delete
    summary: str
    yaml_text: str
    automation: dict[str, Any] | None
    target_id: str | None
    created_at: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "token": self.token,
            "kind": self.kind,
            "summary": self.summary,
            "yaml": self.yaml_text,
            "target_id": self.target_id,
        }


class PendingStore:
    def __init__(self, *, ttl_seconds: float = 900.0) -> None:
        self._ttl = ttl_seconds
        self._items: dict[str, PendingWrite] = {}

    def _purge(self) -> None:
        now = time.time()
        expired = [k for k, v in self._items.items() if now - v.created_at > self._ttl]
        for key in expired:
            self._items.pop(key, None)

    def create(
        self,
        *,
        kind: str,
        summary: str,
        yaml_text: str = "",
        automation: dict[str, Any] | None = None,
        target_id: str | None = None,
    ) -> PendingWrite:
        self._purge()
        item = PendingWrite(
            token=secrets.token_urlsafe(16),
            kind=kind,
            summary=summary,
            yaml_text=yaml_text,
            automation=automation,
            target_id=target_id,
            created_at=time.time(),
        )
        self._items[item.token] = item
        return item

    def get(self, token: str) -> PendingWrite | None:
        self._purge()
        return self._items.get(token)

    def pop(self, token: str) -> PendingWrite | None:
        self._purge()
        return self._items.pop(token, None)
