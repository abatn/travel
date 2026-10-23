#!/usr/bin/env python3
"""Unit-Tests: Signatur, Plausibilität, Konfigurationswechsel (ohne Netz)."""
from __future__ import annotations

import base64
import json
import os
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

from attest.config import load_settings
from attest.models import Observation
from attest.plausibility import check_observation
from attest.signing import canonical_bytes, load_or_create_key, verify_document
from attest.x402_gate import facilitator_config


class SignatureTests(unittest.TestCase):
    def test_roundtrip_and_tamper(self):
        with tempfile.TemporaryDirectory() as tmp:
            key = load_or_create_key(Path(tmp) / "issuer.key")
            doc = key.sign({"version": "1", "subject": {"price": "129.99"}})
            self.assertTrue(verify_document(doc, key.public_key_b64))
            self.assertFalse(verify_document({**doc, "version": "2"}, key.public_key_b64))
            self.assertNotEqual(canonical_bytes(doc), b"")

    def test_key_is_stable(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "k.key"
            first = load_or_create_key(path)
            second = load_or_create_key(path)
            self.assertEqual(first.key_id, second.key_id)
            self.assertEqual(oct(path.stat().st_mode)[-3:], "600")


class PlausibilityTests(unittest.TestCase):
    def _obs(self, **kw):
        base = dict(route="BER-FCO", travel_date=date.today() + timedelta(days=10),
                    price="129.99", price_scope="per_person", source="test-source")
        base.update(kw)
        return Observation(**base)

    def test_ok(self):
        result = check_observation(self._obs(), ttl_seconds=300)
        self.assertEqual(result["status"], "warn")  # keine Quell-URL

    def test_past_date_rejected(self):
        result = check_observation(
            self._obs(travel_date=date.today() - timedelta(days=10)), ttl_seconds=300)
        self.assertEqual(result["status"], "reject")

    def test_cheap_price_warns(self):
        result = check_observation(self._obs(price="0.50"), ttl_seconds=300)
        ids = {c["id"]: c["status"] for c in result["checks"]}
        self.assertEqual(ids["price_range"], "warn")

    def test_route_normalized(self):
        self.assertEqual(self._obs(route="ber-fco").route, "BER-FCO")


class FacilitatorSwitchTests(unittest.TestCase):
    """Beweist: OpenFacilitator -> CDP ist nur Konfiguration."""

    def setUp(self):
        self._env = dict(os.environ)
        for key in ("ATTEST_NETWORK", "ATTEST_FACILITATOR_URL", "ATTEST_FACILITATOR_AUTH",
                    "ATTEST_ASSET", "CDP_API_KEY_ID", "CDP_API_KEY_SECRET",
                    "ATTEST_CDP_ALG"):
            os.environ.pop(key, None)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._env)

    def test_openfacilitator_testnet_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.yaml"
            path.write_text(
                "enabled: true\n"
                "issuer:\n  did: did:web:test\n  key_file: " + str(Path(tmp) / "k.pem") + "\n"
                "payment:\n"
                "  price: '$0.002'\n"
                "  network: eip155:84532\n"
                "  pay_to: '0x1cE5379a485a0bd726fce57BbfDfc316b0D35Cc4'\n"
                "  facilitator:\n"
                "    url: https://pay.openfacilitator.io\n"
                "    auth:\n      mode: none\n",
                encoding="utf-8")
            s = load_settings(path)
        self.assertEqual(s.network, "eip155:84532")
        self.assertTrue(s.testnet)
        self.assertEqual(s.facilitator.url, "https://pay.openfacilitator.io")
        self.assertEqual(s.facilitator.auth.mode, "none")
        self.assertNotIn("create_headers", facilitator_config(s))
        self.assertEqual(s.resolved_asset(), "0x036CbD53842c5426634e7929541eC2318f3dCF7e")

    def test_repo_config_is_mainnet_cdp(self):
        s = load_settings()
        self.assertEqual(s.network, "eip155:8453")
        self.assertFalse(s.testnet)
        self.assertEqual(s.facilitator.url, "https://api.cdp.coinbase.com/platform/v2/x402")
        self.assertEqual(s.facilitator.auth.mode, "cdp_jwt")
        self.assertEqual(s.resolved_asset(), "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913")

    def test_mainnet_cdp_switch(self):
        key = ec.generate_private_key(ec.SECP256R1())
        pem = key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
        os.environ.update({
            "ATTEST_NETWORK": "eip155:8453",
            "ATTEST_FACILITATOR_URL": "https://api.cdp.coinbase.com/platform/v2/x402",
            "ATTEST_FACILITATOR_AUTH": "cdp_jwt",
            "CDP_API_KEY_ID": "test-key-id",
            "CDP_API_KEY_SECRET": base64.b64encode(pem).decode(),
        })
        s = load_settings()
        self.assertFalse(s.testnet)
        self.assertEqual(s.resolved_asset(), "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913")
        cfg = facilitator_config(s)
        self.assertEqual(cfg["url"], "https://api.cdp.coinbase.com/platform/v2/x402")
        self.assertIn("create_headers", cfg)

        headers = cfg["create_headers"]()
        auth = headers["verify"]["Authorization"]
        self.assertTrue(auth.startswith("Bearer "))
        token = auth.split(" ", 1)[1]
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        claims = json.loads(base64.urlsafe_b64decode(payload))
        self.assertEqual(claims["sub"], "test-key-id")
        self.assertEqual(claims["uri"],
                         "POST api.cdp.coinbase.com/platform/v2/x402/verify")
        self.assertGreater(claims["exp"], claims["nbf"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
