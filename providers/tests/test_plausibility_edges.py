#!/usr/bin/env python3
"""Randfälle der Plausibilitätsprüfung.

Fall B: 3,50 EUR - über der Mindestgrenze, nicht in der Liste der typischen
        Fehlerwerte, aber weit unter dem Marktmedian => muss über die
        Verhältnisregel auffallen.
Fall C: die einzige Quelle liefert kaprupte Daten => es darf **keine**
        Preisauskunft geben (kein erfundener Ersatzpreis).
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

import yaml  # noqa: E402

sys.path.insert(0, HERE)
from test_implausible_price import build_registry  # noqa: E402
from fault_stub_server import serve  # noqa: E402


def run_case(name: str, price: float, only_stub: bool, port: int) -> dict:
    tmp = tempfile.mkdtemp(prefix="plaus2-")
    try:
        srv = serve(port, price, 27.99, not only_stub)
        time.sleep(0.8)
        reg_path = build_registry(tmp, port)
        # Stub-Szenario, keine oeffentliche Anzeige: Quellenrechte-Sperre aus.
        os.environ["RIGHTS_ENFORCE"] = "0"
        os.environ["TRVL_BREAKER_FILE"] = os.path.join(tmp, "breakers.json")
        os.environ["TRVL_CALLS_FILE"] = os.path.join(tmp, "last_call.json")
        out_path = os.path.join(tmp, "result.json")
        cmd = [sys.executable, os.path.join(ROOT, "providers", "runner.py"),
               "--registry", reg_path, "--category", "flights",
               "--origin", "BER", "--destination", "FCO",
               "--depart-date", "2026-10-31", "--adults", "1",
               "--currency", "EUR", "--max-stops", "one_stop",
               "--out", out_path]
        if only_stub:
            cmd += ["--only", "trvl_flights"]
        subprocess.run(cmd, capture_output=True, text=True, timeout=900)
        with open(out_path, encoding="utf-8") as fh:
            data = json.load(fh)
        stub = next((p for p in data["providers"] if p["source"] == "trvl_flights"), {})
        cheapest = data.get("cheapest")
        plaus = data.get("price_plausibility") or {}
        print(f"\n--- {name} (Stubpreis {price} EUR) ---")
        print(f"  Status der Quelle:   {stub.get('status')}")
        print(f"  Meldung:             {(stub.get('error') or '')[:150]}")
        print(f"  verworfen:           {plaus.get('rejected')}")
        print(f"  Marktmedian:         {plaus.get('market_median')} "
              f"(Quellen verglichen: {plaus.get('sources_compared')})")
        print(f"  günstigstes Angebot: "
              f"{(cheapest or {}).get('price')} {(cheapest or {}).get('currency')} "
              f"von {(cheapest or {}).get('source')}")
        print(f"  Gesamt-Meldung:      {(plaus.get('message') or '')[:160]}")
        return {"status": stub.get("status"), "cheapest": cheapest,
                "rejected": plaus.get("rejected"), "message": plaus.get("message")}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main() -> int:
    ok = True
    # Fall B: 3,50 EUR -> Verhältnisregel
    b = run_case("Fall B: auffällig, aber nicht extrem", 3.50, False, 8101)
    rejected_b = b["rejected"] or []
    ok_b = (b["status"] == "corrupt" and len(rejected_b) >= 1
            and "unplausibel" in (rejected_b[0].get("reason") or "").lower()
            and any(r.get("source") == "trvl_flights" for r in rejected_b))
    print(f"  -> {'BESTANDEN' if ok_b else 'FEHLGESCHLAGEN'} "
          f"(Regel: fachliche Untergrenze / Ausreisser)")
    ok = ok and ok_b

    # Fall C: einzige Quelle kaprupt -> keine Preisauskunft
    c = run_case("Fall C: einzige Quelle liefert kaprupte Daten", 0.01, True, 8102)
    ok_c = (c["status"] == "corrupt" and c["cheapest"] is None
            and "FEHLER" in (c["message"] or ""))
    print(f"  -> {'BESTANDEN' if ok_c else 'FEHLGESCHLAGEN'} "
          f"(keine Preisauskunft statt falschem Preis)")
    ok = ok and ok_c

    print("\nRandfälle geprüft:", "BESTANDEN" if ok else "FEHLGESCHLAGEN")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
