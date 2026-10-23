#!/usr/bin/env python3
"""Integrationstest: korrupte Quelle -> Runner meldet sie, Bündelung weist sie aus.

Prüft die ganze Kette: Stub-Quelle (0,01 EUR) -> Runner -> Bündelungsvergleich.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "providers"))
sys.path.insert(0, HERE)

from test_implausible_price import build_registry  # noqa: E402
from fault_stub_server import serve  # noqa: E402

PORT = 8103


def main() -> int:
    tmp = tempfile.mkdtemp(prefix="plaus3-")
    try:
        srv = serve(PORT, 0.01, 27.99, True)
        time.sleep(0.8)
        reg_path = build_registry(tmp, PORT)
        env = dict(os.environ)
        env["TRVL_BREAKER_FILE"] = os.path.join(tmp, "breakers.json")
        env["TRVL_CALLS_FILE"] = os.path.join(tmp, "last_call.json")

        flights = os.path.join(tmp, "flights.json")
        subprocess.run([sys.executable, os.path.join(ROOT, "providers", "runner.py"),
                        "--registry", reg_path, "--category", "flights",
                        "--origin", "BER", "--destination", "FCO",
                        "--depart-date", "2026-10-31", "--adults", "1",
                        "--currency", "EUR", "--max-stops", "one_stop",
                        "--out", flights], capture_output=True, text=True,
                       timeout=900, env=env)

        out = os.path.join(tmp, "cmp.json")
        subprocess.run([sys.executable, os.path.join(ROOT, "bundling", "compare.py"),
                        "--flights", flights, "--adults", "1", "--nights", "2",
                        "--currency", "EUR", "--out", out],
                       capture_output=True, text=True, timeout=600, env=env)

        with open(out, encoding="utf-8") as fh:
            d = json.load(fh)
        dq = d.get("data_quality") or {}
        print("Bündelung - Datenqualität:")
        print("  korrupte Quellen:", dq.get("corrupt_sources"))
        print("  Meldungen:")
        for n in (dq.get("notes") or []):
            print("   ", n[:220])
        rec = d.get("recommendation") or {}
        print("  Empfehlung:", rec.get("id"), rec.get("total"), rec.get("currency"))
        print("  Varianten:", [(v.get("id"), v.get("total")) for v in (d.get("variants") or [])])

        totals = [v.get("total") for v in (d.get("variants") or [])]
        ok = ("flights/trvl_flights" in (dq.get("corrupt_sources") or [])
              and any("FEHLER" in n for n in (dq.get("notes") or []))
              and not any(t is not None and abs(float(t) - 0.01) < 0.005 for t in totals)
              and all(t != 0.01 for t in totals))
        print(f"\n  {'INTEGRATIONSTEST BESTANDEN' if ok else 'FEHLGESCHLAGEN'}")
        return 0 if ok else 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
