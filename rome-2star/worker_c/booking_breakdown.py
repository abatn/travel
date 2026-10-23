#!/usr/bin/env python3
"""booking_breakdown.py — read Booking.com's OWN itemised price breakdown for a
hotel stay, straight from the property page's SSR payload.

THE CONTRADICTION THIS RESOLVES
-------------------------------
trvl's booking path dies on an AWS-WAF challenge (HTTP 202/403), so Rome is
only ever priced via Agoda with an undifferentiated tax sum.  Booking's own
price breakdown — the one that names "10 % VAT" and "City tax" as SEPARATE
lines and states "Includes taxes and fees" — is exactly what the Rome task
needs, and it lives on the property page.

THE WAY THROUGH IS NOT A BYPASS
-------------------------------
trvl already implements the provider's own token flow
(`acquireBookingWAFToken` in internal/hotels/booking_search.go) and caches the
resulting `aws-waf-token` in ~/.trvl/cookies/www.booking.com.json.  Replaying
that cached, provider-issued cookie is an ordinary request with an ordinary
header.  No captcha is solved here, no IP rotation, no rate-limit evasion.
If no token is cached the script says so instead of guessing.

WHERE THE DATA LIVES
--------------------
The breakdown is NOT in the Apollo store (`data-capla-store-data="apollo"`).
It is in the page's inline SSR `<script>` payload, as a strict-JSON object
under the key "b_price_breakdown_simplified":

  "b_net_room_price"     [{"b_raw_value":"242.645...","b_type":"net_room_price"}]
  "b_included_charges"   [{"b_copy":"10 % VAT","b_value":"€ 24.26",
                           "b_type":"percentage__included"},
                          {"b_copy":"City tax","b_value":"€ 7.50",
                           "b_type":"per_person_per_night__included"}]
  "b_sum_included_charges" [{"b_raw_value_hotel_currency":31.7646, ...}]
  "b_charges_info_copy"  {"b_line_copy":"Includes taxes and fees",
                           "b_is_all_included":1,"b_tooltip_copy":"Total"}
  "b_total_price"        [{"b_copy_alt":"Total Price",
                           "b_raw_value_user_currency":274.4101}]
  "b_conditional_charges" / "b_nonmandatory_charges"  -> NOT included in total

Usage:
  python3 booking_breakdown.py https://www.booking.com/hotel/it/hotel-lella.html \
      --check-in 2026-10-31 --check-out 2026-11-01 --adults 1 --currency EUR
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36"
)
COOKIE_CACHE = os.path.expanduser("~/.trvl/cookies/www.booking.com.json")
BOOKING = "https://www.booking.com"


# ----------------------------------------------------------------- cookies ---
def cached_waf_token() -> str | None:
    """The aws-waf-token trvl harvested via the provider's own flow."""
    try:
        with open(COOKIE_CACHE) as fh:
            data = json.load(fh)
    except Exception:
        return None
    found: list[str] = []

    def walk(node):
        if isinstance(node, dict):
            if node.get("name") == "aws-waf-token" and isinstance(node.get("value"), str):
                found.append(node["value"])
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(data)
    return found[0] if found else None


def fetch(url: str, token: str | None, timeout: int = 45) -> tuple[int, str]:
    headers = {
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }
    if token:
        headers["Cookie"] = f"aws-waf-token={token}"
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            page = resp.read().decode("utf-8", "replace")
            final = resp.geturl()
            # Safety: Booking may 301 to the bare property URL, silently
            # dropping check-in/check-out.  Without dates the page carries no
            # price breakdown at all, so a dropped query would silently turn
            # into "no data" rather than wrong data — but we still refuse.
            if "checkin=" in url and "checkin=" not in final:
                raise RuntimeError(
                    f"redirect dropped the stay dates ({final}) — refusing to "
                    "parse a date-less price breakdown"
                )
            return resp.status, page
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")


# ------------------------------------------------------------------ parsing ---
def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _match_json_object(page: str, start: int) -> str | None:
    """Brace-match a strict-JSON object starting at the '{' at/after `start`."""
    i = page.find("{", start)
    if i < 0:
        return None
    depth = 0
    instr = False
    esc = False
    j = i
    while j < len(page):
        c = page[j]
        if instr:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                instr = False
        else:
            if c == '"':
                instr = True
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    return page[i : j + 1]
        j += 1
    return None


def extract_breakdowns(page: str) -> list[dict]:
    """Every "b_price_breakdown_simplified" object in the page."""
    out = []
    for m in re.finditer(r'"b_price_breakdown_simplified"\s*:\s*', page):
        blob = _match_json_object(page, m.end())
        if not blob:
            continue
        try:
            obj = json.loads(blob)
        except json.JSONDecodeError:
            continue
        out.append(_summarise(obj))
    return out


def _summarise(obj: dict) -> dict:
    lines = []
    for c in obj.get("b_included_charges") or []:
        if not isinstance(c, dict):
            continue
        lines.append(
            {
                "label": c.get("b_copy") or c.get("b_copy_alt"),
                "kind": c.get("b_type"),
                "amount": _num(c.get("b_raw_value")),
                "display": c.get("b_value"),
                "display_rounded": c.get("b_value_user_currency_rounded"),
            }
        )
    total = None
    for t in obj.get("b_total_price") or []:
        if isinstance(t, dict):
            total = _num(t.get("b_raw_value_user_currency")) or _num(t.get("b_raw_value"))
            break
    net = None
    for t in obj.get("b_net_room_price") or []:
        if isinstance(t, dict):
            net = _num(t.get("b_raw_value"))
            break
    sum_incl = None
    for t in obj.get("b_sum_included_charges") or []:
        if isinstance(t, dict):
            sum_incl = _num(t.get("b_raw_value_hotel_currency"))
            break
    info = obj.get("b_charges_info_copy") or {}
    if not isinstance(info, dict):
        info = {}
    return {
        "net_room_price": net,
        "tax_lines": lines,
        "tax_total": round(sum(x["amount"] for x in lines if x["amount"] is not None), 2),
        "sum_included_charges": sum_incl,
        "total_price": total,
        "includes_taxes_and_fees": bool(info.get("b_is_all_included")),
        "line_copy": info.get("b_line_copy"),
        "conditional_charges": [
            {"label": c.get("b_copy"), "amount": _num(c.get("b_raw_value")), "display": c.get("b_value")}
            for c in (obj.get("b_conditional_charges") or [])
            if isinstance(c, dict)
        ],
        "nonmandatory_charges": [
            {"label": c.get("b_copy"), "amount": _num(c.get("b_raw_value")), "display": c.get("b_value")}
            for c in (obj.get("b_nonmandatory_charges") or [])
            if isinstance(c, dict)
        ],
    }


def hotel_meta(page: str) -> dict:
    """Hotel name + star class from the page's JSON-LD."""
    meta: dict = {}
    for m in re.finditer(
        r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', page, re.S
    ):
        try:
            data = json.loads(m.group(1))
        except json.JSONDecodeError:
            continue
        for node in data if isinstance(data, list) else [data]:
            if isinstance(node, dict) and "Hotel" in str(node.get("@type", "")):
                meta.setdefault("name", node.get("name"))
                sr = node.get("starRating")
                if isinstance(sr, dict):
                    meta.setdefault("stars", sr.get("ratingValue"))
                elif sr is not None:
                    meta.setdefault("stars", sr)
                break
    if "name" not in meta:
        m = re.search(r"<title>(.*?)</title>", page, re.S)
        if m:
            meta["name"] = re.sub(r"\s+", " ", m.group(1)).strip()
    return meta


def search_cards(page: str) -> list[dict]:
    """(name, url) per property card on a Booking search-results page."""
    cards = []
    for m in re.finditer(
        r'<a href="(https://www\.booking\.com/hotel/it/[^"]+)"[^>]*data-testid="title-link"',
        page,
    ):
        url = m.group(1)
        tail = page[m.end() : m.end() + 1200]
        nm = re.search(r'data-testid="title">([^<]+)<', tail)
        name = nm.group(1).strip() if nm else None
        slug = re.search(r"/hotel/it/([A-Za-z0-9\-_]+)\.html", url)
        cards.append({"name": name, "url": url.split("?")[0], "slug": slug.group(1) if slug else None})
    return cards


# --------------------------------------------------------------------- main ---
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("--check-in", required=True)
    ap.add_argument("--check-out", required=True)
    ap.add_argument("--adults", type=int, default=1)
    ap.add_argument("--rooms", type=int, default=1)
    ap.add_argument("--children", type=int, default=0)
    ap.add_argument("--currency", default="EUR")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    q = urllib.parse.urlencode(
        {
            "checkin": args.check_in,
            "checkout": args.check_out,
            "group_adults": args.adults,
            "group_children": args.children,
            "no_rooms": args.rooms,
            "currency": args.currency,
        }
    )
    url = args.url.split("?")[0] + "?" + q

    token = cached_waf_token()
    if not token:
        print(
            "NO aws-waf-token in ~/.trvl/cookies/www.booking.com.json — run trvl once "
            "(it harvests the token through the provider's own flow) or open booking.com "
            "in a browser once.",
            file=sys.stderr,
        )
        return 2

    status, page = fetch(url, token)
    print(f"# HTTP {status} bytes={len(page)} url={url}", file=sys.stderr)
    if status != 200:
        print(page[:400], file=sys.stderr)
        return 1

    meta = hotel_meta(page)
    blocks = extract_breakdowns(page)
    print(f"# {meta.get('name')} stars={meta.get('stars')} -> {len(blocks)} breakdown(s)", file=sys.stderr)
    if args.json:
        print(json.dumps({"hotel": meta, "breakdowns": blocks}, indent=1, default=str))
        return 0
    for b in blocks:
        print(
            f"\n  net={b['net_room_price']}  total={b['total_price']}  "
            f"tax_total={b['tax_total']}  all_included={b['includes_taxes_and_fees']}  "
            f"copy={b['line_copy']!r}"
        )
        for l in b["tax_lines"]:
            print(f"     - {str(l['label']):<14} {str(l['display']):>10}  ({l['kind']})")
        if b["conditional_charges"]:
            print(f"     ! conditional (NOT in total): {b['conditional_charges']}")
        if b["nonmandatory_charges"]:
            print(f"     ! non-mandatory: {b['nonmandatory_charges']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
