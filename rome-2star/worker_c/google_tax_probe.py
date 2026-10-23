#!/usr/bin/env python3
"""Rome-2-star hotel probe: extract *itemised* tax positions from Google's
public Hotels batchexecute response (keyless; same endpoint + RPC id the
keyless `stays` MCP server already uses).

FINDING (2026-10-21, Rome):
  The Google Hotels `AtySUc` response carries each OTA's own tax/fee
  breakdown inside the *deeplink query parameters* of the offer row:

    Booking.com : ...&ext_price_total=52.10&ext_price_tax=7.92&xfc=EUR
    Booking.com : ...&fees=3.51&tax=7.94&total=52.18&currency=EUR   (block-id variant)
    Agoda        : ...&hpa_d_tax=13.98&hpa_d_total=83.93
    Opodo        : ...&mpf=108.01&mpj=18.91&cur=EUR

  The tax-bearing deeplinks live in the hotel entry's provider block at
  `entry[6][2][21..]` / `[22..]`  (the "booking redirect" offer rows).
  The `stays` MCP parser reads `entry[6][2][2]` (SLOT_PROVIDER_LIST) only,
  keeps `price` + `deeplink_url`, and never parses these parameters —
  which is exactly why its `includes_taxes_and_fees` flag is dead/false.

  Practical consequence: the tax-inclusive end price + its itemisation for
  a Rome hotel is reachable WITHOUT ever touching booking.com (no WAF),
  because Google already indexed Booking's own numbers.

Usage:
  /home/batnini/.local/share/pipx/venvs/stays/bin/python google_tax_probe.py
"""
from __future__ import annotations

import datetime
import json
import logging
import sys
import urllib.parse

sys.path.insert(0, "/home/batnini/.local/share/pipx/venvs/stays/lib/python3.12/site-packages")

from stays.models.google_hotels.base import Currency, DateRange, GuestInfo, Location  # noqa: E402
from stays.models.google_hotels.hotels import RPC_ID, HotelSearchFilters  # noqa: E402
from stays.search.client import Client  # noqa: E402
from stays.search.parse.search_parser import _find_hotel_entries, parse_search_response  # noqa: E402

logging.disable(logging.CRITICAL)

CHECK_IN = datetime.date(2026, 10, 31)
CHECK_OUT = datetime.date(2026, 11, 1)
ADULTS = 1
CITY = "hotels in Rome, Italy"
OUT = "/tmp/opencode/rome_tax_itemized.json"

# deeplink param -> normalised field
TAX_KEYS = {
    "ext_price_total": "total",
    "ext_price_tax": "tax",
    "total": "total",
    "tax": "tax",
    "fees": "fees",
    "hpa_d_total": "total",
    "hpa_d_tax": "tax",
    "mpj": "tax",
    "mpf": "fees",
}
CURRENCY_KEYS = ("xfc", "cur", "currency", "selected_currency")
# keys that must not be confused with a tax line
IGNORE = {"total", "tax", "fees"}


def _num(s):
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def _parse_params(url: str) -> dict:
    try:
        return urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
    except Exception:
        return {}


def extract_tax_lines(url: str, provider: str) -> dict | None:
    """Parse a /travel/lodging deeplink (and its nested partner URL)."""
    out: dict = {}
    candidates = [url]
    outer = _parse_params(url)
    for key in ("pcurl", "url", "adurl"):
        for v in outer.get(key, []):
            candidates.append(v)

    for cand in candidates:
        params = _parse_params(cand)
        for raw_key, vals in params.items():
            key = raw_key.lower()
            if key in TAX_KEYS:
                val = _num(vals[0])
                if val is not None:
                    out.setdefault(TAX_KEYS[key], val)
            elif key in CURRENCY_KEYS and len(vals[0]) == 3:
                out.setdefault("currency", vals[0])
    if "total" not in out:
        return None
    out["provider"] = provider
    # the booking channel actually carrying the rate (booking.com, hotel's own site, ...)
    out["channel"] = None
    for cand in candidates:
        host = urllib.parse.urlparse(cand).netloc
        if host and "google.com" not in host and "gstatic" not in host:
            out["channel"] = host
            break
    out["base"] = round(
        out["total"] - (out.get("tax") or 0.0) - (out.get("fees") or 0.0), 2
    )
    out["booking_url"] = next(
        (c for c in candidates if "booking.com" in c or "pcurl" not in c and "google" not in c), None
    )
    return out


def _strings(node):
    if isinstance(node, str):
        yield node
    elif isinstance(node, list):
        for v in node:
            yield from _strings(v)
    elif isinstance(node, dict):
        for v in node.values():
            yield from _strings(v)


def walk_provider_block(entry: list) -> list[tuple[str, str]]:
    """Return [(provider, deeplink)] for every /travel/lodging offer row."""
    found = []
    try:
        block = entry[6][2]
    except (IndexError, TypeError):
        return found
    if not isinstance(block, list):
        return found

    # provider name lives in the offer-row header, e.g.
    #   block[21] = [ [ ["Booking.com", 184, "/travel/lodging/clk?..."], null, ... ] ]
    def provider_name(node) -> str | None:
        cur = node
        for _ in range(4):
            if not isinstance(cur, list) or not cur:
                return None
            cur = cur[0]
            if isinstance(cur, str):
                return cur
            if isinstance(cur, list) and cur and isinstance(cur[0], str):
                return cur[0]
        return None

    for row in block:
        name = provider_name(row)
        for s in _strings(row):
            if isinstance(s, str) and s.startswith("/travel/lodging"):
                found.append((name or "?", s))
    return found


def main():
    client = Client()
    dates = DateRange(check_in=CHECK_IN, check_out=CHECK_OUT)
    guests = GuestInfo(adults=ADULTS)

    filters = HotelSearchFilters(
        location=Location(query=CITY),
        dates=dates,
        guests=guests,
        currency=Currency.EUR,
        hotel_class=[2],
    )
    search_resp = client.post_rpc(RPC_ID, filters.format())
    results = parse_search_response(search_resp)
    print(f"# google hotels search: {len(results)} 2-star hits in Rome "
          f"({CHECK_IN}->{CHECK_OUT}, {ADULTS} adult, EUR)", file=sys.stderr)

    out = []
    for r in results:
        if not r.entity_key:
            continue
        f2 = HotelSearchFilters(
            location=Location(query=CITY),
            dates=dates,
            guests=guests,
            currency=Currency.EUR,
            entity_key=r.entity_key,
        )
        try:
            detail = client.post_rpc(RPC_ID, f2.format())
            entries = _find_hotel_entries(detail)
        except Exception as e:  # noqa: BLE001
            print(f"# detail fail {r.name}: {e}", file=sys.stderr)
            continue
        if not entries:
            continue
        lines = []
        seen = set()
        for provider, deeplink in walk_provider_block(entries[0]):
            t = extract_tax_lines(deeplink, provider)
            if not t:
                continue
            key = (t["provider"], t.get("channel"), t["total"], t.get("tax"), t.get("fees"))
            if key in seen:
                continue
            seen.add(key)
            t["hotel"] = r.name
            t["stars"] = r.star_class
            t["rating"] = r.overall_rating
            lines.append(t)
        if lines:
            out.append({"hotel": r.name, "stars": r.star_class, "rates": lines})

    with open(OUT, "w") as fh:
        json.dump(out, fh, indent=1, default=str)

    for h in out:
        print(f"\n### {h['hotel']} ({h['stars']}*)")
        for t in h["rates"]:
            print(
                f"   {str(t['provider']):<18} channel={str(t.get('channel')):<22} "
                f"base={t['base']:>8} tax={t.get('tax')!s:>7} fees={t.get('fees')!s:>7} "
                f"TOTAL(incl. tax)={t['total']:>8} {t.get('currency','')}"
            )
    print(f"\n# wrote {OUT}", file=sys.stderr)


if __name__ == "__main__":
    main()
