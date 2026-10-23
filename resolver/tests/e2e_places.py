#!/usr/bin/env python3
"""End-to-End-Test: Ortsauflösung in allen vier Kategorien über die UI.

Startet je Kategorie eine echte Suche über die API und prüft, dass
  * die Orte aufgelöst werden (IATA / Stadt / Hafen),
  * die Quellen mit den aufgelösten Werten laufen,
  * unbekannte Orte eine klare Meldung mit Vorschlägen liefern (ohne Quellenabfrage).

Aufruf: python3 resolver/tests/e2e_places.py [BASE_URL]
"""
from __future__ import annotations

import json
import sys
import time
import urllib.parse
import urllib.request

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8077").rstrip("/")
results: list[tuple[bool, str]] = []


def check(ok: bool, label: str, detail: str = "") -> None:
    results.append((bool(ok), label))
    print(f"  {'OK  ' if ok else 'FAIL'}  {label}" + (f"  [{detail}]" if detail else ""))


def search(params: dict, timeout_s: int = 240) -> dict:
    body = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(BASE + "/api/search", data=body, method="POST")
    with urllib.request.urlopen(req, timeout=30) as r:
        job_id = json.loads(r.read().decode())["job_id"]
    started = time.time()
    while time.time() - started < timeout_s:
        with urllib.request.urlopen(f"{BASE}/api/jobs/{job_id}", timeout=30) as r:
            snap = json.loads(r.read().decode())
        if snap.get("state") in ("done", "error"):
            return snap
        time.sleep(2)
    return snap


def cat(snap: dict, name: str) -> dict:
    return (snap.get("categories") or {}).get(name) or {}


def main() -> int:
    print("1) Flug: Toulouse (Stadtname)")
    snap = search({"origin": "BER", "destination": "Toulouse", "depart_date": "2026-11-05",
                   "return_date": "2026-11-08", "adults": "1", "currency": "EUR",
                   "categories": "flights", "timeout_seconds": "45"})
    f = cat(snap, "flights")
    res = (snap.get("resolved") or {}).get("flights") or {}
    d = res.get("destination") or {}
    check(d.get("code") == "TLS", "Ziel auf TLS aufgelöst", f"{d.get('input')} -> {d.get('code')}")
    check(f.get("state") == "done", "Kategorie gelaufen", f"{f.get('items')} Angebote")
    check(f.get("place_resolution") is not None, "Auflösung im Ergebnis enthalten")
    if f.get("items"):
        check((f.get("cheapest") or {}).get("price") is not None, "Preis vorhanden",
              str((f.get("cheapest") or {}).get("price")))

    print("\n2) Flug: frankfuhrt (Tippfehler)")
    snap = search({"origin": "frankfuhrt", "destination": "Rom", "depart_date": "2026-11-05",
                   "adults": "1", "currency": "EUR", "categories": "flights",
                   "timeout_seconds": "45"})
    res = (snap.get("resolved") or {}).get("flights") or {}
    o = res.get("origin") or {}
    check(o.get("code") == "FRA", "Tippfehler auf FRA korrigiert", f"{o.get('input')} -> {o.get('code')}")
    dd = res.get("destination") or {}
    check(dd.get("code") == "FCO", "„Rom“ auf FCO aufgelöst", f"{dd.get('input')} -> {dd.get('code')}")

    print("\n3) Flug: Xyzzy (unbekannt -> klare Meldung, keine Quellenabfrage)")
    snap = search({"origin": "Xyzzy", "destination": "Rom", "depart_date": "2026-11-05",
                   "adults": "1", "currency": "EUR", "categories": "flights",
                   "timeout_seconds": "45"})
    f = cat(snap, "flights")
    check(f.get("state") == "error", "Kategorie mit Fehler beendet")
    check("nicht gefunden" in (f.get("error") or ""), "Meldung nennt den Grund",
          (f.get("error") or "")[:70])
    check(f.get("providers") == [], "keine Quelle wurde abgefragt")
    # Die Oberfläche muss den Nutzer führen, auch wenn es keinen ähnlichen Ort gibt
    with urllib.request.urlopen(f"{BASE}/jobs/{snap['job_id']}", timeout=30) as r:
        page = r.read().decode()
    check("Ort nicht gefunden" in page and "Flughafenkürzel" in page,
          "UI zeigt Hinweis auf Kürzel/Vorschlagsliste")

    print("\n4) Hotel: Rom")
    snap = search({"origin": "BER", "destination": "Rom", "city": "Rom",
                   "depart_date": "2026-11-05", "return_date": "2026-11-08",
                   "adults": "2", "currency": "EUR", "categories": "hotels",
                   "timeout_seconds": "45"})
    h = cat(snap, "hotels")
    res = (snap.get("resolved") or {}).get("hotels") or {}
    d = res.get("destination") or {}
    check(d.get("kind") == "city", "Hotel-Ort als Stadt aufgelöst", str(d.get("name")))
    check(d.get("lat") is not None, "Koordinaten vorhanden", f"{d.get('lat')}, {d.get('lon')}")
    check(h.get("state") == "done" and h.get("items", 0) > 0, "Hotelangebote vorhanden",
          f"{h.get('items')}")

    print("\n5) Fähre: Barcelona -> Palma")
    snap = search({"origin": "Barcelona", "destination": "Palma",
                   "depart_date": "2026-11-05", "adults": "2", "currency": "EUR",
                   "categories": "ferries", "timeout_seconds": "45"})
    fe = cat(snap, "ferries")
    res = (snap.get("resolved") or {}).get("ferries") or {}
    check((res.get("origin") or {}).get("code") == "ESBCN", "Abfahrtshafen ESBCN",
          str((res.get("origin") or {}).get("name")))
    check((res.get("destination") or {}).get("code") == "ESPMI", "Zielhafen ESPMI",
          str((res.get("destination") or {}).get("name")))
    check(fe.get("state") == "done" and fe.get("items", 0) > 0, "Fährenangebote vorhanden",
          f"{fe.get('items')}")

    print("\n6) Kreuzfahrt: Miami")
    snap = search({"origin": "Miami", "destination": "", "depart_date": "2026-11-01",
                   "return_date": "2027-01-31", "adults": "2", "currency": "EUR",
                   "categories": "cruises", "timeout_seconds": "60"})
    c = cat(snap, "cruises")
    res = (snap.get("resolved") or {}).get("cruises") or {}
    o = res.get("origin") or {}
    check(o.get("code") == "MIA", "Hafen-Code MIA", f"{o.get('input')} -> {o.get('code')}")
    check(c.get("state") == "done", "Kreuzfahrt-Kategorie gelaufen", f"{c.get('items')} Angebote")

    passed = sum(1 for ok, _ in results if ok)
    print("\n" + "=" * 64)
    print(f"Ergebnis: {passed}/{len(results)} Prüfungen bestanden")
    for ok, label in results:
        if not ok:
            print("  FEHLGESCHLAGEN:", label)
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
