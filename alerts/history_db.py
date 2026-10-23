#!/usr/bin/env python3
"""Beobachtungshistorie des Wächters - zwei austauschbare Ablagen.

* **jsonl** (Standard): eine JSON-Zeile je Beobachtung. Einfach zu lesen und zu
  prüfen, aber bei sehr vielen Punkten wächst die Datei linear mit.
* **sqlite** (optional): Tabelle mit Index auf (Kategorie, Zeitpunkt). Die
  Fensterabfrage läuft in der Datenbank statt im Arbeitsspeicher.

Beide Ablagen bieten dieselbe Schnittstelle (`append`, `read`, `count`, `prune`),
sodass Wächter, Regelauswertung und `--report` unverändert bleiben.

Welche Ablage schneller ist, hängt von der Messpunktzahl ab - der Vergleich
steht in `alerts/bench_history.py` (Ergebnis: bei stündlicher Messung gewinnt
JSONL deutlich, ab minütlicher Messung dreht sich das Bild).
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
from datetime import datetime, timezone

_TS_RE = re.compile(r'"ts"\s*:\s*"(\d{4}-\d{2}-\d{2})')

SCHEMA = """
CREATE TABLE IF NOT EXISTS observations (
    ts            TEXT NOT NULL,
    category      TEXT NOT NULL,
    effective_price REAL,
    currency      TEXT,
    source        TEXT,
    payload       TEXT NOT NULL,
    PRIMARY KEY (category, ts)
);
CREATE INDEX IF NOT EXISTS idx_obs_cat_ts ON observations(category, ts);
"""


class JsonlStore:
    """Ablage als JSONL (Standard)."""

    backend = "jsonl"

    def __init__(self, path: str):
        self.path = path

    def append(self, record: dict) -> None:
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")

    def read(self, since: datetime | None = None, category: str | None = None) -> list[dict]:
        if not os.path.exists(self.path):
            return []
        out: list[dict] = []
        since_date = since.date().isoformat() if since is not None else None
        with open(self.path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                if since_date is not None:
                    m = _TS_RE.search(line)
                    if m and m.group(1) < since_date:
                        continue        # grober Vorfilter: nicht parsen
                try:
                    rec = json.loads(line)
                except Exception:
                    continue
                if since is not None:
                    try:
                        ts = datetime.fromisoformat(str(rec.get("ts", "")))
                    except Exception:
                        continue
                    if ts < since:
                        continue
                if category and rec.get("category") != category:
                    continue
                out.append(rec)
        return out

    def count(self) -> int:
        if not os.path.exists(self.path):
            return 0
        with open(self.path, encoding="utf-8") as fh:
            return sum(1 for ln in fh if ln.strip())

    def prune(self, keep: int) -> int:
        """Ringpuffer: nur die letzten `keep` Einträge behalten."""
        if keep <= 0 or not os.path.exists(self.path):
            return 0
        with open(self.path, encoding="utf-8") as fh:
            lines = [ln for ln in fh if ln.strip()]
        if len(lines) <= keep:
            return 0
        with open(self.path, "w", encoding="utf-8") as fh:
            fh.writelines(lines[-keep:])
        return len(lines) - keep


class SqliteStore:
    """Ablage in SQLite mit Index auf (Kategorie, Zeitpunkt)."""

    backend = "sqlite"

    def __init__(self, path: str):
        self.path = path
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self._con = sqlite3.connect(path, timeout=10)
        self._con.execute("PRAGMA journal_mode=WAL")
        self._con.execute("PRAGMA synchronous=NORMAL")
        self._con.executescript(SCHEMA)
        self._con.commit()

    def close(self) -> None:
        try:
            self._con.close()
        except Exception:
            pass

    def append(self, record: dict) -> None:
        ts = str(record.get("ts") or datetime.now(timezone.utc).isoformat(timespec="seconds"))
        self._con.execute(
            "INSERT OR REPLACE INTO observations "
            "(ts, category, effective_price, currency, source, payload) "
            "VALUES (?,?,?,?,?,?)",
            (ts, str(record.get("category", "default")),
             record.get("effective_price"), record.get("currency"),
             record.get("source"), json.dumps(record, ensure_ascii=False)))
        self._con.commit()

    def append_many(self, records: list[dict]) -> None:
        """Sammel-Schreibvorgang (eine Transaktion statt einer je Zeile)."""
        rows = []
        for record in records:
            ts = str(record.get("ts") or datetime.now(timezone.utc).isoformat(timespec="seconds"))
            rows.append((ts, str(record.get("category", "default")),
                         record.get("effective_price"), record.get("currency"),
                         record.get("source"), json.dumps(record, ensure_ascii=False)))
        self._con.executemany(
            "INSERT OR REPLACE INTO observations "
            "(ts, category, effective_price, currency, source, payload) "
            "VALUES (?,?,?,?,?,?)", rows)
        self._con.commit()

    def read(self, since: datetime | None = None, category: str | None = None) -> list[dict]:
        sql = "SELECT payload FROM observations"
        params: list = []
        where = []
        if since is not None:
            where.append("ts >= ?")
            params.append(since.isoformat())
        if category:
            where.append("category = ?")
            params.append(category)
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY ts"
        rows = self._con.execute(sql, params).fetchall()
        out = []
        for (payload,) in rows:
            try:
                out.append(json.loads(payload))
            except Exception:
                continue
        return out

    def count(self) -> int:
        return int(self._con.execute("SELECT COUNT(*) FROM observations").fetchone()[0])

    def prune(self, keep: int) -> int:
        """Nur die jüngsten `keep` Beobachtungen behalten."""
        if keep <= 0:
            return 0
        total = int(self._con.execute("SELECT COUNT(*) FROM observations").fetchone()[0])
        if total <= keep:
            return 0
        self._con.execute(
            "DELETE FROM observations WHERE rowid NOT IN "
            "(SELECT rowid FROM observations ORDER BY ts DESC LIMIT ?)", (keep,))
        self._con.commit()
        return total - keep


def make_store(backend: str, path: str, db_path: str | None = None) -> JsonlStore | SqliteStore:
    """Ablage nach Konfiguration wählen."""
    if str(backend).lower() in ("sqlite", "sqlite3", "db") and db_path:
        return SqliteStore(db_path)
    return JsonlStore(path)
