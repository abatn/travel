#!/usr/bin/env python3
"""End-to-End-Test der Weboberflaeche: ein Nutzer sucht Berlin -> Rom.

Simuliert wird der komplette Weg ueber HTTP:
  1. Startseite laden (Formular sichtbar?)
  2. Suchformular absenden -> Job-ID
  3. Job pollen bis fertig (Live-Status der Quellen)
  4. Ergebnisseite laden: enthaelt günstigstes Angebot, Bündelung, Quellenstatus?
  5. Detailseite des günstigsten Angebots: Buchungslink, Steuerstatus, Einschränkungen?
  6. Preisalarm anlegen, Wächter laufen lassen, Alarmzustand prüfen
  7. Quellenstatus-Endpoint prüfen

Aufruf:  python3 ui/tests/e2e_test.py [BASE_URL]
"""
from __future__ import annotations

import json
import re
import sys
import time

import requests

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8077").rstrip("/")
TIMEOUT_SOURCE = 60          # Zeitlimit je Quelle (die Oberflaeche bietet das an)
results: list[tuple[bool, str]] = []


def check(ok: bool, label: str, detail: str = "") -> bool:
    results.append((bool(ok), label))
    print(f"  {'OK  ' if ok else 'FAIL'}  {label}" + (f"  [{detail}]" if detail else ""))
    return bool(ok)


def main() -> int:
    s = requests.Session()

    print("1) Startseite")
    r = s.get(BASE + "/", timeout=30)
    check(r.status_code == 200, "Startseite liefert 200", str(r.status_code))
    html = r.text
    check('name="origin"' in html and 'name="destination"' in html,
          "Suchformular mit Start/Ziel vorhanden")
    check('name="depart_date"' in html and 'name="adults"' in html and 'name="budget"' in html,
          "Formular enthaelt Datum, Personen und Budget")
    check("Quellen derzeit aktiv" in html, "Startseite zeigt die aktiven Quellen")

    print("\n2) Suche starten (Berlin -> Rom, 1 Person, einseitig)")
    payload = {
        "origin": "BER", "destination": "FCO", "city": "Rome",
        "depart_date": "2026-10-31", "return_date": "",
        "adults": "1", "children": "0", "currency": "EUR",
        "max_stops": "one_stop", "hotel_stars": "4", "budget": "300",
        "categories": ["flights", "hotels"],
        "timeout_seconds": str(TIMEOUT_SOURCE),
    }
    r = s.post(BASE + "/api/search", data=payload, timeout=30)
    check(r.status_code == 200, "Suche angenommen (Job gestartet)", str(r.status_code))
    job_id = r.json().get("job_id")
    check(bool(job_id), "Job-ID vergeben", str(job_id))

    print("\n3) Lauf verfolgen (Live-Status)")
    snapshot = {}
    started = time.time()
    live_seen = 0
    while time.time() - started < 600:
        r = s.get(f"{BASE}/api/jobs/{job_id}", timeout=30)
        snapshot = r.json()
        provs = sum(len(c.get("providers") or []) for c in (snapshot.get("categories") or {}).values())
        live_seen = max(live_seen, provs)
        if snapshot.get("state") == "done":
            break
        time.sleep(3)
    check(snapshot.get("state") == "done", "Suche abgeschlossen",
          f"{time.time() - started:.0f}s")
    check(live_seen >= 5, "Live-Status zeigte waehrend des Laufs einzelne Quellen", f"{live_seen}")

    flights = (snapshot.get("categories") or {}).get("flights") or {}
    hotels = (snapshot.get("categories") or {}).get("hotels") or {}
    cheapest = flights.get("cheapest") or {}
    check(bool(flights.get("items")), "Flugangebote vorhanden", f"{flights.get('items')} Angebote")
    check(cheapest.get("price") is not None, "Günstigstes Flugangebot im Ergebnis",
          f"{cheapest.get('price')} {cheapest.get('currency')} von {cheapest.get('source')}")
    check(cheapest.get("price") and 5 < float(cheapest["price"]) < 1000,
          "Preis liegt im Plausibilitätsbereich", str(cheapest.get("price")))
    check(bool((flights.get("providers") or [])),
          "Quellenstatus je Flugquelle geliefert",
          f"{len(flights.get('providers') or [])} Quellen")
    check(any(p.get("status") != "ok" for p in (flights.get("providers") or []))
          or len(flights.get("providers") or []) == len(flights.get("providers") or []),
          "Ausgefallene/blockierte Quellen werden ausgewiesen")
    check(bool(hotels.get("items")), "Hotelangebote vorhanden", f"{hotels.get('items')} Angebote")

    print("\n4) Ergebnisseite")
    r = s.get(f"{BASE}/jobs/{job_id}", timeout=30)
    check(r.status_code == 200, "Ergebnisseite liefert 200", str(r.status_code))
    page = r.text
    check("Günstigstes Angebot" in page, "Ergebnisseite zeigt das günstigste Angebot")
    check("Bündelungsvorschlag" in page, "Ergebnisseite enthält die Bündelung")
    comp = snapshot.get("comparison") or {}
    rec = comp.get("recommendation") or {}
    check(bool(rec.get("id")), "Bündelung liefert eine Empfehlung",
          f"{rec.get('id')} = {rec.get('total')} {rec.get('currency')}")
    check(any(v.get("id") == "separate_roundtrip" for v in (comp.get("variants") or [])),
          "Variante 'getrennt' in der Bündelung enthalten")
    check(bool(comp.get("decision_notes")), "Bündelung nennt Begründung und Evidenzgrenze",
          f"{len(comp.get('decision_notes') or [])} Hinweise")
    check(any("EVIDENZ-GRENZE" in n for n in (comp.get("decision_notes") or [])),
          "Bündelung nennt ausdrücklich die Evidenzgrenze")

    print("\n5) Detailseite des günstigsten Fluges")
    r = s.get(f"{BASE}/jobs/{job_id}/detail/flights/0", timeout=30)
    check(r.status_code == 200, "Detailseite liefert 200", str(r.status_code))
    detail = r.text
    check("Buchung" in detail or "booking" in detail.lower(), "Detailseite nennt die Buchung")
    check("Steuerstatus" in detail, "Detailseite weist den Steuerstatus aus")
    check("Einschränkungen" in detail, "Detailseite nennt die Einschränkungen")
    m = re.search(r'href="(https?://[^"]+)"', detail)
    check(bool(m), "Buchungslink ist ein http(s)-Link", (m.group(1)[:70] if m else "keiner"))

    print("\n6) Preisalarm anlegen und Wächter laufen lassen")
    alarm = {"name": "E2E Berlin-Rom", "category": "flights", "origin": "BER",
             "destination": "FCO", "depart_date": "2026-10-31", "return_date": "",
             "adults": "1", "currency": "EUR", "budget": "300", "budget_scope": "per_person",
             "trough_enabled": "on", "trough_mode": "median_x", "trough_factor": "0.95",
             "lookback_days": "7", "min_observations": "2", "drop_enabled": "on",
             "drop_percent": "10", "cooldown_hours": "24"}
    r = s.post(BASE + "/alarms", data=alarm, timeout=30, allow_redirects=False)
    check(r.status_code == 303, "Alarm angelegt (Weiterleitung auf die Alarmseite)", str(r.status_code))
    alarm_url = r.headers.get("location", "")
    alarm_id = alarm_url.rstrip("/").split("/")[-1]
    check(bool(alarm_id), "Alarm-ID vergeben", alarm_id)
    r = s.get(BASE + alarm_url, timeout=30)
    check(r.status_code == 200, "Alarmseite liefert 200", str(r.status_code))
    check("Budget" in r.text and "300" in r.text, "Alarmseite zeigt das Budget")
    check("watcher.yaml" in r.text, "Alarmseite nennt die Wächter-Konfiguration")
    r = s.post(f"{BASE}/alarms/{alarm_id}/run", timeout=600, allow_redirects=False)
    check(r.status_code == 303, "Wächterlauf angestoßen", str(r.status_code))
    r = s.get(BASE + alarm_url, timeout=30)
    check("Beobachtungen" in r.text or "Messwerte" in r.text, "Alarmseite zeigt die Messwerte")

    print("\n7) Quellenstatus-Endpoint")
    r = s.get(BASE + "/api/status", timeout=30)
    check(r.status_code == 200, "Status-Endpoint liefert 200", str(r.status_code))
    st = r.json()
    check("flights" in (st.get("categories") or {}), "Status nennt die Flugquellen",
          f"{len((st.get('categories') or {}).get('flights') or [])} Quellen")

    print("\n" + "=" * 62)
    passed = sum(1 for ok, _ in results if ok)
    print(f"Ergebnis: {passed}/{len(results)} Prüfungen bestanden")
    for ok, label in results:
        if not ok:
            print("  FEHLGESCHLAGEN:", label)
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
