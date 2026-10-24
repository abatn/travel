#!/usr/bin/env python3
"""Tests für deploy/revenue_report.py - ohne Netzwerkzugriffe."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "deploy"))

from revenue_report import (  # noqa: E402
    PAYTO, TEST_BUYER, estimate_from_block, format_report, load_ledger,
    reconcile_ledger, summarize, transfer_from_log,
)

EXTERNAL_A = "0x1111111111111111111111111111111111111111"
EXTERNAL_B = "0x2222222222222222222222222222222222222222"
OWN = {PAYTO, TEST_BUYER}


def _transfer(payer: str, amount: float, block: int = 1000,
              tx_hash: str = "", log_index: int = 0) -> dict:
    """Test-Transfer im selben Format wie transfer_from_log()."""
    return {
        "payer": payer,
        "amount": amount,
        "amount_micro": int(round(amount * 1_000_000)),
        "block": block,
        "log_index": log_index,
        "tx_hash": tx_hash,
    }


class SummarizeTests(unittest.TestCase):
    def test_own_wallets_are_excluded(self):
        transfers = [
            _transfer(PAYTO, 5.0),
            _transfer(TEST_BUYER.upper(), 3.0),
            _transfer(EXTERNAL_A, 0.01),
        ]
        result = summarize(transfers, OWN)
        self.assertEqual(result["transfers_total"], 3)
        self.assertEqual(result["transfers_own"], 2)
        self.assertEqual(result["transfers_external"], 1)
        self.assertEqual(result["external_volume_usdc"], 0.01)
        self.assertEqual(result["own_volume_usdc"], 8.0)

    def test_sum_of_external_payments(self):
        transfers = [_transfer(EXTERNAL_A, 0.01), _transfer(EXTERNAL_B, 0.02)]
        result = summarize(transfers, OWN)
        self.assertEqual(result["external_volume_usdc"], 0.03)
        self.assertEqual(result["external_volume_micro"], 30000)

    def test_unique_payers(self):
        transfers = [
            _transfer(EXTERNAL_A, 0.01, block=1000),
            _transfer(EXTERNAL_A, 0.02, block=1001),
            _transfer(EXTERNAL_B, 0.03, block=1002),
        ]
        result = summarize(transfers, OWN)
        self.assertEqual(result["unique_payers"], 2)
        self.assertEqual(result["payer_addresses"], [EXTERNAL_A, EXTERNAL_B])
        self.assertEqual(result["first_payment"]["block"], 1000)
        self.assertEqual(result["last_payment"]["block"], 1002)
        self.assertEqual(result["largest_payment"]["amount_usdc"], 0.03)

    def test_empty_list_has_no_division_by_zero(self):
        result = summarize([], OWN)
        self.assertEqual(result["transfers_total"], 0)
        self.assertEqual(result["transfers_external"], 0)
        self.assertEqual(result["transfers_own"], 0)
        self.assertEqual(result["external_volume_usdc"], 0.0)
        self.assertEqual(result["unique_payers"], 0)
        self.assertEqual(result["payer_addresses"], [])
        self.assertIsNone(result["largest_payment"])
        self.assertIsNone(result["first_payment"])
        self.assertIsNone(result["last_payment"])

    def test_first_last_and_largest(self):
        transfers = [
            _transfer(EXTERNAL_A, 0.01, block=1001, tx_hash="0xaa"),
            _transfer(EXTERNAL_B, 0.50, block=1000, tx_hash="0xbb"),
            _transfer(EXTERNAL_A, 0.02, block=1002, tx_hash="0xcc"),
        ]
        result = summarize(transfers, OWN)
        self.assertEqual(result["first_payment"]["tx_hash"], "0xbb")
        self.assertEqual(result["last_payment"]["tx_hash"], "0xcc")
        self.assertEqual(result["largest_payment"]["tx_hash"], "0xbb")
        self.assertEqual(result["largest_payment"]["amount_usdc"], 0.5)


class EstimateTests(unittest.TestCase):
    def test_estimate_is_plausible_lower_bound(self):
        head = 1_000_000
        start = estimate_from_block(head, 1)
        self.assertEqual(start, head - 43200)  # 86400 s / 2 s
        self.assertLess(start, head)

    def test_estimate_clamps_to_zero(self):
        self.assertEqual(estimate_from_block(100, 30), 0)

    def test_estimate_rejects_non_positive_days(self):
        with self.assertRaises(ValueError):
            estimate_from_block(1_000_000, 0)
        with self.assertRaises(ValueError):
            estimate_from_block(1_000_000, -1)

    def test_estimate_rejects_bad_head(self):
        with self.assertRaises(ValueError):
            estimate_from_block(-1, 1)


class LogParsingTests(unittest.TestCase):
    def test_transfer_from_log_parses_amount_and_payer(self):
        from_topic = "0x" + "0" * 24 + EXTERNAL_A[2:]
        to_topic = "0x" + "0" * 24 + PAYTO[2:]
        log = {
            "topics": ["0x" + "d" * 64, from_topic, to_topic],
            "data": hex(12345),
            "blockNumber": hex(4711),
            "logIndex": hex(3),
            "transactionHash": "0xABC",
        }
        transfer = transfer_from_log(log)
        self.assertIsNotNone(transfer)
        self.assertEqual(transfer["payer"], EXTERNAL_A)
        self.assertEqual(transfer["amount_micro"], 12345)
        self.assertEqual(transfer["block"], 4711)
        self.assertEqual(transfer["tx_hash"], "0xabc")

    def test_transfer_from_log_ignores_short_topics(self):
        self.assertIsNone(transfer_from_log({"topics": ["0xaa"]}))


class LedgerTests(unittest.TestCase):
    def test_missing_ledger_returns_empty_list(self):
        missing = Path(tempfile.gettempdir()) / "gibt-es-nicht-invoices.jsonl"
        self.assertEqual(load_ledger(missing), [])

    def test_reconcile_ledger(self):
        transfers = [
            _transfer(EXTERNAL_A, 0.01, tx_hash="0xaa"),
            _transfer(PAYTO, 0.09, tx_hash="0xbb"),
        ]
        invoices = [
            {"payer": EXTERNAL_A, "tx_hash": "0xaa", "created_at": "2026-10-24T12:00:00Z"},
            {"payer": PAYTO, "tx_hash": "0xbb", "created_at": "2026-10-24T12:01:00Z"},
            {"payer": EXTERNAL_B, "tx_hash": "0xcc", "created_at": "2026-10-24T12:02:00Z"},
        ]
        result = reconcile_ledger(invoices, transfers, OWN)
        self.assertEqual(result["invoices_in_period"], 3)
        self.assertEqual(result["invoices_external"], 2)
        self.assertEqual(result["invoices_matched_onchain"], 2)
        self.assertEqual(result["invoices_without_onchain_tx"], 1)
        self.assertEqual(result["onchain_external_without_invoice"], 0)


class FormatTests(unittest.TestCase):
    def test_report_contains_required_lines(self):
        summary = summarize([
            _transfer(PAYTO, 1.0),
            _transfer(EXTERNAL_A, 0.01),
            _transfer(EXTERNAL_B, 0.02),
        ], OWN)
        report = {
            "generated_at": "2026-10-24T12:00:00Z",
            "pay_to": PAYTO,
            "window": {
                "days": 30,
                "from_block": 1000,
                "to_block": 2000,
                "from_block_estimated": True,
                "block_seconds": 2.0,
                "from_time": 1_700_000_000,
                "to_time": 1_702_000_000,
            },
            "summary": summary,
            "ledger": {"ledger_present": False},
        }
        text = format_report(report)
        self.assertIn("0.030000 USDC", text)
        self.assertIn("2 fremd und 1 eigene", text)
        self.assertIn("Nur fremde Wallets zählen als Umsatz.", text)
        self.assertIn(EXTERNAL_A, text)
        self.assertIn(EXTERNAL_B, text)
        self.assertIn("Startblock", text)

    def test_empty_report_has_no_payment_line_crash(self):
        summary = summarize([], OWN)
        report = {
            "generated_at": "2026-10-24T12:00:00Z",
            "pay_to": PAYTO,
            "window": {
                "days": 1,
                "from_block": 0,
                "to_block": 0,
                "from_block_estimated": False,
                "block_seconds": 2.0,
                "from_time": None,
                "to_time": None,
            },
            "summary": summary,
            "ledger": {"ledger_present": False},
        }
        text = format_report(report)
        self.assertIn("0.000000 USDC", text)
        self.assertIn("Größte Einzelzahlung: keine", text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
