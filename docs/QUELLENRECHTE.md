# Quellenrechte: Was wir verwenden und was wir verkaufen dürfen

Stand: 24.10.2026. Grundlage: `providers/registry.yaml` (22 Quellen) und die
Lizenzangaben in `docs/SOURCES_FETCH.md`, `docs/SOURCES_FERRIES.md`,
`docs/SOURCES_CRUISES.md`.

## Entscheidender Unterschied: zwei Verwendungen

**A) Anzeige (Website, Suche, M1 Pay-per-Crawl)**
Wir zeigen fremde Preise. Hier zählt das Recht des **Datenanbieters**, nicht die
Lizenz des MCP-Wrappers. Eine MIT-Lizenz am Wrapper erlaubt den Code, nicht die
Daten. Nur für diese Verwendung ist die Tabelle unten maßgeblich.

**B) Attestierung (M2, unser heutiges Produkt)**
Der **Käufer liefert die Beobachtung selbst** (`POST /api/attest` mit Route,
Datum, Preis, `source`, `source_url`). Wir holen keine Daten, wir prüfen nur
formale Plausibilität (`attest/plausibility.py`: Strecke, Preisrahmen,
Reisedatum, Frische, Quell-URL, Preisbasis) und signieren mit Ed25519. Das
Ergebnis geht an denselben Käufer zurück.
→ Wir **verteilen keine fremden Daten** und ersetzen keine Datenbank. Wir
beurkunden eine Behauptung des Käufers („ich habe X bei Quelle Y gesehen").
Die Verantwortung für die Beobachtung und die Zulässigkeit der Quelle liegt
beim Käufer. Wir behaupten ausdrücklich nicht, den Preis selbst geprüft zu
haben – das steht so im Attest (`plausibility.status = beobachtet`, nicht
„garantiert buchbar").

**Folge:** Für M2 ist keine Quellen-Allowlist im Code nötig. Eine Allowlist
würde den Zweck verfehlen, weil der Käufer seine eigene Quelle mitbringt.
Wichtig ist nur, dass wir die Beobachtung nicht als eigene Erhebung ausgeben.

## Quellenübersicht (maßgeblich für Anzeige / M1)

| Quelle | Kategorie | Lizenz laut Doku | Für Anzeige/Verkauf |
|---|---|---|---|
| `trvl_flights`, `trvl_ferries` (trvl) | Flüge, Fähren | PolyForm Noncommercial 1.0.0 | **nein** (nicht kommerziell) |
| `flights-gf` | Flüge | keine Lizenzdatei, Google-Flights-Scraper | **nein** |
| `googleflights-local` | Flüge | MIT-Wrapper, aber „personal/local use only“, umgeht Consent-Screen | **nein** |
| `fli_flights` | Flüge | Google-Flights-Engine, Lizenz nicht dokumentiert | **prüfen** |
| `skiplagged_flights` | Flüge | Metasuche, AGB nicht geprüft | **prüfen** |
| `stays_hotels` | Hotels | MIT-Wrapper, Datenbasis Google Hotels | **prüfen** |
| `rome_hotel_taxes` | Hotels | projektinternes Skript (unser Code) | **ja** (eigene Logik, Werte kommen aus der Anfrage) |
| `maqami-travel`, `maqami-travel-hotels` | Flüge, Hotels | MIT | **prüfen** (Anbieter-AGB) |
| `octotrip-flights` | Flüge | MIT | **prüfen** |
| `alice-flights` | Flüge | MIT (REST-API) | **prüfen** |
| `easygroupflights` | Flüge | MIT | **prüfen** |
| `callstay` | Hotels | keine Lizenz veröffentlicht (gehosteter Dienst) | **prüfen** |
| `pilotplans-hotels` | Hotels | keine Lizenz veröffentlicht | **prüfen** |
| `bookresorts` | Hotels | keine Lizenz veröffentlicht | **prüfen** |
| `ferryhopper_mcp` | Fähren | Ferryhopper-Dienst, AGB nicht geprüft | **prüfen** |
| `finnlines_ferry` | Fähren | eigene GraphQL-API, WAF-Umgehung per Chrome-UA | **prüfen** |
| `hal-cruises` | Kreuzfahrten | proprietäre Solr-Suche | **prüfen** |
| `rcl-cruises` (+ Celebrity) | Kreuzfahrten | proprietäre JSON-APIs | **prüfen** |
| `skiplagged_hotels` | Hotels | deaktiviert | nicht im Einsatz |
| `hal-price-api` | Kreuzfahrten | deaktiviert | nicht im Einsatz |
| `ignav`, `stayingapi`, `mcp-flight-search` | – | API-Key nötig | nicht im Einsatz |

**Ergebnis:** Für die Anzeige sind derzeit nur `rome_hotel_taxes` (eigener Code)
und potenziell die „prüfen“-Quellen nach Klärung zulässig. Die Google-Flights-
und trvl-Quellen dürfen **nicht** angezeigt oder verkauft werden.

## Umsatz-Trennung (Wash-Volume)

Diese Zahlungen sind **kein** Umsatz:
- Testzahlungen der eigenen Wallet (`0xbD93…99d59`).
- Die monatliche Selbstzahlung (`deploy/travel-monthly-payment.sh`).
- Zahlungen an die eigene payTo-Adresse (`0x1cE5…Cc4`).

`deploy/payment_watch.py` filtert diese Wallets und meldet nur fremde Zahler.

## Umsetzung im Code

- `providers/rights.py` filtert Quellen vor jeder Suche.
- `providers/registry.yaml` hat je Quelle einen Block:
  ```yaml
  rights:
    status: own | approved | unverified | prohibited
    evidence: "Beleg / Quelle"
    checked_at: 2026-10-24
  ```
- **Standard:** `prohibited` wird nicht angezeigt (Flüge 9→6, Fähren 3→2).
  `unverified` bleibt sichtbar, bis die AGB geklärt sind.
- Strenger (nur `own`/`approved`): `RIGHTS_INCLUDE_UNVERIFIED=0`.
- Filter aus (nur lokale Forschung): `RIGHTS_ENFORCE=0`.
- Test: `python3 -m providers.tests.test_rights`.

## Offene Punkte

1. Für jede „prüfen“-Quelle die AGB des Anbieters lesen (Weiterverkauf/Anzeige
   erlaubt?) oder Quelle streichen; danach Status auf `approved`/`prohibited`.
2. Für M1 (Pay-per-Crawl) gilt die Tabelle oben: Nur freigegebene Quellen dürfen
   hinter der Bezahlschranke angezeigt werden.
3. M2 braucht keine Allowlist; die Attestierung weist die Quelle als
   Käuferangabe aus.
