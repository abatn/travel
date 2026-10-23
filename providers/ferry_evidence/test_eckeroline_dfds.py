#!/usr/bin/env python3
"""Eckerö Line (Magento-AJAX) + DFDS Availability-Endpoint live testen.

Eckerö: 2-Schritt (GET Homepage -> form_key + Session-Cookie -> POST /checkout/bookingBar/getdepartures)
Ziel: Preisbasis belegen (adults=1 vs adults=2 vs mit Fahrzeug).
"""
from __future__ import annotations

import json
import re
import sys

import requests

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36"


def eckeroline(date: str, adults: int = 1, children: int = 0, with_car: bool = False,
               product: str = "ELI_STD") -> dict:
    s = requests.Session()
    s.headers.update({"User-Agent": UA})
    home = s.get("https://www.eckeroline.fi/", timeout=30)
    m = re.search(r'name="form_key"\s+(?:type="hidden"\s+)?value="([^"]+)"', home.text)
    if not m:
        return {"error": "form_key not found", "home_status": home.status_code}
    form_key = m.group(1)
    payload = {
        "form_key": form_key, "date": date, "district": "outward", "earliest": "",
        "latest": "", "timeType": "", "productCode": product, "vehicle1": "", "vehicle2": "",
        "withCar": with_car, "adults": adults, "children": children, "infants": 0,
    }
    r = s.post("https://www.eckeroline.fi/checkout/bookingBar/getdepartures",
               data=json.dumps(payload), timeout=30,
               headers={"Content-Type": "application/json", "Accept": "application/json",
                        "X-Requested-With": "XMLHttpRequest"})
    out = {"status": r.status_code, "content_type": r.headers.get("content-type"),
           "request": payload, "url": "https://www.eckeroline.fi/checkout/bookingBar/getdepartures"}
    try:
        out["json"] = r.json()
    except Exception:
        out["text"] = r.text[:600]
    return out


def dfds(route: str = "DKCPH-NOOSL", date: str = "2026-11-05", adults: int = 1,
         vehicle: str = "NCAR") -> dict:
    url = "https://travel-search-prod.dfds-pax-web.com/api/available-travel-dates"
    params = {"direction": "outbound", "salesOwner": "19", "numberOfAdults": str(adults),
              "vehicleType": vehicle, "route": route, "date": date}
    r = requests.get(url, params=params, timeout=30,
                     headers={"User-Agent": UA, "Accept": "application/json"})
    out = {"status": r.status_code, "url": r.url, "content_type": r.headers.get("content-type")}
    try:
        out["json"] = r.json()
    except Exception:
        out["text"] = r.text[:600]
    return out


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    res = {}
    if which in ("all", "ecker"):
        res["ecker_adults1"] = eckeroline("2026-11-05", adults=1)
        res["ecker_adults2"] = eckeroline("2026-11-05", adults=2)
        res["ecker_car"] = eckeroline("2026-11-05", adults=1, with_car=True)
    if which in ("all", "dfds"):
        res["dfds_cph_osl"] = dfds("DKCPH-NOOSL", "2026-11-05")
        res["dfds_osl_cph"] = dfds("NOOSL-DKCPH", "2026-11-05")
    print(json.dumps(res, indent=1, ensure_ascii=False)[:8000])
