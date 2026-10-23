#!/usr/bin/env python3
"""Prüft alle Buchungslinks eines Suchlaufs (Struktur + Erreichbarkeit).

Aufruf:
    python3 affiliate/check_links.py <job_id> [--limit 20] [--json]

Liest die Ergebnisdateien aus ui/state/jobs/<job_id>/ und prüft je Angebot den
Buchungslink: Ist er ein Affiliate-Link? Steckt die ID drin? Ist das Ziel
erreichbar? Gibt eine Tabelle und einen Exitcode (0 = alle geprüften Links ok).
"""
from __future__ import annotations

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import builder  # noqa: E402
import verify  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("job_id")
    ap.add_argument("--limit", type=int, default=20)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    job_dir = os.path.join(ROOT, "ui", "state", "jobs", args.job_id)
    if not os.path.isdir(job_dir):
        print(f"Lauf {args.job_id} nicht gefunden ({job_dir})")
        return 2

    cfg = builder.load_config()
    rows = []
    for name in sorted(os.listdir(job_dir)):
        if not name.endswith(".json") or name == "job.json":
            continue
        try:
            data = json.load(open(os.path.join(job_dir, name), encoding="utf-8"))
        except Exception:
            continue
        category = name[:-5]
        for item in (data.get("ranked") or [])[: args.limit]:
            url = item.get("booking_url")
            if not url:
                continue
            built = builder.build(str(url), cfg)
            res = verify.verify_link(built, cfg)
            rows.append({"category": category, "source": item.get("source"),
                         "price": item.get("price"), "currency": item.get("currency"),
                         "affiliate": built.get("affiliate"),
                         "partner": built.get("partner"),
                         "reason": built.get("reason"),
                         "verified": res.get("verified"),
                         "status": res.get("verify_status"),
                         "error": res.get("verify_error"),
                         "url": built.get("url")})

    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=1))
    else:
        print(f"{'Kategorie':10s} {'Quelle':20s} {'Preis':>9}  {'Affiliate':9s} "
              f"{'Erreichbar':10s} Begründung")
        print("-" * 96)
        for r in rows:
            price = f"{r['price']} {r['currency']}" if r["price"] is not None else "-"
            print(f"{r['category']:10s} {str(r['source'])[:20]:20s} {price:>9}  "
                  f"{('ja' if r['affiliate'] else 'nein'):9s} "
                  f"{('ja' if r['verified'] else 'nein'):10s} "
                  f"{(r['reason'] or r['error'] or '')[:44]}")

    affiliate_count = sum(1 for r in rows if r["affiliate"])
    verified_count = sum(1 for r in rows if r["verified"])
    print(f"\n{len(rows)} Links geprüft · {affiliate_count} Affiliate-Links · "
          f"{verified_count} davon erreichbar")
    # Exitcode 0, wenn jeder Affiliate-Link auch erreichbar war
    return 0 if affiliate_count == verified_count else 1


if __name__ == "__main__":
    raise SystemExit(main())
