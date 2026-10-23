# Schiffsreisen (Fähren & Kreuzfahrten) – Integration ins System

Stand 21.10.2026 · Alle Preise aus echten Werkzeugaufrufen.

---

## 1. Was neu dazugekommen ist

| Baustein | Änderung |
|---|---|
| **Registry** (`providers/registry.yaml`) | zwei neue Kategorien: `ferries` (3 Quellen) und `cruises` (2 aktive + 1 vorbereitete) |
| **Runner** (`providers/runner.py`) | Kategorie ist frei wählbar bzw. kommagetrennt (`flights,ferries,hotels`) – eine Quelle darf mehrere Kategorien bedienen; Quellen mit unbestätigter Preisbasis werden aus dem Ranking genommen |
| **Normalisierung** (`providers/normalize.py`) | additive Felder für Schiffsreisen: `departure_date`, `return_date`, `nights`, `boarding`, `destination`, `all_inclusive`, `taxes_included`, `drinks_included`; `extract.price_divisor` (Cent → Euro); `extract.currency` darf eine Konstante sein |
| **Bündelung** (`bundling/compare.py`) | drei neue Varianten: Kreuzfahrt allein, Anreise-Flug + Kreuzfahrt, Flug + Fähre + Hotel; Währungsschutz; Buchungsbedingungen (`bundling/ship_conditions.json`) |
| **Wächter** (`alerts/watcher.py`) | mehrere Kategorien je Lauf, eigene Regeln je Kategorie, neue Regel `drop_pct` (Preissturz gegen die Hochwasser-Marke), Zustand je Kategorie |
| **Konfiguration** | `alerts/alert_config.example.yaml` (Kategorien, Regeln je Kategorie), `alerts/alert_config.ships.yaml` (Beispiel nur Schiffsreisen), `bundling/fx_rates.json` (Wechselkursplätze) |

---

## 2. Gefundene Quellen (live verifiziert)

### Fähren – 17 Kandidaten geprüft, 12 blockiert, 4 funktionsfähig, davon 3 übernommen

| Quelle | Transport | Preis | Verfügbarkeit | Preisbasis |
|---|---|---|---|---|
| `ferryhopper_mcp` (`https://mcp.ferryhopper.com/mcp`) | MCP/HTTP | `expectedPrice.totalPriceInCents` (Cent) | `hasCabin/hasVehicles/hasPets/hasETicket` | **je Person** (Passagierzahl wird nicht ausgewertet, Kabinenklassen je Kabine) |
| `trvl_ferries` (trvl-Router, `intent=search_ground`, `type=ferry`) | MCP/stdio | `result.routes[].price` + `currency` (EUR) | Abfahrts-/Ankunftszeit, `freshness` | **je Person** (kein Passagierparameter in der Ground-Suche) |
| `finnlines_ferry` (Finnlines-GraphQL) | HTTP | `chargeTotal` (Cent) | `isAvailable` je Abfahrt | **je Person, linear belegt** (1 → 17,60 €, 2 → 35,20 €, 4 → 70,40 €) |

Blockiert mit wörtlichen Fehlern: Transitland `401 {"error":"Unauthorized"}` · Resrobot `400 errorCode="API_PARAM"` ·
`api.transit.rest` DNS-Fehler · Searoutes `403 {"message":"Forbidden"}` · Eckerö-Magento `200` mit leerem Body ·
DFDS `200 {"dates":{},"offerDates":[]}` (kein Preisfeld) · Tallink `200 …"trips":{}` · Finnlines ohne Browser-User-Agent
`403 WAFForbiddenException` · Direct Ferries `404` · Flix/Irish Ferries `404` (HTML) · P&O `403 Microsoft-Azure-Application-Gateway` ·
Viking Line `403` (Bot-Wall) · OpenSeaMap/MarineTraffic nur Positionsdaten, keine Preise.

### Kreuzfahrten – 18 Kandidaten geprüft, 7 blockiert, 4 mit Fehler, 2 übernommen

| Quelle | Transport | Preis | Verfügbarkeit | Preisbasis |
|---|---|---|---|---|
| `hal-cruises` (Holland America Line, öffentliche Solr-Suche) | HTTP | `price_EUR_RESTRICTED` = günstigster buchbarer Kabinenpreis **inkl. Steuern**, je Person | `soldOut`, `departDate/arrivalDate/duration` | **je Person** (Site-Kennung „priceUnit: per Person“) |
| `rcl-cruises` (Royal Caribbean/Celebrity, CLI-Wrapper `providers/cruise_rcl.py`) | CLI | `pricing.invoice.{cruiseFare, subtotal, taxesAndFees, total}` | Fahrten, Kabinen, `refundability` | **je Person** (Gegenprobe 1/2/3 Erw. → 561,15 / 696,30 / 1.060,45 USD) |

Blockiert mit wörtlichen Fehlern: Siloah-MCP `404 "Not found"` (Worker nicht mehr ausgeliefert) ·
Cruise-Itinerary-MCP `401 "Sign in to Cruise Itinerary…"` · MSC `401 Unauthorized` · Costa `400 "Required header 'agencyid' not specified"` ·
Hapag-Lloyd `Security Check` · Viking Line `404` · TUI/AIDA TLS-/DNS-Fehler · Expedia `429 "Provisioned request rate has been exceeded"` ·
Kayak/HolidayCheck/Check24/Cruise1 nur HTML · Amadeus `404 Resource Not found` · Google Travel Cruises `404` · CruiseMapper `404`.

---

## 3. Die abweichenden Buchungsbedingungen – und wie die Logik damit umgeht

Schiffsreisen folgen **nicht** denselben Regeln wie Flüge und Hotels. Die sieben Bedingungen stehen in
`bundling/ship_conditions.json` (S1–S7) und werden in jeder Ausgabe mitzitiert:

| ID | Bedingung | Folge für den Vergleich |
|---|---|---|
| S1 | Kreuzfahrtpreise sind **Personenpreise für die ganze Reise** (Kabine + Nächte an Bord) | Für die Reisenächte wird **kein Hotel** gerechnet – sonst wäre die Variante systematisch zu teuer |
| S2 | Ob Verpflegung/Getränke enthalten sind, hängt von Kabinenkategorie und Board-Option ab; **All-Inclusive ist eine Option, nicht der Standard** | Ein „All-Inclusive“-Preis darf nicht mit „Hotel plus Verpflegung“ gleichgesetzt werden, solange die Board-Optionen nicht vergleichbar sind |
| S3 | Hafengebühren, Steuern, Trinkgelder, Ausflüge können **zusätzlich** anfallen | Der ausgewiesene Endpreis kann unter dem zahlbaren Betrag liegen → die Ausgabe nennt die Preisart (Kabinenpreis) |
| S4 | Kreuzfahrten meist erst **ab zwei Personen** | Bei 1 Person wird die Variante als „nicht vergleichbar (Mindestbelegung)“ gekennzeichnet |
| S5 | Storno-/Umbuchungsbedingungen sind **strenger** als bei Einzeltickets | Ein nominell billigerer Kreuzfahrtpreis kann bei Datumsänderung teurer werden als Flug plus Hotel |
| S6 | Fährpreise je **Fahrzeug** und/oder je Person | Ein Fahrzeugtarif deckt die ganze Gruppe ab und darf **nicht** noch einmal mit der Personenzahl multipliziert werden |
| S7 | Eine Fähre ersetzt eine **Flugstrecke**, nicht das Hotel | Die Variante benennt, ob die Fähre Zubringer (Hotel nötig) oder Ersatz (kein Hotel) ist |

**Was die Quellen tatsächlich liefern (belegt):** Keine keyless Quelle liefert echtes All-Inclusive – alle liefern
**Kabinenpreis inklusive Steuern**; Getränke, Ausflüge, Spa und Internet sind ausdrücklich Aufpreis
(`potentialBeveragePackage=false`, `included[].type="premium"`, `taxesAndFeesBundled=true`, `taxesAndFeesCombined_EUR=true`).
Das System liest diese Felder (`taxes_included`, `all_inclusive`, `drinks_included`) und gibt sie je Angebot aus.

**Währungsschutz:** Die Kreuzfahrtquelle rechnet in USD, Flüge und Hotels in EUR. Ohne **belegten** Wechselkurs wird
**nicht** umgerechnet; die Ausgabe weist die Währungsabweichung aus und kennzeichnet den Vergleich als
„Größenordnung“. Belegte Kurse können in `bundling/fx_rates.json` (Kurs + Quelle + Stand) eingetragen werden.

---

## 4. Die neuen Bündel-Varianten

| Variante | Rechnung |
|---|---|
| `cruise_only` | Kreuzfahrt (Endpreis inkl. Steuern) × Personen – **ohne Hotel**, weil die Nächte an Bord sind (S1) |
| `cruise_plus_flight` | Anreise zum Abfahrtshafen (Flug) × Personen + Kreuzfahrt |
| `flight_ferry_hotel` | Flug × Personen + Fähre + Hotel × Nächte (Fähre als Zubringer zu einem Inselziel, S7) |

Beispiel aus dem Testlauf (Palma, 2 Personen, 3 Nächte):
`separate_roundtrip` 320,41 € · `flight_ferry_hotel` 393,77 € (Fähre 36,68 €/Person, Quelle Ferryhopper) –
die Fähre ersetzt die Flugstrecke, nicht das Hotel.

---

## 5. Schiffsreisen im Preis-Alarm

Der Wächter kann mehrere Kategorien gleichzeitig überwachen, jede mit eigenen Regeln
(`alerts/alert_config.ships.yaml` als Vorlage):

```yaml
request:
  categories: [ferries, cruises]
rules_by_category:
  ferries:
    budget: 120.0
    budget_scope: total
  cruises:
    budget: 600.0
    budget_scope: per_person
    drop_pct: {enabled: true, percent: 15}
```

Live-Beispiel (Wächterlauf über beide Kategorien):
```
ALARM (ferries/budget): Preis 36.68 EUR (gesamt: 73.36) liegt unter/auf dem Budget 120.0 EUR
ALARM (cruises/budget): Preis 554.0 EUR (je Person: 554.0) liegt unter/auf dem Budget 600.0 EUR
```
Der Verlauf wird je Kategorie getrennt geführt, die Hochwasser-Marke (Basis für die Regel `drop_pct`) ebenfalls –
so kann ein Preissturz bei Kreuzfahrten erkannt werden, ohne dass Flüge und Fähren sich gegenseitig die
Statistik vermischen.
