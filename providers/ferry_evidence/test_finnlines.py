#!/usr/bin/env python3
"""Finnlines-GraphQL (AWS AppSync, oeffentlicher SPA-Key) live testen.

Endpunkt: https://dm3xyy44wbeivgqmeymvmw22be.appsync-api.eu-central-1.amazonaws.com/graphql
Header  : x-api-key: da2-zvuktusyubbstlw7khps4vyeie  (oeffentlicher SPA-Client-Identifier)
Ziel    : chargeTotal / chargePerUnit / isAvailable pruefen und Preisbasis
          (1 vs. 2 Passagiere, ohne Fahrzeug) belegen.
"""
from __future__ import annotations

import json
import sys

import requests

ENDPOINT = "https://dm3xyy44wbeivgqmeymvmw22be.appsync-api.eu-central-1.amazonaws.com/graphql"
KEY = "da2-zvuktusyubbstlw7khps4vyeie"  # oeffentlicher SPA-Key, im trvl-Quellcode dokumentiert

TIMETABLE_Q = ("query ListTimeTableAvailability($query:TimetableQuery!){listTimeTableAvailability("
               "query:$query){...on Timetable{sailingCode departureDate departureTime arrivalDate "
               "arrivalTime departurePort arrivalPort isAvailable shipName crossingTime chargeTotal}}}")
PRODUCTS_Q = ("query ListProductsAvailability($query:ProductsQuery!){listProductsAvailability("
               "query:$query){...on Product{code type name desc maxPeople available chargePerUnit}"
               "...on ApiError{errorCode errorMessage}}}")


def post(query: str, variables: dict) -> dict:
    r = requests.post(ENDPOINT, json={"query": query, "variables": variables}, timeout=40,
                      headers={"Content-Type": "application/json", "x-api-key": KEY,
                               "User-Agent": "mimo-ferry-research/1.0 (research@example.org)"})
    out = {"http_status": r.status_code}
    try:
        out["json"] = r.json()
    except Exception:
        out["text"] = r.text[:800]
    return out


def timetable(frm: str, to: str, date: str, adults: int = 1) -> dict:
    variables = {"query": {
        "currency": "EUR", "language": "EN",
        "tariff": [{"legCode": 1, "type": "SPECIAL"}],
        "sailings": [{"legCode": 1, "departurePort": frm, "arrivalPort": to,
                      "startDate": date, "numberOfDays": 1}],
        "passengers": [{"legCode": 1, "id": i + 1, "type": "ADULT"} for i in range(adults)],
    }}
    return post(TIMETABLE_Q, variables)


def products(frm: str, to: str, date: str, dep_time: str = "") -> dict:
    variables = {"query": {"currency": "EUR", "language": "EN", "departurePort": frm,
                           "arrivalPort": to, "departureDate": date, "departureTime": dep_time}}
    return post(PRODUCTS_Q, variables)


if __name__ == "__main__":
    route = (sys.argv[1] if len(sys.argv) > 1 else "FIHEL-DETRV").split("-")
    date = sys.argv[2] if len(sys.argv) > 2 else "2026-11-05"
    res = {
        "timetable_1adult": timetable(route[0], route[1], date, 1),
        "timetable_2adults": timetable(route[0], route[1], date, 2),
        "products": products(route[0], route[1], date),
    }
    print(json.dumps(res, indent=1, ensure_ascii=False)[:6000])
