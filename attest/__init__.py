"""Verifizierte Preis-Attestierungen (Monetarisierungsmodell M2).

Ein Agent bezahlt per x402 (HTTP 402) für eine signierte, mit Quelle und
Zeitstempel versehene Preisbeobachtung. Der Facilitator ist reine Konfiguration:
OpenFacilitator (Base Sepolia, kostenlos) oder Coinbase CDP (Mainnet, JWT).
"""

from .config import Settings, load_settings  # noqa: F401
