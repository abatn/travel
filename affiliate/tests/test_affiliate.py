#!/usr/bin/env python3
"""Tests der Affiliate-Schicht (ohne echte Anbieter, ohne echte IDs).

Prüft: Domain-Bindung, kein Erfinden von IDs, kein Doppel-Tagging,
Strukturprüfung, Erreichbarkeitsprüfung (lokaler Testserver), Rechtstexte.
"""
from __future__ import annotations

import json
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
AFF = os.path.dirname(HERE)
sys.path.insert(0, AFF)

os.environ["AFFILIATE_CONFIG"] = os.path.join(HERE, "test_config.yaml")

import builder  # noqa: E402
import legal  # noqa: E402
import verify  # noqa: E402

CFG = builder.load_config()
results: list[tuple[bool, str]] = []


def check(ok: bool, label: str, detail: str = "") -> None:
    results.append((bool(ok), label))
    print(f"  {'OK  ' if ok else 'FAIL'}  {label}" + (f"  [{detail}]" if detail else ""))


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):        # noqa: N802
        if self.path.startswith("/ok"):
            body = b'{"ok":true}'
            self.send_response(200)
        elif self.path.startswith("/missing"):
            body = b'nicht da'
            self.send_response(404)
        else:
            body = b'?'
            self.send_response(500)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    do_HEAD = do_GET

    def log_message(self, *a):
        pass


def main() -> int:
    srv = HTTPServer(("127.0.0.1", 0), Handler)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()

    print("1) Domain-Bindung und ID-Pflicht")
    # Booking.com ist in der Testkonfiguration dem Demo-Partner zugeordnet
    r = builder.build("https://www.booking.com/hotel/it/test.html?aid=1", CFG)
    check(r["affiliate"] is True and r["partner"] == "demo",
          "Booking.com-Link wird getaggt (Demo-Partner)", r["url"][:80])
    check("ref=TESTMARKER-0000" in r["url"], "ID steht im Link")
    check(r["structure_ok"] is True, "Strukturprüfung bestanden")
    check(r.get("test_id") is True, "Testkennung wird markiert")

    # Ryanair ist KEIN Partner -> kein Link (LCC-Fallstrick)
    r2 = builder.build("https://www.ryanair.com/de/de/trip/flights/select?adults=1", CFG)
    check(r2["affiliate"] is False, "Ryanair-Link bleibt ungetaggt (keine Provision)")
    check("kein Partnerprogramm" in (r2["reason"] or ""), "Grund wird genannt",
          (r2["reason"] or "")[:60])

    # Ohne ID (echte Konfiguration) wird nicht getaggt
    os.environ.pop("AFFILIATE_CONFIG", None)
    real = builder.load_config()
    r3 = builder.build("https://www.booking.com/hotel/it/test.html", real)
    check(r3["affiliate"] is False, "Ohne konfigurierte ID kein Affiliate-Link")
    check("keine ID" in (r3["reason"] or ""), "Grund: keine ID konfiguriert",
          (r3["reason"] or "")[:70])
    os.environ["AFFILIATE_CONFIG"] = os.path.join(HERE, "test_config.yaml")

    print("\n2) Kein Doppel-Tagging, ungültige Links")
    r4 = builder.build("https://www.booking.com/x?ref=TESTMARKER-0000", CFG)
    check(r4["affiliate"] is False and "bereits getaggt" in (r4["reason"] or ""),
          "Bereits getaggter Link wird nicht erneut getaggt")
    r5 = builder.build("javascript:alert(1)", CFG)
    check(r5["affiliate"] is False and r5["structure_ok"] is False,
          "Nicht-http-Link wird abgelehnt")
    r6 = builder.build("", CFG)
    check(r6["affiliate"] is False and "kein gueltiger" in (r6["reason"] or ""),
          "Leerer Link wird abgelehnt")

    print("\n3) Strukturprüfung erkennt kaputte Templates")
    bad_cfg = json.loads(json.dumps(CFG))
    bad_cfg["demo"]["link_template"] = "{target}?nocampaign=1"   # ID fehlt
    r7 = builder.build("https://www.booking.com/x", bad_cfg)
    check(r7["affiliate"] is False and r7["structure_ok"] is False,
          "Template ohne ID fällt durch die Strukturprüfung")
    check(r7["url"] == "https://www.booking.com/x",
          "Bei Fehlschlag bleibt der Original-Link")

    print("\n4) Erreichbarkeitsprüfung (lokaler Testserver)")
    good = f"http://127.0.0.1:{port}/ok"
    r8 = verify.verify_link(builder.build(good, CFG), CFG)
    check(r8["affiliate"] and r8["verified"] is True,
          "Erreichbarer Link wird verifiziert", f"HTTP {r8.get('verify_status')}")
    bad = f"http://127.0.0.1:{port}/missing"
    r9 = verify.verify_link(builder.build(bad, CFG), CFG)
    check(r9["affiliate"] and r9["verified"] is False,
          "404 wird als nicht verifiziert gemeldet", str(r9.get("verify_error")))
    check(r9["verify_status"] == 404, "HTTP-Status wird durchgereicht")
    # Cache: zweiter Aufruf ohne Netz
    r10 = verify.verify_link(builder.build(good, CFG), CFG)
    check(r10.get("verify_cached") is True, "Zweite Prüfung kommt aus dem Cache")

    print("\n5) Nicht freigegebener Host wird nicht geprüft")
    r11 = verify.check("https://www.ryanair.com/de", None, CFG)
    check(r11["ok"] is False and "nicht fuer die Pruefung freigegeben" in (r11["error"] or ""),
          "Fremder Host löst keine Prüfung aus (kein fremder Traffic)")

    print("\n6) Rechtstexte und UI-Leitplanken")
    check(bool(legal.DISCLOSURE_SHORT) and "Anzeige" in legal.DISCLOSURE_SHORT,
          "Kurz-Disclosure nennt 'Anzeige'")
    check("Provision" in legal.DISCLOSURE_LONG, "Lang-Disclosure nennt die Provision")
    check("nicht Reiseveranstalter" in legal.LEGAL_NOTICE, "Rechtshinweis: Vermittlerrolle")
    check("kein Gesamtpreis-Angebot" in legal.LEGAL_NOTICE,
          "Rechtshinweis: kein Gesamtpreis-Angebot")
    check(legal.ui_guard("<a href='#'>Anzeige · Affiliate-Link</a>") == [],
          "Sauberes HTML passiert die Leitplanken")
    check(any("Zahlungsbezug" in f for f in legal.ui_guard("<input name='kreditkarte'>")),
          "Zahlungsfeld wird von der Leitplanke erkannt")
    check(any("Paket-Buchung" in f for f in legal.ui_guard("<button>Paket buchen</button>")),
          "Paket-Buchung wird von der Leitplanke erkannt")
    check(any("Kennzeichnung" in f for f in legal.ui_guard("<p>affiliate</p>")),
          "Affiliate ohne 'Anzeige' wird erkannt")

    srv.shutdown()
    passed = sum(1 for ok, _ in results if ok)
    print("\n" + "=" * 60)
    print(f"Ergebnis: {passed}/{len(results)} Prüfungen bestanden")
    for ok, label in results:
        if not ok:
            print("  FEHLGESCHLAGEN:", label)
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
