#!/usr/bin/env python3
"""Endpunkt-Scan: Liste von URLs mit eigenem User-Agent ansprechen und
Status/Content-Type/Ausschnitt protokollieren (für Negativbefunde)."""
from __future__ import annotations

import json
import sys

import requests

UA = "mimo-ferry-research/1.0 (research@example.org)"

URLS = [
    # --- Aggregatoren / Vergleichsportale
    "https://www.directferries.com/",
    "https://www.directferries.com/api/",
    "https://www.ferryhopper.com/",
    "https://ferryhopper.com/api/connections",
    "https://www.ferry.se/",
    "https://www.ferry24.com/",
    "https://www.ferries.gr/",
    # --- Betreiber
    "https://api.stenaline.com/",
    "https://www.stenaline.com/",
    "https://www.wasaline.com/",
    "https://www.irishferries.com/",
    "https://www.wightlink.co.uk/",
    "https://www.poferries.com/",
    "https://www.flix.com/",
    "https://www.flixbus.de/",
    "https://www.vikingline.com/",
    "https://www.colorline.no/",
    "https://www.bornholmslinje.dk/",
    "https://www.grandinavi.it/",
    "https://www.trasmediterranea.es/",
    "https://www.mobylines.com/",
    "https://www.corsica-ferries.co.uk/",
    "https://www.levanterries.gr/",
    "https://www.aegeansea Lines.com/",
    # --- Öffentliche Mobilitäts-APIs
    "https://api.entur.no/graphql",
    "https://entur.no/graphql",
    "https://www.entur.no/",
    "https://api.resrobot.se/v2.1/timetable.json",
    "https://api.transitous.org/api/v1/",
    "https://api.transitous.org/motis/v1/plan",
    "https://api.transitous.org/motis/v2/plan",
    "https://api.tfl.gov.uk/Line/meta/Mode/ferry",
    "https://api.opendata.transport.gov.uk/",
    "https://api.searoutes.com/",
]


def probe(url: str, method: str = "GET", data=None, headers=None) -> dict:
    h = {"User-Agent": UA, "Accept": "application/json, text/html;q=0.9,*/*;q=0.8"}
    if headers:
        h.update(headers)
    out = {"url": url, "method": method}
    try:
        r = requests.request(method, url, headers=h, data=data, timeout=25,
                             allow_redirects=True)
        out["status"] = r.status_code
        out["final_url"] = r.url
        out["content_type"] = r.headers.get("content-type")
        body = r.content[:400]
        try:
            txt = body.decode("utf-8", "replace")
        except Exception:
            txt = repr(body)
        out["snippet"] = " ".join(txt.split())[:350]
    except Exception as exc:
        out["error"] = f"{type(exc).__name__}: {exc}"
    return out


if __name__ == "__main__":
    extra = sys.argv[1:]
    res = [probe(u) for u in (URLS + extra)]
    for r in res:
        print(json.dumps(r, ensure_ascii=False))
