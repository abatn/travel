#!/usr/bin/env python3
"""rome-hotel-taxes — MCP server (stdio) that returns Rome hotel prices with
*itemised* tax positions.

This is a "copy" of the working, keyless `stays` engine (Google Hotels MCP,
serverInfo "Google Hotels MCP Server" v4.1.1): same endpoint, same RPC id
(`AtySUc` at https://www.google.com/_/TravelFrontendUi/data/batchexecute),
same request shape — but the tax-bearing deeplink parameters are parsed
instead of dropped.

WHY (the contradiction this resolves):
  * booking.com  -> HTTP 202 AWS-WAF challenge for every direct request
                    (trvl's booking path therefore only ever sees Agoda).
  * google/bing  -> the `stays` MCP *reaches* the right rates but sets
                    `includes_taxes_and_fees = false` unconditionally, because
                    `RatePlan.includes_taxes_and_fees` is declared in
                    models/google_hotels/detail.py:26 and never assigned in
                    search/parse/provider_parser.py:174-180.
  * GOOGLE's own response DOES carry the itemisation, inside the offer
    deeplink query parameters:
        Booking.com : ext_price_total=52.10 & ext_price_tax=7.92 & xfc=EUR
        Booking.com : fees=3.51 & tax=7.94 & total=52.18 & currency=EUR
        Agoda        : hpa_d_tax=13.98 & hpa_d_total=83.93
        Opodo        : mpf=108.01 & mpj=18.91 & cur=EUR
    Those deeplinks live in the hotel entry's provider block at
    `entry[6][2][21..]` / `[22..]` — NOT at `entry[6][2][2]`
    (SLOT_PROVIDER_LIST), which is the only slot the `stays` parser reads.

NO API KEY. NO booking.com request. Google already indexed Booking's own
numbers, so the tax-inclusive end price + its line items are reachable
without ever touching a WAF-protected origin.

Install:
    claude mcp add rome-hotel-taxes -- python3 /home/batnini/mimo-agents/rome-2star/worker_c/rome_hotel_taxes_mcp.py
"""
from __future__ import annotations

import datetime
import json
import logging
import os
import sys
import urllib.parse

sys.path.insert(0, "/home/batnini/.local/share/pipx/venvs/stays/lib/python3.12/site-packages")

from stays.models.google_hotels.base import Currency, DateRange, GuestInfo, Location  # noqa: E402
from stays.models.google_hotels.hotels import RPC_ID, HotelSearchFilters  # noqa: E402
from stays.search.client import Client  # noqa: E402
from stays.search.parse.search_parser import _find_hotel_entries, parse_search_response  # noqa: E402

logging.disable(logging.CRITICAL)

# ---------------------------------------------------------------- JSON-RPC ---
TOOLS = [
    {
        "name": "search_hotels_with_itemized_taxes",
        "description": (
            "Search Google Hotels and return every book's *tax-inclusive* stay "
            "total together with its itemised tax/fee lines (base, tax, fees, "
            "total, currency). No API key. Each rate line comes from the OTA's "
            "own figures (Booking.com, Agoda, Hostelworld, ...) as indexed by "
            "Google; booking.com itself is never contacted, so no WAF."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "location": {"type": "string", "description": "Destination, e.g. 'hotels in Rome, Italy'"},
                "check_in": {"type": "string", "description": "YYYY-MM-DD"},
                "check_out": {"type": "string", "description": "YYYY-MM-DD"},
                "adults": {"type": "integer", "default": 1},
                "children": {"type": "integer", "default": 0},
                "rooms": {"type": "integer", "default": 1},
                "currency": {"type": "string", "default": "EUR"},
                "stars": {"type": "array", "items": {"type": "integer"}, "description": "e.g. [2]"},
                "max_hotels": {"type": "integer", "default": 15},
            },
            "required": ["location", "check_in", "check_out"],
        },
    }
]

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
    out: dict = {}
    candidates = [url]
    outer = _parse_params(url)
    for key in ("pcurl", "url", "adurl"):
        for v in outer.get(key, []):
            candidates.append(v)
    for cand in candidates:
        for raw_key, vals in _parse_params(cand).items():
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
    out["channel"] = next(
        (
            urllib.parse.urlparse(c).netloc
            for c in candidates
            if urllib.parse.urlparse(c).netloc
            and "google" not in urllib.parse.urlparse(c).netloc
            and "gstatic" not in urllib.parse.urlparse(c).netloc
        ),
        None,
    )
    out["base_price"] = round(out["total"] - (out.get("tax") or 0.0) - (out.get("fees") or 0.0), 2)
    out["booking_url"] = next((c for c in candidates if "booking.com" in c), None)
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


def walk_provider_block(entry: list):
    try:
        block = entry[6][2]
    except (IndexError, TypeError):
        return
    if not isinstance(block, list):
        return
    for row in block:
        name = provider_name(row)
        for s in _strings(row):
            if isinstance(s, str) and s.startswith("/travel/lodging"):
                yield name or "?", s


def run_search(args: dict) -> dict:
    ci = datetime.date.fromisoformat(args["check_in"])
    co = datetime.date.fromisoformat(args["check_out"])
    guests = GuestInfo(
        adults=int(args.get("adults", 1)),
        child_ages=[int(a) for a in args.get("child_ages", [])],
    )
    cur = Currency(args.get("currency", "EUR").upper())
    stars = [int(s) for s in args.get("stars", [])] or None
    max_hotels = int(args.get("max_hotels", 15))
    location = Location(query=args.get("location", "hotels in Rome, Italy"))
    dates = DateRange(check_in=ci, check_out=co)

    client = Client()
    filters = HotelSearchFilters(
        location=location, dates=dates, guests=guests, currency=cur, hotel_class=stars or []
    )
    results = parse_search_response(client.post_rpc(RPC_ID, filters.format()))

    hotels = []
    for r in results:
        if len(hotels) >= max_hotels:
            break
        if not r.entity_key:
            continue
        f2 = HotelSearchFilters(
            location=location, dates=dates, guests=guests, currency=cur, entity_key=r.entity_key
        )
        try:
            entries = _find_hotel_entries(client.post_rpc(RPC_ID, f2.format()))
        except Exception as e:  # noqa: BLE001
            hotels.append({"name": r.name, "stars": r.star_class, "error": str(e)[:200]})
            continue
        if not entries:
            continue
        lines, seen = [], set()
        for provider, deeplink in walk_provider_block(entries[0]):
            t = extract_tax_lines(deeplink, provider)
            if not t:
                continue
            key = (t["provider"], t.get("channel"), t["total"], t.get("tax"), t.get("fees"))
            if key in seen:
                continue
            seen.add(key)
            lines.append(t)
        if lines:
            lines.sort(key=lambda x: x["total"])
            hotels.append(
                {
                    "name": r.name,
                    "stars": r.star_class,
                    "rating": r.overall_rating,
                    "lat": r.latitude,
                    "lng": r.longitude,
                    "rates": lines,
                }
            )
    return {
        "query": {
            "location": args.get("location"),
            "check_in": args["check_in"],
            "check_out": args["check_out"],
            "nights": (co - ci).days,
            "adults": guests.adults,
            "currency": cur.value,
            "stars": stars,
        },
        "source": "Google Hotels batchexecute RPC AtySUc (keyless, no booking.com request)",
        "hotels": hotels,
    }


def handle(req: dict) -> dict | None:
    method = req.get("method")
    rid = req.get("id")
    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": rid,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "rome-hotel-taxes", "version": "1.0.0"},
            },
        }
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": rid, "result": {"tools": TOOLS}}
    if method == "tools/call":
        name = req.get("params", {}).get("name")
        args = req.get("params", {}).get("arguments", {}) or {}
        if name != TOOLS[0]["name"]:
            return {
                "jsonrpc": "2.0",
                "id": rid,
                "result": {"content": [{"type": "text", "text": f"unknown tool {name}"}], "isError": True},
            }
        try:
            data = run_search(args)
            text = json.dumps(data, indent=1, default=str)
            is_error = False
        except Exception as e:  # noqa: BLE001
            text = f"error: {e}"
            is_error = True
        return {
            "jsonrpc": "2.0",
            "id": rid,
            "result": {
                "content": [{"type": "text", "text": text}],
                "structuredContent": data if not is_error else {},
                "isError": is_error,
            },
        }
    if method and method.startswith("notifications/"):
        return None
    return {"jsonrpc": "2.0", "id": rid, "result": {}}


def main() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            continue
        resp = handle(req)
        if resp is not None:
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
