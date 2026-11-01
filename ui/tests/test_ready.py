#!/usr/bin/env python3
"""Readiness: /health ist Liveness, /ready prüft Registry/State/Zahlungswege."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ui"))

from fastapi.testclient import TestClient  # noqa: E402

import app as ui_app  # noqa: E402


class ReadyTests(unittest.TestCase):
    def setUp(self):
        self._attest = ui_app.ATTEST_ENABLED
        self._payapi = ui_app.PAYAPI_ENABLED
        ui_app.ATTEST_ENABLED = False
        ui_app.PAYAPI_ENABLED = False
        ui_app._READY_CACHE.clear()
        self.client = TestClient(ui_app.app)

    def tearDown(self):
        ui_app.ATTEST_ENABLED = self._attest
        ui_app.PAYAPI_ENABLED = self._payapi
        ui_app._READY_CACHE.clear()

    def test_health_is_liveness(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json().get("ok"))

    def test_ready_disabled_components_is_ok(self):
        with mock.patch("attest.config.load_settings",
                        return_value=mock.Mock(enabled=False)), \
             mock.patch("attest.payapi.config.load",
                        return_value=mock.Mock(enabled=False)):
            response = self.client.get("/ready")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["ok"])
        self.assertEqual(body["checks"]["registry"]["status"], "ok")
        self.assertEqual(body["checks"]["state"]["status"], "ok")
        self.assertEqual(body["checks"]["attest"]["status"], "disabled")
        self.assertEqual(body["checks"]["payapi"]["status"], "disabled")

    def test_ready_fails_when_enabled_component_is_down(self):
        ui_app.ATTEST_ENABLED = True
        with mock.patch.object(ui_app, "_facilitator_ready", return_value=(False, "down")):
            response = self.client.get("/ready")
        self.assertEqual(response.status_code, 503)
        body = response.json()
        self.assertFalse(body["ok"])
        self.assertEqual(body["checks"]["attest"]["status"], "error")


if __name__ == "__main__":
    unittest.main(verbosity=2)
