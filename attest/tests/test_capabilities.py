#!/usr/bin/env python3
"""Tests für den Capability-Katalog (M3, ohne Netz)."""
from __future__ import annotations

import json
import unittest
from dataclasses import replace
from decimal import Decimal
from urllib.parse import urlparse

from attest.capabilities import (
    CAPABILITIES,
    DEFAULT_ATTEST_PRICE,
    capabilities_document,
    normalize_price,
)
from attest.config import Settings
from attest.discovery import SAMPLE_INPUT, atomic_amount
from attest.x402_gate import ATTEST_PATH

BASE = "https://agent.example"
PLACEHOLDERS = ("{{", "TODO", "TBD", "FIXME", "PLACEHOLDER", "lorem ipsum")


def _settings(**overrides) -> Settings:
    return replace(Settings(), public_base_url=BASE, **overrides)


class CapabilityCatalogTests(unittest.TestCase):
    def setUp(self):
        self.settings = _settings()
        self.document = capabilities_document(self.settings)
        self.by_id = {cap["id"]: cap for cap in self.document["capabilities"]}

    def test_all_capabilities_present(self):
        self.assertEqual(
            [cap["id"] for cap in CAPABILITIES],
            ["attest_price", "search_flights", "resolve_place", "price_history"],
        )
        self.assertEqual(len(self.document["capabilities"]), 4)
        self.assertEqual(set(self.by_id), {c["id"] for c in CAPABILITIES})
        for cap in self.document["capabilities"]:
            for field in ("id", "name", "description", "price_usdc", "status",
                          "endpoint", "method", "input_schema", "example"):
                self.assertIn(field, cap)
            self.assertIn(cap["method"], ("GET", "POST"))
            self.assertIsInstance(cap["input_schema"], dict)
            self.assertIsInstance(cap["example"], dict)

    def test_only_attest_price_is_available(self):
        available = [c["id"] for c in self.document["capabilities"]
                     if c["status"] == "available"]
        planned = [c["id"] for c in self.document["capabilities"]
                   if c["status"] == "planned"]
        self.assertEqual(available, ["attest_price"])
        self.assertEqual(sorted(planned),
                         ["price_history", "resolve_place", "search_flights"])
        # Geplante Endpunkte dürfen nicht als verfügbar beworben werden.
        for cap in self.document["capabilities"]:
            self.assertIn(cap["status"], ("available", "planned"))
            if cap["status"] == "planned":
                self.assertIn("geplant", cap.get("note", "").lower())

    def test_attest_price_matches_gate(self):
        cap = self.by_id["attest_price"]
        self.assertEqual(cap["endpoint"], ATTEST_PATH)
        self.assertEqual(cap["method"], "POST")

    def test_prices_are_positive(self):
        for cap in self.document["capabilities"]:
            price = Decimal(cap["price_usdc"])
            self.assertGreater(price, 0, cap["id"])
            self.assertGreaterEqual(price.as_tuple().exponent, -6, cap["id"])
            atomic = cap["price_atomic"]
            self.assertIsInstance(atomic, int, cap["id"])
            self.assertGreater(atomic, 0, cap["id"])
            self.assertEqual(atomic, int(atomic_amount(cap["price_usdc"])))

    def test_document_payment_block(self):
        payment = self.document["payment"]
        self.assertEqual(self.document["version"], "1")
        self.assertEqual(payment["protocol"], "x402")
        self.assertEqual(payment["network"], self.settings.network)
        self.assertEqual(payment["pay_to"], self.settings.pay_to)
        self.assertEqual(payment["currency"], "USDC")
        self.assertIn("asset", payment)
        self.assertIn("contact", self.document)
        self.assertIsInstance(self.document["contact"], str)
        self.assertEqual(self.document["provider"]["name"], "Reise-Agent")
        self.assertEqual(self.document["provider"]["url"], BASE)

    def test_urls_are_absolute(self):
        for cap in self.document["capabilities"]:
            parsed = urlparse(cap["url"])
            self.assertIn(parsed.scheme, ("http", "https"), cap["id"])
            self.assertTrue(parsed.netloc, cap["id"])
            self.assertTrue(cap["url"].endswith(cap["endpoint"]), cap["id"])
            self.assertEqual(cap["url"], f"{BASE}{cap['endpoint']}")

    def test_base_url_argument_wins(self):
        document = capabilities_document(self.settings, base_url="https://other.example/")
        self.assertEqual(document["provider"]["url"], "https://other.example")
        for cap in document["capabilities"]:
            self.assertEqual(cap["url"], f"https://other.example{cap['endpoint']}")

    def test_attest_example_is_sample_input(self):
        example = self.by_id["attest_price"]["example"]
        self.assertEqual(example, SAMPLE_INPUT)
        self.assertIn("route", example)
        self.assertIn("price", example)
        schema = self.by_id["attest_price"]["input_schema"]
        for field in ("route", "travel_date", "price", "currency", "price_scope",
                      "source", "source_url", "passengers"):
            self.assertIn(field, schema["properties"])
        for field in ("route", "travel_date", "price", "price_scope", "source"):
            self.assertIn(field, schema["required"])

    def test_no_placeholders_and_no_secrets(self):
        raw = json.dumps(self.document, ensure_ascii=False)
        for marker in PLACEHOLDERS:
            self.assertNotIn(marker, raw)
        for key in ("api_key", "secret", "token", "private_key", "authorization"):
            self.assertNotIn(key, raw.lower())

    def test_price_follows_settings(self):
        self.assertEqual(self.by_id["attest_price"]["price_usdc"], "0.002")
        document = capabilities_document(_settings(price="$0.03"))
        cap = next(c for c in document["capabilities"] if c["id"] == "attest_price")
        self.assertEqual(cap["price_usdc"], "0.03")
        self.assertEqual(cap["price_atomic"], 30000)

    def test_invalid_price_falls_back(self):
        for broken in ("", "   ", "kostenlos", "-1", "0"):
            self.assertEqual(normalize_price(broken), DEFAULT_ATTEST_PRICE)
            document = capabilities_document(_settings(price=broken))
            cap = next(c for c in document["capabilities"]
                       if c["id"] == "attest_price")
            self.assertEqual(cap["price_usdc"], DEFAULT_ATTEST_PRICE)
            self.assertEqual(cap["price_atomic"], 10000)

    def test_document_does_not_mutate_constant(self):
        before = json.dumps(CAPABILITIES, sort_keys=True)
        document = capabilities_document(self.settings)
        document["capabilities"][0]["input_schema"]["type"] = "array"
        document["capabilities"][0]["price_usdc"] = "99"
        self.assertEqual(json.dumps(CAPABILITIES, sort_keys=True), before)


if __name__ == "__main__":
    unittest.main(verbosity=2)
