#!/usr/bin/env python3
"""Vergleicht die beiden Historien-Ablagen des Wächters (JSONL vs. SQLite).

Beantwortet die Frage: **ab wie vielen Messpunkten lohnt sich die Datenbank?**
Gemessen wird derselbe Vorgang bei beiden Ablagen:
  * Anlegen eines Messpunkts (Schreiben)
  * Fensterabfrage der letzten 7 Tage mit Kategorie-Filter (Lesen - das ist der
    teure Schritt in der Regelauswertung)

Aufruf:
    python3 alerts/bench_history.py [--sizes 1000,10000,50000,200000] [--keep]
Ergebnis: eine Tabelle mit Zeit je Vorgang und der Schnittpunkt, ab dem SQLite
schneller ist.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from history_db import JsonlStore, SqliteStore  # noqa: E402


def build_records(n: int) -> list[dict]:
    """n synthetische Messpunkte (2 Kategorien, 60 Minuten Abstand)."""
    base = datetime.now(timezone.utc) - timedelta(minutes=60 * n)
    out = []
    for i in range(n):
        ts = (base + timedelta(minutes=60 * i)).isoformat(timespec="seconds")
        out.append({"ts": ts, "category": "flights" if i % 2 else "hotels",
                    "effective_price": 100.0 + (i % 97), "currency": "EUR",
                    "source": f"src_{i % 7}", "price": 100.0 + (i % 97),
                    "request": {"origin": "BER", "destination": "FCO"}})
    return out


def bench(store, records: list[dict], since: datetime, category: str) -> dict:
    """Schreiben (einzeln, wie der Wächter es tut), Lesen (Fensterabfrage)."""
    t0 = time.perf_counter()
    for rec in records:
        store.append(rec)
    t_write = time.perf_counter() - t0
    t0 = time.perf_counter()
    rows = store.read(since=since, category=category)
    t_read = time.perf_counter() - t0
    return {"write_s": round(t_write, 3), "read_s": round(t_read, 4),
            "rows": len(rows), "count": store.count()}


def bench_batch(store, records: list[dict], since: datetime, category: str) -> dict:
    """Sammelschreiben (nur SQLite bietet das an) + Fensterabfrage."""
    t0 = time.perf_counter()
    if hasattr(store, "append_many"):
        store.append_many(records)
    else:
        for rec in records:
            store.append(rec)
    t_write = time.perf_counter() - t0
    t0 = time.perf_counter()
    rows = store.read(since=since, category=category)
    t_read = time.perf_counter() - t0
    return {"write_s": round(t_write, 3), "read_s": round(t_read, 4),
            "rows": len(rows), "count": store.count()}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sizes", default="1000,10000,50000,200000")
    ap.add_argument("--keep", action="store_true", help="Dateien behalten")
    args = ap.parse_args()
    sizes = [int(x) for x in args.sizes.split(",") if x.strip()]

    tmp = tempfile.mkdtemp(prefix="hist-bench-")
    print(f"{'Punkte':>9} | {'JSONL schr.':>12} | {'JSONL lesen':>12} | "
          f"{'SQLite schr.':>13} | {'SQLite lesen':>13} | {'schneller (Lesen)':>18}")
    print("-" * 92)
    crossover = None
    for n in sizes:
        recs = build_records(n)
        since = datetime.now(timezone.utc) - timedelta(days=7)
        j = JsonlStore(os.path.join(tmp, f"h_{n}.jsonl"))
        q = SqliteStore(os.path.join(tmp, f"h_{n}.db"))
        bj = bench(j, recs, since, "flights")
        bq = bench(q, recs, since, "flights")
        winner = "SQLite" if bq["read_s"] < bj["read_s"] else "JSONL"
        if crossover is None and winner == "SQLite":
            crossover = n
        print(f"{n:>9} | {bj['write_s']:>11.3f}s | {bj['read_s']:>11.4f}s | "
              f"{bq['write_s']:>12.3f}s | {bq['read_s']:>12.4f}s | {winner:>18}")
        q.close()
    print("-" * 92)
    print("Hinweis: 'schreiben' = einzelne Messpunkte (wie der Wächter im Betrieb),")
    print("        'lesen' = Fensterabfrage 7 Tage mit Kategorie-Filter (der teure Schritt).")
    if crossover:
        print(f"Schnittpunkt: ab {crossover} Beobachtungen ist die Datenbank schneller "
              f"(7-Tage-Fenster mit Kategorie-Filter).")
    else:
        print("Kein Schnittpunkt im gemessenen Bereich: JSONL ist in allen Größen schneller.")
    print(f"Stündliche Messung (24/Tag, 1 Kategorie) erreicht {365 * 24} Punkte/Jahr, "
          f"minütliche {365 * 24 * 60} Punkte/Jahr - das entscheidet die Wahl.")
    if not args.keep:
        shutil.rmtree(tmp, ignore_errors=True)
    else:
        print(f"Dateien in {tmp}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
