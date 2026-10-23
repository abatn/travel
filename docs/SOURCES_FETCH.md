# Quellen-Fetch: verifizierte Meta-Such-Provider für Flüge und Hotels

**Stand:** 21.10.2026, Testfenster 15:47–18:30 UTC
**Testroute Flüge:** `BER → FCO`, Abflug `2026-10-31`, Rückflug `2026-11-01`, 1 Erw., Economy
(+ Preisbasen-Gegenprobe mit 2 Erw.)
**Testroute Hotel:** `Rome (IT)`, Check-in `2026-10-31`, Check-out `2026-11-01`, 2 Erw., 1 Zimmer, EUR
(+ Preisbasen-Gegenprobe mit 3 Nächten)

**Regeln eingehalten:** Websuche ausschließlich für *Recherche* (Repos, Endpunkte, Lizenzen, Aktivität,
Preisbasen-Dokumentation). **Keine** Preise per Web ermittelt – alle Preisangaben stammen aus echten
Tool-/HTTP-Antworten. Nichts unter `/home/batnini/mimo-agents/harness/` geändert. Keine bestehenden
MCP-Server deinstalliert (7 neue Server **hinzugefügt**).

**Artefakte:**
* Maschinenlesbare Registry: `/home/batnini/mimo-agents/providers/registry.candidates.json` (33 Quellen: 20 `ok`, 7 `blocked`, 6 `error`)
* Rohantworten/Testskripte: `/tmp/opencode/providers-2026-10-21/` (`mcpcall.py`, `verify_all.sh`, `<name>*.json`)
* Testclient: `/tmp/opencode/providers-2026-10-21/mcpcall.py` (stdio **und** Streamable-HTTP, JSON-RPC 2.0)

---

## 1. Ergebnisübersicht

### 1.1 Flugquellen

| Quelle | Kategorie | Key nötig | Erreichbar | Endpreis-/Steuerfeld | Lizenz | letzte Aktivität | Testbeleg |
|---|---|---|---|---|---|---|---|
| **maqami-travel** | flights | **nein** | ✅ | **ja: `pricing.display.total` + `.taxes` + `.fees` + `.base`** | MIT | 2026-10-17 | 15 Journeys, `total=369.25 EUR / base=346.22 / taxes=23.03 / fees=0`; 2 Erw. → 738.50 (=2×) |
| trvl | flights | nein | ✅ | nein (nur `all_in_cost` = Preis + **Gepäck**) | PolyForm Noncommercial 1.0.0 | 2026-10-19 | `count=12`, `completeness=partial` (queried 13 / succeeded 8), Google-Flights-Cooldown |
| skiplagged | flights | nein | ✅ (429/1015 unter Burst) | nein (Steuerfeld nur im *Hotel*-Tool) | Anbieterdienst (kein Quellcode) | 2026-10-21 | `price.amount=208 USD`, `pagination.totalAvailable=300` |
| octotrip-flights | flights | nein | ✅ | nein (dafür `baggage`) | MIT | 2026-10-04 | 6 Ergebnisse, `price=252.34 EUR`, `gate=Kissandfly.com`, 15-min-Gültigkeit |
| alice-flights (REST) | flights | nein | ✅ | nein (nur `totalPrice`) | MIT | 2026-09-22 | HTTP 200, `totalPrice=679/431 USD`, `pricingDetails` je Passagiertyp; Sabre + CrazyLama |
| easygroupflights | flights | nein | ✅ | nein | MIT | 2026-10-13 | „Prices are per person", `€289.31`, 10 Fares, `offer_id` 30 min gültig |
| flights-gf | flights | nein | ✅ | nein | keine Lizenzdatei | 2026-10-12 | `itineraries[0].price=312 EUR`, `cheapest_price=312` |
| googleflights-local | flights | nein | ✅ | nein | MIT | 2026-08-31 | `count=2`, `cheapest_price=312 EUR` (identische Datenbasis wie flights-gf) |
| pricewin | flights | nein | ✅ | nein | MIT | 2026-10-17 | 2-Schritt: `sessionId` → `status=completed`, 26 Hin-/21 Rückflüge, USD |
| flyan | flights | nein | ✅ | **nein – nur Grundpreis** | MIT | 2026-10-19 | `price=29.32 EUR` (= Ryans `farfnd`-Grundtarif) |
| fli | flights | nein | ✅ | – | MIT | 2026-09-20 | `{"success":true,"flights":[],"count":0}` → **0 Treffer** |
| google-flights | flights | nein | ❌ | – | ISC (npm 1.0.3) | 2026-04-17 | `Error: No flight data found in response — Google may have changed the response format` |
| ignav | flights | **ja** | ❌ | – | n/a | 2026-10-21 | HTTP 401 `api_key_required: MCP tool calls require an Ignav account` |
| gondola | flights | **ja** | ❌ | – | n/a | 2026-10-21 | 401 `insufficient_scope` – *„Sign in to Gondola to use this tool"* (trotz anonymem `tools/list`) |
| letsfg | flights | **ja** | ❌ | – | n/a | 2026-10-21 | 401 `unauthorized` – OAuth-Refresh/Connect-Flow |
| flightclaw | flights | **ja** | ❌ | – | n/a | 2026-10-21 | 401 Unauthorized (leerer Body), OAuth per E-Mail-Code |
| mcp-flight-search | flights | **ja** (SerpApi) | ❌ | – | MIT | 2026-10-15 | `Set SERP_API_KEY to your SerpApi key (serpapi.com) to search flights.` |
| kiwi-tequila (HTTP) | flights | **ja** | ❌ | – | n/a | 2026-10-21 | Demo-Key → `{"error_code":401,"message":"Unauthorized"}`; ohne Key → 403 |
| weekendflights | flights | **ja** (Pro) | ⚠️ | nein | n/a | 2026-10-21 | `combo=sat-mon` → `{"error":"pro_required"}`; gratis nur `fri-sun` (46/52 Wochenenden) |
| a2bflight | flights | nein | ⚠️ Cache | nein | n/a | 2026-10-21 | `checked=2026-10-21`, Abflug `2026-11-07` statt angefragtem Datum |
| aplusz-flight-fares | flights | nein | ⚠️ Cache | nein | n/a | 2026-10-21 | `{"error":"unknown_destination","to":"FCO"}` + „cheapest observed fare" |
| mubboo-flights | flights | nein | ⚠️ | – | n/a | 2026-10-21 | Tools: `find_airports`, `prepare_flight_search`, `get_service_info` – *„no live fares"* |

### 1.2 Hotelquellen

| Quelle | Kategorie | Key nötig | Erreichbar | Endpreis-/Steuerfeld | Lizenz | letzte Aktivität | Testbeleg |
|---|---|---|---|---|---|---|---|
| **rome-hotel-taxes** | hotels | nein | ✅ | **ja: `total` + `tax` + `fees` + `base_price`** (pro Ratenzeile) | projektintern (lokales Python) | 2026-10-21 | `{"total":90.2,"tax":19.11,"base_price":71.09,"currency":"EUR","channel":"www.booking.com"}` |
| **maqami-travel** (Hotels) | hotels | nein | ✅ | **ja: `retailRate.total[]` + `retailRate.taxesAndFees[]` (mit `included`)** | MIT | 2026-10-17 | `total=1248.16 EUR`, `taxesAndFees=[{"included":false,"description":"RESORT","amount":20}]` |
| **callstay** | hotels | nein | ✅ | **ja: `total_all_in` + `fees[]` mit `included_in_total`** | n/a (Dienst) | 2026-10-21 | `total_all_in=317.98 EUR`, `fees=[{25.19,included:true},{14.98,included:false}]`, `due_at_property=14.98` |
| stays | hotels | nein | ✅ | Teil: `includes_taxes_and_fees` (false) + `cancellation_kind` | MIT | 2026-08-24 | 3 Hotels `display_price` 66/105/81 EUR; Detailraten USD mit `includes_taxes_and_fees:false` |
| pricewin (Hotels) | hotels | nein | ✅ | nein (kein tax/fee-Feld), aber `freeCancellationDeadline` | MIT | 2026-10-17 | 136 Hotels, Preise je OTA (booking/traveloka/tripcom/airbnb) in USD |
| bookresorts | hotels | nein | ✅ | Anbieter-Summary: *„stay totals in USD with taxes & fees"* (kein Feld) | n/a (Dienst) | 2026-10-21 | 15/109 Hotels, `total_price_usd=132.38`, `free_cancellation_available`, `free_cancellation_until=2026-10-28` |
| pilotplans-hotels | hotels | nein | ✅ | nein | n/a (Dienst) | 2026-10-21 | 3 Hotels, `price=649.52 EUR` + `coordinates`, Raten USD mit `refundable` |
| bluepillow-hotels | hotels | **ja** (anonym zur Laufzeit) | ✅ | Steuer nur im OTA-Deeplink (`TotalPrice/TotalTax/TotalFee`) | n/a (Dienst) | 2026-10-21 | 19 Properties, 3–4 OTAs je Hotel, `get_anonymous_key` → `pk_anon_…` (120/min, 60000/day) |
| getmyhotels | hotels | nein | ⚠️ | nein | n/a (Repo 404) | 2026-10-21 | nur **2** Hotels für Rom, Preis laut Anbieter *„indicative"* |
| hotelscasa | hotels | nein | ⚠️ | nein | keine Lizenzdatei | 2026-09-19 | 10 Hotels, *„from EUR 60 per night"* (Katalogpreise, keine Datumsparameter) |
| stayingapi | hotels | **ja** | ❌ | – | MIT | 2026-08-25 | 401 `missing_api_key` – *„An OAuth Bearer access token is required."* |

---

## 2. Kernbefund für die Normalisierung

### 2.1 Flug: erstmals ein keyless Provider mit explizitem Steuerfeld

`maqami-travel` (`post_flights_rates`) ist der **einzige** getestete, kostenlose, keyless Anbieter,
der für Flüge Steuern **als eigene Position** ausweist:

```json
"pricing": { "display": { "total": 369.25, "currency": "EUR", "base": 346.22, "taxes": 23.03, "fees": 0 } }
```

Damit ist die im Projekt offene Evaluator-Lücke „Steuer-/Endpreisstatus nicht belegt → höchstens 0,75"
für Flüge **schließbar** – ohne Key, ohne Registrierung, ohne Kreditkarte.

### 2.2 Preisbasis (der zweite, teuerste Fehlerpunkt)

| Quelle | Preisbezug | Beleg |
|---|---|---|
| **maqami-travel** | **Summe für alle Passagiere** | 1 Erw. `total=369.25 EUR` → 2 Erw. `total=738.50 EUR` (exakt 2×) |
| **skiplagged** | **Summe für alle Passagiere** | 1 Erw. `208 USD` → 2 Erw. `416 USD` (exakt 2×) |
| **octotrip-flights** | **Summe für alle Passagiere** | 1 Erw. `252.34 EUR` → 2 Erw. `≈ 2×` |
| **alice-flights (REST)** | **Summe für alle Passagiere** | 1 ADT `431 USD` → 2 ADT `868 USD` (`pricingDetails[].totalPrice=434` je ADT) |
| **trvl** | **pro Person** (Gesamt = Preis × Personen) | Werkzeug-Doku *„Flights are priced per person"*; CLI rechnet selbst `cheapest * adults` |
| **flights-gf** | Summe für alle Passagiere (Tool-Doku) | *„Prices are totals for all passengers"* |
| **easygroupflights** | **pro Person** (explizit) | Antworttext: *„Prices are per person."* |
| **pricewin (Flug)** | je Richtung getrennt | `outboundFlights[].price=90 USD`, `returnFlights[].price=292 USD` (kein Rundtrip-Wert) |
| **flyan** | Grundpreis Einzelflug | `29.32 EUR` = Ryans `farfnd`-Grundtarif, **ohne** Steuern |
| **stays** (Hotel) | Zimmerpreis **pro Nacht** | `display_price` × Nächte; Detailraten kommen unabhängig von `currency` in **USD** |
| **callstay** (Hotel) | `nightly` / `total` / `total_all_in` getrennt | 1 Nacht: `nightly=306`, `total=306` |
| **pricewin (Hotel)** | **nicht eindeutig belegt** | 1 Nacht `164.18 USD` vs. 3 Nächte `611.28 USD` (nicht 3×) → Summe des Aufenthalts mit tagesspezifischen Raten wahrscheinlich, **nicht** als Pro-Nacht belegt |
| **maqami (Hotel)** | Gesamtpreis des Aufenthalts | 1 Nacht `1245.46 EUR` vs. 3 Nächte `3697.38 EUR` (≈ 3×) |

**Regel für die Registry:** jedes Provider-Objekt braucht ein Feld `price_basis` ∈
`per_passenger | trip_total | per_night | stay_total | per_leg | unknown` – ohne dieses Feld darf kein
Anbieterwert als Endpreis im Harness verwendet werden.

### 2.3 Währung

* **EUR-fähig (keine Umrechnung nötig):** maqami-travel, octotrip-flights, callstay, easygroupflights,
  flights-gf, googleflights-local, pilotplans-hotels (nur im Suchergebnis), stays (mit `currency`-Parameter).
* **USD-zwang (Umrechnung nötig):** skiplagged, pricewin (Flug **und** Hotel), alice-flights, bookresorts,
  pilotplans-Raten, getmyhotels.
* **Gemischt:** trvl (USD *oder* EUR je Provider), stays (Suche EUR / Detailraten USD),
  pilotplans (Suche EUR / Raten USD).
* **Projekt-Regel:** eigene Umrechnung ist im Harness nicht zulässig (trvl rechnet fest 25/28) –
  USD-Quellen eignen sich daher nur als *Preisvergleichsindikator*, nicht als Preisbasis.

### 2.4 Stops

| Quelle | Feld |
|---|---|
| maqami-travel | `segments[].stopCount` (je Richtung) |
| trvl | `flights[].stops` + `legs[].direction` + `warnings[]` (`standard`/`virtual-interline`/`nonstop`/`one-stop`) |
| skiplagged | `flights[].layovers` + `flights[].attributes[]` |
| octotrip-flights | `results[].stops`, `results[].is_direct`, `results[].tags[]` |
| flights-gf / googleflights-local | `itineraries[].stops` / `results[].stops` (+ `stops_label`) |
| pricewin | `outboundFlights[].stops`, `stopCities[]` |
| alice-flights | indirekt: Anzahl `segments[].flights[]` je Richtung |
| flyan / easygroupflights / weekendflights | **kein** Stops-Feld (Text bzw. Einzelflug) |

### 2.5 Koordinaten

* **mit Koordinaten:** stays (`lat`/`lng`, CLI `latitude`/`longitude`), rome-hotel-taxes (`lat`/`lng`),
  pilotplans-hotels (`coordinates.latitude/longitude`), pricewin-Hotel (`detail.geoInfo.latitude/longitude`),
  bluepillow-hotels (im Text: `'(41.8915954, 12.5106293)'`), MAQAMI-Hotels (`get_data_hotel`: lat/lng).
* **ohne Koordinaten (nur IATA/Ortsname):** alle Flugquellen, bookresorts, callstay, getmyhotels, hotelscasa.

### 2.6 Stornobedingung

| Quelle | Feld |
|---|---|
| maqami-travel (Hotel) | `rates[].cancellationPolicies.cancelPolicyInfos[].cancelTime / .amount / .type`, `refundableTag` |
| maqami-travel (Flug) | `offers[].terms.refundable`, `terms.refundFee.amount`, `terms.changeFee.amount` |
| rome-hotel-taxes | nur indirekt über die OTA-Deeplinks (`ext_price_total`/`ext_price_tax`) – **kein** eigenes Feld |
| stays | `rooms[].rates[].cancellation_kind` (`free_until`/`non_refundable`), `cancellation_free_until`, `cancellation_description` |
| callstay | `rooms[].refundable`, `rooms[].cancellation_policy` |
| bookresorts | `hotels[].free_cancellation_available`, `options[].refundable`, `options[].free_cancellation_until` |
| pricewin (Hotel) | `rateOptions[].policy.isRefundable`, `.freeCancellationDeadline`, `.cancellationPolicyText`; Tool `get_cancellation_policy` |
| pilotplans-hotels | `offers[].refundable` (Bool) |
| bluepillow-hotels | „free cancellation" im Fließtext je Angebot |
| getmyhotels | `hotels[].cheapestRoom.cancellation` (Freitext, z. B. „Non-refundable") |

---

## 3. Detailabschnitte je Quelle

> Testkommandos nutzen den Projekt-Client `/tmp/opencode/providers-2026-10-21/mcpcall.py`
> (`stdio "<cmd>" <tool> <json>` bzw. `http "<url>" <tool> <json>`).
> Der Client protokolliert `initialize` → `notifications/initialized` → `tools/list` → `tools/call` (JSON-RPC 2.0).

### 3.1 maqami-travel (NEU, HTTP, keyless) – **Empfehlung 1 für Flüge + Hotel**

* Endpunkt: `https://mcp.maqami.co/` · Registry: `io.github.negm17111995/maqami-travel` v1.0.9
* Lizenz MIT · Repo `github.com/negm17111995/mcp-server` · letzter Commit 2026-10-17 · Release v1.0.9 (2026-10-07)
* Kein API-Key, kein Login, kein Konto („The endpoint accepts connections without authentication.")

**Installation (neu):**
```bash
cd /home/batnini/mimo-agents/flight-agent
claude mcp add --transport http maqami-travel https://mcp.maqami.co/
```

**Flugtest:**
```bash
python3 mcpcall.py http https://mcp.maqami.co/ post_flights_rates \
 '{"legs":[{"origin":"BER","destination":"FCO","date":"2026-10-31","direction":"OUTBOUND"},
           {"origin":"FCO","destination":"BER","date":"2026-11-01","direction":"INBOUND"}],
   "adults":1,"currency":"EUR","country":"DE"}'
```
Antwort (gekürzt):
```json
{"searchUrl":"https://book.maqami.co/flights/journeys?adults=1&...&outOrigin=BER&outDestination=FCO&outDate=2026-10-31&inDate=2026-11-01&currency=EUR",
 "data":[{"journeys":[{"journeyKey":"fea3ba37cbb1ca9d","isCheapest":true,
   "totalDuration":{"iso8601":"PT4H20M","minutes":260},
   "segments":[{"arrivalTime":"2026-10-31T16:55:00","carrier":{"marketingCode":"U2","marketingName":"easyJet"},
                "departureTime":"2026-10-31T14:50:00","originCode":"BER","destinationCode":"FCO",
                "direction":"OUTBOUND","stopCount":0}],
   "cheapestOffer":{"expiration":"2026-10-21T16:05:43.058Z",
     "pricing":{"display":{"total":369.25,"currency":"EUR","base":346.22,"taxes":23.03,"fees":0}},
     "baggage":{"hasCarryOnBag":false,"hasCheckedBag":false,
                "included":[{"bagType":"personal","pieces":1,"size":"45X36X20CM","passengerType":"ALL"}]},
     "fare":{"family":"Light","mixedCabin":false},
     "terms":{"changeable":true,"refundable":true,
              "changeFee":{"amount":106,"currency":"EUR"},"refundFee":{"amount":59,"currency":"EUR"}}},
   "offers":[{"pricing":{"display":{"total":516.08,"currency":"EUR","base":493.05,"taxes":23.03,"fees":0}}, ...}]}]}]}
```
**Preisbasen-Gegenprobe:** `adults=1` → `total=369.25 EUR`; `adults=2` → `total=738.50 EUR` (= exakt 2×).
→ **Trip-Gesamtpreis für alle Passagiere.**

**Hoteltest:**
```bash
python3 mcpcall.py http https://mcp.maqami.co/ post_hotels_rates \
 '{"hotelIds":["lp327d0"],"occupancies":[{"adults":2,"childrenAges":[]}],
   "checkin":"2026-10-31","checkout":"2026-11-01","currency":"EUR","guestNationality":"IT"}'
```
Antwort (gekürzt):
```json
{"data":[{"hotelId":"lp327d0","roomTypes":[{"offerId":"mqo1_…","supplier":"MAQAMI","supplierId":2,
 "rates":[{"occupancyNumber":1,"name":"Junior Suite Diocletian View","adultCount":2,"childCount":0,
   "boardType":"BI","boardName":"Breakfast Included",
   "retailRate":{"total":[{"amount":1248.16,"currency":"EUR"}],
                 "taxesAndFees":[{"included":false,"description":"RESORT","amount":20,"currency":"EUR"}]},
   "cancellationPolicies":{"cancelPolicyInfos":[{"cancelTime":"2026-10-26 10:00:00","amount":1191.99,
                                                "currency":"EUR","type":"amount","timezone":"GMT"}],
                           "hotelRemarks":[],"refundableTag":"RFN"},
   "offerRetailRate":{"amount":1248.16,"currency":"EUR"},"rateType":"package"}]}]}]}
```
**Preisbasen-Gegenprobe:** `post_hotels_min_rates` 1 Nacht → `1245.46 EUR`, 3 Nächte → `3697.38 EUR` (≈ 3×)
→ **Gesamtpreis des Aufenthalts.**

**Einschränkungen / Belastbarkeit**
* Antworten sind sehr groß (ein `offerId` ist ein ~2 kB signierter String) → Antwort kürzen
  (`tools/trim_json.py`-Muster) und `maxRatesPerHotel`/`limit` setzen.
* Angebote haben `expiration` (hier 30–40 min) – Preis ist eine Momentaufnahme mit Ablaufzeit.
* Rate-Limit: nicht dokumentiert; Endpoint trägt `cacheScope: public` – bei Parallelaufrufen watchen.
* Suchwerkzeuge (`get_data_hotels*`) liefern **ohne** Preis – erst `post_hotels_rates`/`post_hotels_min_rates`.
* MAQAMI ist eine Booking-Plattform (Buchung/Preishaltung über `book.maqami.co` + `post_rates_prebook`/`post_flights_verify`).

---

### 3.2 trvl (bestehend, MCP-stdio + CLI) – Hauptpfad Flüge

* Endpunkt: `/home/batnini/.local/bin/trvl mcp` · CLI `trvl flights BER FCO 2026-10-31 --return 2026-11-01 --format json`
* Lizenz **PolyForm Noncommercial 1.0.0** (nur nicht-kommerziell!) · Repo `github.com/MikkoParkkola/trvl`
* letzter Commit 2026-10-19 · Release v1.27.0 (2026-10-10) · `serverInfo: trvl v1.27.0`

**Test:**
```bash
trvl flights BER FCO 2026-10-31 --return 2026-11-01 --format json
```
Antwort (gekürzt):
```json
{"success":true,"count":12,"trip_type":"round_trip","flights":[
  {"price":208,"currency":"USD","duration":3115,"stops":2,"provider":"skiplagged","fare_type":"round_trip",
   "warnings":["standard","nonstop"],
   "legs":[{"departure_airport":{"code":"BER"},"arrival_airport":{"code":"FCO"},
            "departure_time":"2026-10-31T22:20:00+01:00","arrival_time":"2026-11-01T00:30:00+01:00",
            "airline":"Ryanair","direction":"outbound"},
           {"departure_airport":{"code":"FCO"},"arrival_airport":{"code":"BER"},
            "departure_time":"2026-11-01T06:10:00+01:00","arrival_time":"2026-11-03T07:55:00+01:00",
            "airline":"Ryanair","direction":"inbound"}],
   "booking_url":"https://skiplagged.com/flights/BER/FCO/2026-10-31/2026-11-01?..."}],
 "provider_statuses":[
   {"id":"native_roundtrip:google_flights","status":"rate_limited",
    "error":"google flights quota refusal (code 13): upstream provider rate-limited or temporarily unavailable"},
   {"id":"outbound:kiwi","status":"ok","results":15},
   {"id":"outbound:ryanair","status":"ok","results":1},
   {"id":"outbound:wizzair","status":"failed",
    "error":"wizzair: status 400, validationCodes [InvalidMarket]: wizzair declined the request"},
   {"id":"outbound:skiplagged","status":"skipped","error":"one-way Skiplagged skipped; queried once as a native round-trip instead"}],
 "completeness":{"state":"partial","queried":13,"succeeded":8,
   "missing":["native_roundtrip:google_flights","outbound:google_flights","outbound:wizzair","inbound:google_flights","inbound:wizzair"]}}
```
**Fehlerbild heute:** `google_flights` dauerhaft `rate_limited` (Cooldown), `wizzair` → `InvalidMarket`
(die Route ist kein Wizz-Markt), `skiplagged` je nach Last `rate_limited`/`circuit_broken` →
`completeness.state = "partial"`. „Günstigster Tarif" heißt immer „günstigster Tarif **innerhalb der
antwortenden Provider**".
**Weiterer Befund:** der `inbound`-Leg landet am `2026-11-03` bei Rückkehr `2026-11-01`
→ Rückflugdatum je Leg selbst prüfen, nicht aus dem Suchparameter übernehmen.
**Lizenz-Hinweis:** PolyForm Noncommercial – kommerzielle Nutzung ist untersagt.

---

### 3.3 stays (bestehend, MCP-stdio) – Hauptpfad Hotel

* Endpunkt: `/home/batnini/.local/bin/stays mcp` · `serverInfo: Google Hotels MCP Server v4.1.1`
* Lizenz MIT · Repo `github.com/him229/stays` · letzter Commit 2026-08-24 · PyPI `stays` 0.1.1

**Test:**
```bash
python3 mcpcall.py stdio "/home/batnini/.local/bin/stays mcp" search_hotels \
 '{"query":"hotels in Rome","check_in":"2026-10-31","check_out":"2026-11-01","adults":2,"currency":"EUR","max_results":3}'
```
```json
{"success":true,"count":3,"hotels":[
 {"name":"Hotel Roma Tor Vergata","entity_key":"ChgIz5iys9Wrp931ARoLL2cvMXRtZzhwYm0QAQ","kgmid":"/g/1tmg8pbm",
  "display_price":66,"currency":"EUR","star_class":4,"overall_rating":3.7,"review_count":3024,
  "amenities":["BEACH_ACCESS","GYM","INDOOR_POOL","PET_FRIENDLY","POOL","RESTAURANT"],
  "lat":41.8662019,"lng":12.6301635},
 {"name":"Appia Park Hotel","display_price":105,"currency":"EUR","star_class":4,"lat":41.8390255,"lng":12.5502162},
 {"name":"All Time Relais & Sport Hotel","display_price":81,"currency":"EUR","star_class":4,"lat":41.8083132,"lng":12.4468283}]}
```
Detailraten:
```json
{"rooms":[{"name":"Standard Room","rates":[
  {"provider":"Booking.com","price":151,"currency":"USD","breakfast_included":false,
   "includes_taxes_and_fees":false,
   "deeplink_url":"https://www.google.com/aclk?sa=l&ai=DChsSEwjh35WowMuXAxWHhf0FHVWSAzsYACICCAEQARoCd2Y&...",
   "cancellation_kind":"free_until","cancellation_free_until":"2026-10-30",
   "cancellation_description":"Free cancellation until Oct 30 12:59 AM"},
  {"provider":"Expedia.de","price":128,"currency":"USD","includes_taxes_and_fees":false,
   "cancellation_kind":"free_until","cancellation_free_until":"2026-10-30"}]}]}
```
**Fehlerbild / Grenzen:** `includes_taxes_and_fees` ist durchgängig `false`; die Detailraten kommen
**unabhängig von `currency` in USD** (Suche EUR 66 vs. Detailrate 151 USD) → Währung je Wert ausweisen,
nicht mischen. `hotel_class` wird nicht durchgesetzt (Sterne selbst prüfen). Google-Hotels-Cooldown
möglich → dann frischer CLI-Prozess `stays search … --format json`.

---

### 3.4 rome-hotel-taxes (bestehend, lokales Python-MCP) – Steuerpositionen für Hotels

* Endpunkt: `python3 /home/batnini/mimo-agents/rome-2star/worker_c/rome_hotel_taxes_mcp.py`
* `serverInfo: rome-hotel-taxes v1.0.0` · projektintern, kein Key, keine Lizenz (lokales Skript)

**Test:**
```bash
python3 mcpcall.py stdio "python3 /home/batnini/mimo-agents/rome-2star/worker_c/rome_hotel_taxes_mcp.py" \
 search_hotels_with_itemized_taxes \
 '{"location":"Rome","check_in":"2026-10-31","check_out":"2026-11-01","adults":2,"rooms":1,"currency":"EUR","max_hotels":2}'
```
```json
{"query":{"location":"Rome","check_in":"2026-10-31","check_out":"2026-11-01","nights":1,"adults":2,"currency":"EUR"},
 "source":"Google Hotels batchexecute RPC AtySUc (keyless, no booking.com request)",
 "hotels":[{"name":"ibis Roma Fiera","stars":3,"rating":4.2,"lat":41.8221475,"lng":12.394640299999999,
  "rates":[{"fees":17.35,"tax":17.35,"total":70.75,"currency":"EUR","provider":"ibis Roma Fiera",
            "channel":"www.bluepillow.de","base_price":36.05,"booking_url":null},
           {"total":76.0,"currency":"EUR","channel":"www.stayforlong.de","base_price":76.0,"booking_url":null},
           {"currency":"EUR","total":90.2,"tax":19.11,"channel":"www.booking.com","base_price":71.09,
            "booking_url":"/travel/lodging/clk?...&ext_price_total%3D90.20%26ext_price_tax%3D19.11%26xfc%3DEUR..."}]},
  {"name":"Ibis Styles Vintage Hotel Rome","stars":4,"rating":3.7,"lat":41.837959999999995,"lng":12.5942779,
   "rates":[{"total":76.0,"currency":"EUR","channel":"www.stayforlong.de","base_price":76.0},
            {"total":100.0,"tax":22.73,"currency":"EUR","channel":"www.booking.com","base_price":77.27}]}]}
```
**Warum das funktioniert:** booking.com liefert bei Direktabruf HTTP 202 (AWS-WAF-Challenge). Der Server
parst stattdessen die **von Google indexierten** OTA-Zahlen aus dem deeplink-Query
(`ext_price_total` / `ext_price_tax` / `hpa_d_tax` / `mpf`) – booking.com selbst wird nie kontaktiert.
**Grenze:** Stornobedingung ist nur indirekt (über die OTA-Deeplinks/Channel) vorhanden.

---

### 3.5 skiplagged (bestehend, MCP-HTTP, keyless)

* Endpunkt: `https://mcp.skiplagged.com/mcp` · `serverInfo: @skiplagged/mcp v0.0.4` · offizieller Anbieter-MCP
* Lizenz: nicht veröffentlicht (Anbieterdienst, kein Quellcode) · Registry: nicht im offiziellen Registry

**Test:**
```bash
python3 mcpcall.py http https://mcp.skiplagged.com/mcp sk_flights_search \
 '{"origin":"BER","destination":"FCO","departureDate":"2026-10-31","returnDate":"2026-11-01",
   "adults":1,"fareClass":"economy","limit":3,"sort":"price"}'
```
```json
{"searchUrl":"https://skiplagged.com/flights/BER/FCO/2026-10-31/2026-11-01",
 "flights":[
  {"type":"FlightCard","id":"BER-FCO-2026-10-31-2026-11-01-trip=FR134,FR4861-W46464-FR2666",
   "airlines":"Ryanair","duration":"2h 10m","layovers":0,"price":{"amount":208,"currency":"USD"},
   "attributes":["standard","nonstop"],
   "deepLink":"https://skiplagged.com/flights/BER/FCO/2026-10-31/2026-11-01?..."},
  {"airlines":"Wizz Air","duration":"12h 25m","layovers":1,"price":{"amount":235,"currency":"USD"},
   "attributes":["virtual-interline","one-stop"]}],
 "pagination":{"totalAvailable":300,"currentlyShowing":3,"offset":0,"limit":3,"hasMoreResults":true}}
```
**Fehlerbild (heute beobachtet):** unter Last `HTTP 429 Too Many Requests` mit Cloudflare-Body
`{"type":"…/cloudflare-1xxx-errors/error-1015/","title":"Error 1015: You are being rate limited…"}`.
Reproduziert zweimal: (1) einmaliger Burst → nach **45 s** Pause wieder `rc=0`;
(2) nach mehreren Aufrufen in kurzer Zeit → **~4 Minuten** Sperre (zwischenzeitlich meldete
`claude mcp list` „✗ Failed to connect"), danach wieder `rc=0` mit
`price.amount=212 USD`, `layovers=0`. → **starkes Per-IP-Rate-Limit**; im Harness Abstand einhalten
(nicht mehrfach im selben Lauf pollen) und `provider_statuses`/`circuit_broken` auswerten.
**Steuer:** Schema-Sweep über alle 10 Tools: `taxesAndFeesInDollars` und `totalPriceInDollars` existieren
**ausschließlich in `sk_hotel_details`** (Hotels) – im Flugtool nicht.

---

### 3.6 octotrip-flights (bestehend, MCP-HTTP, keyless)

* Endpunkt: `https://mcp.octotrip.app/flights/mcp` · `serverInfo: OctoTrip Flights v1.30.0`
* Lizenz MIT · Repo `github.com/octotrip/flights` · letzter Commit 2026-10-04 · Registry `app.octotrip/flights`

**Test:**
```bash
python3 mcpcall.py http https://mcp.octotrip.app/flights/mcp search \
 '{"origin":"BER","destination":"FCO","departure_date":"2026-10-31","return_date":"2026-11-01",
   "adults":1,"trip_class":"Y","currency":"EUR","locale":"en"}'
```
```json
{"results":[{"airline":"Ryanair","airline_code":"FR","is_direct":true,"stops":0,"total_duration_minutes":260,
   "price":252.34,"currency":"EUR","baggage":"No checked bag, Cabin bag: 0 piece(s)",
   "gate":"Kissandfly.com","booking_url":"https://mcp.octotrip.app/flights/r/01a15f27-…?u=800000",
   "link_type":"affiliate","tags":["convenient_ticket","direct"],
   "affiliate_disclosure":"This link contains affiliate attribution. …"}],
 "total":6,"total_available":6862,
 "validity":"Results and booking links are valid for approximately 15 minutes.",
 "origin_resolved":{"iata":"BER", …}, "destination_resolved":{"iata":"FCO", …},
 "query":{"origin":"BER","destination":"FCO","departure_date":"2026-10-31","return_date":"2026-11-01",
          "adults":1,"children":0,"infants":0,"trip_class":"Y","currency":"EUR","locale":"en"}}
```
**Einschränkungen:** Affiliate-Links; ~15 min Gültigkeit; Rate-Limit 1 rps (Burst 5); blockiert
`curl`-User-Agent (`{"error":"ua_blocked"}`) – MCP-Client mit Browser-UA funktioniert.

---

### 3.7 alice-flights (NEU, reine HTTP-API, keyless)

* Endpunkt: `POST https://api.alice.co.il/flights/search` · Lizenz MIT
  (`github.com/blackrabbit-travel/alice-flights-mcp`, letzter Commit 2026-09-22)
* **Wichtig:** der offizielle MCP-Weg `https://mcp.alice.co.il/mcp` ist **nicht** keyless
  (401 `invalid_token`, OAuth 2.0 mit Browser-Consent) – keyless ist nur die REST-API.

**Test:**
```bash
curl -s -X POST https://api.alice.co.il/flights/search -H 'Content-Type: application/json' \
 -d '{"flightClass":"tour","passengers":{"ADT":1},"segments":[
      {"index":1,"from":{"code":"BER","type":"city"},"to":{"code":"FCO","type":"city"},"departure":"2026-10-31"},
      {"index":2,"from":{"code":"FCO","type":"city"},"to":{"code":"BER","type":"city"},"departure":"2026-11-01"}]}'
```
```json
{"distributorTypeToResultsAmount":[{"type":"CrazyLama","amount":4},{"type":"Sabre","amount":4}],"success":true,
 "result":{"best":[{"segments":[{"flights":[{"departureDate":"2026-10-31T15:05:00",
    "departureAirportLocation":"BER","departureAirportTerminal":"1",
    "arrivalDate":"2026-10-31T16:30:00","arrivalAirportLocation":"ZRH","arrivalAirportTerminal":"",
    "operatingAirline":"LX","marketingAirline":"LX","flightNumber":967,
    "firstLuggageIncluded":false,"firstFreeLuggageIncluded":false,"secondFreeLuggageIncluded":false,
    "seatsNumber":9,"cabin":"ECONOMY","brand":"EconomyBasic","fareBasisCode":"LETNHBU3/DXEU","duration":85.0}]}],
   "deepLink":"https://www.alice.co.il/a/f/v2/?api-version=2.0&affiliateId=…",
   "totalPrice":679.0,"pqId":"c3cfaa49-258d-4970-a4bf-b0bbdddc4586",
   "totalPriceInFlowCurrency":679.0,"flowCurrencyCode":"USD",
   "pricingDetails":[{"passengerType":"ADT","totalPrice":431.0}],
   "duration":500.0,"flags":{"airportChange":false,"nextDayArrival":false,"redEye":false}}],
  "cheapest":[{"totalPrice":431.0,"flowCurrencyCode":"USD","pricingDetails":[{"passengerType":"ADT","totalPrice":431.0}],
               "duration":1480.0}],
  "shortest":[ … ]}}
```
**Preisbasis:** `adults=1` → `totalPrice=431.0`; `adults=2` → `totalPrice=868.0` (`pricingDetails` 434/ADT)
→ **Trip-Gesamtpreis für alle Passagiere**.
**Belastbarkeit:** laut Repo 10 Suchen/Minute und 200/Tag pro IP; HTTP 200 bei 8 Ergebnissen
(4 Sabre + 4 CrazyLama). Bonusfelder: `seatsNumber`, `firstFreeLuggageIncluded`, `fareBasisCode`.

---

### 3.8 easygroupflights (NEU, MCP-HTTP, keyless)

* Endpunkt: `https://mcp.easygroupflights.com/mcp` · `serverInfo: easygroupflights v2.1.0`
* Lizenz MIT · Repo `github.com/codeblockssk/easygroupflights-mcp` · letzter Commit 2026-10-13
  · Registry `com.easygroupflights/easygroupflights`

**Installation (neu):**
```bash
claude mcp add --transport http easygroupflights https://mcp.easygroupflights.com/mcp
```

**Test:**
```bash
python3 mcpcall.py http https://mcp.easygroupflights.com/mcp egf_search_flights \
 '{"origin":"BER","destination":"FCO","departure_date":"2026-10-31","return_date":"2026-11-01","passengers":1,"limit":3}'
```
```
Fares BER → FCO, 2026-10-31 returning 2026-11-01, 1 traveller. Prices are per person.

 1. €289.31 — Ryanair, direct out, direct back
    out 31.10.2026 22:20 · back 01.11.2026 09:55
    flights FR134 / FR41
    offer_id of_hZDBasMwEET_Zc-ypV3LsSQovQV6NbkFEyRbToRdx0gyppT-e0loe-…
 2. €319.98 — Ryanair, direct out, direct back …
 3. €347.31 — Ryanair, EasyJet, direct out, direct back …
Showing 1–3 of 10. Each offer_id lasts 30 minutes.
```
`egf_get_offer`:
```
289.31 EUR per person — Ryanair, flights FR134 / FR41.
Departs 2026-10-31T22:20, returns 2026-11-01T09:55.
Book: https://www.pelikan.sk/sk/let/80000/1/2/detail/?tabIdentifier=…
This offer is valid until 2026-10-21T16:31:59.000Z; after that, search again.
```
**Einschränkungen:** Antwort ist **Fließtext**, kein JSON → Parser nötig; Verkaufsplattform
`pelikan.sk`; kein Steuerfeld.

---

### 3.9 callstay (NEU, MCP-HTTP, keyless) – Hotel-Endpreis

* Endpunkt: `https://callstay.com/api/mcp` · `serverInfo: callstay v0.1.0`
* Lizenz: nicht veröffentlicht (gehosteter Dienst) · Registry `com.callstay/hotels`

**Installation (neu):**
```bash
claude mcp add --transport http callstay https://callstay.com/api/mcp
```

**Test:**
```bash
python3 mcpcall.py http https://callstay.com/api/mcp search_stays \
 '{"query":"Rome","destination":"Rome","checkin":"2026-10-31","checkout":"2026-11-01","adults":2,"rooms":1,"currency":"EUR","max_results":3}'
```
```json
{"understood":"A room for 2 guests in Rome, Italy from Oct 31 to Nov 1","needs":[],
 "destination":"Rome, Italy",
 "stay":{"checkin":"2026-10-31","checkout":"2026-11-01","adults":2,"rooms":1,"children_ages":[]},
 "dates_assumed":false,"inventory":"live","market_total":19511,"notice":null,
 "results":[{"slug":"hotel-viminale","name":"Hotel Viminale","city":"Rome","stars":4,"rating":10,
   "review_count":2152,"nightly":306,"total":306,"currency":"EUR",
   "url":"https://callstay.com/rooms/hotel-viminale?checkin=2026-10-31&checkout=2026-11-01&adults=2&rooms=1&utm_source=mcp-anonymous"},
  {"slug":"maalot-roma-small-luxury-hotels-of-the-world","name":"Maalot Roma …","stars":5,"nightly":832,"total":832,"currency":"EUR"}]}
```
`price_stay` (der eigentliche Endpreis):
```bash
python3 mcpcall.py http https://callstay.com/api/mcp price_stay \
 '{"slug":"hotel-viminale","checkin":"2026-10-31","checkout":"2026-11-01","adults":2,"rooms":1,"currency":"EUR"}'
```
```json
{"slug":"hotel-viminale","name":"Hotel Viminale",
 "stay":{"checkin":"2026-10-31","checkout":"2026-11-01","adults":2,"rooms":1,"nights":1},
 "status":"priced",
 "rooms":[{"room_key":"3383458.bi.n","room_name":"Double or Twin STANDARD","board":"Breakfast Included",
   "refundable":false,"cancellation_policy":null,"pay_at_property":false,"currency":"EUR",
   "nightly":303,"total":303,"total_all_in":317.98,"due_at_property":14.98,
   "fees":[{"description":"Taxes and Fees","amount":25.19,"currency":"EUR","included_in_total":true},
            {"description":"Taxes and Fees","amount":14.98,"currency":"EUR","included_in_total":false}],
   "fees_unknown":false,
   "room":{"description":"…","size":"16 m²","max_occupancy":2,"beds":[{"quantity":1,"type":"Queen bed"}],
           "amenities":["Coffee/tea maker","Minibar", …]},
   "book_url":"https://callstay.com/rooms/hotel-viminale?…#rooms"}]}
```
**Bemerkenswert:** `total_all_in` (Endpreis) **und** `fees[]` mit `included_in_total` – die Aufteilung
„im Endpreis enthalten" vs. „im Hotel zu zahlen" (`due_at_property`) ist maschinenlesbar.
**Grenze:** keine Koordinaten im Antwortumfang, `market_total=19511` deutet auf große Coverage hin.

---

### 3.10 bookresorts (NEU, MCP-HTTP, keyless) – Hotel mit Stornodaten

* Endpunkt: `https://www.bookresorts.com/api/br/mcp` · `serverInfo: BookResorts hotel booking v1.0.0`
* Lizenz: nicht veröffentlicht (gehosteter Dienst) · Registry `com.bookresorts/hotel-booking`

**Installation (neu):**
```bash
claude mcp add --transport http bookresorts https://www.bookresorts.com/api/br/mcp
```

**Test:**
```bash
python3 mcpcall.py http https://www.bookresorts.com/api/br/mcp search_hotels \
 '{"destination":"Rome","checkin":"2026-10-31","checkout":"2026-11-01","adults":2,"rooms":1,"min_stars":3}'
```
```json
{"summary":"15 of 109 available hotels in Rome for 2026-10-31 → 2026-11-01 (1 nights), cheapest first. Prices are stay totals in USD with taxes & fees, from BookResorts.",
 "hotels":[{"hotel_id":"lp1a06d1","name":"B&B Hotel Roma Fiumicino Aeroporto Fiera 1","city":"Fiumicino","country":"IT",
   "stars":3,"guest_rating":8.6,"reviews":5183,"total_price_usd":132.38,"per_night_usd":132,
   "free_cancellation_available":true,"boards":["Room Only","Breakfast Included"],
   "page":"https://www.bookresorts.com/hotel/lp1a06d1?ci=2026-10-31&co=2026-11-01&adults=2"},
  {"hotel_id":"lp2d0a0","name":"Hotel Cristoforo Colombo","city":"Rome","stars":4,"guest_rating":8.4,
   "reviews":12370,"total_price_usd":140.55,"per_night_usd":141,"free_cancellation_available":true}]}
```
`get_hotel`:
```json
{"hotel":{"hotel_id":"lp2d0a0","name":"Hotel Cristoforo Colombo","stars":4,"guest_rating":8.4,
  "amenities":["Fitness facilities","WiFi available","Free WiFi","Parking", …]},
 "stay":{"checkin":"2026-10-31","checkout":"2026-11-01","nights":1,"rooms":1,"guests":[{"adults":2,"children":[]}]},
 "rooms":[{"room":"Twin Room","size_sqft":172,"sleeps":2,"options":[
   {"option_id":"VOGHQs-lNZ","board":"Room Only","refundable":false,"free_cancellation_until":null,
    "total_price_usd":148.4,"per_night_usd":148},
   {"option_id":"naZGhi6ACM","board":"Breakfast Included","refundable":true,
    "free_cancellation_until":"2026-10-28T12:00:00.000Z","total_price_usd":160.29,"per_night_usd":160}]}]}
```
**Grenze:** USD-only (kein `currency`-Parameter im Schema) → im Projekt keine eigene Umrechnung zulässig;
Steuerstatus nur über das Anbieter-Summary belegt, nicht als Feld.

---

### 3.11 pilotplans-hotels (NEU, MCP-HTTP, keyless)

* Endpunkt: `https://mcp.pilotplans.com/mcp` · `serverInfo: pilot-hotels v1.0.0`
* Lizenz: nicht veröffentlicht (gehosteter Dienst) · Registry `com.pilotplans/hotels`

**Installation (neu):**
```bash
claude mcp add --transport http pilotplans-hotels https://mcp.pilotplans.com/mcp
```

**Test:**
```bash
python3 mcpcall.py http https://mcp.pilotplans.com/mcp search_hotels \
 '{"location":"Rome","check_in":"2026-10-31","check_out":"2026-11-01","guests":2,"rooms":1,"currency":"EUR","limit":3}'
```
```json
{"hotels":[{"id":"eyJrIjoiaH90ZWwiLCJob3RlbElkIjoibHAyYmQ5ZiIsImNoZWNraW4iOiIyMDI2LTEwLTMxIiwiY2hlY2tvdXQiOiIyMDI2LTExLTAxIn0…",
   "name":"Hotel Artemide","starRating":4,"price":649.52,"currency":"EUR",
   "coordinates":{"latitude":41.900813,"longitude":12.493614},
   "url":"https://pilotplans.com/stays/hotel-artemide-lp2bd9f?checkInDate=2026-10-31&checkOutDate=2026-11-01&rooms=2&currency=EUR",
   "propertyType":"Hotel","address":"Via Nazionale 22","city":"Rome","country":"IT","rating":9.6,"reviewCount":2637},
  {"name":"The Hive Hotel","starRating":4,"price":275.2,"currency":"EUR","coordinates":{…}},
  {"name":"Hotel Nazionale","starRating":4,"price":420.93,"currency":"EUR","coordinates":{…}}],
 "currency":"EUR","returned":3,"has_more":true,"next_offset":3}
```
`get_room_rates_for_hotel`:
```json
{"hotelId":"lp2bd9f","offers":[{"offerId":"eyJrIjoib2ZmZXIi…","roomName":"Comfort Double",
  "board":"Breakfast Included","refundable":true,"price":729.86,"currency":"USD"}]}
```
Der `offerId` ist ein base64-Payload (`{"k":"offer","hotelId":"lp2bd9f","price":729.86,"currency":"USD","provider":"NUITEE","checkin":"2026-10-31","checkout":"2026-11-01","occupancies":[{"adults":2,"children":[]}]}`) –
maschinenlesbar, aber **ohne** Steuerpositionen. **Grenze:** Währungswechsel Suche(EUR) → Raten(USD).

---

### 3.12 bluepillow-hotels (NEU, MCP-HTTP, Key anonym zur Laufzeit)

* Endpunkt: `https://mcp.b2a.bluepillow.com/` · `serverInfo: bluepillow-hotels v1.1.0`
* Lizenz: nicht veröffentlicht (gehosteter Dienst) · Registry `com.bluepillow/hotels`
* **Key:** `key_required=true`, aber der Key ist **anonym und ohne Registrierung** zur Laufzeit abrufbar.

**Installation (neu):**
```bash
claude mcp add --transport http bluepillow-hotels https://mcp.b2a.bluepillow.com/
```

**Test (3 Schritte):**
```bash
python3 mcpcall.py http https://mcp.b2a.bluepillow.com/ get_anonymous_key '{"label":"opencode-test","agent":"mimo-agents"}'
```
```json
{"key":"pk_anon_db6b427d4c74d1904e9ad7a3755bb8254242a0d6",
 "rate_limit":{"requests_per_minute":120,"requests_per_day":60000}}
```
```bash
python3 mcpcall.py http https://mcp.b2a.bluepillow.com/ resolve_destination \
 '{"api_key":"pk_anon_…","name":"Rome","country":"IT","type":"city"}'
# -> Rome, Italy (id=dest_589df9597c00cb10c8da9663, type=city, confidence=1.0, accomodations_count=10000)

python3 mcpcall.py http https://mcp.b2a.bluepillow.com/ search_stays \
 '{"api_key":"pk_anon_…","location":{"type":"destination_id","value":"dest_589df9597c00cb10c8da9663"},
   "dates":{"check_in":"2026-10-31","check_out":"2026-11-01"},"guests":{"adults":2,"rooms":1}}'
```
```
Found 19 properties (total_estimate=21), more available with cursor=…
  - Villa Luzzatti Hostel - Rome, IT (41.8915954, 12.5106293); rating=3.0 (658 ratings, 79 readable reviews), stars=-, 3 OTAs; id=prop_5f29316767a9d11a88b3ebb5
        AVAILABILITY: live for requested dates (5 operator(s))
          LIVE BEST: 56.1/night via HostelWorld — 56.1 total — free cancellation — 3 rooms left
          OTHER OFFER: 120.12/night via TripCom — 120.12 total — 1 room left
          OTHER OFFER: 112.32/night via Agoda — 112.32 total — free cancellation — 1 room left
          OTHER OFFER: 143.55/night via Expedia — 143.55 total — free cancellation — 5 rooms left
        from 56.1/night (USD, live for the requested dates) · link: https://www.bluepillow.com/search/5f29316767a9d11a88b3ebb5?…
```
`check_property_availability` liefert die **Steuerwerte im Buchungs-Deeplink**:
```
- OFFER: €216.77/night via Agoda — €216.77 total — breakfast included — 1 room left
  book: https://www.bluepillow.com/skippy?…redirecturl=https%3A%2F%2Fwww.agoda.com%2Fpartners%2F…%26TotalPrice%3D216.77%26TotalTax%3D19.71%26TotalFee%3D0.00%26mcur%3DEUR…
- OFFER: €217.04/night via Expedia — €217.04 total — 1 room left
  book: …expedia.com…%26mpb%3D18.64%26mpa%3D186.40…
```
**Grenzen:** (1) `api_key` muss bei **jedem** Tool-Aufruf mitgegeben werden (Registry-Key ist nicht
konfigurierbar) → der Agent muss `get_anonymous_key` einmal vorab aufrufen und den Key mitführen;
(2) Antwort ist **Fließtext**, kein JSON → Parser nötig; (3) `location` muss ein
`{type,value}`-Objekt sein (freier Ortsname → HTTP 400 `invalid_request`).

---

### 3.13 pricewin (bestehend, MCP-HTTP, keyless) – Flüge **und** Hotels

* Endpunkt: `https://mcp.price.win/mcp` · `serverInfo: pricewin v1.19.0`
* Lizenz MIT · Repo `github.com/PriceDotWin/pricewin-agent-plugin` · letzter Commit 2026-10-17
* Quelle laut Anbieter: Booking.com, Agoda, Traveloka, Trip.com, Google Flights (keine Partnerschaften)

**Flugtest (2 Schritte):**
```bash
python3 mcpcall.py http https://mcp.price.win/mcp search_flights_live \
 '{"origin":"BER","destination":"FCO","departureDate":"2026-10-31","returnDate":"2026-11-01","adults":1}'
# -> {"sessionId":"2456a996-adce-4ba9-b909-4f081482ed60","status":"pending", …}
sleep 12
python3 mcpcall.py http https://mcp.price.win/mcp poll_flight_results '{"sessionId":"2456a996-…"}'
```
```json
{"status":"completed","totalOutbound":26,"totalReturn":21,
 "outboundFlights":[{"airline":"U2","airlineCode":"U2","flightNumber":"2984",
   "departure":{"airport":"BER","city":"BER","time":"14:50","date":"2026-10-31"},
   "arrival":{"airport":"FCO","city":"FCO","time":"16:55","date":"2026-10-31"},
   "duration":125,"stops":0,"stopCities":[],"price":90,"currency":"USD","cabin":"economy",
   "bookingUrl":"https://www.price.win/go/_8DkmN0s9om"}],
 "returnFlights":[{"airline":"U2","flightNumber":"5082",
   "departure":{"airport":"FCO","time":"09:50","date":"2026-11-01"},
   "arrival":{"airport":"BER","time":"12:05","date":"2026-11-01"},
   "duration":135,"stops":0,"price":292,"currency":"USD","cabin":"economy"}]}
```
**Hoteltest (2 Schritte):**
```bash
python3 mcpcall.py http https://mcp.price.win/mcp search_hotels_live \
 '{"city":"Rome","checkIn":"2026-10-31","checkOut":"2026-11-01","adults":2,"rooms":1}'
# -> {"sessionId":"tb8bdYFH91mM.dEZC62k2","status":"pending","tier":"tier1","fxRates":{"USD":1,"EUR":0.89075}, …}
sleep 15
python3 mcpcall.py http https://mcp.price.win/mcp poll_search_results \
 '{"sessionId":"tb8bdYFH91mM.dEZC62k2","nights":1,"limit":3}'
```
```json
{"status":"completed","totalHotels":136,"bookingStatus":"completed","agodaStatus":"completed",
 "travelokaStatus":"completed","tier":"tier1","fxRates":{"USD":1,"VND":25846.19,"EUR":0.89075},
 "hotels":[{"name":"Holiday Inn Rome - Eur Parco Dei Medici by IHG","stars":4,"rating":8.1,"reviewCount":3108,
   "location":"Viale Castello della Magliana, 65, Rome, Lazio, 00148, Italy",
   "prices":{"booking":{"price":164.18,"currency":"USD","url":"https://www.price.win/go/BemGWzQLLYK"},
             "traveloka":{"price":146.85,"currency":"USD","url":"https://www.price.win/go/H4PJfbkOx1A"},
             "tripcom":{"price":123,"currency":"USD","url":"https://www.price.win/go/pheMJdr55jT"}},
   "urls":{"booking":"https://www.price.win/go/BemGWzQLLYK", …}}]}
```
`get_ota_hotel_detail` (liefert Koordinaten + Storno):
```json
{"ota":"booking","propertyUrl":"https://www.booking.com/hotel/it/holidayinnrome.html","found":true,
 "detail":{"propertyId":80042,"source":"booking","name":"Holiday Inn Rome - Eur Parco Dei Medici by IHG",
   "geoInfo":{"latitude":41.8231913679073,"longitude":12.4121911371933},
   "roomTypes":[{"roomName":"Standard Room","roomId":8004221,"maxOccupancy":2,"bedType":"2 full beds",
     "price":{"amount":164.18,"currency":"USD","crossedOutPrice":null},"cancellation":"Non-refundable",
     "mealPlan":"Breakfast US$22\nDinner US$34","paymentInfo":"Prepayment","availableRooms":12,
     "rateOptions":[{"price":164.18,"policy":{"isRefundable":false,"freeCancellationDeadline":null,
        "cancellationPolicyText":"Non-refundable","paymentTiming":"PREPAY","paymentPolicyText":"Prepayment"}},
       {"price":184.43,"policy":{"isRefundable":true,"freeCancellationDeadline":"2026-10-29 23:59:59 +0100",
        "cancellationPolicyText":"Free cancellation until 2026-10-29 23:59:59 +0100"}}]}]}}
```
**Grenzen:** 2-Schritt-Flow; USD; **kein** Steuer-/Gebührenfeld (Feld-Sweep über die gesamte Antwort:
keine `tax*`/`fee*`-Felder); Preisbasen Hotel nicht eindeutig belegt (1 Nacht 164.18 USD vs. 3 Nächte
611.28 USD → nicht 3×).

---

### 3.14 flights-gf / googleflights-local (bestehend / NEU, MCP-stdio, keyless)

```bash
# flights-gf (bestehend)
python3 mcpcall.py stdio "uvx --from git+https://github.com/FredrikBakken/flights-mcp flights-mcp" \
 search_flights '{"from_airport":"BER","to_airport":"FCO","departure_date":"2026-10-31","return_date":"2026-11-01","adults":1,"seat":"economy","currency":"EUR","max_results":3}'
# googleflights-local (NEU)
claude mcp add googleflights-local -- uvx --from git+https://github.com/altunoren/googleflights-mcp googleflights-mcp
python3 mcpcall.py stdio "uvx --from git+https://github.com/altunoren/googleflights-mcp googleflights-mcp" \
 search_flights '{"from_airport":"BER","to_airport":"FCO","departure_date":"2026-10-31","return_date":"2026-11-01","currency":"EUR","max_results":2}'
```
```json
{"itineraries":[{"price":312,"currency":"EUR","airlines":["SWISS"],"stops":1,
   "total_duration_minutes":730,"total_duration":"12h 10m",
   "departure":"2026-10-31T07:15:00","arrival":"2026-10-31T19:25:00",
   "legs":[{"from_airport":{"code":"BER","name":"Berlin Brandenburg Airport"},
            "to_airport":{"code":"ZRH","name":"Zurich Airport"},
            "departure":"2026-10-31T07:15:00","arrival":"2026-10-31T08:45:00",
            "duration_minutes":90,"plane_type":"Airbus A321neo"}, …],
   "carbon":{"emission_grams":192000,"typical_on_route_grams":142000,"difference_percent":35}}],
 "count":3,"cheapest_price":312,"currency":"EUR",
 "google_flights_url":"https://www.google.com/travel/flights/search?tfs=…&curr=EUR","truncated":true}
```
`googleflights-local` liefert dieselbe Datenbasis in etwas anderer Form:
```json
{"query":{"from":"BER","to":"FCO","departure_date":"2026-10-31","trip":"round-trip","seat":"economy",
          "currency":"EUR","return_date":"2026-11-01"},
 "count":2,"cheapest_price":312,
 "results":[{"airlines":["SWISS"],"price":312,"currency":"EUR","stops":1,"stops_label":"1 aktarma",
   "departure":"2026-10-31 07:15","arrival":"2026-10-31 19:25","duration_minutes":185,
   "legs":[{"from":"BER","to":"ZRH","departure":"2026-10-31 07:15","arrival":"2026-10-31 08:45",
            "duration_minutes":90,"plane_type":"Airbus A321neo"}],
   "carbon_grams":125000,"carbon_vs_typical_grams":142000}]}
```
**Grenzen (beide):** kein Steuerfeld; **der Rückflug erscheint nicht als eigenes Feld** (nur der Hinweg
ist ausgewiesen) → für Rundtrips ein Auswertungsrisiko; `flights-gf` hat keine Lizenzdatei im Repo,
`googleflights-local` ist MIT (Stand 2026-08-31).

---

### 3.15 flyan / fli / google-flights (bestehend, nicht als Preisquelle geeignet)

**flyan** (Ryanair, Grundpreis):
```bash
python3 mcpcall.py stdio "flyan-mcp" find_flights '{"from_airport":"BER","to_airport":"FCO","from_date":"2026-10-31","to_date":"2026-11-01"}'
```
```json
{"result":[{"flight_number":"FR134","from":"BER","from_name":"Berlin Brandenburg","to":"FCO",
  "to_name":"Rome Fiumicino","to_country":"it","departure":"2026-10-31T22:20:00",
  "arrival":"2026-11-01T00:30:00","price":29.32,"currency":"EUR"}]}
```
Gegenprobe Ryans `farfnd`-API liefert denselben Grundtarif → **kein Endpreis**.

**fli** (0 Treffer):
```bash
python3 mcpcall.py stdio "fli-mcp" search_flights '{"origin":"BER","destination":"FCO","departure_date":"2026-10-31","return_date":"2026-11-01","passengers":1,"currency":"EUR"}'
```
```json
{"success":true,"flights":[],"count":0,"trip_type":"ROUND_TRIP"}
```
Hinweis: der Passagier-Parameter heißt `passengers` (nicht `adults`); `adults` → Pydantic-Fehler
`Unexpected keyword argument [type=unexpected_keyword_argument]`.

**google-flights** (heute defekt):
```bash
python3 mcpcall.py stdio "npx -y google-flights-mcp" search_flights '{"origin":"BER","destination":"FCO","departureDate":"2026-10-31","returnDate":"2026-11-01","cabinClass":"economy","adults":1,"sortBy":"price","maxResults":3}'
```
```
isError=true
Error: No flight data found in response — Google may have changed the response format
```

---

### 3.16 Blockierte Quellen (Fehlerbilder im Wortlaut)

| Quelle | Kommando | Fehlerbild |
|---|---|---|
| ignav | `mcpcall.py http https://ignav.com/mcp search_flights …` | `HTTPError 401 Unauthorized: {"jsonrpc":"2.0","id":2,"error":{"code":-32001,"message":"api_key_required: MCP tool calls require an Ignav account. Cloud MCP clients can connect with OAuth at https://ignav.com/mcp. Local clients can create a free account at https://ignav.com/signup to get 1,000 free requests, then send the API key as X-Api-Key or Authorization: Bearer YOUR_API_KEY."}}` |
| gondola | `mcpcall.py http https://mcp.gondola.ai/mcp search_flights …` | `isError=true`, `_meta.mcp/www_authenticate: Bearer realm="mcp.gondola.ai" … error="insufficient_scope" … scope="mcp:read"`, Text: *„Authentication is required. Sign in to Gondola to use this tool."* |
| letsfg | `mcpcall.py http https://letsfg.co/mcp … tools` | `HTTPError 401 Unauthorized: {"error":"unauthorized","message":"Authentication required: this request carried no valid credential. If you are an MCP client connected with OAuth, refresh your access token; …"}` |
| stayingapi | `mcpcall.py http https://mcp.stayingapi.com/mcp … tools` | `HTTPError 401 Unauthorized: {"error":{"type":"authentication_error","code":"missing_api_key","message":"An OAuth Bearer access token is required.","retryable":false}}` |
| flightclaw | `mcpcall.py http https://mcp.flightclaw.com/mcp … tools` | `HTTPError 401 Unauthorized:` (leerer Body) → OAuth-Sign-in per E-Mail-Code |
| mcp-flight-search | `mcpcall.py stdio "uvx --from mcp-flight-search mcp-flight-search" search_flights_tool …` | `isError=true`: *„Error executing tool search_flights_tool: Set SERP_API_KEY to your SerpApi key (serpapi.com) to search flights."* |
| kiwi-tequila | `curl -H 'apikey: <Demo-Key>' https://api.tequila.kiwi.com/v2/search?…` | `{"error_code":401,"message":"Unauthorized"}`; ohne Header `{"error_code":403,"message":"'apikey' header is required"}` |
| weekendflights | `mcpcall.py http https://weekendflights.app/mcp weekend_prices '{"origin":"BER","dest":"FCO","combo":"sat-mon"}'` | `{"error":"pro_required","locked":true,"trigger":"sat-mon","detail":"combo \"sat-mon\" is Pro data. Free data is fri-sun, economy, any stops, any passenger mix, no time window."}` (gratis: `fri-sun`, 46/52 Wochenenden, EUR) |
| a2bflight | `mcpcall.py http https://mcp.a2bflight.com/mcp route_fares '{"from":"BER","to":"FCO"}'` | liefert Cache: `"checked":"2026-10-21","depart_date":"2026-11-07"` (nicht das angefragte Datum), keine Datumsabfrage möglich |
| aplusz | `mcpcall.py http https://aplusz.app/mcp find_cheapest_fare '{"from":"BER","to":"FCO"}'` | `{"error":"unknown_destination","to":"FCO","hint":"Send an uppercase IATA city code. Covered codes: https://aplusz.app/v1/cities"}` |
| mubboo-flights | `mcpcall.py http https://mubboo.flights/api/mcp … tools` | Tools `find_airports`, `prepare_flight_search`, `get_service_info` – *„Search preparation only; no live fares, availability, booking or payment."* |

---

## 4. Neu installierte MCP-Server (Konfiguration ohne Codeänderung)

Alle im **Projekt-Scope** `/home/batnini/mimo-agents/flight-agent` registriert
(`claude mcp list` → alle 17 Server „✓ Connected"); kein bestehender Server wurde entfernt.

| Name | `claude mcp add`-Befehl | Lizenz | Aktivität |
|---|---|---|---|
| `maqami-travel` | `claude mcp add --transport http maqami-travel https://mcp.maqami.co/` | MIT | 2026-10-17 |
| `callstay` | `claude mcp add --transport http callstay https://callstay.com/api/mcp` | n/a | 2026-10-21 |
| `bookresorts` | `claude mcp add --transport http bookresorts https://www.bookresorts.com/api/br/mcp` | n/a | 2026-10-21 |
| `pilotplans-hotels` | `claude mcp add --transport http pilotplans-hotels https://mcp.pilotplans.com/mcp` | n/a | 2026-10-21 |
| `easygroupflights` | `claude mcp add --transport http easygroupflights https://mcp.easygroupflights.com/mcp` | MIT | 2026-10-13 |
| `bluepillow-hotels` | `claude mcp add --transport http bluepillow-hotels https://mcp.b2a.bluepillow.com/` | n/a | 2026-10-21 |
| `googleflights-local` | `claude mcp add googleflights-local -- uvx --from git+https://github.com/altunoren/googleflights-mcp googleflights-mcp` | MIT | 2026-08-31 |

Nicht als MCP registriert, sondern als **HTTP-API** in der Registry geführt:
`alice-flights` → `POST https://api.alice.co.il/flights/search` (der zugehörige MCP-Wert
`https://mcp.alice.co.il/mcp` ist OAuth-pflichtig und wurde **nicht** installiert).

Kontrollausgabe:
```
fli ✓ | stays ✓ | rome-hotel-taxes ✓ | trvl ✓ | google-flights ✓ | skiplagged ✓ | octotrip-flights ✓
pricewin ✓ | flyan ✓ | flights-gf ✓ | maqami-travel ✓ | callstay ✓ | bookresorts ✓
pilotplans-hotels ✓ | easygroupflights ✓ | bluepillow-hotels ✓ | googleflights-local ✓
```

---

## 5. Empfehlung

### 5.1 Aufnehmen (17)

**Flug – Primärpfad**
1. **maqami-travel** – einziger keyless Provider mit **explizitem Steuer-/Gebührenfeld** für Flüge
   (`taxes`, `fees`, `base`, `total`), Trip-Gesamtpreis, EUR, Gepäck, Storno-/Änderungsgebühren,
   Angebots-Ablauf. → **löst die offene Evaluator-Lücke „Steuerstatus" für Flüge.**
2. **trvl** – beste Multi-Provider-Abdeckung (13 Provider abgefragt), Preis-Basis „pro Person" dokumentiert,
   `provider_statuses`/`completeness` als Vollständigkeitsbeleg. (Lizenz: nur nicht-kommerziell!)
3. **octotrip-flights** – EUR ohne Umrechnung, `baggage` für `all_in_cost`, `gate`/`query` auditierbar.
4. **skiplagged** – offizieller Anbieter-MCP, `attributes[]` für die Stopp-Klassifikation, 300 Verbindungen.
5. **alice-flights (REST)** – Sabre-GDS, strukturiertes JSON, `seatsNumber`/Gepäck/Fare-Basis.
6. **easygroupflights** – EUR, Preis pro Person explizit dokumentiert.
7. **flights-gf** + **googleflights-local** – Google-Flights-Basis in EUR (Ersatzweg zu trvls
   `google_flights`-Provider, der dauerhaft im Cooldown ist).
8. **pricewin** – Multi-OTA-Flugvergleich (Agoda + Google Flights) als weiterer Aggregator.

**Hotel – Primärpfad**
9. **rome-hotel-taxes** – Endpreis **+** Steuern **+** Basispreis je Rate, EUR, Koordinaten, kein WAF.
10. **stays** – Koordinaten, Sterne, Bewertung, Detailraten mit `includes_taxes_and_fees`/`cancellation_kind`.
11. **maqami-travel (Hotels)** – `taxesAndFees[]` **mit `included`-Flag** + `cancellationPolicies` + `refundableTag`.
12. **callstay** – `total_all_in` + `fees[]` mit `included_in_total` + `due_at_property`.
13. **pricewin (Hotels)** – 136 Hotels, 4 OTAs, `freeCancellationDeadline`.
14. **bookresorts** – 109 Hotels, Sternefilter, `free_cancellation_until` mit Datum.
15. **pilotplans-hotels** – Koordinaten + Sterne + `refundable`.
16. **bluepillow-hotels** – 16+ Buchungsseiten, Steuern im Deeplink (nur mit Parser).

### 5.2 Nicht aufnehmen (16) – Begründung

| Name | Grund |
|---|---|
| `google-flights` | heute defekt (`No flight data found in response`); zuvor nur Fließtext mit falschem Rückflug |
| `flyan` | nur Grundpreis (29.32 EUR), kein Endpreis, nur Einzelflug |
| `fli` | 0 Treffer (heute erneut bestätigt) |
| `getmyhotels` | nur 2 Beispiel-Hotels für Rom, Preise „indicative" |
| `hotelscasa` | Katalogpreise, keine datumsbezogenen Live-Raten |
| `ignav` | 401 `api_key_required` |
| `gondola` | 401 OAuth trotz anonymem `tools/list` |
| `letsfg` | 401 OAuth |
| `stayingapi` | 401 OAuth (Bearer) |
| `flightclaw` | 401 OAuth (E-Mail-Code) |
| `mcp-flight-search` | SerpApi-Key nötig |
| `kiwi-tequila` | Demo-Key ungültig (401), ohne Key 403 |
| `weekendflights` | nur `fri-sun` gratis, Testroute `sat-mon` = `pro_required` |
| `a2bflight` | nur Cache, keine Datumssuche |
| `aplusz-flight-fares` | nur Cache + `unknown_destination` für FCO |
| `mubboo-flights` | keine Tarife, nur Suchlinks |

### 5.3 Offene Punkte für die Registry-Umsetzung

1. **Pflichtfeld `price_basis`** (siehe 2.2) – ohne dieses Feld darf kein Wert als Endpreis gelten.
2. **Pflichtfeld `tax_status`** ∈ `itemized` (maqami, callstay, rome-hotel-taxes) |
   `flag_only` (stays: `includes_taxes_and_fees`) | `claimed` (bookresorts: nur Anbieter-Summary) |
   `none` (alle übrigen).
3. **Keine eigene Umrechnung** – USD-Quellen (skiplagged, pricewin, alice, bookresorts, pilotplans-Raten)
   nur als Vergleichsindikator, nicht als Preisbasis.
4. **Währung je Wert ausweisen**, nicht mischen (stays: Suche EUR / Detailraten USD;
   pilotplans: Suche EUR / Raten USD; trvl: USD oder EUR je Provider).
5. **Rückflug separat prüfen** – bei flights-gf, googleflights-local und trvl erscheint der Rückflug
   nicht (oder nicht mit dem Suchdatum) als eigenes Feld.
6. **Antwortgröße begrenzen** – maqami (`offerId` ~2 kB, 15 Journeys), pricewin (136 Hotels),
   bluepillow (Fließtext) → `limit`/`maxRatesPerHotel`/`max_results` setzen und kürzen.
7. **Lizenz beachten:** `trvl` = PolyForm Noncommercial (nicht kommerziell einsetzen).
   `flights-gf`, `bookresorts`, `callstay`, `pilotplans`, `bluepillow`, `hotelscasa` haben keine
   veröffentlichte Open-Source-Lizenz → Nutzungsbedingungen des Anbieters prüfen.
8. **Rate-Limits:** skiplagged (Cloudflare 1015), octotrip (1 rps), pricewin (2-Schritt-Latenz),
   alice (10/min, 200/Tag pro IP), bluepillow (120/min, 60000/Tag), trvl/Google (Cooldown 900 s).
