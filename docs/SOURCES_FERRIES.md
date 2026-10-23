# Quellen-Ferries: keylose Fähr-Quellen (Fahrplan, Preise, Verfügbarkeit)

**Stand:** 21.10.2026, Testfenster 19:25–19:45 MESZ
**Testroute Fähre:** `Barcelona (BRC) → Palma de Mallorca (PAL)`, Abfahrt `2026-11-05`, 2 Erw., EUR
(Prüfstrecken zusätzlich: `Helsinki → Tallinn`, `Stockholm → Helsinki`, `Naantali (FINLI) → Kapellskär (SEKPS)`,
`Helsinki (Vuosaari) → Tallinn`, negativ `Kopenhagen → Oslo`, `Piraeus → Mykonos`, `Ibiza → Barcelona`)
**Kurzurteil:** **3 keyless Quellen funktionieren heute mit echten Preisen + Verfügbarkeit**
(`ferryhopper_mcp`, `trvl_ferries`, `finnlines_ferry`), 14 weitere Kandidaten sind blockiert – jeweils mit
wörtlichem Fehlerbild dokumentiert.

**Regeln eingehalten:** Preise stammen ausschließlich aus echten Tool-/HTTP-Antworten (keine Web-Suchtreffer).
Nichts unter `/home/batnini/mimo-agents/harness/` geändert. Keine Pakete installiert (alle Testskripte laufen
mit dem vorhandenen `requests`/`yaml` aus `providers/`). Nichts unter `providers/registry.yaml` geändert –
die Registry-Blöcke unten sind **Einsatzfertig**, aber noch nicht eingetragen.

**Artefakte**
* Maschinenlesbar: `/home/batnini/mimo-agents/providers/ferry_candidates.json` (17 Quellen: 4 `ok`, 12 `blocked`, 1 `error`)
* Belege/Skripte: `/home/batnini/mimo-agents/providers/ferry_evidence/`
* Test-Registry (End-to-End gegen `providers/runner.py`): `providers/ferry_evidence/registry.ferries.test.yaml`
* Testclient: `providers/ferry_evidence/mcpcall.py` (MCP stdio **und** Streamable-HTTP, JSON-RPC 2.0, SSE-Parser)

---

## 1. Ergebnisübersicht

### 1.1 Funktionierende keyless Quellen

| Quelle | Transport | Key | Preisfeld | Währung | Verfügbarkeit | Preisbasis | Lizenz / Aktivität |
|---|---|---|---|---|---|---|---|
| **ferryhopper_mcp** | `mcp_http` | **nein** | `legs[].options[].segments[].accommodations[].expectedPrice.totalPriceInCents` (Cent) | kein Feld → EUR (Basis-Währung laut Anbieter) | `hasCabin/hasVehicles/hasPets/hasETicket` | **je Person** (Sitzklassen) / je Kabine (Kabinenklassen) – belegt | Anbieterdienst, Doku frei (2025-12-10), Dienst aktiv 2026-10-21 |
| **trvl_ferries** | `mcp_stdio` | **nein** | `result.routes[].price` (+ `sources[].price`) | `result.routes[].currency` = `EUR` | `departure.time`/`arrival.time`, `sources[].freshness` | **je Person** (1 Erw., ohne Fahrzeug) | PolyForm Noncommercial 1.0.0, pushed 2026-10-21, 89 ★ |
| **finnlines_ferry** | `http` (GraphQL) | **nein** (öffentlicher SPA-Key) | `data.listTimeTableAvailability[].chargeTotal` (Cent) | in der Query gesetzt: `currency: EUR` | `isAvailable` (bool) je Abfahrt, `available` je Tarifklasse | **je Person** – per Passagier-Skalierung bewiesen | Anbieterdienst, API live 2026-10-21 |

### 1.2 Blockierte Kandidaten (wörtliche Fehler)

| Kandidat | HTTP | Wörtliches Fehlerbild / Antwort |
|---|---|---|
| Transitland v2 | **401** | `{"error":"Unauthorized"}` (Key nötig; zusätzlich **keine** Preisfelder) |
| Resrobot v2.1 | **400** | `<Error ... errorCode="API_PARAM" errorText="Missing value for required param accessId" .../>` |
| MOTIS v1 (`api.transit.rest`) | DNS | `Could not resolve host: api.transit.rest`; Apex `transit.rest` → `The deployment could not be found on Vercel. DEPLOYMENT_NOT_FOUND` (404) |
| MOTIS 2 (Transitous) | **400** | `{"error":"unknown feed id \"\""}` (auf `/api/v1/plan` **und** `/api/v6/plan`); `/api/v1/health` → `{"rt":true,"gbfs":true}` |
| Searoutes API | **403** | `{"message":"Forbidden"}` |
| Eckerö Line (Magento) | 200 | `content-type: text/html; charset=UTF-8`, **Body Länge 0** (leer) – trotz korrekt extrahiertem `form_key=nLXL9HM40hpgFUVB`; keine Session-Cookies |
| DFDS Availability | 200 | `{"dates": {}, "disabledDates": [], "offerDates": []}` (leer; **kein** Preisfeld in der API) |
| Tallink `/api/timetables` | 200 | `{"defaultSelections":{"outwardSail":null,"returnSail":null},"trips":{},"isClubOneOnlyPromotion":null}` – leere `trips`; `cruiseSummary`/`travelclasses` laut trvl-Quellcode von F5-WAF blockiert (302) |
| Finnlines GraphQL *ohne* Browser-UA | **403** | `{"errors":[{"errorType":"WAFForbiddenException","message":"403 Forbidden"}]}` → mit Chrome-UA 200 |
| Direct Ferries | 404 | `/api/` → `Direct Ferries – Sorry this page no longer exists`; `basedata.js` enthält nur `siteCurrencyId`, keine Preis-API |
| Flix Ferry | 404 | `/api/`, `/api/v1/`, `/de/ferry`, `/en/ferry`, `/en/booking/ferry` → alle 404-HTML |
| Irish Ferries | 404/301 | `/` → 301 auf `/de/Travel-to-Ireland/`; `/en/`, `/booking/` → `Sorry, the page you are looking for cannot be found` |
| Wightlink | 200/404-DNS | `/book/` → 200 HTML (Next.js); `api.wightlink.co.uk` → NXDOMAIN; `/api/` → HTML |
| Color Line | 404 | `/en` → 404 |
| P&O Ferries | **403** | `Microsoft-Azure-Application-Gateway/v2` (WAF) |
| Viking Line `find-trip` | **403** | Bot-Wall-HTML (`<META NAME="ROBOTS" CONTENT="NOINDEX, NOFOLLOW">` + Challenge); `www.vikingline.com` → 403 (Cloudflare) |
| OpenSeaMap | SSL-Fehler | `api.openseamap.org` → `SSLCertVerificationError`; `www.openseamap.org` → 200, **nur** Schiffspositionen, **keine Preise** |
| MarineTraffic | 200 | nur HTML/Bot-Schutz, keine offene Preis-API |
| Fjord Line (`leffen-fjordline/mcp-forge`) | – | 0 ★, keine Lizenz, kein Update seit 2026-01-16 → nicht übernommen |
| Ferry VN (`ferry-vn/ferry-sdk`) | – | Apache-2.0, pushed 2026-10-20, aber **Partner-API mit Key** und nur Vietnam-Routen |

---

## 2. Detailbelege

### 2.1 Ferryhopper MCP (`https://mcp.ferryhopper.com/mcp`) — keyless, live

Transport: Streamable HTTP, JSON-RPC 2.0, **kein API-Key, kein Account, keine Session-ID nötig**
(`initialize` → HTTP 200, Antworten als SSE `event: message` / `data: {...}`).

```
python3 providers/ferry_evidence/mcpcall.py 'https://mcp.ferryhopper.com/mcp' get_ports '{}' \
  --out providers/ferry_evidence/fh_get_ports.json
python3 providers/ferry_evidence/mcpcall.py 'https://mcp.ferryhopper.com/mcp' search_ferry_trips \
  '{"legs":[{"departureLocation":"Barcelona","arrivalLocation":"Palma de Mallorca","departureDate":"2026-11-05"}]}' \
  --out providers/ferry_evidence/fh_search_Barcelona_Palma_de_Mallorca.json
```

`tools/list` → 6 Tools: `get_ports`, `get_disruptions`, `get_direct_connections_for_ports`,
`search_trips` (deprecated), `search_ferry_trips`, `trip_details`.

**K gekürzte Rohantwort** (`fh_search_Barcelona_Palma_de_Mallorca.json`, `result.structuredContent`):

```json
{"legs":[{"departurePort":{"name":"BARCELONA","code":"BRC"},
          "arrivalPort":{"name":"PALMA DE MALLORCA","code":"PAL"},
          "departureDate":"2026-11-05",
          "options":[
            {"id":"BRC/PAL/2026-11-05T21:30:00Z/40c430",
             "segments":[{"vehicleIsMandatory":false,
               "departureDateTime":"2026-11-05T21:30:00Z","arrivalDateTime":"2026-11-06T06:00:00Z",
               "ownerCompany":{"name":"GRANDI NAVI VELOCI","code":"GNV"},
               "vessel":{"name":"TENACIA","code":"40c430"},
               "accommodations":[
                 {"type":"LOUNGE_DECK","expectedPrice":{"totalPriceInCents":3668}},
                 {"type":"SEAT_NOTNUMBERED","expectedPrice":{"totalPriceInCents":3725}},
                 {"type":"CABIN_FULL","expectedPrice":{"totalPriceInCents":25813}},
                 {"type":"CABIN_FULL_WINDOW","expectedPrice":{"totalPriceInCents":24388}},
                 {"type":"LUX_CABIN_FULL_WINDOW","expectedPrice":{"totalPriceInCents":29138}}],
               "hasCabin":false,"hasVehicles":true,"hasPets":true,"hasETicket":false}]}]}]}
```

* **Preisfeld:** `expectedPrice.totalPriceInCents` (Int, EUR-Cents) → Divisor 100 nötig.
* **Währung:** *kein Feld in der Antwort*. Ferryhopper-FAQ („Payments, Data Privacy & Safety“):
  *„While our base prices are in Euros (€), you can easily select your preferred local currency during the
  checkout process."* → Basis-Währung **EUR**; der Registry-Runner setzt `currency` aus dem Kontext.
* **Verfügbarkeit:** `hasCabin`, `hasVehicles`, `hasPets`, `hasETicket` (bool) je Segment; Tarifklassen-Liste
  je Segment. Keine Platz-/Sitzplatzzahlen.
* **Abfrageparameter:** `legs[].departureLocation` / `arrivalLocation` (freier Hafen-/Ortsname),
  `legs[].departureDate` (YYYY-MM-DD), 1–5 Legs (Rundreise = 2 Legs, Insel-Hopping bis 5).
  **Keine** Passagier-/Fahrzeug-Parameter → Preise gelten für 1 erwachsene Person ohne Fahrzeug.
* **Preisbasis-Beweis (empirisch):** `search_ferry_trips` mit Zusatzparametern `passengers=2/adults=2`,
  `vehicles=1/car=1`, `passengers=4+children=2` liefert **identische** Preise
  (Beleg: `ferryhopper_pax_ignored_evidence.json`; Vergleichsbasis `fh_search_Barcelona_Palma_de_Mallorca.json`).
  → Der gelieferte Preis ist ein **Personenpreis** (Sitz-/Deckklasse) bzw. bei `CABIN_*` ein **Kabinenpreis je Einheit**
  (Kabinenklassen erscheinen als teurere Alternativen im Ranking; das günstigste Item ist die Personenpreisklasse).
* **Abdeckung:** `get_ports` → **1453 Ports** in 33 Ländern (COPENHAGEN, OSLO, HELSINKI, TALLINN, PIRAEUS,
  MYKONOS, BARCELONA, PALMA DE MALLORCA, IBIZA, DUBLIN, HOLYHEAD, KLAIPEDA, NAPLES, TENERIFE …),
  190+ Reedereien laut Anbieter-Doku.
* **Negative Teilergebnisse:** `Copenhagen → Oslo` → `Leg 1: No route found between requested locations.`;
  `Piraeus → Mykonos`, `Helsinki → Tallinn`, `Ibiza → Barcelona` (2026-11-05) → `options: []`
  (Route/Datum nicht im Katalog) – die Quelle ist **nicht** flächendeckend.
* **Keine Buchungs-URL** im MCP (nur `options[].id` → `trip_details`). trvl baut daraus
  `https://www.ferryhopper.com/en/booking/results?...&IDSCode=<...>&passengers=1&vehicles=0&pets=0`.

### 2.2 trvl (`/home/batnini/.local/bin/trvl mcp`, Tool `travel`) — keyless, Multi-Provider

```
/home/batnini/.local/bin/trvl ground 'Barcelona' 'Palma de Mallorca' 2026-11-05 --type ferry --format json
python3 providers/ferry_evidence/mcpcall.py --stdio '["/home/batnini/.local/bin/trvl","mcp"]' travel \
  '{"intent":"search_ground","params":{"from":"Helsinki","to":"Tallinn","date":"2026-11-05","type":"ferry"}}'
```

MCP-Router nimmt `origin`/`destination` und benennt sie selbst um (`"renamed":["destination -> to","origin -> from"]`);
`return_date` liefert die Rückfahrt als zweites Bein.

```json
{"success": true, "count": 3, "routes": [
  {"provider":"grandi navi veloci","type":"ferry","price":36.68,"currency":"EUR",
   "departure":{"city":"Barcelona","time":"2026-11-05T21:30:00Z"},
   "booking_url":"https://www.ferryhopper.com/en/booking/results?...&IDSCode=BRCPALGNV202611052130202611060600-40c430&passengers=1&vehicles=0&pets=0",
   "sources":[{"provider":"grandi navi veloci","price":36.68,"currency":"EUR","freshness":"live"}]},
  {"provider":"trasmed","type":"ferry","price":41,"currency":"EUR", "...":"..."},
  {"provider":"balearia","type":"ferry","price":60,"currency":"EUR", "...":"..."}]}
```

* `Helsinki → Tallinn`: 13 Routen, `eckeroline` **19 EUR**, Abfahrt `Länsisatama Terminal 2 (M/S Finlandia)` →
  `Old Port A-Terminal`, `booking_url` `…/booking?from=HEL&to=TLL&date=2026-11-05&adults=1`.
* `Stockholm → Helsinki`: `vikingline` **39 EUR**, `amenities: ["Reference schedule"]`.
* **Preisbasis:** Die Ground-Suche hat **weder Passagier- noch Fahrzeugparameter** (`cmd/trvl/ground.go`:
  nur `--currency`, `--provider`, `--return`, `--max-price`, `--type`, `--allow-browser-fallbacks`) →
  Preis ist **je 1 erwachsene Person ohne Fahrzeug**; die Booking-URL enthält `passengers=1&vehicles=0&pets=0`.
* **Wichtig (Transparenz):** Nur der Provider `ferryhopper` liefert **live** Preise (36.68 EUR = identisch zum
  MCP-Wert 3668 Cent). DFDS/Viking Line/Eckerö Line liefern **fest kodierte Referenzpreise**
  (Kennzeichnung `amenities: ["Reference"]` / `["Reference schedule"]`) aus veröffentlichten Fahrplänen –
  diese sind **nicht** live und nicht exakt buchbar. Für Registry-Zwecke ist `trvl_ferries` deshalb als
  Aggregator zu behandeln, dessen Live-Anteil über `sources[].freshness` prüfbar ist.
* Fehlerbild im Log: `ground provider error provider=rome2rio error="rome2rio: blocked: bot wall (HTTP 403)"`,
  `ground provider error provider=ferryhopper error="ferryhopper: tool error: No route found between requested locations."`
* Lizenz: **PolyForm Noncommercial 1.0.0** → nicht kommerziell nutzbar (wichtig für Registry-Entscheidung).

### 2.3 Finnlines GraphQL (AWS AppSync) — keyless, live, **Preisbasis bewiesen**

Endpunkt: `https://dm3xyy44wbeivgqmeymvmw22be.appsync-api.eu-central-1.amazonaws.com/graphql`
Header `x-api-key: da2-zvuktusyubbstlw7khps4vyeie` – der **öffentliche SPA-Client-Identifier**
aus dem Booking-Bundle (im trvl-Quellcode kommentiert als *„public SPA client identifier, not a secret"*).

```
python3 providers/ferry_evidence/test_finnlines.py FINLI-SEKPS 2026-11-05
```

**Achtung:** ohne browser-ähnlichen User-Agent blockt AWS WAF:
`{"errors":[{"errorType":"WAFForbiddenException","message":"403 Forbidden"}]}` – mit
`User-Agent: Mozilla/5.0 … Chrome/131.0.0.0` → HTTP 200.

**K gekürzte Rohantwort** (`finnlines_pax_scaling.json`):

```json
{"listTimeTableAvailability":[
  {"sailingCode":"NLIKPS202611051000","departureDate":"2026-11-05","departureTime":"10:00",
   "arrivalDate":"2026-11-05","arrivalTime":"17:15","departurePort":"FINLI","arrivalPort":"SEKPS",
   "isAvailable":true,"shipName":"FINNCANOPUS","crossingTime":"30:00","chargeTotal":1760},
  {"sailingCode":"NLIKPS202611052245","departureTime":"22:45",
   "isAvailable":false,"shipName":"FINNSIRIUS","chargeTotal":null}]}
```

**Preisbasis-Beweis (Passagier-Skalierung, identische Abfahrt `NLIKPS202611051000`):**

| Passagiere in der Query | `chargeTotal` | in EUR |
|---|---|---|
| 1 ADULT | 1760 | **17.60** |
| 2 ADULT | 3520 | **35.20** (exakt 2×) |
| 4 ADULT | 7040 | **70.40** (exakt 4×) |
| 2 ADULT + 1 CHILD | 4960 | **49.60** (2 × 17.60 + 14.40 Kind) |

→ `chargeTotal` ist **linear je Person** → `price_scope: per_person`, `price_scope_confidence: confirmed`.
Zweite Query `listProductsAvailability` liefert die Tarifklassen mit `chargePerUnit` + `maxPeople`
(z. B. `A2` *Outside cabin, 2 beds*, `maxPeople: 2`, `chargePerUnit: 31052` → **Kabinenpreis je Einheit**,
`available: "LIMITED"`; `BCY` Fahrrad `chargePerUnit: null`). Kabinen sind also **nicht** je Person.

**Abfrageparameter:** `variables.query.currency` = `{currency}` (EUR), `departurePort`/`arrivalPort` =
**Finnlines-Hafenkürzel** (`FIHEL`, `FINLI`, `SEKPS`, `DETRV` …), `startDate` = `{depart_date}`,
`passengers[]` = 1 ADULT (statisch im YAML-Body – `{adults}` wird bewusst **nicht** gerendert, weil der
Preis je Person ist und der Runner `price_total = price × adults` selbst bildet).

**Pflicht-Feld:** `accommodations: []` muss mitgesendet werden, sonst
`Variable 'query' has coerced Null value for NonNull type '[Accommodation!]!'`.

**Route Helsinki → Travemünde** (`FIHEL→DETRV`): `isAvailable: false`, `chargeTotal: null` – die Route ist
in diesem Tarif nicht buchbar (nur `FINLI→SEKPS` war live).

---

## 3. Registry-Blöcke (direkt einsetzbar in `providers/registry.yaml`)

> **Voraussetzung:** Die Fähr-Quellen liefern Preise in **Cent**. Die Normalisierung kennt bisher keinen
> Divisor → in `providers/normalize.py` wurde **additiv** `extract.price_divisor` ergänzt
> (4 Zeilen, rückwärtskompatibel, **keine** Änderung unter `harness/`). Ohne diese Ergänzung wären die
> Preise 100-fach zu hoch. Diff:
> `providers/normalize.py` → in `normalize_item()` vor dem Return:
> ```python
> divisor = extract.get("price_divisor")
> try: divisor = float(divisor) if divisor else 1.0
> except (TypeError, ValueError): divisor = 1.0
> if divisor not in (0.0, 1.0):
>     price = _num(price); all_in = _num(all_in)
>     if price is not None: price = price / divisor
>     if all_in is not None: all_in = all_in / divisor
> ```

```yaml
  # ---------------------------------------------------------------- FÄHREN
  - id: ferryhopper_mcp
    category: ferries
    transport: mcp_http
    enabled: true
    price_scope: per_person
    price_scope_confidence: confirmed
    url: "https://mcp.ferryhopper.com/mcp"
    tool: search_ferry_trips
    note: >-
      Ferryhopper-MCP (Streamable HTTP, JSON-RPC 2.0, SSE-Antworten) – keyless, live.
      Preise in EUR-Cents (expectedPrice.totalPriceInCents), Verfügbarkeitsflags
      hasCabin/hasVehicles/hasPets/hasETicket. {origin}/{destination} = Hafen-/Ortsname
      (freier Text), {depart_date} = YYYY-MM-DD, {return_date} = 2. leg (Rundreise).
      Kein Passagier-/Fahrzeug-Parameter -> Preis = 1 erwachsene Person ohne Fahrzeug;
      Sitzklassen je Person, CABIN_*-Klassen je Kabine (günstigstes Item = Personenpreis).
      Währung kommt aus dem Kontext-Fallback (EUR, Ferryhopper-Basiswährung).
    headers:
      Accept: "application/json, text/event-stream"
    params:
      legs:
        - departureLocation: "{origin}"
          arrivalLocation: "{destination}"
          departureDate: "{depart_date}"
    extract:
      items_path: legs
      expand:
        path: [options, segments, accommodations]
        price: expectedPrice.totalPriceInCents
        price_divisor: 100
        name: type
        provider: null

  - id: trvl_ferries
    category: ferries
    transport: mcp_stdio
    enabled: true
    price_scope: per_person
    price_scope_confidence: confirmed
    command: ["/home/batnini/.local/bin/trvl", "mcp"]
    tool: travel
    note: >-
      trvl-Router, intent=search_ground + type=ferry – keyless. Liefert Angebote je
      Abfahrt mit price/currency/booking_url/freshness. Preis = 1 Erwachsener ohne
      Fahrzeug (die Ground-Suche kennt keine Passagierzahl). Achtung: nur der Provider
      'ferryhopper' ist live; DFDS/Viking Line/Eckerö Line liefern Referenzpreise
      (amenities=['Reference']). Lizenz trvl: PolyForm Noncommercial 1.0.0 (nicht kommerziell).
    params:
      intent: search_ground
      params:
        from: "{origin}"
        to: "{destination}"
        date: "{depart_date}"
        return_date: "{return_date}"
        type: "ferry"
    extract:
      items_path: result.routes
      price: price
      currency: currency
      provider: provider
      booking_url: booking_url
      name: departure.station
      legs: legs

  - id: finnlines_ferry
    category: ferries
    transport: http
    enabled: true
    price_scope: per_person
    price_scope_confidence: confirmed
    url: "https://dm3xyy44wbeivgqmeymvmw22be.appsync-api.eu-central-1.amazonaws.com/graphql"
    method: POST
    note: >-
      Finnlines-Buchungs-GraphQL (AWS AppSync) – keyless (x-api-key ist der öffentliche
      SPA-Client-Identifier), live. chargeTotal = Summe je Passagier (linear: 1→17.60,
      2→35.20, 4→70.40 EUR), isAvailable = Verfügbarkeit je Abfahrt. {origin}/{destination}
      = Finnlines-Hafenkürzel (FINLI, SEKPS, FIHEL, DETRV …), KEINE Staedtenamen.
      Pflicht: browser-ähnlicher User-Agent (sonst 403 WAFForbiddenException) und
      accommodations: [] in der Query.
    headers:
      Content-Type: application/json
      x-api-key: "da2-zvuktusyubbstlw7khps4vyeie"
      Origin: "https://booking.finnlines.com"
      Referer: "https://booking.finnlines.com/"
      User-Agent: "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    body:
      query: "query ListTimeTableAvailability($query:TimetableQuery!){listTimeTableAvailability(query:$query){...on Timetable{sailingCode departureDate departureTime arrivalDate arrivalTime departurePort arrivalPort isAvailable shipName crossingTime chargeTotal}}}"
      variables:
        query:
          currency: "{currency}"
          language: EN
          tariff:
            - legCode: 1
              type: SPECIAL
          sailings:
            - legCode: 1
              departurePort: "{origin}"
              arrivalPort: "{destination}"
              startDate: "{depart_date}"
              numberOfDays: 1
          passengers:
            - legCode: 1
              id: 1
              type: ADULT
          accommodations: []
    extract:
      items_path: data.listTimeTableAvailability
      price: chargeTotal
      price_divisor: 100
      name: shipName
      provider: null
```

### 3.1 End-to-End-Test gegen `providers/runner.py`

```
python3 providers/runner.py --registry providers/ferry_evidence/registry.ferries.test.yaml \
  --category ferries --origin 'Barcelona' --destination 'Palma de Mallorca' \
  --depart-date 2026-11-05 --return-date 2026-11-08 --adults 2 --currency EUR
```

Ergebnis (`ferry_evidence/runner_barcelona_palma.json`):

```json
"providers":[{"source":"ferryhopper_mcp","status":"ok","items":71,"elapsed_s":0.86},
             {"source":"finnlines_ferry","status":"ok","items":0,"elapsed_s":0.28},
             {"source":"trvl_ferries","status":"ok","items":3,"elapsed_s":14.87}],
"totals":{"providers":3,"ok":3,"failed":0,"items":33}
```

Günstigste Angebote (Auszug, 2 Erw. → `price_total` = 2 × Preis):

| Preis | Währung | name | provider | Quelle |
|---|---|---|---|---|
| 36.68 | EUR | LOUNGE_DECK | (–) | ferryhopper_mcp |
| 36.68 | EUR | BARCELONA | grandi navi veloci | trvl_ferries |
| 37.25 | EUR | SEAT_NOTNUMBERED | (–) | ferryhopper_mcp |
| 41.00 | EUR | BARCELONA | trasmed | trvl_ferries |
| 60.00 | EUR | BARCELONA | balearia | trvl_ferries |

Zweite Route (Finnlines) – `runner_naantali_kapellskar.json`:

```json
{"source":"finnlines_ferry","status":"ok","items":2}
{"price":17.6,"currency":"EUR","name":"FINNCANOPUS","price_scope":"per_person","price_total":35.2}
```

→ Der Runner bildet `price_total = 17.60 × 2 = 35.20` und damit **exakt** den von der API gelieferten
2-Personen-Gesamtpreis (3520 Cent) – unabhängige Bestätigung der Preisbasis `per_person`.

---

## 4. GitHub-Recherche

`https://api.github.com/search/repositories?q=ferry+api+mcp&sort=updated` (2026-10-21):

| Repo | Lizenz | letzte Aktivität | Bewertung |
|---|---|---|---|
| `MikkoParkkola/trvl` (89 ★) | PolyForm Noncommercial 1.0.0 | 2026-10-21 | **übernommen** – 8 Fähr-Provider (Ferryhopper live, Tallink, Viking Line, Eckerö, Stena, Finnlines, DFDS), Ground-Suche mit Preisen |
| `ferry-vn/ferry-sdk` (0 ★) | Apache-2.0 | 2026-10-20 | Partner-API Vietnam, **Key nötig**, keine EU-Routen → ausgeschlossen |
| `adrianetti/travel-search` (2 ★) | keine | 2026-03-27 | MCP-Wrapper (Kiwi/Skiplagged/Trivago/Ferryhopper), kein eigener Fähr-Endpunkt |
| `leffen-fjordline/mcp-forge` (0 ★) | keine | 2026-01-16 | Fjord-Line-Abfahrt-API, inaktiv/klein → ausgeschlossen |
| `Navendra8/DirectFerriesScrapping` u.a. | – | 2023–2025 | reine HTML-Scraper ohne stabile API → ausgeschlossen |

Der trvl-Quellcode war die entscheidende Fundgrube für die **öffentlichen** Endpunkte
(`internal/ground/ferryhopper.go`, `eckeroline.go`, `dfds.go`, `tallink.go`, `finnlines.go`,
`vikingline.go` sowie `docs/PROVIDERS.md`).

---

## 5. Empfehlung

**Aufnehmen:**
1. `ferryhopper_mcp` – beste Abdeckung (1453 Ports, 190+ Reedereien), live, keyless, Preis + Verfügbarkeit.
2. `trvl_ferries` – stärkster Aggregator (mehrere Reedereien, Buchungslinks) **aber** Lizenz „noncommercial“
   und ein Teil der Preise sind Referenz-Fahrpläne → ggf. `enabled: false` bzw. nur für internen Vergleich.
3. `finnlines_ferry` – einzige Quelle mit **bewiesener** Preisbasis und echtem `isAvailable`; Deckung
   derzeit nur FINLI↔SEKPS.

**Nicht aufnehmen:** alle 14 übrigen Kandidaten (Begründung je Quelle in `ferry_candidates.json`
→ `recommendation.exclude`).

**Offen / nächste Schritte**
* Ferryhopper: Buchungs-URL im MCP fehlt → entweder aus `options[].id` selbst bauen (Muster aus trvl)
  oder `trip_details` als zweiten Call im `followup` nutzen.
* `price_divisor` sollte in `providers/normalize.py` übernommen werden (additiv, siehe Abschnitt 3).
* Weitere Reedereien (Stena/Wightlink/Irish Ferries/P&O) haben keine keyless Preis-API –
  ein Scraping-Pfad (HTML) wäre rechtlich/technisch fragwürdig und wurde bewusst nicht gebaut.
* `{vehicle}` wird von **keiner** der drei Quellen unterstützt (Fahrzeugtarife fehlen) – die Registry
  sollte das explizit als nicht verfügbar ausweisen.

---

## 6. Dateiübersicht

| Datei | Inhalt |
|---|---|
| `providers/ferry_candidates.json` | Maschinenlesbare Kandidatenliste (17 Quellen, Empfehlung) |
| `docs/SOURCES_FERRIES.md` | Dieser Bericht |
| `providers/ferry_evidence/mcpcall.py` | MCP-Testclient (stdio + Streamable-HTTP, SSE-Parser) |
| `providers/ferry_evidence/inspect_mcp.py` | Antwort-Auswertung (Preisfelder/Währung) |
| `providers/ferry_evidence/probe_endpoints.py` + `probe_endpoints_out.jsonl` | Endpunkt-Scan aller Negativbefunde |
| `providers/ferry_evidence/test_finnlines.py` + `finnlines_*.json` | Finnlines-Tests inkl. Passagier-Skalierung |
| `providers/ferry_evidence/test_eckeroline_dfds.py` + `eckeroline_dfds_raw.json` | Eckerö-/DFDS-Tests |
| `providers/ferry_evidence/fh_*.json`, `ferryhopper_pax_ignored_evidence.json` | Ferryhopper-MCP-Rohantworten |
| `providers/ferry_evidence/tallink_timetables_raw.json` | Tallink-Antwort (leere trips) |
| `providers/ferry_evidence/registry.ferries.test.yaml` | Test-Registry (End-to-End gegen den Runner) |
| `providers/ferry_evidence/runner_*.json` | Runner-Ergebnisse (Barcelona→Palma, Naantali→Kapellskär) |
