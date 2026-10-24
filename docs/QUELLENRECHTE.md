# Quellenrechte: Was wir verkaufen dürfen

Stand: 24.10.2026. Grundlage: Lizenzangaben und Nutzungshinweise aus `docs/SOURCES_*.md`
sowie die Repo-Seiten der MCP-Wrapper. Die Lizenz eines MCP-Wrappers (z. B. MIT) gibt **keine**
Rechte an den Daten des dahinterliegenden Anbieters. Entscheidend sind die Nutzungsbedingungen
des Datenanbieters.

## Regel

1. Eine Beobachtung wird **nur verkauft**, wenn die Quelle schriftlich oder über eine
   kommerzielle Nutzungsbedingung für Weiterverkauf freigegeben ist (Status **freigegeben**).
2. Quellen mit Status **nicht verkaufbar** dürfen weder im Attest-Feld `source` noch in
   bezahlten Antworten vorkommen.
3. Eigene Beobachtungen (z. B. selbst erfasste Preise der eigenen Buchungsseite) sind erlaubt,
   wenn sie nicht aus fremden Scraping-Quellen stammen.
4. Bis eine Quelle freigegeben ist, werden Preise nur für interne Tests genutzt. Diese Tests
   gelten nicht als Umsatz.

## Quellenstatus

| Quelle | Kategorie | Lizenz / Nutzung laut Doku | Status |
|---|---|---|---|
| `googleflights-local` (altunoren/googleflights-mcp) | Flüge | MIT-Wrapper, aber Hinweis: „scrapes Google Flights' public web interface … intended for personal/local use only … Compliance with Google's Terms of Service is your responsibility“; umgeht den Consent-Screen mit eigenen Cookies | **nicht verkaufbar** |
| `flights-gf` | Flüge | keine Lizenzdatei, Datenbasis Google Flights | **nicht verkaufbar** |
| `trvl_flights`, `trvl_ferries`, `trvl_hotels` (trvl) | Flüge/Fähren/Hotels | PolyForm Noncommercial 1.0.0: nicht kommerziell | **nicht verkaufbar** |
| `hotelscasa` | Hotels | keine Lizenzdatei, Katalogpreise | **nicht verkaufbar** |
| Fähren-HTML-Scraper (z. B. DirectFerries-Scraping) | Fähren | ausgeschlossen (HTML-Scraping, rechtlich fragwürdig, in SOURCES_FERRIES.md bewusst nicht gebaut) | **nicht verkaufbar** |
| `stays` (him229/stays) | Hotels | MIT-Wrapper, Datenanbieter unklar | **prüfen** |
| `octotrip-flights`, `maqami-travel`, `alice-flights` | Flüge | MIT-Wrapper bzw. REST-API, Anbieter-AGB nicht geprüft | **prüfen** |
| `callstay`, `bookresorts`, `pilotplans`, `bluepillow` | Hotels | gehostete Dienste, keine Lizenz veröffentlicht | **prüfen** |
| `ignav`, `stayingapi`, `mcp-flight-search` | Flüge/Hotels | API-Key nötig, nicht genutzt | nicht im Einsatz |

Ergebnis heute: **keine Quelle ist für den Verkauf freigegeben.**

## Was jetzt zu tun ist

- Für jede Quelle mit Status **prüfen** die Nutzungsbedingungen des Anbieters lesen und
  entweder eine schriftliche Freigabe einholen oder die Quelle streichen.
- Für Flüge eine Quelle mit kommerzieller Lizenz wählen (z. B. offizielle Partner-APIs mit
  Weiterverkaufsrecht). Ohne Freigabe keine Preise verkaufen.
- Die Attest-Pipeline muss vor dem ersten Verkauf nur freigegebene Quellen zulassen
  (Allowlist im Code, siehe Vorschlag unten).

## Umsatz-Trennung (Wash-Volume)

Diese Zahlungen gelten **nicht** als Umsatz:
- Testzahlungen von unserer eigenen Wallet (`0xbD93…99d59`) während der Entwicklung.
- Die monatliche Selbstzahlung (`deploy/travel-monthly-payment.sh`) zur Erhaltung des Listings.
- Zahlungen an unsere eigene payTo-Adresse (`0x1cE5…Cc4`).

Der Zahlungs-Watch (`deploy/payment_watch.py`) filtert diese Wallets aus. Umsatz wird nur
für fremde Zahler ausgewiesen.

## Vorschlag (noch nicht umgesetzt)

`attest/models.py` lehnt Quellen ab, die nicht in einer Allowlist stehen
(z. B. `ATTEST_ALLOWED_SOURCES`, zunächst leer). Damit können keine nicht freigegebenen
Quellen versehentlich verkauft werden.
