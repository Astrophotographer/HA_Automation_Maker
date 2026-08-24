"""Local SQLite event log. No GPS, no camera, no Home Assistant import."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path


@dataclass(frozen=True)
class StoredEvent:
    ts: float
    entity_id: str
    domain: str
    old_state: str | None
    new_state: str
    actor: str
    area_id: str | None
    hour: int
    weekday: int


class EventStore:
    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts REAL NOT NULL,
                    entity_id TEXT NOT NULL,
                    domain TEXT NOT NULL,
                    old_state TEXT,
                    new_state TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    area_id TEXT,
                    hour INTEGER NOT NULL,
                    weekday INTEGER NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_events_entity ON events(entity_id, ts)"
            )
            conn.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS idx_events_dedup
                ON events(entity_id, ts, COALESCE(old_state, ''), new_state)
                """
            )
            conn.commit()

    def _insert_row(
        self,
        conn: sqlite3.Connection,
        *,
        ts: float,
        entity_id: str,
        domain: str,
        old_state: str | None,
        new_state: str,
        actor: str,
        area_id: str | None,
        hour: int,
        weekday: int,
        ignore_duplicates: bool,
    ) -> bool:
        sql = (
            "INSERT OR IGNORE INTO events"
            if ignore_duplicates
            else "INSERT INTO events"
        )
        cur = conn.execute(
            f"""
            {sql}
            (ts, entity_id, domain, old_state, new_state, actor, area_id, hour, weekday)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                ts,
                entity_id,
                domain,
                old_state,
                new_state,
                actor,
                area_id,
                hour,
                weekday,
            ),
        )
        return cur.rowcount > 0

    def insert(
        self,
        *,
        ts: float | None = None,
        entity_id: str,
        domain: str,
        old_state: str | None,
        new_state: str,
        actor: str,
        area_id: str | None = None,
    ) -> None:
        when = datetime.fromtimestamp(
            ts or datetime.now(timezone.utc).timestamp(), tz=timezone.utc
        )
        with self._connect() as conn:
            self._insert_row(
                conn,
                ts=when.timestamp(),
                entity_id=entity_id,
                domain=domain,
                old_state=old_state,
                new_state=new_state,
                actor=actor,
                area_id=area_id,
                hour=when.hour,
                weekday=when.weekday(),
                ignore_duplicates=False,
            )
            conn.commit()

    def insert_if_new(
        self,
        *,
        ts: float,
        entity_id: str,
        domain: str,
        old_state: str | None,
        new_state: str,
        actor: str,
        area_id: str | None = None,
    ) -> bool:
        when = datetime.fromtimestamp(ts, tz=timezone.utc)
        with self._connect() as conn:
            inserted = self._insert_row(
                conn,
                ts=when.timestamp(),
                entity_id=entity_id,
                domain=domain,
                old_state=old_state,
                new_state=new_state,
                actor=actor,
                area_id=area_id,
                hour=when.hour,
                weekday=when.weekday(),
                ignore_duplicates=True,
            )
            conn.commit()
            return inserted

    def purge_older_than(self, days: int) -> int:
        cutoff = datetime.now(timezone.utc).timestamp() - days * 86400
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM events WHERE ts < ?", (cutoff,))
            conn.commit()
            return cur.rowcount

    def clear(self) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM events")
            conn.commit()

    def count(self) -> int:
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) AS c FROM events").fetchone()
            return int(row["c"] if row else 0)

    def max_ts(self) -> float | None:
        with self._connect() as conn:
            row = conn.execute("SELECT MAX(ts) AS mx FROM events").fetchone()
        if not row or row["mx"] is None:
            return None
        return float(row["mx"])

    def span_days(self) -> float:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT MIN(ts) AS mn, MAX(ts) AS mx FROM events"
            ).fetchone()
        if not row or row["mn"] is None or row["mx"] is None:
            return 0.0
        return max(0.0, (float(row["mx"]) - float(row["mn"])) / 86400.0)

    def fetch_since(self, days: int) -> list[StoredEvent]:
        cutoff = datetime.now(timezone.utc).timestamp() - days * 86400
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT ts, entity_id, domain, old_state, new_state, actor, area_id, hour, weekday
                FROM events
                WHERE ts >= ?
                ORDER BY ts ASC
                """,
                (cutoff,),
            ).fetchall()
        return [
            StoredEvent(
                ts=float(r["ts"]),
                entity_id=r["entity_id"],
                domain=r["domain"],
                old_state=r["old_state"],
                new_state=r["new_state"],
                actor=r["actor"],
                area_id=r["area_id"],
                hour=int(r["hour"]),
                weekday=int(r["weekday"]),
            )
            for r in rows
        ]
