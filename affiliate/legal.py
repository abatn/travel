#!/usr/bin/env python3
"""Rechtliche Texte, Disclosure und Leitplanken der Oberfläche.

Die Texte setzen die Recherche aus affiliate/ENTSCHEIDUNG.md um:

* **Affiliate-Kennzeichnung** (§ 5a UWG, § 6 DDG; LG München I 09.07.2024,
  OLG München 30.10.2025): „Anzeige“ direkt am Link, sichtbar vor dem Klick.
* **Vermittlerrolle** (§ 651b, § 651c, § 651w BGB): Der Vertrag kommt mit dem
  Anbieter zustande; wir nehmen keine Zahlung entgegen, geben keine Buchungs-
  daten weiter und verkaufen kein Paket zu einem Gesamtpreis.
* **Preisvergleich ≠ Angebot:** Die Bündelungssumme ist ein Vergleichswert.

`ui_guard()` prüft gerendertes HTML auf genau diese Punkte (für Tests).
"""
from __future__ import annotations

import re

DISCLOSURE_SHORT = "Anzeige · Affiliate-Link"
DISCLOSURE_TEST = "Anzeige · Testkennung (kein echtes Partnerprogramm)"

DISCLOSURE_LONG = (
    "Dieser Link ist ein Affiliate-Link. Wenn du darüber buchst, erhalten wir vom Anbieter "
    "eine Provision. Für dich ändert sich der Preis dadurch nicht. Die Empfehlung richtet sich "
    "ausschließlich nach dem Preis – nicht nach der Provision."
)

LEGAL_NOTICE = (
    "Wir vermitteln Reiseleistungen, wir sind nicht Reiseveranstalter. Der Vertrag über jede "
    "Leistung kommt ausschließlich mit dem jeweiligen Anbieter zustande; dort wird auch bezahlt. "
    "Wir nehmen keine Zahlungen entgegen und geben keine Buchungs- oder Zahlungsdaten an weitere "
    "Anbieter weiter. Die Summen im Vergleich sind ein Vergleichswert und kein Gesamtpreis-Angebot."
)

BUNDLE_NOTICE = (
    "Die Bündelung ist ein Preisvergleich, kein Paketangebot. Jede Leistung wird beim jeweiligen "
    "Anbieter separat ausgewählt und bezahlt (§ 651b BGB: kein einheitlicher Buchungsvorgang, kein "
    "Gesamtpreis)."
)

NO_PAYMENT_NOTE = (
    "Diese Oberfläche nimmt keine Zahlung vor und speichert keine Zahlungsdaten."
)

# Zuordnung der Textkonstanten zu den i18n-Schlüsseln der Oberfläche.
_TEXT_KEYS = {
    "DISCLOSURE_SHORT": "affiliate.disclosure_short",
    "DISCLOSURE_TEST": "affiliate.disclosure_test",
    "DISCLOSURE_LONG": "affiliate.disclosure_long",
    "LEGAL_NOTICE": "affiliate.legal_notice",
    "BUNDLE_NOTICE": "affiliate.bundle_notice",
    "NO_PAYMENT_NOTE": "affiliate.no_payment",
}


def key_for(name: str) -> str:
    """i18n-Schlüssel zu einer Textkonstanten, z. B. ``DISCLOSURE_SHORT``.

    Unbekannte Namen werden unverändert zurückgegeben, damit Aufrufer nicht
    versehentlich einen leeren Schlüssel erhalten.
    """
    return _TEXT_KEYS.get(name, name)


def disclosure_for(link_info: dict | None) -> str | None:
    """Passende Kennzeichnung für einen Link (oder None, wenn kein Affiliate-Link)."""
    info = link_info or {}
    if not info.get("affiliate"):
        return None
    return DISCLOSURE_TEST if info.get("test_id") else DISCLOSURE_SHORT


# --------------------------------------------------------------- UI-Leitplanken
_FORBIDDEN_PAYMENT = re.compile(
    r"(kreditkarte|credit.?card|iban|bic\b|kontonummer|kartennummer|cvv|paypal|stripe|"
    r"klarna|zahlungspflichtig|jetzt\s+kaufen|jetzt\s+bezahlen)", re.I)
_FORBIDDEN_PACKAGE = re.compile(
    r"(paket\s+buchen|pauschalreise\s+buchen|gesamtpreis\s+buchen|alles\s+buchen|"
    r"package\s+checkout)", re.I)


def ui_guard(html: str) -> list[str]:
    """Prüft gerendertes HTML gegen die Leitplanken. Leere Liste = in Ordnung."""
    findings: list[str] = []
    if _FORBIDDEN_PAYMENT.search(html):
        findings.append("Zahlungsbezug im HTML gefunden (die UI darf keine Zahlung anbieten)")
    if _FORBIDDEN_PACKAGE.search(html):
        findings.append("Paket-Buchung im HTML gefunden (würde § 651b BGB auslösen)")
    if "affiliate" in html.lower() and "anzeige" not in html.lower():
        findings.append("Affiliate-Erwähnung ohne sichtbare Kennzeichnung 'Anzeige'")
    return findings


def link_attributes(link_info: dict | None) -> dict:
    """Attribute für den Buchungslink."""
    info = link_info or {}
    attrs = {"target": "_blank", "rel": "noopener"}
    if info.get("affiliate"):
        # sponsored kennzeichnet Affiliate-Links für Suchmaschinen (§ 5a UWG)
        attrs["rel"] = "sponsored noopener noreferrer"
    return attrs
