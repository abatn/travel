#!/usr/bin/env python3
"""Tests für den Rechnungsledger (USDC-Einnahmen)."""
from __future__ import annotations

import csv
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml

from attest import billing
from attest.billing import export_csv, list_invoices, record_invoice

REPO_ROOT = Path(__file__).resolve().parents[2]


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
            self.assertIn("supplier_tax_id", rows[0])

    def test_supplier_tax_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Path(tmp) / "invoices.jsonl"

            # 1) Umgebungsvariable hat Vorrang
            with mock.patch.dict(os.environ, {"ATTEST_TAX_ID": "TN-TEST-1"}):
                rec = record_invoice(
                    _attestation("att_tax_1", "10000"), {"transaction": "0x1"}, path=ledger)
            self.assertEqual(rec["supplier_tax_id"], "TN-TEST-1")

            # 2) ohne Env kommt der Wert aus ui/legal.yaml (echte tunesische MwSt-IdNr.)
            with mock.patch.dict(os.environ, {"ATTEST_TAX_ID": ""}):
                rec = record_invoice(
                    _attestation("att_tax_2", "10000"), {"transaction": "0x2"}, path=ledger)
            legal_data = yaml.safe_load(
                (REPO_ROOT / "ui" / "legal.yaml").read_text(encoding="utf-8")) or {}
            expected = str(
                (legal_data.get("betreiber") or {}).get("umsatzsteuer_id") or "").strip()
            if expected.startswith("["):
                expected = ""
            self.assertEqual(rec["supplier_tax_id"], expected)
            self.assertEqual(expected, "1096754w")  # tunesische MwSt-IdNr.

            # 3) Platzhalter in ui/legal.yaml -> "" – keine erfundene Nummer
            ui_dir = Path(tmp) / "ui"
            ui_dir.mkdir()
            (ui_dir / "legal.yaml").write_text(
                'betreiber:\n  umsatzsteuer_id: \'[USt-IdNr. oder "keine"]\'\n',
                encoding="utf-8")
            with mock.patch.dict(os.environ, {"ATTEST_TAX_ID": ""}), \
                    mock.patch.object(billing, "ROOT", Path(tmp)):
                rec = record_invoice(
                    _attestation("att_tax_3", "10000"), {"transaction": "0x3"}, path=ledger)
            self.assertEqual(rec["supplier_tax_id"], "")

            # 4) explizit "keine" -> "" (z. B. Kleinunternehmer)
            (ui_dir / "legal.yaml").write_text(
                "betreiber:\n  umsatzsteuer_id: \"keine\"\n", encoding="utf-8")
            with mock.patch.dict(os.environ, {"ATTEST_TAX_ID": ""}), \
                    mock.patch.object(billing, "ROOT", Path(tmp)):
                rec = record_invoice(
                    _attestation("att_tax_4", "10000"), {"transaction": "0x4"}, path=ledger)
            self.assertEqual(rec["supplier_tax_id"], "")


if __name__ == "__main__":
    unittest.main(verbosity=2)
