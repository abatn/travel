#!/usr/bin/env python3
"""Migriert die beiden Ledger auf globale, kollisionsfreie Rechnungsnummern.

Neues Schema:
    v1: RE-<Jahr>-V1-000001
    v2: RE-<Jahr>-V2-000001

Zusätzlich wird die PayAPI-Canary-Zahlung 0x799e7c01… als erster V2-Datensatz
eingefügt, falls sie noch fehlt. Der Vorgang ist idempotent: ein zweiter Lauf
erzeugt weder Duplikate noch eine neue Nummerierung.

Aufruf (aus dem Projektverzeichnis):
    python scripts/migrate_invoice_numbers.py --dry-run
    python scripts/migrate_invoice_numbers.py
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
V1_LEDGER = ROOT / "attest" / "state" / "invoices.jsonl"
V2_LEDGER = ROOT / "attest" / "payapi" / "state" / "invoices.jsonl"

CANARY_TX = "0x799e7c01a183a3172135f4fe71a1972ea759ff57f8b323179d0a7574d8ad4432"
CANARY_PAYER = "0x171d8021b98c53dcbb3c9c30cbbbeb1b01850fca"
PAY_TO = "0x1cE5379a485a0bd726fce57BbfDfc316b0D35Cc4"
CANARY_DATE = "2026-10-28T20:22:10.792036Z"


def _read(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def _sort_key(row: dict[str, Any]) -> tuple[str, str]:
    return (str(row.get("invoice_date") or ""), str(row.get("attestation_id") or ""))


def _canary_record() -> dict[str, Any]:
    return {
        "service": "Reise-Agent Attest v2 (PayAPI)",
        "description": "Preis-Attestierung (PayAPI-Canary, Testzahlung)",
        "amount": "0.01",
        "currency": "USDC",
        "amount_usd": "0.01",
        "network": "eip155:8453",
        "tx_hash": CANARY_TX,
        "payer": CANARY_PAYER,
        "pay_to": PAY_TO,
        "attestation_id": "canary_799e7c01a183a317",
        "source": "payapi-market-verification",
        "note": (
            "Manuell nachgetragen am 09.11.2026. Beleg: PayAPI-Market-Listing "
            "travel-agent-price-attestation (verified_at 2026-10-28T20:22:10Z) "
            "und Base-Receipt Block 53214782 (10000 USDC-Units an pay_to)."
        ),
        "issuer_did": "did:web:travel.hanibal-ai.com:payapi",
        "vat_note": os.environ.get(
            "ATTEST_VAT_NOTE",
            "Umsatzsteuer wird nach gesonderter Prüfung ausgewiesen.",
        ).strip(),
        "supplier_tax_id": "1096754w",
        "invoice_date": CANARY_DATE,
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }


def _ensure_canary(rows: list[dict[str, Any]]) -> bool:
    if any(str(r.get("tx_hash", "")).lower() == CANARY_TX.lower() for r in rows):
        return False
    rows.append(_canary_record())
    return True


def _renumber(rows: list[dict[str, Any]], series: str) -> list[dict[str, Any]]:
    rows.sort(key=_sort_key)
    counters: dict[str, int] = {}
    result: list[dict[str, Any]] = []
    for row in rows:
        raw_date = str(row.get("invoice_date") or row.get("created_at") or "")
        year = raw_date[:4] if raw_date[:4].isdigit() else str(datetime.now(timezone.utc).year)
        counters[year] = counters.get(year, 0) + 1
        updated = dict(row)
        updated["invoice_series"] = series
        updated["invoice_no"] = f"RE-{year}-{series}-{counters[year]:06d}"
        updated.setdefault("source", "")
        updated.setdefault("note", "")
        result.append(updated)
    return result


def _write(path: Path, rows: list[dict[str, Any]], *, dry_run: bool) -> None:
    text = "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows)
    if dry_run:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    if path.exists():
        shutil.copy2(path, path.with_name(path.name + f".bak-{stamp}"))
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    if path.exists():
        os.chmod(tmp, path.stat().st_mode & 0o777)
    os.replace(tmp, path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--v1", default=str(V1_LEDGER))
    parser.add_argument("--v2", default=str(V2_LEDGER))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    v1_path = Path(args.v1)
    v2_path = Path(args.v2)

    v1_rows = _read(v1_path)
    v2_rows = _read(v2_path)
    canary_added = _ensure_canary(v2_rows)

    v1_new = _renumber(v1_rows, "V1")
    v2_new = _renumber(v2_rows, "V2")

    numbers = [r["invoice_no"] for r in v1_new + v2_new]
    duplicates = sorted({n for n in numbers if numbers.count(n) > 1})
    if duplicates:
        print(f"FEHLER: doppelte Rechnungsnummern: {duplicates}", file=sys.stderr)
        return 1

    print(f"v1: {len(v1_new)} Rechnungen -> {v1_path}")
    for row in v1_new:
        print(f"  {row['invoice_no']}  {row['invoice_date'][:10]}  {row.get('tx_hash','')[:20]}")
    print(f"v2: {len(v2_new)} Rechnungen -> {v2_path}")
    for row in v2_new:
        print(f"  {row['invoice_no']}  {row['invoice_date'][:10]}  {row.get('tx_hash','')[:20]}")
    print(f"Canary neu eingefügt: {'ja' if canary_added else 'nein (bereits vorhanden)'}")
    print(f"Doppelte Nummern: {duplicates or 'keine'}")

    _write(v1_path, v1_new, dry_run=args.dry_run)
    _write(v2_path, v2_new, dry_run=args.dry_run)
    if args.dry_run:
        print("DRY-RUN: keine Datei geschrieben.")
    else:
        print("Ledger geschrieben (Backups mit .bak-<Zeitstempel>).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
