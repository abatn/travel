#!/usr/bin/env python3
"""Royal Caribbean / Celebrity Cruises - keyless JSON-Quellen fuer die Kategorie `cruises`.

Alle Aufrufe gehen an oeffentliche Endpunkte der Reederei. Es wird KEIN persoenlicher
API-Key benoetigt - nur der statische, im Website-Javascript sichtbare AppKey der
Web-App (`AppKey`-Header) sowie ein normaler Browser-User-Agent.

Endpunkte (alle ohne Login, ohne Key):
 1) GET  https://aws-prd.api.rccl.com/en/{brand}/web/v2/ships
        -> Flotte: [{shipCode, name, brand, ...}] (Royal Caribbean + Celebrity)
 2) GET  https://aws-prd.api.rccl.com/en/{brand}/web/v3/ships/{shipCode}/voyages
        -> alle Abfahrten des Schiffes: [{sailDate (YYYYMMDD), duration, regionCode,
                                          voyageCode, voyageDescription, shipCode}]
        ACHTUNG: die packageCode der Reederei = shipCode + voyageCode
                  (z. B. voyageCode "4BH355" + shipCode "WN" -> "WN4BH355")
 3) POST https://www.{brand-domain}/room-selection/api/v1/rooms
        -> Kabinenpreis + Rechnung fuer eine konkrete Abfahrt:
           pricing.invoice = {cruiseFare, subtotal, taxesAndFees, total, discount,
                              potentialBeveragePackage}
           pricing.perPersonAmount (Preis PRO PERSON), pricing.taxesAndFeesBundled
           sailing.itinerary = {id, name, description, ship, departurePort, destination}
           sailing.startDate / endDate / sailDate / debarkDate
 4) GET  https://www.{brand-domain}/itinerary/<slug>  (serverseitig gerendertes JSON)
        -> "initial-tabs": Empfehlungs-Abfahrten mit "netPrice" (von-Preis PRO PERSON,
           inkl. Steuern) + "taxedAndFees" (Steueranteil) + "taxesFeesIncluded"

Preismodell (belegt, siehe docs/SOURCES_CRUISES.md):
   price  = cruiseFare / Personen        (Kabinenpreis OHNE Steuern, je Person)
   all_in = total / Personen             (Endpreis INKL. Steuern, je Person)
   taxes_included = taxesAndFeesBundled  (true)
   drinks_included = potentialBeveragePackage (false = Getränke NICHT inklusive)

Aufruf (cli-Transport der Registry):
    python3 providers/cruise_rcl.py --origin MIA --destination BAHAM \
        --depart-date 2026-11-01 --return-date 2027-06-30 --adults 2 --currency USD

Ausgabe: JSON auf stdout -> {"items": [ ... ]}
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
from datetime import date, datetime

import requests

UA_WEB = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:149.0) "
          "Gecko/20100101 Firefox/149.0")
APPKEY_WEB = "hyNNqIPHHzaLzVpcICPdAdbFV8yvTsAm"   # oeffentlicher Web-AppKey (RCL/Celebrity)
AWS_API = "https://aws-prd.api.rccl.com/en/{brand}/web"
BRANDS = {
    "royal": {"api_brand": "royal", "domain": "royalcaribbean.com", "label": "Royal Caribbean"},
    "celebrity": {"api_brand": "celebrity", "domain": "celebritycruises.com",
                  "label": "Celebrity Cruises"},
}
FEATURED_PAGES = {
    "royal": ["https://www.royalcaribbean.com/cruise-from/miami-florida",
              "https://www.royalcaribbean.com/cruise-ships"],
    "celebrity": ["https://www.celebritycruises.com/cruise-from/miami-florida",
                  "https://www.celebritycruises.com/cruise-ships"],
}
# Abfahrtshafen-Code -> Slug der "/cruise-from/<slug>"-Seite
PORT_SLUG = {
    "MIA": "miami-florida", "FLL": "fort-lauderdale-florida",
    "BCN": "barcelona-spain", "CIV": "civitavecchia-italy",
    "HAM": "hamburg-germany", "BOS": "boston-massachusetts",
    "BAL": "baltimore-maryland", "HOU": "houston-texas",
    "SEA": "seattle-washington", "SIN": "singapore",
    "NYC": "new-york-new-jersey", "ORL": "orlando-florida",
    "TPA": "tampa-florida", "SJU": "san-juan-puerto-rico",
    "LAX": "los-angeles-california", "NOL": "new-orleans-louisiana",
    "GAL": "galveston-texas",
}


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": UA_WEB, "Accept-Encoding": "gzip, deflate",
                      "Accept-Language": "en-US,en;q=0.9"})
    return s


def _unescape(text: str) -> str:
    t = html.unescape(text).replace("&#34;", '"').replace("&quot;", '"')
    return (t.replace("\\u003d", "=").replace("\\u0026", "&").replace("\\u0027", "'")
             .replace("\\/", "/"))


def _d(value: str | None) -> date | None:
    if not value:
        return None
    val = str(value)
    try:
        return datetime.strptime(val[:10], "%Y-%m-%d").date()
    except ValueError:
        pass
    try:
        return datetime.strptime(val, "%Y%m%d").date()
    except ValueError:
        return None


def fetch_fleet(session: requests.Session, brand: str = "royal") -> list[dict]:
    """Flotte (Schiffscodes + Namen) aus der oeffentlichen Web-API."""
    url = AWS_API.format(brand=brand) + "/v2/ships"
    r = session.get(url, params={"sort": "name"},
                    headers={"Accept": "application/json", "AppKey": APPKEY_WEB},
                    timeout=60)
    r.raise_for_status()
    return (r.json().get("payload") or {}).get("ships") or []


def fetch_voyages(session: requests.Session, ship_code: str, brand: str = "royal") -> list[dict]:
    """Alle Abfahrten eines Schiffes (Datum, Dauer, Region, voyageCode)."""
    url = AWS_API.format(brand=brand) + f"/v3/ships/{ship_code}/voyages"
    r = session.get(url, headers={"Accept": "application/json", "AppKey": APPKEY_WEB},
                    timeout=60)
    r.raise_for_status()
    return (r.json().get("payload") or {}).get("voyages") or []


def fetch_cabin_price(session: requests.Session, package_code: str, sail_date: str,
                       adults: int, children: int, currency: str,
                       brand: str = "royal") -> dict | None:
    """Kabinenpreis + Rechnung fuer eine Abfahrt (JSON, ohne Login)."""
    domain = BRANDS[brand]["domain"]
    body = {
        "countryCode": "USA",
        "packageId": package_code,
        "sailDate": sail_date,
        "currencyCode": currency,
        "language": "en",
        "options": True,
        "roomNumbers": True,
        "platform": "web",
        "rooms": [{
            "adultCount": int(adults),
            "childCount": int(children),
            "stateroomTypeCode": "INTERIOR",
            "stateroomSubtypeCode": "I",
            "accessible": False,
            "selectionFallbackStrategy": "RECOMMENDATION",
            "editMode": True,
            "reset": False,
            "taxesAndFeesBundled": True,
            "qualifiers": {"fireFighter": False, "military": False,
                           "police": False, "senior": False},
        }],
    }
    try:
        r = session.post(f"https://www.{domain}/room-selection/api/v1/rooms", json=body,
                         headers={"accept": "*/*", "content-type": "application/json",
                                  "brand": "R" if brand == "royal" else "C",
                                  "country": "USA",
                                  "Referer": f"https://www.{domain}/itinerary/{package_code}"},
                         timeout=60)
    except requests.RequestException:
        return None
    if r.status_code != 200:
        return None
    try:
        return r.json()
    except ValueError:
        return None


def fetch_featured(session: requests.Session, line: str = "royal",
                   origin: str = "") -> list[dict]:
    """Empfehlungs-Abfahrten mit Werbepreis (netPrice) - serverseitig gerendert."""
    candidates = list(FEATURED_PAGES.get(line, FEATURED_PAGES["royal"]))
    slug = PORT_SLUG.get((origin or "").upper())
    if slug:
        candidates.insert(0, f"https://www.royalcaribbean.com/cruise-from/{slug}")
    for url in candidates:
        try:
            r = session.get(url, timeout=60)
            r.raise_for_status()
        except requests.RequestException:
            continue
        body = _unescape(r.text)
        marker = ':initial-tabs="'
        idx = body.find(marker)
        if idx < 0:
            continue
        try:
            tabs, _ = json.JSONDecoder().raw_decode(body[idx + len(marker):])
        except ValueError:
            continue
        items: list[dict] = []
        for tab in tabs:
            for it in tab.get("tabItems", []):
                it = dict(it)
                it["_line"] = BRANDS[line]["label"]
                items.append(it)
        if items:
            return items
    return []


def fetch_sailing_ports(session: requests.Session, ship_code: str, sail_date: str,
                        brand: str = "royal") -> str | None:
    """Abfahrtshafen-Code einer Abfahrt (billiger GET, ohne Preisantrag).

    GET /v3/ships/{code}/sailDate/{YYYYMMDD} -> payload.sailingInfo[0].itinerary.events[]
    -> events[0].port.portCode (portType EMBARK) = Abfahrtshafen (z. B. "MIA").
    """
    url = AWS_API.format(brand=brand) + f"/v3/ships/{ship_code}/sailDate/{sail_date}"
    try:
        r = session.get(url, headers={"Accept": "application/json", "AppKey": APPKEY_WEB},
                        timeout=45)
        if r.status_code != 200:
            return None
        payload = (r.json().get("payload") or {})
        sailing = payload.get("sailingInfo") or {}
        if isinstance(sailing, list):
            sailing = sailing[0] if sailing else {}
        itin = (sailing or {}).get("itinerary") or {}
        for event in itin.get("events") or itin.get("portInfo") or []:
            port = event.get("port") if isinstance(event.get("port"), dict) else event
            if (port.get("portType") or "").upper() == "EMBARK":
                return port.get("portCode")
    except (requests.RequestException, ValueError, AttributeError):
        return None
    return None


def candidates(session: requests.Session, args) -> list[dict]:
    """Sailings aus der Voyages-API, gefiltert nach Zeitraum/Region/Dauer."""
    brand = args.line
    ships = fetch_fleet(session, brand)
    if args.ship:
        ships = [sh for sh in ships if (sh.get("shipCode") or "").upper() == args.ship.upper()]
    out: list[dict] = []
    for sh in ships:
        code = sh.get("shipCode")
        if not code:
            continue
        try:
            voyages = fetch_voyages(session, code, brand)
        except (requests.RequestException, ValueError):
            continue
        for v in voyages:
            d = _d(v.get("sailDate"))
            if d is None:
                continue
            if args.depart_date and d < args.depart_date:
                continue
            if args.return_date and d > args.return_date:
                continue
            if args.destination and (v.get("regionCode") or "").upper() != args.destination.upper():
                continue
            if args.nights and v.get("duration") and int(v["duration"]) != int(args.nights):
                continue
            out.append({
                "ship_code": code,
                "ship_name": sh.get("name"),
                "package_code": code + (v.get("voyageCode") or ""),
                "sail_date": d,
                "nights": v.get("duration"),
                "region": v.get("regionCode"),
                "description": v.get("voyageDescription"),
                "line": BRANDS[brand]["label"],
            })
    out.sort(key=lambda x: (x["sail_date"], x["package_code"]))
    return out


def price_item(session: requests.Session, cand: dict, args) -> dict | None:
    """Preis + Rechnung fuer eine Abfahrt holen und aufbereiten."""
    data = fetch_cabin_price(session, cand["package_code"],
                             cand["sail_date"].isoformat(), args.adults, args.children,
                             args.currency, args.line)
    if not data:
        return None
    inv = (data.get("pricing") or {}).get("invoice") or {}
    pp = ((data.get("rooms") or [{}])[0].get("room") or {}).get("pricing") or {}
    sailing = data.get("sailing") or {}
    itin = sailing.get("itinerary") or {}
    dep = itin.get("departurePort") or {}
    dest = itin.get("destination") or {}
    total = inv.get("total")
    if total is None:
        return None
    n = max(1, args.adults + args.children)
    subtotal = inv.get("subtotal")
    if subtotal is None:
        subtotal = float(inv.get("cruiseFare") or 0) + float((inv.get("discount") or {}).get("amount") or 0)
    return {
        "price": round(float(subtotal) / n, 2),
        "all_in": round(float(total) / n, 2),
        "currency": data.get("currencyCode") or args.currency,
        "provider": cand["line"],
        "ship_code": cand["ship_code"],
        "ship_name": (itin.get("ship") or {}).get("name") or cand["ship_name"],
        "name": itin.get("name") or cand["description"],
        "itinerary_description": itin.get("description") or cand["description"],
        "departure_date": cand["sail_date"].isoformat(),
        "return_date": sailing.get("endDate"),
        "nights": cand["nights"],
        "boarding": dep.get("code"),
        "boarding_name": dep.get("name"),
        "destination": dest.get("code"),
        "destination_name": dest.get("name"),
        "package_code": itin.get("id") or cand["package_code"],
        "region": cand["region"],
        "taxes_included": bool(pp.get("taxesAndFeesBundled", True)),
        "taxes_per_person": round(float(inv.get("taxesAndFees") or 0) / n, 2),
        "cabin_fare_total": inv.get("cruiseFare"),
        "taxes_total": inv.get("taxesAndFees"),
        "cabin_total": total,
        "discount_total": (inv.get("discount") or {}).get("amount"),
        "drinks_included": bool(inv.get("potentialBeveragePackage")),
        "refundability": pp.get("refundability"),
        "cabin_class": "INTERIOR",
        "booking_url": f"https://www.{BRANDS[args.line]['domain']}/booking/landing"
                       f"?shipCode={itin.get('ship', {}).get('code') or cand['ship_code']}"
                       f"&packageCode={itin.get('id') or cand['package_code']}"
                       f"&sailDate={cand['sail_date'].isoformat()}"
                       f"&destinationCode={dest.get('code') or cand['region'] or ''}"
                       f"&selectedCurrencyCode={data.get('currencyCode') or args.currency}"
                       f"&country=USA",
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--origin", default="", help="Abfahrtshafen-Code, z. B. MIA")
    ap.add_argument("--destination", default="", help="Zielregion-Code, z. B. BAHAM/CARIB")
    ap.add_argument("--depart-date", dest="depart_date", default="")
    ap.add_argument("--return-date", dest="return_date", default="")
    ap.add_argument("--adults", type=int, default=2)
    ap.add_argument("--children", type=int, default=0)
    ap.add_argument("--currency", default="USD")
    ap.add_argument("--line", default="royal", choices=["royal", "celebrity"])
    ap.add_argument("--ship", default="", help="Schiffscode, z. B. WN")
    ap.add_argument("--nights", type=int, default=0)
    ap.add_argument("--max-price-calls", type=int, default=25,
                    help="Obergrenze fuer Preisantrufe (Room-Selection-API)")
    ap.add_argument("--limit", type=int, default=25)
    args = ap.parse_args()
    for attr in ("depart_date", "return_date"):
        val = getattr(args, attr)
        setattr(args, attr, _d(val) if val else None)

    session = _session()
    cands = candidates(session, args)
    items: list[dict] = []
    calls = 0
    port_checks = 0
    for cand in cands:
        if len(items) >= args.limit:
            break
        if calls >= args.max_price_calls:
            break
        # Abfahrtshafen vorab filtern (billiger GET statt Preisantrag)
        if args.origin:
            port = fetch_sailing_ports(session, cand["ship_code"],
                                       cand["sail_date"].strftime("%Y%m%d"), args.line)
            port_checks += 1
            if port and port.upper() != args.origin.upper():
                continue
        calls += 1
        item = price_item(session, cand, args)
        if not item:
            continue
        if args.origin and (item.get("boarding") or "").upper() != args.origin.upper():
            continue
        items.append(item)

    json.dump({"items": items, "source": "royalcaribbean-web",
               "price_basis": "per_person", "currency": args.currency,
               "adults": args.adults, "children": args.children,
               "price_calls": calls, "port_checks": port_checks,
               "candidates": len(cands)},
              sys.stdout, ensure_ascii=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
