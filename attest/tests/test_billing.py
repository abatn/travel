#!/usr/bin/env python3
"""Tests für den Rechnungsledger (USDC-Einnahmen)."""
from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from attest.billing import export_csv, list_invoices, record_invoice


def _attestation(att_id="att_test_1", amount="10000"):
    return {
        "id": att_id,
        "issued_at": "2026-10-23T18:05:23Z",
        "issuer": {"did": "did:web:test", "pay_to": "0x1cE5379a485a0bd726fce57BbfDfc316b0D35Cc4"},
        "subject": {"route": "BER-FCO", "travel_date": "2026-11-05"},
        "payment": {"amount": amount, "network": "eip155:8453", "payer": "0xbD93"},
    }


class BillingTests(unittest.TestCase):
    def test_record_dedupe_and_csv(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Path(tmp) / "invoices.jsonl"
            first = record_invoice(_attestation(), {"transaction": "0xabc"}, path=ledger)
            self.assertEqual(first["invoice_no"], "RE-2026-000001")
            self.assertEqual(first["amount"], "0.01")
            self.assertEqual(first["currency"], "USDC")
            self.assertEqual(first["tx_hash"], "0xabc")

            # idempotent pro Attestierung
            again = record_invoice(_attestation(), {"transaction": "0xabc"}, path=ledger)
            self.assertEqual(again["invoice_no"], "RE-2026-000001")
            self.assertEqual(len(list_invoices(ledger)), 1)

            second = record_invoice(
                _attestation("att_test_2", "2000"), {"transaction": "0xdef"}, path=ledger)
            self.assertEqual(second["invoice_no"], "RE-2026-000002")
            self.assertEqual(second["amount"], "0.002")
            self.assertEqual(len(list_invoices(ledger)), 2)

            out = export_csv(Path(tmp) / "export.csv", ledger)
            with out.open(encoding="utf-8") as fh:
                rows = list(csv.DictReader(fh))
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0]["invoice_no"], "RE-2026-000001")
            self.assertEqual(rows[1]["tx_hash"], "0xdef")


if __name__ == "__main__":
    unittest.main(verbosity=2)
