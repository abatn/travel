#!/usr/bin/env python3
"""rome_2star_booking.py — end-to-end: find 2-star Rome hotels, then read
Booking.com's OWN itemised price breakdown for each.

PIPELINE
--------
1. Google Hotels `AtySUc` batchexecute (keyless, no booking.com request)
   -> the 2-star Rome hotel list, with reliable `star_class == 2`.
2. Booking.com searchresults page per hotel NAME
   (reusing the aws-waf-token trvl already harvested via the provider's own
   flow and cached in ~/.trvl/cookies/www.booking.com.json)
   -> the property slug.
3. Booking.com property page
   -> `RoomTableQueryResult:{}` -> Booking's OWN star class,
   -> `b_price_breakdown_simplified` -> the tax lines:
        "10 % VAT"          (percentage__included)
        "City tax"          (per_person_per_night__included)
        -> b_total_price, b_charges_info_copy "Includes taxes and fees"

Nothing here solves a captcha, rotates an IP or evades a rate limit: the WAF
token is the provider's own, obtained by trvl through Booking's own browser
flow.  The script simply refuses to run without it.

Usage:
  python3 rome_2star_booking.py --check-in 2026-10-31 --check-out 2026-11-01 \
      --adults 1 --currency EUR --max-hotels 6
"""
from __future__ import annotations

import argparse
import datetime
import json
import logging
import re
import sys
import time
import urllib.parse

sys.path.insert(0, "/home/batnini/.local/share/pipx/venvs/stays/lib/python3.12/site-packages")

import booking_breakdown as BB  # noqa: E402
from stays.models.google_hotels.base import Currency, DateRange, GuestInfo, Location  # noqa: E402
from stays.models.google_hotels.hotels import RPC_ID, HotelSearchFilters  # noqa: E402
from stays.search.client import Client  # noqa: E402
from stays.search.parse.search_parser import parse_search_response  # noqa: E402

logging.disable(logging.CRITICAL)


def google_2star(city: str, ci: datetime.date, co: datetime.date, adults: int, cur: str, limit: int):
    client = Client()
    filters = HotelSearchFilters(
        location=Location(query=f"hotels in {city}, Italy"),
        dates=DateRange(check_in=ci, check_out=co),
        guests=GuestInfo(adults=adults),
        currency=Currency(cur.upper()),
        hotel_class=[2],
    )
    results = parse_search_response(client.post_rpc(RPC_ID, filters.format()))
    out = []
    for r in results:
        if len(out) >= limit:
            break
        if r.star_class == 2 and r.name:
            out.append({"name": r.name, "stars": r.star_class, "rating": r.overall_rating,
                        "lat": r.latitude, "lng": r.longitude})
    return out


def booking_search_slug(name: str, ci, co, adults: int, cur: str, token: str):
    q = urllib.parse.urlencode(
        {"ss": name, "checkin": ci, "checkout": co, "group_adults": adults,
         "no_rooms": 1, "group_children": 0, "currency": cur, "lang": "en-us"}
    )
    status, page = BB.fetch(f"{BB.BOOKING}/searchresults.html?{q}", token)
    if status != 200:
        return None, status
    m = re.search(r'href="https://www\.booking\.com/hotel/it/([A-Za-z0-9\-_]+)\.html', page)
    if not m:
        return None, status
    return m.group(1), status


def booking_property(slug: str, ci, co, adults: int, cur: str, token: str):
    q = urllib.parse.urlencode(
        {"checkin": ci, "checkout": co, "group_adults": adults, "group_children": 0,
         "no_rooms": 1, "currency": cur}
    )
    status, page = BB.fetch(f"{BB.BOOKING}/hotel/it/{slug}.html?{q}", token)
    if status != 200:
        return None, status, []
    meta = BB.hotel_meta(page)
    # Booking's own star class
    bstars = None
    m = re.search(r'data-capla-store-data="apollo"[^>]*>(.*?)</script>', page, re.S)
    if m:
        try:
            store = json.loads(m.group(1))
            for k, v in store.items():
                if k.startswith("RoomTableQueryResult") and isinstance(v, dict):
                    bstars = v.get("stars")
                    meta["booking_property_name"] = v.get("propertyName")
                    meta["booking_accommodation_type_id"] = v.get("accommodationTypeId")
                    break
        except json.JSONDecodeError:
            pass
    meta["booking_stars"] = bstars
    return meta, status, BB.extract_breakdowns(page)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--city", default="Rome")
    ap.add_argument("--check-in", default="2026-10-31")
    ap.add_argument("--check-out", default="2026-11-01")
    ap.add_argument("--adults", type=int, default=1)
    ap.add_argument("--currency", default="EUR")
    ap.add_argument("--max-hotels", type=int, default=6)
    ap.add_argument("--out", default="/tmp/opencode/rome_2star_booking.json")
    args = ap.parse_args()

    token = BB.cached_waf_token()
    if not token:
        print("NO cached aws-waf-token -> run trvl once first.", file=sys.stderr)
        return 2

    ci, co = args.check_in, args.check_out
    gh = google_2star(args.city, datetime.date.fromisoformat(ci),
                      datetime.date.fromisoformat(co), args.adults, args.currency, args.max_hotels)
    print(f"# google hotels: {len(gh)} 2-star candidates in {args.city}", file=sys.stderr)

    results = []
    for g in gh:
        slug, st = booking_search_slug(g["name"], ci, co, args.adults, args.currency, token)
        time.sleep(2.5)
        if not slug:
            print(f"# no booking slug for {g['name']} (HTTP {st})", file=sys.stderr)
            continue
        meta, st, breakdowns = booking_property(slug, ci, co, args.adults, args.currency, token)
        time.sleep(2.5)
        if meta is None:
            print(f"# property fetch failed for {slug} (HTTP {st})", file=sys.stderr)
            continue
        cheapest = None
        for b in breakdowns:
            if b["total_price"] is None:
                continue
            if cheapest is None or b["total_price"] < cheapest["total_price"]:
                cheapest = b
        rec = {
            "google": g,
            "booking_url": f"{BB.BOOKING}/hotel/it/{slug}.html",
            "booking_name": meta.get("name"),
            "booking_stars": meta.get("booking_stars"),
            "booking_accommodation_type_id": meta.get("booking_accommodation_type_id"),
            "breakdowns": len(breakdowns),
            "cheapest_breakdown": cheapest,
        }
        results.append(rec)
        if cheapest:
            tl = "; ".join(f"{l['label']} {l['display']}" for l in cheapest["tax_lines"])
            print(
                f"  {g['name'][:38]:<40} booking_stars={meta.get('booking_stars')} "
                f"net={cheapest['net_room_price']} total={cheapest['total_price']} "
                f"[{tl}] all_incl={cheapest['includes_taxes_and_fees']}",
                file=sys.stderr,
            )
        else:
            print(f"  {g['name'][:38]:<40} booking_stars={meta.get('booking_stars')} -> no breakdown",
                  file=sys.stderr)

    with open(args.out, "w") as fh:
        json.dump({"query": vars(args), "results": results}, fh, indent=1, default=str)
    print(f"# wrote {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
