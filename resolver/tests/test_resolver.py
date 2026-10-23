#!/usr/bin/env python3
"""Tests des Orts-Resolvers (offline, ohne Netz).

Aufruf: python3 resolver/tests/test_resolver.py
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.dirname(HERE)
sys.path.insert(0, RES)

import resolver as places  # noqa: E402

results: list[tuple[bool, str]] = []


def check(ok: bool, label: str, detail: str = "") -> None:
    results.append((bool(ok), label))
    print(f"  {'OK  ' if ok else 'FAIL'}  {label}" + (f"  [{detail}]" if detail else ""))


def expect(text: str, category: str, code: str, label: str) -> None:
    r = places.resolve(text, category, use_cache=False)
    check(r.get("ok") is True and r.get("code") == code, label,
          f"{text} ({category}) -> {r.get('code')} / {r.get('name')}")


def main() -> int:
    print("1) Flüge")
    expect("Toulouse", "flights", "TLS", "Stadtname -> IATA")
    expect("frankfuhrt", "flights", "FRA", "Tippfehler -> FRA")
    expect("frank", "flights", "FRA", "Präfix -> Frankfurt (nicht Frank Pais)")
    expect("FCO", "flights", "FCO", "Kürzel direkt")
    expect("Barcleona", "flights", "BCN", "Tippfehler Barcelona -> BCN")

    print("\n2) Hotels (Stadt + Koordinaten)")
    r = places.resolve("Rom", "hotels", use_cache=False)
    check(r["ok"] and r["code"] == "FCO" and r["kind"] == "city", "„Rom“ -> Stadt Rom (FCO)")
    check(r.get("lat") and r.get("lon"), "Koordinaten vorhanden",
          f"{r.get('lat')}, {r.get('lon')}")
    expect("Wienn", "hotels", "VIE", "deutscher Tippfehler -> Wien")

    print("\n3) Fähren (Hafenname)")
    r = places.resolve("Palma", "ferries", use_cache=False)
    check(r["ok"] and r["code"] == "ESPMI", "Palma -> Palma de Mallorca (kein „Palmar Norte“)",
          f"{r.get('code')} {r.get('name')}")
    expect("Barcelona", "ferries", "ESBCN", "Barcelona -> ESBCN")

    print("\n4) Kreuzfahrten (3-stelliger Hafen-Code)")
    expect("Miami", "cruises", "MIA", "Miami -> MIA")
    expect("Hamburg", "cruises", "HAM", "Hamburg -> HAM")
    expect("Hamburg", "cruises", "HAM", "Hamburg erneut (Cache-Pfad)")

    print("\n5) Fehlerfälle")
    r = places.resolve("Xyzzy", "flights", use_cache=False)
    check(r["ok"] is False and r.get("code") is None, "Unbekanntes Wort -> ok=false")
    check(r.get("reason"), "Grund wird genannt", str(r.get("reason"))[:50])
    r = places.resolve("", "flights", use_cache=False)
    check(r["ok"] is False, "Leere Eingabe -> ok=false")

    print("\n6) Vorschläge (Autocomplete)")
    s = places.suggestions("toul", "flights", 5)
    check(any(x["code"] == "TLS" for x in s), "TLS in den Vorschlägen",
          ", ".join(x["code"] for x in s[:5]))
    s = places.suggestions("miam", "cruises", 5)
    check(any(x["code"] == "MIA" for x in s), "MIA in den Kreuzfahrt-Vorschlägen")

    print("\n7) Datenbestand")
    st = places.stats()
    check(st["airports"] > 8000, "Flughäfen geladen", str(st["airports"]))
    check(st["ports"] > 15000, "Häfen geladen", str(st["ports"]))
    check(st["aliases"] >= 100, "Alias-Tabelle geladen", str(st["aliases"]))

    passed = sum(1 for ok, _ in results if ok)
    print("\n" + "=" * 60)
    print(f"Ergebnis: {passed}/{len(results)} Prüfungen bestanden")
    for ok, label in results:
        if not ok:
            print("  FEHLGESCHLAGEN:", label)
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
