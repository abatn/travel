#!/usr/bin/env python3
"""Szenario-Test: eine Flug-API liefert 0,01 EUR (kaputte Daten).

Ablauf:
  1. Stub-Server starten, der die trvl-Antwortform mit einem 0,01-EUR-Tarif liefert.
  2. Temporäre Registry bauen: trvl_flights -> Stub, alle anderen Quellen bleiben live.
  3. Den echten Runner laufen lassen und prüfen, was passiert.

Erwartung (nach der Härtung):
  * der 0,01- EUR-Tarif erscheint NICHT im Ranking,
  * die Quelle wird als "korrupt" gemeldet (Plausibilitätsfehler im Protokoll),
  * der günstigste echte Preis kommt aus einer anderen Quelle.

Aufruf:  python3 providers/tests/test_implausible_price.py
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "providers"))

import yaml  # noqa: E402

PORT = int(os.environ.get("STUB_PORT", "8099"))
BROKEN_PRICE = 0.01


def build_registry(tmp: str, port: int = None) -> str:
    """Registry-Kopie: trvl_flights zeigt auf den Stub, der Rest bleibt live."""
    port = port or PORT
    with open(os.path.join(ROOT, "providers", "registry.yaml"), encoding="utf-8") as fh:
        reg = yaml.safe_load(fh)
    for p in reg["providers"]:
        if p["id"] == "trvl_flights":
            p["transport"] = "http"
            p["url"] = f"http://127.0.0.1:{port}/flights"
            p["method"] = "GET"
            p["params"] = {"origin": "{origin}", "destination": "{destination}",
                           "departure_date": "{depart_date}"}
            p["extract"] = {
                "items_path": "result.flights",
                "price": "price", "currency": "currency", "stops": "stops",
                "all_in": "all_in_cost", "provider": "provider", "legs": "legs",
                "warnings": "warnings", "booking_url": "booking_url",
            }
            p["note"] = "TEST-STUB: liefert absichtlich einen kaputten Preis von 0,01 EUR"
    path = os.path.join(tmp, "registry_stub.yaml")
    with open(path, "w", encoding="utf-8") as fh:
        yaml.safe_dump(reg, fh, allow_unicode=True, sort_keys=False)
    return path


def main() -> int:
    tmp = tempfile.mkdtemp(prefix="plaus-")
    try:
        # 1) Stub starten
        stub = subprocess.Popen(
            [sys.executable, os.path.join(HERE, "fault_stub_server.py"),
             "--port", str(PORT), "--price", str(BROKEN_PRICE),
             "--real-price", "27.99"],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        import time
        time.sleep(1.5)

        # 2) Registry mit Stub
        reg_path = build_registry(tmp, PORT)
        # Stub-Szenario, keine oeffentliche Anzeige: Quellenrechte-Sperre aus.
        os.environ["RIGHTS_ENFORCE"] = "0"
        os.environ["TRVL_BREAKER_FILE"] = os.path.join(tmp, "breakers.json")
        os.environ["TRVL_CALLS_FILE"] = os.path.join(tmp, "last_call.json")

        # 3) Runner laufen lassen
        out_path = os.path.join(tmp, "result.json")
        cmd = [sys.executable, os.path.join(ROOT, "providers", "runner.py"),
               "--registry", reg_path, "--category", "flights",
               "--origin", "BER", "--destination", "FCO",
               "--depart-date", "2026-10-31", "--adults", "1",
               "--currency", "EUR", "--max-stops", "one_stop",
               "--out", out_path]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
        print(f"Runner-Exitcode: {r.returncode}")
        if r.stderr.strip():
            print("stderr:", r.stderr.strip()[:300])

        with open(out_path, encoding="utf-8") as fh:
            data = json.load(fh)

        print("\n=== Provider-Status ===")
        for p in data["providers"]:
            print(f"  {p['source']:22s} {p['status']:10s} items={p['items']:>3} "
                  f"{(p.get('error') or '')[:110]}")

        print("\n=== Günstigstes Angebot laut Ranking ===")
        cheapest = data.get("cheapest")
        if cheapest:
            print(f"  {cheapest['price']} {cheapest['currency']} von {cheapest['source']} "
                  f"(Preisbasis {cheapest.get('price_scope')})")
        else:
            print("  keines")

        print("\n=== Preise je Quelle (Top 5) ===")
        for it in data.get("ranked", [])[:5]:
            print(f"  {it['price']:>8} {it['currency']} | {it['source']}")

        # Prüfungen
        prices = [it["price"] for it in data.get("ranked", [])]
        broken_in_ranking = any(abs(p - BROKEN_PRICE) < 0.005 for p in prices)
        stub_status = next((p for p in data["providers"] if p["source"] == "trvl_flights"), {})
        flagged = "plausib" in (stub_status.get("error") or "").lower() \
            or "korrupt" in (stub_status.get("error") or "").lower() \
            or stub_status.get("status") in ("error", "corrupt")

        print("\n=== Prüfung ===")
        print(f"  0,01 EUR im Ranking?           {'JA (FEHLER!)' if broken_in_ranking else 'nein (korrekt)'}")
        print(f"  Quelle als korrupt gemeldet?    {'ja' if flagged else 'nein (FEHLER!)'}")
        print(f"  Status der Quelle:              {stub_status.get('status')}")
        print(f"  Meldung:                        {(stub_status.get('error') or '')[:200]}")
        print(f"  günstigster echter Preis:        "
              f"{(cheapest or {}).get('price')} {(cheapest or {}).get('currency')} "
              f"von {(cheapest or {}).get('source')}")
        ok = (not broken_in_ranking) and flagged
        print(f"\n  {'TEST BESTANDEN' if ok else 'TEST FEHLGESCHLAGEN'}")
        return 0 if ok else 1
    finally:
        try:
            stub.terminate()
        except Exception:
            pass
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
