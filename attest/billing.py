"""Rechnungs-/Buchungs-Ledger für USDC-Einnahmen (Grundlage für Buchhaltung).

Kein Steuerbescheid und keine Rechtsberatung: Das Modul schreibt pro
erfolgreicher Attestierung einen unveränderlichen Datensatz (JSONL) mit
Betrag, Datum, Tx-Hash, Leistung, Empfänger und Payer.

Aufruf:
    python -m attest.billing --json
    python -m attest.billing --csv attest/artifacts/invoices.csv
"""
from __future__ import annotations

import argparse
import csv
import fcntl
import json
import os
import sys
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DEFAULT_LEDGER = HERE / "state" / "invoices.jsonl"
SERVICE = "Verifizierte Preis-Attestierung (x402)"
USDC_DECIMALS = 6


def ledger_path(path: str | Path | None = None) -> Path:
    if path:
        return Path(path)
    override = os.environ.get("ATTEST_LEDGER", "").strip()
    return Path(override) if override else DEFAULT_LEDGER


def _atomic_to_usd(value: Any) -> Decimal:
    try:
        raw = (Decimal(str(value)) / (Decimal(10) ** USDC_DECIMALS)).quantize(Decimal("0.000001"))
        return Decimal(format(raw.normalize(), "f"))
    except (InvalidOperation, TypeError):
        return Decimal("0")


def _read_all(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def _next_number(rows: list[dict[str, Any]], year: int) -> str:
    prefix = f"RE-{year}-"
    used = [
        int(r["invoice_no"].split("-")[-1])
        for r in rows
        if str(r.get("invoice_no", "")).startswith(prefix)
        and str(r["invoice_no"]).split("-")[-1].isdigit()
    ]
    return f"{prefix}{max(used, default=0) + 1:06d}"


def record_invoice(attestation: dict[str, Any], settlement: dict[str, Any],
                   *, path: str | Path | None = None,
                   service: str = SERVICE) -> dict[str, Any]:
    """Schreibt eine Rechnung, idempotent pro Attestierungs-ID. Gibt den Datensatz zurück."""
    target = ledger_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)

    attestation_id = str(attestation.get("id") or "")
    payment = attestation.get("payment") or {}
    subject = attestation.get("subject") or {}
    amount = payment.get("amount") or "0"
    amount_usd = _atomic_to_usd(amount)
    issued = str(attestation.get("issued_at") or datetime.now(timezone.utc).isoformat())

    lock_path = target.with_suffix(target.suffix + ".lock")
    with lock_path.open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            rows = _read_all(target)
            if attestation_id:
                for row in rows:
                    if row.get("attestation_id") == attestation_id:
                        return row

            year = datetime.fromisoformat(issued.replace("Z", "+00:00")).year
            record = {
                "invoice_no": _next_number(rows, year),
                "invoice_date": issued,
                "service": service,
                "description": (
                    f"Preis-Attestierung {subject.get('route', '')} "
                    f"{subject.get('travel_date', '')}"
                ).strip(),
                "amount": str(amount_usd),
                "currency": "USDC",
                "amount_usd": str(amount_usd),
                "network": payment.get("network") or settlement.get("network"),
                "tx_hash": settlement.get("transaction") or "",
                "payer": payment.get("payer") or settlement.get("payer") or "",
                "pay_to": (attestation.get("issuer") or {}).get("pay_to") or "",
                "attestation_id": attestation_id,
                "issuer_did": (attestation.get("issuer") or {}).get("did") or "",
                "vat_note": os.environ.get("ATTEST_VAT_NOTE", "").strip(),
                "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            }
            with target.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
            return record
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def list_invoices(path: str | Path | None = None) -> list[dict[str, Any]]:
    return _read_all(ledger_path(path))


def export_csv(target: str | Path, path: str | Path | None = None) -> Path:
    rows = list_invoices(path)
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "invoice_no", "invoice_date", "service", "description", "amount", "currency",
        "amount_usd", "network", "tx_hash", "payer", "pay_to", "attestation_id",
        "issuer_did", "vat_note", "created_at",
    ]
    with target.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description="USDC-Rechnungsledger")
    parser.add_argument("--json", action="store_true", help="Ledger als JSON ausgeben")
    parser.add_argument("--csv", help="Ledger als CSV exportieren")
    parser.add_argument("--ledger", help="alternativer Ledger-Pfad")
    args = parser.parse_args()

    if args.csv:
        print(export_csv(args.csv, args.ledger))
        return 0
    rows = list_invoices(args.ledger)
    if args.json:
        print(json.dumps(rows, indent=2, ensure_ascii=False))
    else:
        print(f"{len(rows)} Rechnungen")
        for row in rows:
            print(f"{row['invoice_no']}  {row['invoice_date'][:10]}  "
                  f"{row['amount']} {row['currency']}  {row['tx_hash'][:18]}…")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
