"""Zweite, unabhängige M2-Instanz für PayAPI Market.

Eigene Konfiguration, eigener Ed25519-Schlüssel, eigener Rechnungs-Ledger und
eine eigene URL (``/api/attest-v2``). Die bestehende Instanz unter
``/api/attest`` bleibt unverändert.
"""
from __future__ import annotations

from .instance import PAYAPI_PATH, install

__all__ = ["PAYAPI_PATH", "install"]
