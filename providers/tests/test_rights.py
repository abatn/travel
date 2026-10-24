#!/usr/bin/env python3
"""Prüft die Quellenrechte-Sperre (Default-Deny, gesperrte Quellen)."""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "providers"))

import yaml  # noqa: E402

from rights import (  # noqa: E402
    blocked_providers, display_allowed, filter_providers, status_of,
)

REGISTRY = ROOT / "providers" / "registry.yaml"


def _provider(status: str | None, pid: str = "x") -> dict:
    p = {"id": pid, "category": "flights", "enabled": True}
    if status is not None:
        p["rights"] = {"status": status}
    return p


class RightsTests(unittest.TestCase):
    def test_status_defaults_to_unverified(self):
        self.assertEqual(status_of(_provider(None)), "unverified")
        self.assertEqual(status_of(_provider("unknown-value")), "unverified")
        self.assertEqual(status_of(_provider("own")), "own")

    def test_prohibited_is_blocked(self):
        self.assertFalse(display_allowed(_provider("prohibited")))
        self.assertTrue(display_allowed(_provider("own")))
        self.assertTrue(display_allowed(_provider("approved")))

    def test_unverified_is_allowed_by_default_but_blockable(self):
        self.assertTrue(display_allowed(_provider("unverified")))
        self.assertFalse(display_allowed(_provider("unverified"), include_unverified=False))

    def test_enforce_off_allows_everything(self):
        self.assertTrue(display_allowed(_provider("prohibited"), enforce=False))

    def test_filter_providers_mixed(self):
        provs = [_provider("prohibited", "a"), _provider("own", "b"),
                 _provider("unverified", "c")]
        self.assertEqual([p["id"] for p in filter_providers(provs, enforce=True,
                                                            include_unver=True)],
                         ["b", "c"])
        self.assertEqual([p["id"] for p in filter_providers(provs, enforce=True,
                                                            include_unver=False)],
                         ["b"])

    def test_registry_has_rights_for_every_provider(self):
        reg = yaml.safe_load(REGISTRY.read_text())
        provs = reg["providers"]
        self.assertGreaterEqual(len(provs), 20)
        for p in provs:
            self.assertIn("rights", p, f"{p.get('id')} ohne rights-Block")
            self.assertIn(status_of(p), ("own", "approved", "unverified", "prohibited"))

    def test_google_scrapers_are_prohibited(self):
        reg = yaml.safe_load(REGISTRY.read_text())
        by_id = {p["id"]: p for p in reg["providers"]}
        for pid in ("googleflights-local", "flights-gf", "trvl_flights", "trvl_ferries"):
            self.assertEqual(status_of(by_id[pid]), "prohibited", pid)

    def test_blocked_report_names_reason(self):
        blocked = blocked_providers([_provider("prohibited", "a")])
        self.assertEqual(blocked[0]["id"], "a")
        self.assertEqual(blocked[0]["status"], "prohibited")


if __name__ == "__main__":
    unittest.main(verbosity=2)
