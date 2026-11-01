#!/usr/bin/env python3
"""Prüft die Quellenrechte-Sperre: prohibited blockiert, unverified sichtbar (Default),
strikter Modus, Env-Defaults und Registry-Invarianten."""
from __future__ import annotations

import os
import sys
import unittest
from collections import Counter
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "providers"))

import yaml  # noqa: E402

from rights import (  # noqa: E402
    blocked_providers, display_allowed, enforce_enabled, filter_providers,
    include_unverified, status_of,
)

REGISTRY = ROOT / "providers" / "registry.yaml"
PROHIBITED = {"trvl_flights", "trvl_ferries", "flights-gf", "googleflights-local"}
DISABLED = {"skiplagged_hotels", "hal-price-api"}
EXPECTED_CATEGORIES = {"flights": 6, "hotels": 6, "ferries": 2, "cruises": 2}


def _registry() -> list[dict]:
    return yaml.safe_load(REGISTRY.read_text())["providers"]


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

    def test_env_defaults(self):
        with mock.patch.dict(os.environ, clear=False):
            os.environ.pop("RIGHTS_INCLUDE_UNVERIFIED", None)
            os.environ.pop("RIGHTS_ENFORCE", None)
            self.assertTrue(include_unverified())
            self.assertTrue(enforce_enabled())
            os.environ["RIGHTS_INCLUDE_UNVERIFIED"] = "0"
            self.assertFalse(include_unverified())
            os.environ["RIGHTS_ENFORCE"] = "0"
            self.assertFalse(enforce_enabled())

    def test_registry_counts(self):
        reg = _registry()
        enabled = [p for p in reg if p.get("enabled", True)]
        disabled = {p["id"] for p in reg if not p.get("enabled", True)}
        self.assertEqual(len(reg), 22)
        self.assertEqual(len(enabled), 20)
        self.assertEqual(disabled, DISABLED)

    def test_prohibited_set_is_exact(self):
        reg = _registry()
        prohibited = {p["id"] for p in reg if status_of(p) == "prohibited"}
        self.assertEqual(prohibited, PROHIBITED)
        for p in reg:
            if p["id"] in PROHIBITED:
                self.assertTrue(p.get("enabled", True), f"{p['id']} muss enabled bleiben (Forschung)")

    def test_effective_providers_per_category(self):
        reg = _registry()
        enabled = [p for p in reg if p.get("enabled", True)]
        effective = filter_providers(enabled, enforce=True, include_unver=True)
        self.assertEqual(len(effective), 16)
        self.assertEqual(dict(Counter(p["category"] for p in effective)), EXPECTED_CATEGORIES)
        self.assertFalse(PROHIBITED & {p["id"] for p in effective})

    def test_strict_mode_leaves_only_own_source(self):
        reg = _registry()
        enabled = [p for p in reg if p.get("enabled", True)]
        strict = filter_providers(enabled, enforce=True, include_unver=False)
        self.assertEqual([p["id"] for p in strict], ["rome_hotel_taxes"])

    def test_enforce_off_passes_prohibited(self):
        reg = _registry()
        enabled = [p for p in reg if p.get("enabled", True)]
        unfiltered = filter_providers(enabled, enforce=False)
        self.assertTrue(PROHIBITED <= {p["id"] for p in unfiltered})


if __name__ == "__main__":
    unittest.main(verbosity=2)
