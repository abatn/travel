#!/usr/bin/env python3
"""Intelligente Kombination: Paket vs. getrennte Buchung vs. Einweg-Gabelflug.

Der Vergleich rechnet aus einer einheitlichen Eingabe (Ergebnis des Provider-Runners
plus optional ein Pauschalpreis aus einer Paketquelle) die drei Varianten und schlägt
die günstigste mit Begründung vor. Die Begründung stützt sich auf Belege aus
`bundling/evidence.json` (TRIZ-Recherche), nicht auf Annahmen.

Aufruf:
    python3 bundling/compare.py --flights flights.json --hotels hotels.json \\
        --oneways oneway_out.json,oneway_in.json --package package.json \\
        --adults 2 --nights 6 --out vergleich.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any

HERE = os.path.dirname(os.path.abspath(__file__))
EVIDENCE_PATH = os.path.join(HERE, "evidence.json")
SHIP_CONDITIONS_PATH = os.path.join(HERE, "ship_conditions.json")


def load_json(path: str | None) -> Any:
    if not path or not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def cheapest(result: dict | None) -> dict | None:
    """Günstigstes Angebot aus einem Runner-Ergebnis (Endpreis bevorzugt, wenn vorhanden)."""
    if not result:
        return None
    items = result.get("ranked") or []
    if not items:
        return None
    return items[0]


def price_of(item: dict | None, prefer_all_in: bool = True) -> float | None:
    if not item:
        return None
    if prefer_all_in and item.get("all_in") is not None:
        return float(item["all_in"])
    return float(item["price"]) if item.get("price") is not None else None


def load_ship_conditions() -> list[dict]:
    data = load_json(SHIP_CONDITIONS_PATH) or {}
    return data.get("conditions", []) if isinstance(data, dict) else []


def party_total(item: dict | None, adults: int, prefer_all_in: bool = False) -> float | None:
    """Gesamtpreis fuer die ganze Reisegruppe - Scope korrekt behandelt.

    prefer_all_in=True (Kreuzfahrten): der Endpreis inkl. Steuern ist das, was
    tatsaechlich gezahlt wird - er wird je Person multipliziert.
    """
    if not item:
        return None
    scope = item.get("price_scope") or "per_person"
    if prefer_all_in and item.get("all_in") is not None:
        per_person = float(item["all_in"])
        return per_person * adults if scope in ("per_person", "per_night") else per_person
    total = item.get("price_total")
    if total is None:
        base = item.get("price")
        if base is None:
            return None
        total = base * adults if scope in ("per_person", "per_night") else base
    return float(total)


def load_evidence() -> list[dict]:
    data = load_json(EVIDENCE_PATH) or {}
    return data.get("evidence", []) if isinstance(data, dict) else []


def evidence_for(topic: str, evidence: list[dict]) -> list[dict]:
    out = []
    for ev in evidence:
        if topic in (ev.get("supports") or []):
            out.append({"id": ev.get("id"), "claim": ev.get("claim"),
                        "strength": ev.get("strength"), "quote": ev.get("quote"),
                        "source": f"{ev.get('source_publisher')} ({ev.get('source_date')})",
                        "url": ev.get("source_url")})
    return out


def data_quality(results: list[tuple[str, dict | None]]) -> dict:
    """Datenqualitaet aller Quellen: Ausfaelle, korrupte Antworten, unplausible Preise.

    results: Liste aus (Kategorie, Runner-Ergebnis)
    """
    notes: list[str] = []
    corrupt: list[str] = []
    unavailable: list[str] = []
    for category, res in results:
        if not isinstance(res, dict):
            continue
        plaus = res.get("price_plausibility") or {}
        msg = plaus.get("message")
        if msg:
            notes.append(msg)
        for src in (plaus.get("corrupt_sources") or []):
            corrupt.append(f"{category}/{src}")
        for p in (res.get("providers") or []):
            status = str(p.get("status") or "")
            if status in ("ok", ""):
                continue
            # Nur strukturierte Angaben: die UI übersetzt Status und Quelle.
            # Der rohe Fehlertext bleibt im Runner-Log (und im API-Snapshot).
            unavailable.append({
                "category": category,
                "source": p.get("source"),
                "status": status,
            })
    return {"corrupt_sources": corrupt,
            "unavailable_sources": unavailable,
            "notes": notes,
            "clean": not corrupt}


def compare(flights: dict | None, hotels: dict | None, oneways: list[dict] | None,
             package: dict | None, adults: int, nights: int,
             currency: str = "EUR", cruises: dict | None = None,
             ferries: dict | None = None, fx_path: str | None = None) -> dict:
    ev = load_evidence()
    fl_item = cheapest(flights)
    ho_item = cheapest(hotels)
    fl_price = price_of(fl_item)
    ho_price = price_of(ho_item)

    variants: list[dict] = []

    # (1) Rundflug + Hotel getrennt
    if fl_price is not None and ho_price is not None:
        total = fl_price * adults + ho_price * nights
        variants.append({
            "id": "separate_roundtrip",
            "label": "Hin-/Rückflug zusammen + Hotel getrennt",
            "flight_total": round(fl_price * adults, 2),
            "hotel_total": round(ho_price * nights, 2),
            "total": round(total, 2),
            "currency": currency,
            "components": {"flight": fl_item.get("name") or fl_item.get("provider"),
                           "hotel": ho_item.get("name")},
            "risks": ["Hin- und Rückflug sind ein Ticket – Umbuchung wirkt nur auf den Rückflug",
                       "Hotel und Flug sind unabhängig voneinander stornierbar (vorteilhaft)"],
        })

    # (2) Gabelflug (zwei getrennte Einwegtickets) + Hotel
    if oneways:
        out_item = cheapest(oneways[0]) if len(oneways) > 0 else None
        in_item = cheapest(oneways[1]) if len(oneways) > 1 else None
        p_out, p_in = price_of(out_item), price_of(in_item)
        if p_out is not None and p_in is not None and ho_price is not None:
            total = (p_out + p_in) * adults + ho_price * nights
            variants.append({
                "id": "split_roundtrip",
                "label": "Gabelflug (zwei Einwegtickets, ggf. verschiedene Airlines) + Hotel",
                "flight_total": round((p_out + p_in) * adults, 2),
                "hotel_total": round(ho_price * nights, 2),
                "total": round(total, 2),
                "currency": currency,
                "components": {"outbound": out_item.get("name") or out_item.get("provider"),
                               "inbound": in_item.get("name") or in_item.get("provider"),
                               "hotel": ho_item.get("name")},
                "risks": ["Zwei getrennte Tickets: kein Anspruch auf Anschluss bei Verspätung",
                          "Gepäck muss in beiden Teilen neu eingecheckt werden",
                          "Hotel und Flug unabhängig stornierbar"],
            })

    # (2b) Schiffsreisen: Kreuzfahrt allein / Kreuzfahrt + Flug / Flug + Faehre + Hotel
    ship_notes: list[str] = []
    cr_item = cheapest(cruises)
    fe_item = cheapest(ferries)
    cr_total = party_total(cr_item, adults, prefer_all_in=True)
    fe_total = party_total(fe_item, adults)
    cr_all_in = (cr_item or {}).get("all_in")
    fe_scope = (fe_item or {}).get("price_scope")
    conditions = load_ship_conditions()

    if cr_total is not None and adults >= 2:
        variants.append({
            "id": "cruise_only",
            "label": "Kreuzfahrt allein (Kabine + Naechte an Bord)",
            "flight_total": 0.0,
            "hotel_total": 0.0,
            "total": round(cr_total, 2),
            "currency": (cr_item or {}).get("currency") or currency,
            "components": {"cruise": (cr_item or {}).get("name") or (cr_item or {}).get("provider"),
                           "source": (cr_item or {}).get("source")},
            "conditions": [c["id"] for c in conditions if c.get("scope") == "cruise"],
            "booking_terms": _booking_terms(cr_item),
            "risks": ["Kabinenpreis - Hafengebuehren, Trinkgelder und Ausfluege koennen zusaetzlich anfallen",
                       "Storno-/Umbuchungsbedingungen sind strenger als bei Einzeltickets",
                       "Angebote meist erst ab zwei Personen"],
        })
        ship_notes.append("Kreuzfahrtvariante: Naechte sind im Preis enthalten, deshalb wird fuer die "
                          "Reise kein Hotel gerechnet (S1).")
    elif cr_total is not None:
        ship_notes.append("Kreuzfahrtpreis nur fuer 1 Person - Vergleich mit Pauschale/Flug+Hotel "
                          "aufgrund der Mindestbelegung nicht aussagekraeftig (S4).")

    if cr_total is not None and fl_price is not None and adults >= 2:
        variants.append({
            "id": "cruise_plus_flight",
            "label": "Anreise zum Abfahrtshafen (Flug) + Kreuzfahrt",
            "flight_total": round(fl_price * adults, 2),
            "hotel_total": 0.0,
            "total": round(cr_total + fl_price * adults, 2),
            "currency": currency,
            "components": {"flight": fl_item.get("name") or fl_item.get("provider"),
                           "cruise": (cr_item or {}).get("name")},
            "conditions": [c["id"] for c in conditions if c.get("scope") == "cruise"],
            "risks": ["Flug und Kreuzfahrt sind zwei getrennte Buchungen - kein Anschlussschutz",
                       "Kabinenpreis ohne Hafengebuehren/Trinkgelder/Ausfluege"],
        })

    if fl_price is not None and fe_total is not None and ho_price is not None:
        variants.append({
            "id": "flight_ferry_hotel",
            "label": "Flug + Faehre als Zubringer + Hotel am Inselziel",
            "flight_total": round(fl_price * adults, 2),
            "hotel_total": round(ho_price * nights, 2),
            "total": round(fl_price * adults + fe_total + ho_price * nights, 2),
            "currency": currency,
            "components": {"flight": fl_item.get("name") or fl_item.get("provider"),
                           "ferry": (fe_item or {}).get("name") or (fe_item or {}).get("provider"),
                           "ferry_scope": fe_scope,
                           "hotel": ho_item.get("name")},
            "conditions": [c["id"] for c in conditions if c.get("scope") == "ferry"],
            "risks": ["Faehre ist ein eigenes Ticket - Zeitplan und Gepaeck muessen passen",
                       "Bei Fahrzeugtarif deckt der Preis die ganze Gruppe (nicht nochmal multipliziert)"],
        })
        ship_notes.append("Faehren-Variante: die Faehre ersetzt eine Flugstrecke, nicht das Hotel (S7); "
                          "der Preis-Scope der Quelle entscheidet ueber die Multiplikation (S6).")

    # (3) Pauschale (falls eine Paketquelle konfiguriert ist)
    pkg_total = None
    if package:
        pkg = package.get("total") if isinstance(package, dict) else None
        if pkg is None and isinstance(package, dict):
            pkg = price_of(package.get("cheapest"))
        if pkg is not None:
            pkg_total = float(pkg)
            variants.append({
                "id": "package",
                "label": "Pauschale (Flug + Hotel gebündelt)",
                "total": round(pkg_total, 2),
                "currency": package.get("currency", currency) if isinstance(package, dict) else currency,
                "components": {"source": package.get("source", "Paketquelle")},
                "risks": ["Änderung nur des Flug- oder Hotelteils oft gegen Aufpreis",
                          "Pauschalpreis kann Steuern/Gebühren anders ausweisen als Einzelbuchung"],
            })

    # Waehrungen angleichen (nur mit belegtem Kurs), sonst Kennzeichnung
    fx_notes: list[str] = []
    rates = load_fx_rates(fx_path)
    for v in variants:
        if v.get("currency") and v["currency"].upper() != currency.upper():
            conv, note = to_currency(v.get("total"), v.get("currency"), currency, rates)
            if conv is not None:
                v["total_original"] = v["total"]
                v["currency_original"] = v.get("currency")
                v["total"] = round(conv, 2)
                v["currency"] = currency
                v["fx_note"] = note
            else:
                v["currency_comparable"] = False
                v["fx_note"] = note
                fx_notes.append(f"{v['id']}: {note}")
    variants.sort(key=lambda v: v["total"])
    recommendation = variants[0] if variants else None
    # "Knappster statt billigster": guenstigster Preis je Person und Nacht
    for v in variants:
        denom = max(1, adults * max(1, nights))
        v["price_per_person_night"] = round(v["total"] / denom, 2)
    best_value = min(variants, key=lambda v: v["price_per_person_night"]) if variants else None
    if fx_notes:
        fx_notes.insert(0, "Achtung: nicht alle Varianten sind in derselben Waehrung - "
                            "der Vergleich ist nur eine Groessenordnung.")
    gaps = [v for v in variants[1:]]
    savings = [round(v["total"] - recommendation["total"], 2) for v in gaps] if recommendation else []

    return {
        "generated_at": __import__("time").strftime("%Y-%m-%dT%H:%M:%S%z"),
        "input": {"adults": adults, "nights": nights, "currency": currency},
        "data_quality": data_quality([
            ("flights", flights), ("hotels", hotels),
            ("oneway_out", (oneways or [None, None])[0] if oneways else None),
            ("oneway_in", (oneways or [None, None])[1] if oneways and len(oneways) > 1 else None),
            ("package", package), ("cruises", cruises), ("ferries", ferries),
        ]),
        "variants": variants,
        "recommendation": recommendation,
        "best_value": best_value,
        "best_value_note": ("Guenstigste Variante je Person und Nacht (Preis-Leistungs-Vergleich); "
                            "die Empfehlung darueber ist die guenstigste GESAMTSUMME."),
        "savings_vs_alternatives": savings,
        "evidence": {
            "split_roundtrip": evidence_for("separate_roundtrip", ev),
            "mixed_airlines": evidence_for("mixed_airlines", ev),
            "flight_plus_hotel": evidence_for("flight_plus_hotel", ev),
            "counter_evidence": (load_json(EVIDENCE_PATH) or {}).get("counter_evidence", []),
            "loaded": bool(ev),
        },
        "decision_notes": _notes(recommendation, gaps, ev) + ship_notes + fx_notes,
        "currency": {"target": currency, "rates_loaded": bool(rates),
                     "rates": {k: v.get("source") for k, v in rates.items()}},
        "ship_conditions": conditions,
        "ship_context": {
            "cruise": {"available": cr_item is not None,
                       "price_total": round(cr_total, 2) if cr_total else None,
                       "all_in": cr_all_in, "source": (cr_item or {}).get("source"),
                       "currency": (cr_item or {}).get("currency"),
                       "booking_terms": _booking_terms(cr_item)},
            "ferry": {"available": fe_item is not None,
                      "price_total": round(fe_total, 2) if fe_total else None,
                      "price_scope": fe_scope, "source": (fe_item or {}).get("source"),
                      "currency": (fe_item or {}).get("currency")},
        },
        "sources": {
            "flights": (flights or {}).get("providers"),
            "hotels": (hotels or {}).get("providers"),
            "oneways": [((o or {}).get("providers")) for o in (oneways or [])],
            "package": package,
        },
    }


def load_fx_rates(path: str | None = None) -> dict:
    """Belegte Wechselkurse: {"USD": {"rate": 0.92, "source": "...", "as_of": "..."}}.

    Ohne belegten Kurs wird NICHT umgerechnet - die Ausgabe weist die
    Währungsunterschiede dann ausdrücklich aus.
    """
    if path:
        data = load_json(path) or {}
        return data.get("rates", {}) if isinstance(data, dict) else {}
    try:
        sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
        from fx import get_rate  # type: ignore
        rates: dict[str, dict] = {}
        for ccy in ("USD", "GBP", "CHF", "CAD", "AUD"):
            info = get_rate(ccy, "EUR")
            if info.get("rate"):
                rates[ccy] = info
        return rates
    except Exception:
        return {}


def to_currency(value: float | None, from_ccy: str | None, to_ccy: str,
                rates: dict) -> tuple[float | None, str | None]:
    """Wert in die Zielwaehrung - nur mit belegtem Kurs."""
    if value is None:
        return None, None
    if not from_ccy or from_ccy.upper() == to_ccy.upper():
        return value, None
    rate = (rates.get(from_ccy.upper()) or {})
    factor = rate.get("rate")
    if not factor:
        return None, (f"kein belegter Wechselkurs fuer {from_ccy}->{to_ccy} "
                      f"(nicht umgerechnet)")
    try:
        return value * float(factor), f"{from_ccy}->{to_ccy} Faktor {factor} (Quelle: {rate.get('source', 'unbekannt')})"
    except Exception:
        return None, f"Wechselkurs {from_ccy}->{to_ccy} unbrauchbar (nicht umgerechnet)"


def _booking_terms(item: dict | None) -> dict:
    """Vom Werkzeug gemeldete Buchungsbedingungen (Board/Getraenke/Steuern/Umfang)."""
    if not item:
        return {}
    out = {}
    for key, label in (("nights", "naechte_an_bord"),
                       ("boarding", "einhafen_hafen"),
                       ("departure_date", "abfahrt"),
                       ("taxes_included", "steuern_ enthalten"),
                       ("all_inclusive", "all_inclusive"),
                       ("drinks_included", "getraenke_enthalten")):
        val = item.get(key)
        if val is not None:
            out[label] = val
    out["quelle"] = item.get("source")
    out["preisbasis"] = item.get("price_scope")
    return out


def _topic_for(variant_id: str) -> str:
    # Evidenz-Vokabular: separate_roundtrip = getrennte Einweg-/Gabelflug-Buchung,
    # flight_plus_hotel = Flug + Hotel getrennt statt Pauschale.
    return {"split_roundtrip": "separate_roundtrip",
            "separate_roundtrip": "flight_plus_hotel",
            "package": "flight_plus_hotel"}.get(variant_id, "flight_plus_hotel")


def _notes(rec: dict | None, gaps: list[dict], evidence: list[dict]) -> list[str]:
    if not rec:
        return ["Keine vergleichbaren Preise verfügbar."]
    notes = [f"Empfehlung: {rec['label']} – {rec['total']} {rec.get('currency', 'EUR')} "
             f"für {rec.get('components')}"]
    for gap, saving in zip(gaps, [round(g["total"] - rec["total"], 2) for g in gaps]):
        notes.append(f"Alternative {gap['label']}: {gap['total']} "
                     f"(+{saving} {gap.get('currency', 'EUR')})")
    if rec.get("price_per_person_night") is not None:
        notes.append(f"Preis-Leistung: empfohlene Variante {rec['price_per_person_night']} "
                     f"{rec.get('currency', 'EUR')} je Person und Nacht.")
    if rec:
        cited = evidence_for(_topic_for(rec["id"]), evidence)
        if cited:
            top = ", ".join(f"{c['id']} ({c['strength']})" for c in cited[:6])
            notes.append(f"Beleglage zur gewählten Variante: {top} "
                         f"(Quelldetails in bundling/evidence.json und docs/EVIDENCE_SPLIT_BOOKING.md)")
        else:
            notes.append("HINWEIS: für diese Variante liegen keine Belege vor – die Empfehlung "
                         "stützt sich nur auf die Preisrechnung.")
    if not evidence:
        notes.append("HINWEIS: keine Belege geladen (bundling/evidence.json fehlt) – "
                     "die Empfehlung stützt sich nur auf die Preisrechnung, nicht auf Marktstudien.")
    else:
        gaps = (load_json(EVIDENCE_PATH) or {}).get("gap_notes")
        if gaps:
            notes.append("EVIDENZ-GRENZE: " + (gaps if isinstance(gaps, str) else str(gaps))[:400])
        notes.append("Die Empfehlung folgt dem LIVE-Preisvergleich. Die Belege zeigen ein mögliches "
                     "Sparpotenzial getrennter Buchung (E1: bis 30 % international), belegen aber "
                     "KEINE allgemeine Regel 'getrennt ist immer günstiger' – E6 (gleicher Vendor) zeigt "
                     "das Gegenteil als Regelfall. Getrennt buchen nur, wenn Anschlussschutz, "
                     "Gepäckdurchgang oder Umbuchbarkeit nicht zählen; Paket bei Insolvenzschutz, "
                     "Beistand und kostenfreiem Storno (E16/E17).")
    return notes


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--flights")
    ap.add_argument("--hotels")
    ap.add_argument("--oneways", help="Komma-getrennte Dateien: Hinweg,Rückweg")
    ap.add_argument("--package")
    ap.add_argument("--cruises", help="Runner-Ergebnis der Kategorie cruises")
    ap.add_argument("--ferries", help="Runner-Ergebnis der Kategorie ferries")
    ap.add_argument("--adults", type=int, default=1)
    ap.add_argument("--nights", type=int, default=1)
    ap.add_argument("--currency", default="EUR")
    ap.add_argument("--fx", help="JSON-Datei mit belegten Wechselkursen (z. B. bundling/fx_rates.json)")
    ap.add_argument("--out")
    args = ap.parse_args()

    oneways = [load_json(p) for p in (args.oneways or "").split(",") if p.strip()]
    out = compare(load_json(args.flights), load_json(args.hotels), oneways,
                  load_json(args.package), args.adults, args.nights, args.currency,
                  cruises=load_json(args.cruises), ferries=load_json(args.ferries),
                  fx_path=args.fx)
    text = json.dumps(out, ensure_ascii=False, indent=1)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
