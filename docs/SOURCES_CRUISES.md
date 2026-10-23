# Quellen-Fetch: Kreuzfahrten (Schiffsreisen mit Übernachtung)

**Stand:** 21.10.2026, Testfenster 18:15–20:30 UTC
**Testroute:** Abfahrtshafen `MIA` (Miami) / `FLL` (Fort Lauderdale), Zielregion `BAHAM` bzw. `CARIB`,
Abfahrtsfenster `2026-11-01` … `2027-06-30`, 2 Erwachsene / 0 Kinder, Währung USD bzw. EUR
(+ Preisbasen-Gegenproben mit 1 / 2 / 3 Erwachsenen bei Royal Caribbean, mit den Märkten
`US/en_US` und `NL/nl_NL` bei Holland America)

**Regeln eingehalten:** Websuche ausschließlich für *Recherche* (Repos, Endpunkte, Lizenz, Aktivität).
**Keine** Preise per Web ermittelt – alle Preisangaben stammen aus echten API-/HTTP-Antworten.
Nichts unter `/home/batnini/mimo-agents/harness/` geändert. Keine bestehenden MCP-Server deinstalliert.

**Artefakte:**

* Maschinenlesbare Registry: `/home/batnini/mimo-agents/providers/cruise_candidates.json`
  (18 Quellen: 7 `ok`, 7 `blocked`, 4 `error`; Empfehlung: 7 `include`, 11 `exclude`)
* Rohantworten: `/home/batnini/mimo-agents/providers/cruise_evidence/`
* Neue Dateien: `providers/cruise_rcl.py` (CLI-Wrapper), `providers/registry_cruises_example.yaml`
* Testskripte: `/tmp/opencode/cruise/` (`make_evidence.py`, `probe.py`, `mcpcall.py`, `venv/`)

---

## 0. Ergebnis in einem Satz

Zwei Reedereien liefern **heute keyless, echte Live-Preise mit Währung, Preisbasis und
Steuer-/Inklusiv-Angaben**: **Holland America Line** (öffentliche Solr-Suche + kabinenweise
Preis-API) und **Royal Caribbean / Celebrity Cruises** (öffentliche JSON-APIs der Buchungsstrecke).
Beide sind über die bestehende Registry-Architektur (`http` bzw. `cli`) ansprechbar.

---

## 1. Ergebnisübersicht

| Quelle | Kategorie | Key nötig | Erreichbar | Preisfeld | Währung | Preisbasis | Steuern/All-Inclusive | Lizenz | letzte Aktivität |
|---|---|---|---|---|---|---|---|---|---|
| **hal-cruises** (`/search/halcruisesearch`) | cruises | **nein** | ✅ HTTP 200 | `price_EUR_RESTRICTED` (+ `sortPrice_EUR`, `price_EUR_BASEPRICE/FLEXIBLE`) | EUR (auch USD) | **pro Person** (Site-i18n `priceUnit="per Person"`) | `taxesAndFeesCombined_EUR=true`, `taxExpenses_EUR` | proprietär | 21.10.2026 live |
| **hal-price-api** (`/api/v2/price/cruise/{id}`) | cruises | **nein** (Markt-Header) | ✅ HTTP 200 | `data.bestAvailable.price` / `.basePrice` / `.tax` | `data.currencyCode` (USD/EUR) | **pro Person** | `taxAndFeesCombined=true`, `amenities.obcUSD` (Onboard-Guthaben) | proprietär | 21.10.2026 live |
| **royalcaribbean-web-api** (ships/voyages/sailDate/GraphQL) | cruises | **nein** (statischer Web-AppKey) | ✅ HTTP 200 | GraphQL `products[].price[].promotionalPrice` (Add-ons) | `price[].currency` | **pro Person** | Add-on-Kategorien (`beverage`, `dining`, `spa`, …) | proprietär | 21.10.2026 live |
| **royalcaribbean-room-selection** (POST `/room-selection/api/v1/rooms`) | cruises | **nein** | ✅ HTTP 200 | `pricing.invoice.cruiseFare/taxesAndFees/total`, `perPersonAmount` | `currencyCode` | **pro Person** (belegt) | `potentialBeveragePackage=false`, `taxesAndFeesBundled=true`, `refundability` | proprietär | 21.10.2026 live |
| **royalcaribbean-itinerary-page** (RSC) | cruises | **nein** | ✅ HTTP 200 | `lowestPrice.amount` / `.total`, schema.org `lowPrice` | schema.org `priceCurrency` | **pro Person** | **`isAllInclusive`**, `included[]` (standard/premium) | proprietär | 21.10.2026 live |
| **celebrity-cruises** (gleiche APIs, `brand=C`) | cruises | **nein** | ✅ HTTP 200 | wie RCL | USD/EUR | **pro Person** | wie RCL | proprietär | 21.10.2026 live |
| **rcl-cruises** (CLI-Wrapper `providers/cruise_rcl.py`) | cruises | **nein** | ✅ 15 Angebote / 31 s | `price` + `all_in` | USD/EUR | **pro Person** | `taxes_included`, `drinks_included` | eigener Code | 21.10.2026 |
| siloahtravel-mcp | cruises | nein (laut Doku) | ❌ | – | – | – | – | MIT | Repo 2026-10 |
| cruise-itinerary-mcp | cruises | **ja** (Login) | ❌ | – | – | – | – | proprietär | 2026-10-05 |
| vectotechnology-cruise-api | cruises | **ja** (OAuth1) | ❌ | – | – | – | – | proprietär | 2026-10 |
| msc-cruises | cruises | nein | ❌ 401 | – | – | – | – | proprietär | 21.10.2026 |
| costa-cruises | cruises | **ja** (`agencyid`) | ❌ 400 | – | – | – | – | proprietär | 21.10.2026 |
| ncl | cruises | nein | ❌ 404 | – | – | – | – | proprietär | 21.10.2026 |
| hapag-lloyd | cruises | nein | ❌ WAF | – | – | – | – | proprietär | 21.10.2026 |
| viking-line | cruises | nein | ❌ 404 | – | – | – | – | proprietär | 21.10.2026 |
| tuicruises / aida-cruises | cruises | nein | ❌ TLS/DNS | – | – | – | – | proprietär | 21.10.2026 |
| expedia / kayak / holidaycheck / check24 / cruise1 | cruises | nein | ❌ 429/HTML | – | – | – | – | proprietär | 21.10.2026 |
| amadeus / google-travel-cruises / cruise1 / apify | cruises | **ja** | ❌ 404 | – | – | – | – | proprietär | 21.10.2026 |

---

## 2. Funktionierende Quellen im Detail

### 2.1 Holland America Line – öffentliche Solr-Suche (`http`, keyless)

**Endpunkt**

```
GET https://www.hollandamerica.com/search/halcruisesearch
```

Kein API-Key, keine Session, kein JavaScript nötig. Nur ein normaler Browser-User-Agent und
ein `Referer` auf die Suchseite. Die Antwort ist eine Solr-artige JSON-Struktur:

```json
{ "response": { "numFound": 25, "start": 0, "numFoundExact": true, "docs": [ … ] } }
```

**Testkommando**

```bash
curl -sS -A 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36' \
  -H 'Accept: application/json' \
  -H 'Referer: https://www.hollandamerica.com/en/us/find-a-cruise' \
  --get \
  --data-urlencode 'fq=embarkPortCode:MIA AND departDate:[2026-11-01T00:00:00Z TO 2027-06-30T00:00:00Z]' \
  --data-urlencode 'rows=20' \
  --data-urlencode 'fl=cruiseId,shipId,shipName,embarkPortCode,embarkPortName,disembarkPortCode,disembarkPortName,departDate,arrivalDate,duration,soldOut,name,sortPrice_EUR,sortPrice_USD,taxExpenses_EUR,taxesAndFeesCombined_EUR,price_EUR_RESTRICTED,price_EUR_BASEPRICE,price_EUR_FLEXIBLE' \
  'https://www.hollandamerica.com/search/halcruisesearch'
```

**Gekürzte Rohantwort** (Beleg: `providers/cruise_evidence/hal_search_mia_2026-11-01_2027-06-30.json`)

```json
{"response":{"numFound":25,"start":0,"docs":[
 {"cruiseId":"U680","shipName":"Zuiderdam#@#UU","embarkPortCode":"MIA","embarkPortName":"Miami, Florida, US#@#MIA",
  "disembarkPortCode":"MIA","disembarkPortName":"Miami, Florida, US",
  "departDate":"2026-11-11T00:00:00Z","arrivalDate":"2026-11-21T00:00:00Z","duration":10,"soldOut":false,
  "name":"10-DAY SOUTHERN CARIBBEAN: CABO ROJO & ABC ISLANDS",
  "sortPrice_EUR":1589.0,"sortPrice_USD":1549.0,"taxExpenses_EUR":274.37,"taxesAndFeesCombined_EUR":true,
  "price_EUR_RESTRICTED":839.0,"price_EUR_BASEPRICE":889.0,"price_EUR_FLEXIBLE":1589.0},
 {"cruiseId":"U683","name":"7-DAY WESTERN CARIBBEAN: GREATER ANTILLES & MEXICO","departDate":"2026-11-21T00:00:00Z",
  "duration":7,"soldOut":false,"price_EUR_RESTRICTED":604.0,"price_EUR_BASEPRICE":639.0,"price_EUR_FLEXIBLE":1129.0,
  "sortPrice_EUR":1129.0,"taxExpenses_EUR":204.6,"taxesAndFeesCombined_EUR":true}]}}
```

**Preisfeld / Währung**

| Bedeutung | Feld |
|---|---|
| günstigster buchbarer Kabinenpreis **inkl. Steuern**, pro Person | `price_<CCY>_RESTRICTED` |
| Kabinenpreis (Basis-Tarif) | `price_<CCY>_BASEPRICE` |
| erstattbare Anzahlung | `price_<CCY>_FLEXIBLE` |
| Sortierpreis der Website (= FLEXIBLE, **nicht** der günstigste!) | `sortPrice_<CCY>` |
| Steuer-/Hafenanteil **innerhalb** des Preises | `taxExpenses_<CCY>` |
| „Steuern & Gebühren sind im Preis enthalten" | `taxesAndFeesCombined_<CCY>` = `true` |

`sortPrice` ist **nicht** der „von"-Preis der Website – er ist der FLEXIBLE-Preis
(bei allen geprüften Docs `sortPrice == price_FLEXIBLE`). Der echte „von"-Preis ist
`price_<CCY>_RESTRICTED`; das bestätigt die Preis-API (§2.2) über `bestAvailable`.

**Währung**: steckt im Feldnamen (`EUR`, `USD`, `CAD`, `GBP`, `AUD` sind alle vorhanden).
Der `fl`-Parameter bestimmt, welche Varianten mitgeliefert werden.

**Preisbasis: pro Person – belegt**

* HAL bittet in der Preis-API um **keine** Personenzahl; die Preise sind per Definition pro Person.
* Die Website selbst schreibt es in ihrem i18n-Bundle:
  `"priceUnit":"pro Person"` (deutsch) bzw. `"priceUnit":"per Person"` (englisch),
  `"priceLabel":"Starting from:"`, `"itemPriceValue":"{0}/person"`.
* Preis-API-Gegenprobe (Beleg: `cruise_evidence/hal_price_basis.txt`):
  `country=US locale=en_US → currencyCode=USD bestAvailable.price=999 tax=150 basePrice=849`
  `country=NL locale=nl_NL → currencyCode=EUR bestAvailable.price=934 tax=237.16 basePrice=696.84`
  → `price − tax = basePrice` (999−150 = 849, 934−237.16 = 696.84) ⇒ der ausgewiesene Preis
  **enthält** Steuern, der Anteil ist `tax`/`taxExpenses`.

**Verfügbarkeit**: `soldOut` (bool), `departDate`/`arrivalDate`/`duration`,
`response.numFound` (Trefferzahl), `price_<CCY>_RESTRICTED = 0` ⇒ nicht buchbar.

**Abfrageparameter**: `fq` (Pflicht, Solr-Filter), `rows`, `start`, `fl`.
`{origin}`/`{destination}` müssen **HAL-Hafencodes** sein (`MIA`, `FLL`, `HAM`, `BCN`, `CIV`, …),
keine Ortsnamen. Destination = `disembarkPortCode`.

**Lizenz/Aktivität:** proprietäre Website-API (kein Quellcode), Datenstand tagesaktuell,
abrufbar ohne jede Anmeldung.

---

### 2.2 Holland America Line – kabinenweise Preis-API (`http`, keyless)

**Endpunkt**

```
GET https://www.hollandamerica.com/api/v2/price/cruise/{cruiseId}
Header: country: US, locale: en_US, brand: hal      (+ Cookie country=US)
```

**Testkommando**

```bash
curl -sS -H 'country: US' -H 'locale: en_US' -H 'brand: hal' -b 'country=US' \
  -H 'Accept: application/json' 'https://www.hollandamerica.com/api/v2/price/cruise/U679'
```

**Gekürzte Rohantwort** (Beleg: `providers/cruise_evidence/hal_price_U679_USD.json`)

```json
{"data":{
  "sailingDate":"2026-10-31","departDate":"2026-10-31","arriveDate":"2026-11-11",
  "cruiseCode":"U679","itineraryId":"C6E11C","shipCode":"UU","currencyCode":"USD",
  "taxAndFeesCombined":true,"webDestCode":"C","portCharges":null,"serviceCharges":[],
  "bestAvailable":{"tax":150,"price":999,"launchPrice":1639,"fare":"QF1","classification":"restricted",
                    "category":"UU_IN_IN","basePrice":849,"baseTax":0,"flight":null,
                    "taxAndFeesCombined":true,"promoCodes":["QF_USD"],
                    "amenities":{"obcUSD":"100.00"},"includedPromos":["KR1","OFA"]},
  "roomTypes":[{"name":"Inside","categories":[{"name":"Inside","id":"UU_IN_IN","price":[
      {"tax":150,"price":1714,"launchPrice":2299,"fare":"N11","classification":"flexible","basePrice":1564,"taxAndFeesCombined":true},
      {"tax":150,"price":999,"launchPrice":1639,"fare":"QF1","classification":"restricted","basePrice":849,"taxAndFeesCombined":true,"amenities":{"obcUSD":"100.00"}}]}]},
   {"name":"Ocean View","categories":[{"name":"Ocean View","id":"UU_OV_OV","price":[
      {"tax":150,"price":1814,"launchPrice":2999,"classification":"flexible","basePrice":1664},
      {"tax":150,"price":1099,"launchPrice":2339,"classification":"restricted","basePrice":949}]}]}]}}
```

**Fehlerbilder (wörtlich)**

| Situation | Antwort |
|---|---|
| ohne `country`/`locale`/`brand`-Header | HTTP 400 `{"message": "Missing required request parameters: [country, locale, brand]"}` |
| `country=EU` (nicht als Markt hinterlegt) | HTTP 412 `{"data":null,"errors":[{"message":"No Country"}]}` |
| `country=NL, locale=nl_NL` | HTTP 200, `currencyCode=EUR`, `bestAvailable.price=934` |
| `country=US, locale=en_US` | HTTP 200, `currencyCode=USD`, `bestAvailable.price=999` |

**All-Inclusive-relevant:** `taxAndFeesCombined=true` (Preis enthält Steuern/Gebühren),
`amenities.obcUSD` (Onboard-Guthaben im Tarif), `classification` (`restricted` = nur
Anzahlung/nicht erstattbar, `flexible` = erstattbare Anzahlung) – **kein** All-Inclusive:
Getränke/Ausflüge/Spa/Internet sind bei HAL immer Aufpreis.

---

### 2.3 Royal Caribbean / Celebrity – öffentliche JSON-APIs (keyless)

#### (a) Flotte / Abfahrten / Route

```bash
curl -sS -H 'Accept: application/json' -H 'AppKey: hyNNqIPHHzaLzVpcICPdAdbFV8yvTsAm' \
  'https://aws-prd.api.rccl.com/en/royal/web/v2/ships?sort=name'
curl -sS -H 'Accept: application/json' -H 'AppKey: hyNNqIPHHzaLzVpcICPdAdbFV8yvTsAm' \
  'https://aws-prd.api.rccl.com/en/royal/web/v3/ships/WN/voyages'
curl -sS -H 'Accept: application/json' -H 'AppKey: hyNNqIPHHzaLzVpcICPdAdbFV8yvTsAm' \
  'https://aws-prd.api.rccl.com/en/royal/web/v3/ships/WN/sailDate/20261102'
```

* `/v2/ships` → HTTP 200, **47 Schiffe** (Royal Caribbean + Celebrity), `payload.ships[].shipCode/name`.
* `/v3/ships/{code}/voyages` → HTTP 200, **149 Abfahrten** für WN:
  `{"shipCode":"WN","sailDate":"20261019","sailEndDate":"20261023","duration":4,"regionCode":"BAHAM","voyageCode":"4BH354","voyageDescription":"4 Night Bahamas & Perfect Day Cruise"}`
* `/v3/ships/{code}/sailDate/{YYYYMMDD}` → HTTP 200, Reiseroute:
  `itinerary.events[].port = {"portCode":"MIA","portName":"Miami, Florida","portCountry":"USA","portType":"EMBARK"}` …
  (Tag 2–5: `CRU` Cruising, `NAS` Nassau, `PCC` Perfect Day CocoCay).

> **Strukturregel (wichtig):** die `packageCode` der Reederei = `shipCode` + `voyageCode`
> (`"4BH355"` + `"WN"` → `WN4BH355`). Damit sind aus der öffentlichen Voyages-API **alle**
> buchbaren Pakete und Abfahrtsdaten ableitbar – ohne die geschützte Website-Suche.

#### (b) Kabinenpreis + Rechnung (`POST /room-selection/api/v1/rooms`)

```bash
python3 - <<'PY'
import requests
s = requests.Session()
s.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:149.0) Gecko/20100101 Firefox/149.0',
                   'Accept-Encoding': 'gzip, deflate'})
body = {'countryCode':'USA','packageId':'WN4BH355','sailDate':'2026-11-02','currencyCode':'USD',
        'language':'en','options':True,'roomNumbers':True,'platform':'web',
        'rooms':[{'adultCount':2,'childCount':0,'stateroomTypeCode':'INTERIOR','stateroomSubtypeCode':'I',
                  'accessible':False,'selectionFallbackStrategy':'RECOMMENDATION','editMode':True,
                  'reset':False,'taxesAndFeesBundled':True,
                  'qualifiers':{'fireFighter':False,'military':False,'police':False,'senior':False}}]}
r = s.post('https://www.royalcaribbean.com/room-selection/api/v1/rooms', json=body,
           headers={'accept':'*/*','content-type':'application/json','brand':'R','country':'USA'})
print(r.status_code, r.text[:400])
PY
```

**Gekürzte Rohantwort** (Beleg: `providers/cruise_evidence/rcl_rooms_WN4BH355_2026-11-02.json`)

```json
{"sailing":{"startDate":"2026-11-02","endDate":"2026-11-06","sailDate":"2026-11-02","debarkDate":"2026-11-06",
  "itinerary":{"id":"WN4BH355","name":"Perfect Day CocoCay & Bahamas",
    "ship":{"code":"WN","name":"Wonder of the Seas","maxOccupancy":4},
    "departurePort":{"code":"MIA","name":"Miami","region":"Florida","countryCode":"USA"},
    "destination":{"code":"BAHAM","name":"Bahamas"}}},
 "currencyCode":"USD","countryCode":"USA","hasHotels":false,
 "pricing":{"invoice":{"cruiseFare":426,"subtotal":426,"taxesAndFees":270.3,"total":696.3,
                        "other":[],"potentialBeveragePackage":false}},
 "rooms":[{"outcome":"ROOM_FOUND","room":{"stateroomType":{"code":"INTERIOR","name":"Interior","included":[]},
   "stateroomSubtype":{"code":"I","name":"Interior"},
   "pricing":{"invoice":{"cruiseFare":426,"subtotal":426,"taxesAndFees":270.3,"total":696.3},
              "amount":696.3,"perPersonAmount":348.15,"taxesAndFeesBundled":true,
              "refundability":"DEPOSIT_NOT_REFUNDABLE",
              "terms":{"lines":["*The price is per person (unless otherwise specified above), cruise only, reflects any promotional savings, and is subject to change until the booking is confirmed. …"]}}}]}}
```

**Preisbasis: pro Person – durch Gegenprobe belegt**
(Beleg: `providers/cruise_evidence/rcl_price_basis_probe_1_2_3_adults.json`, gleiche Abfahrt 2026-11-02)

| Reisende | `invoice.total` (Partei) | `perPersonAmount` | Probe |
|---|---|---|---|
| 1 | 561.15 | 561.15 | — |
| 2 | 696.30 | 348.15 | 696.30 = 2 × 348.15 ✓ |
| 3 | 1060.45 | 353.48 | 1060.45 = 3 × 353.48 ✓ |

Die Rechnung skaliert also linear mit der Personenzahl ⇒ **Preis pro Person**.
Der Preis ist zugleich **`cruise only`** („The price is per person …, cruise only") – enthalten sind
Steuern und Hafenkautionen, **nicht** Getränke/Flug.

**Steuer- und All-Inclusive-Felder**

| Feld | Bedeutung |
|---|---|
| `pricing.invoice.taxesAndFees` | Steuern + Hafengebühren (im `total` enthalten) |
| `rooms[].room.pricing.taxesAndFeesBundled` | `true` ⇒ Steuern im Preis |
| `pricing.invoice.potentialBeveragePackage` | `false` ⇒ **Getränkepauschale nicht enthalten** |
| `rooms[].room.stateroomType.included` | im Tarif enthaltene Leistungen |
| `pricing.invoice.discount.items[].description` | aktive Aktionen, z. B. `"60% Off Second Guest"`, `"Scary Good Deals"`, `"3rd & 4th Guests Sail Free"` |

**Fehlerbilder (wörtlich)**

| Situation | Antwort |
|---|---|
| `curl` (TLS-Fingerprint) | HTTP 403 Akamai: `Access Denied … https://errors.edgesuite.net/18.c2c1102.1792603958.21f0389e` |
| `python-requests` | HTTP 200 (Browser-UA + `Accept-Encoding: gzip, deflate`) |
| `sailDate` im Format `20261205` | HTTP 400 `{"code":"BAD_INPUT", … "message":"must match format \"date\"", "target":".sailDate"}` |
| `stateroomTypeCode` leer | HTTP 400 `… "must be equal to constant", "target":".rooms.0.stateroomTypeCode"` |
| `stateroomSubtypeCode` leer | HTTP 400 `… "must match pattern \"^[A-Z0-9]{1,2}$\"", "target":".rooms.0.stateroomSubtypeCode"` |
| falsche `packageId`/kein sailing am Datum | HTTP 400 (kein `pricing`-Objekt) |
| `curl_cffi`/`requests` **ohne** vorheriges Laden der Iterarionsseite | HTTP 200, aber `_not-found`-RSC statt Preisdaten |

#### (c) Iterarionsseite – serverseitiges JSON mit `isAllInclusive`

```bash
curl -sS -H 'RSC: 1' -H 'Accept: text/x-component' \
 'https://www.royalcaribbean.com/itinerary/7-night-perfect-day-cococay-caribbean-from-miami-on-icon-IC07E484?sailDate=2026-12-05&packageCode=IC07E484&groupId=IC07MIA-2623281014&country=USA'
```

**Gekürzte Rohantwort** (Beleg: `providers/cruise_evidence/rcl_itinerary_IC07E484_excerpt.txt`)

```
"lowestPrice":{"amount":1136.43,"total":2272.86},
"totalSailings":23,
"isAllInclusive":false,
"voyageType":"OCEAN","hasShoreExcursions":true,
"included":[{"code":"Food","type":"standard","name":"Food and snacks at our cafes and buffets"},
            {"code":"Drinks","type":"premium","name":"Cocktails, specialty coffees, sodas and bottled water"},
            {"code":"ShoreExcursions","type":"premium","name":"Shore excursions"},
            {"code":"WiFi","type":"premium","name":"Wi-Fi to stay connected at sea"},
            {"code":"SpecialtyRestaurants","type":"premium","name":"World-class dining at speciality restaurants"}],
schema.org AggregateOffer: {"itemProp":"priceCurrency","content":"USD"},
                           {"itemProp":"lowPrice","content":"1136.43"},
                           {"itemProp":"offerCount","content":"23"},
                           {"itemProp":"validFrom","content":"2026-12-05T00:00:00.000Z"},
                           {"itemProp":"availability","content":"https://schema.org/InStock"}
i18n: "pricing.priceUnit":"/person*", "pricing.pricingShownIsPerPerson":"Pricing shown is per person.",
      "pricing.roomTypeDescription":"Prices include taxes and fees (optional gratuities are not included).",
      "pricing.priceDisclosureIncludedTaxesAndFees":"*Taxes & fees included",
      "pricing.priceDisclosureExcludedTaxesAndFees":"*plus {taxesAndFees} in taxes & fees"
```

Das ist die **einzige Quelle im Set mit einem echten `isAllInclusive`-Flag** und der
Aufteilung `type: standard` (inklusive Leistung) vs. `type: premium` (Aufpreis) –
genau die Felder, die die Bündelungslogik braucht.

#### (d) GraphQL – Add-on-Preise (Getränke, Ausflüge, Spa …)

```bash
curl -sS -X POST 'https://aws-prd.api.rccl.com/en/royal/web/graphql' \
  -H 'Content-Type: application/json' -H 'AppKey: hyNNqIPHHzaLzVpcICPdAdbFV8yvTsAm' \
  -d '{"operationName":"WebCategories","variables":{"sailDate":"2026-12-05","shipCode":"IC"},"query":"query WebCategories($shipCode: ShipCodeScalar!, $sailDate: LocalDateScalar!, $regionCode: String) { categories(shipCode: $shipCode, sailDate: $sailDate, regionCode: $regionCode, filter: {limitCategoriesWithProducts: true}) { ... on CategoryResultSuccess { categories { id name } } } }"}'
```

→ HTTP 200, Kategorien: `beverage, shorex, cococay, dining, internet, key, roomdelivery, spa, onboardactivities, celebrations, photoPackage, gifts`.
Mit `operationName: WebProductsByCategory`, `category: "beverage"` → 6 Produkte mit Preisen
(Beleg: `cruise_evidence/rcl_graphql_beverage_IC_2026-12-05.json`):

```
Classic Soda Package          promo=13.99 USD  daily=$18.00  base=$18.00
San Pellegrino Water (8)      promo=16.99 USD  daily=None     base=$22.00
Refreshment Package           promo=32.99 USD  daily=$42.00  base=$42.00
Specialty Coffee Card         promo=33.99 USD  daily=None     base=$40.00
Women of Wine Tasting Exp.    promo=36.99 USD  daily=None     base=$50.00
```

GraphQL-Introspection ist **offen** (`__schema` abrufbar) – nützlich für die Schema-Doku.
Hinweis: `products` ist ein **Union-Typ**, `price` ist eine **Liste** – der Parser muss das berücksichtigen.

#### (e) CLI-Wrapper `providers/cruise_rcl.py` (registryfertig)

```bash
cd /home/batnini/mimo-agents
python3 providers/cruise_rcl.py --origin MIA --destination BAHAM \
  --depart-date 2026-11-01 --return-date 2027-06-30 --adults 2 --currency USD --max-price-calls 25 --limit 10
```

```json
{"candidates":342,"port_checks":65,"price_calls":11,"items":[
 {"departure_date":"2026-11-02","boarding":"MIA","destination":"BAHAM","nights":4,
  "price":213.0,"all_in":348.15,"currency":"USD","taxes_included":true,"drinks_included":false,
  "package_code":"WN4BH355","group_id":"WN04MIA-1040267344","sailings_count":70,
  "cabin_fare_total":426,"taxes_total":270.3,"cabin_total":696.3,"discount_total":null,
  "booking_url":"https://www.royalcaribbean.com/booking/landing?shipCode=WN&packageCode=WN4BH355&sailDate=2026-11-02&destinationCode=BAHAM&selectedCurrencyCode=USD&country=USA"}]}
```

Ablauf: (1) Flotte → (2) Voyages-API (Abfahrtsdaten, `packageCode = shipCode+voyageCode`) →
(3) optional billiger `sailDate`-GET zum Filtern des Abfahrtshafens → (4) Preis-API je Abfahrt.
Celebrity läuft mit `--line celebrity` (Pfad `/en/celebrity/…`, Host `www.celebritycruises.com`, Header `brand: C`).

---

## 3. Blockierte Quellen – wörtliche Fehlerbilder

| Quelle | Kommando | Wörtliche Antwort |
|---|---|---|
| Siloah Travel MCP | `POST https://mcp.siloah.travel/mcp` (JSON-RPC initialize) | HTTP **404** `Not found` (auch `/health`, `/openapi.json`); `GET /` liefert die Next.js-Marketingseite. Mit curl-UA: Cloudflare-Challenge `<title>Just a moment...</title> … challenges.cloudflare.com`. |
| Cruise Itinerary MCP | `POST https://cruise-itinerary.com/mcp` | HTTP **401** `{"error":"invalid_request","error_description":"Sign in to Cruise Itinerary to use this server. A free account needs only an email address."}` |
| VECTO Cruise API | `POST https://api.vectotechnology.com/cruise/getCruiseLines` | ohne Header `{"errors":[{"code":"E101","description":"Missing conversation_id header"}]}`; mit UUID `{"errors":[{"code":"E100","description":"4096 - Unknown error"}]}`; Collection-Auth ist `oauth1` mit leeren `consumerKey/consumerSecret` |
| MSC Cruises | `GET https://www.msccruises.com/api/sailings` | HTTP **401** `<title>Unauthorized</title> … Please contact your administrator` |
| Costa Cruises | `POST https://www.costacruises.com/api/v2/cruise/booking/agency` | HTTP **400** `{"errorCode":"BAD_REQUEST","errorDescription":"Required header 'agencyid' not specified", …}` |
| NCL | `GET https://www.ncl.com/api/sailings`, `/find-a-cruise` | HTTP **404** (HTML-Fehlerseite, 164564 bytes) |
| Hapag-Lloyd | `GET https://www.hapag-lloyd.com/en/cruises` | HTTP 200 mit `<title>Security Check - Hapag-Lloyd</title>`; `/en/cruises` → HTTP **404** `Page not Found - Hapag-Lloyd` |
| Viking Line | `GET https://www.vikingline.com/api/departures` | HTTP **404** (HTML, 335378 bytes); Startseite ohne jede JSON-API-Referenz |
| TUI Cruises / AIDA | `GET https://www.tuicruises.com/`, `https://www.aida-cruises.de/` | TLS: `SSL: no alternative certificate subject name matches target hostname`; DNS: `Could not resolve host` für `www.tui-cruises.de`, `www.lastminute-cruise.de` |
| Expedia | `GET https://www.expedia.de/Cruises` | HTTP **429** `{"error":"Too Many Requests","message":"Provisioned request rate has been exceeded","code":429}` |
| Kayak / HolidayCheck / Check24 / Cruise1 | `GET …/cruises`, `…/`, … | HTTP 404 bzw. reine HTML-Seiten ohne Preis-JSON |
| Amadeus Cruises | `GET https://api.amadeus.com/v1/shopping/cruise-offers?origin=MIA` | HTTP **404** `{"errors":[{"code":38196,"title":"Resource Not found","status":404,"detail":"The targeted resource doesn't exist"}]}` |
| Google Travel Cruises | `GET https://travel.google.com/travel/cruises` | HTTP **404** `<title>Error 404 (Not Found)!!1</title>` – Google hat keine öffentliche Cruise-Suche |
| CruiseMapper | `GET https://www.cruisemapper.com/ships.html` | HTTP **404** `<title>Error page | CruiseMapper</title>` |
| HAL `/api/ratecalendar` (vermutete Endpunkte) | `GET https://www.hollandamerica.com/api/ratecalendar` | HTTP **404** `404 Resource at '/content/hal/global/api/ratecalendar.html' not found` |
| MCP-Discovery (Siloah) | `python3 mcpcall.py http … tools` | `HTTPError 404 Not Found: Not found` |

Vollständige Rohliste: `providers/cruise_evidence/probe_results.json` (24 Endpunkte mit Status,
Länge und Body-Auszug).

---

## 4. Registry-Blöcke (direkt einsetzbar)

Vollständige, lauffähige Registry: `providers/registry.cruises.yaml` (Auszug aus
`providers/cruise_evidence/registry_cruises_example.yaml`, mit dem echten Runner getestet).

```yaml
  # ---------------------------------------------------------------- KREUZFAHRTEN
  - id: hal-cruises
    category: cruises
    transport: http
    enabled: true
    price_scope: per_person
    price_scope_confidence: confirmed
    url: "https://www.hollandamerica.com/search/halcruisesearch"
    method: GET
    headers:
      Accept: application/json
      Referer: "https://www.hollandamerica.com/en/us/find-a-cruise"
      User-Agent: "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    params:
      fq: "embarkPortCode:{origin} AND departDate:[{depart_date}T00:00:00Z TO {return_date}T00:00:00Z]"
      rows: "20"
      fl: "cruiseId,shipId,shipName,embarkPortCode,embarkPortName,disembarkPortCode,disembarkPortName,departDate,arrivalDate,duration,soldOut,name,sortPrice_EUR,sortPrice_USD,taxExpenses_EUR,taxesAndFeesCombined_EUR,price_EUR_RESTRICTED,price_EUR_BASEPRICE,price_EUR_FLEXIBLE,price_USD_RESTRICTED"
    coerce:
      adults: int
    extract:
      items_path: response.docs
      price: price_EUR_RESTRICTED      # guenstigster Kabinenpreis inkl. Steuern, PRO PERSON
      all_in: price_EUR_RESTRICTED     # Preis ist steuerinklusive -> identisch zum Endpreis
      currency: EUR                    # Konstante (Quelle liefert kein Waehrungsfeld, nur Feldsuffixe)
      taxes_included: taxesAndFeesCombined_EUR
      provider: shipName
      name: name
      departure_date: departDate
      nights: duration
      boarding: embarkPortCode
      booking_url: itineraryURL        # relativer AEM-Pfad, Prefix: https://www.hollandamerica.com
    note: >-
      Holland America Line, oeffentliche Solr-Suche, kein Key. Preis = guenstigster
      Kabinen-Fare (RESTRICTED) PRO PERSON in EUR; taxesAndFeesCombined_EUR=true heisst
      "Steuern & Gebuehren enthalten" (taxExpenses_EUR = Steueranteil darin).
      sortPrice_EUR ist der FLEXIBLE-Preis und NICHT der guenstigste - nicht als Preis nehmen.
      {origin}/{destination} = HAL-Hafencodes (MIA, FLL, HAM, BCN, ...).

  - id: rcl-cruises
    category: cruises
    transport: cli
    enabled: true
    price_scope: per_person
    price_scope_confidence: confirmed
    command: ["python3", "/home/batnini/mimo-agents/providers/cruise_rcl.py",
              "--origin", "{origin}", "--destination", "{destination}",
              "--depart-date", "{depart_date}", "--return-date", "{return_date}",
              "--adults", "{adults}", "--children", "{children}", "--currency", "{currency}",
              "--max-price-calls", "30", "--limit", "15"]
    coerce:
      adults: int
      children: int
    extract:
      items_path: items
      price: price           # Kabinenpreis je Person nach Rabatt, OHNE Steuern
      all_in: all_in         # Endpreis je Person INKL. Steuern
      currency: currency
      provider: provider
      name: name
      departure_date: departure_date
      nights: nights
      boarding: boarding
      booking_url: booking_url
      taxes_included: taxes_included
      drinks_included: drinks_included
    note: >-
      Royal Caribbean/Celebrity, oeffentliche JSON-APIs (kein Key). price = Kabinenpreis
      pro Person OHNE Steuern, all_in = Endpreis pro Person INKL. Steuern
      (taxesAndFeesBundled=true). drinks_included=false -> Getraenke NICHT inklusive.
      {origin} = Abfahrtshafen-Code (MIA/FLL/...), {destination} = Zielregion-Code
      (BAHAM/CARIB/MED/ALASKA/...). Preisbasis belegt: Rechnung skaliert linear mit
      der Personenzahl (1/2/3 Erw. -> 561.15 / 696.30 / 1060.45 USD fuer dieselbe Abfahrt).
```

**Optionaler Zusatzbeitrag (kabinenweise Preise, braucht einen `followup`-Transport):**

```yaml
  - id: hal-price-api
    category: cruises
    transport: http
    enabled: false          # aktivieren, sobald ein 2-Schritt-Followup im Runner existiert
    price_scope: per_person
    price_scope_confidence: confirmed
    url: "https://www.hollandamerica.com/api/v2/price/cruise/{cruise_id}"
    method: GET
    headers:
      Accept: application/json
      country: US
      locale: en_US
      brand: hal
      User-Agent: "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    extract:
      items_path: data.bestAvailable
      price: price
      all_in: price
      currency: currencyCode
    note: >-
      Kabinenweise Preise je HAL-Reise: bestAvailable.price (Endpreis inkl. Steuern),
      .basePrice (ohne Steuern), .tax, .launchPrice, .classification
      (restricted/flexible/baseprice), .amenities.obcUSD (Onboard-Guthaben).
      Braucht {cruise_id} aus hal-cruises -> daher als followup, nicht als eigene Suche.
```

### 4.1 Nötige Ergänzungen im Runner/normalize (additiv, rückwärtskompatibel)

`providers/normalize.py` wurde additiv erweitert (bestehende Flug-/Hotel-Quellen unverändert):

* neue Normalisierungsfelder: `departure_date`, `return_date`, `nights`, `boarding`,
  `destination`, `all_inclusive`, `taxes_included`, `drinks_included`
* `extract.currency` darf jetzt eine **Konstante** sein (`"EUR"`), wenn die Antwort selbst
  kein Währungsfeld führt (bisher wäre `EUR` als Pfadname gesucht worden)
* `dedupe()` nimmt `departure_date` in den Key auf – sonst würden mehrere Abfahrten
  desselben Itinerariums mit gleichem Preis zusammengefasst werden (bei Flügen/Hotels
  ist das Feld nicht gesetzt → Verhalten unverändert)

Für `python3 providers/runner.py --category cruises` muss in `providers/runner.py` die
`choices=["flights","hotels"]` um `"cruises"` erweitert werden (eine Zeile) – der Aufruf
über `runner.run(reg, "cruises", ctx)` funktioniert bereits.

**Beleg des End-to-End-Laufs** (`providers/cruise_evidence/runner_cruises_output.json`):

```json
{"providers":[{"source":"hal-cruises","status":"ok","error":null,"items":20,"elapsed_s":0.2},
               {"source":"rcl-cruises","status":"ok","error":null,"items":15,"elapsed_s":31.47}],
 "totals":{"providers":2,"ok":2,"failed":0,"items":35}}
```

Beispielzeilen daraus:

```
rcl-cruises  Perfect Day CocoCay & Bahamas  price= 213.0  all_in= 348.15 USD dep=2026-11-02 board=MIA n=4 tax_incl=True  drinks=False
hal-cruises  7-DAY EASTERN CARIBBEAN: AMBER COVE & BAHAMAS price=554.0 all_in=554.0 EUR dep=2026-11-28 board=MIA n=7 tax_incl=True
```

---

## 5. All-Inclusive vs. Kabinenpreis

**Kernaussage:** Keine der getesteten keyless Quellen liefert eine *echte*
All-Inclusive-Reise, die Getränke/Verpflegung/Ausflüge **im** Reisepreis enthält. Alle
liefern den **Kabinenpreis inkl. Steuern** und weisen Getränke/Ausflüge/Spa/Internet als
**Aufpreis** aus. Für die Bündelungslogik heißt das: der vergleichbare „Endpreis" ist
`Kabinenpreis + Steuern` – Getränke und Ausflüge dürfen **nicht** als enthalten
ausgewiesen werden.

| Feld | Quelle | Bedeutung | Wert im Test |
|---|---|---|---|
| `taxesAndFeesCombined_<CCY>` | HAL Suche | Steuern & Gebühren **im** Preis | `true` (U680: 274.37 EUR von 839 EUR) |
| `taxExpenses_<CCY>` | HAL Suche | Steueranteil **innerhalb** des Preises | `204.6` / `237.16` / `274.37` EUR |
| `price_<CCY>_RESTRICTED` | HAL Suche | günstigster Kabinen-Fare (inkl. Steuern) | `604` / `839` EUR |
| `price_<CCY>_BASEPRICE` | HAL Suche | Basis-Tarif (inkl. Steuern) | `639` / `889` EUR |
| `price_<CCY>_FLEXIBLE` | HAL Suche | erstattbare Anzahlung | `1129` / `1589` EUR |
| `data.bestAvailable.basePrice` | HAL Preis-API | Kabinenpreis **ohne** Steuern | `849` USD (Preis 999 − tax 150) |
| `data.bestAvailable.tax` | HAL Preis-API | Steuern/Gebühren | `150` USD / `237.16` EUR |
| `data.bestAvailable.taxAndFeesCombined` | HAL Preis-API | Steuern im Preis | `true` |
| `data.bestAvailable.amenities.obcUSD` | HAL Preis-API | Onboard-Guthaben **im** Tarif | `100.00` USD |
| `data.bestAvailable.classification` | HAL Preis-API | Tarifart (Zahlungsart, **kein** All-Inclusive) | `restricted` |
| `includedPromos` / `promoCodes` | HAL Preis-API | aktive Aktionen | `["NS1","Z34"]` / `["QF_USD"]` |
| `pricing.invoice.taxesAndFees` | RCL room-selection | Steuern + Hafengebühren (im `total`) | `270.3` USD (Partei) |
| `pricing.invoice.potentialBeveragePackage` | RCL room-selection | Getränkepauschale enthalten? | **`false`** ⇒ nicht enthalten |
| `rooms[].room.pricing.taxesAndFeesBundled` | RCL room-selection | Steuern im Preis | `true` |
| `rooms[].room.pricing.refundability` | RCL room-selection | Zahlungsart | `DEPOSIT_NOT_REFUNDABLE` |
| `rooms[].room.stateroomType.included` | RCL room-selection | im Tarif enthaltene Leistungen | `[]` |
| `pricing.invoice.discount.items[].description` | RCL room-selection | Aktionen | `"60% Off Second Guest"`, `"Scary Good Deals"`, `"3rd & 4th Guests Sail Free"` |
| **`isAllInclusive`** | RCL Iterarionsseite | **echtes All-Inclusive-Flag** | `false` |
| `included[].type = "standard"` | RCL Iterarionsseite | inklusive Leistung | Food/Buffets, Standardgetränke, Entertainment, Privatinsel |
| `included[].type = "premium"` | RCL Iterarionsseite | **Aufpreis** | SpecialtyRestaurants, Drinks, WiFi, Spa, ShoreExcursions, Photography, Nursery, Laundry |
| `pricing.roomTypeDescription` | RCL Iterarionsseite | Steuer-/Trinkgeld-Hinweis | `"Prices include taxes and fees (optional gratuities are not included)."` |
| `pricing.priceDisclosureIncludedTaxesAndFees` | RCL Iterarionsseite | Textbaustein | `"*Taxes & fees included"` |
| `pricing.priceDisclosureExcludedTaxesAndFees` | RCL Iterarionsseite | Textbaustein | `"*plus {taxesAndFees} in taxes & fees"` |
| `pricing.pricingShownIsPerPerson` | RCL Iterarionsseite | Preisbasis | `"Pricing shown is per person."` |
| `price[].promotionalPrice` (Kategorie `beverage`) | RCL GraphQL | Getränkepauschale als Aufpreis | `13.99` … `36.99` USD |

**Empfehlung für die Bündelungslogik**

1. `price` = Kabinenpreis **ohne** Steuern, `all_in` = **mit** Steuern – bei HAL ist die
   Quelle nur „inklusive" verfügbar, dann sind beide Felder gleich und `taxes_included=true`.
2. `taxes_included`/`taxesAndFeesCombined` ist das **einzige** belastbare Feld für
   „Steuern drin?".
3. `drinks_included`/`potentialBeveragePackage` bzw. die `included[].type`-Liste ist das
   belastbare Feld für „Getränke/Extras drin?".
4. **Trinkgelder sind nie enthalten** („optional gratuities are not included") und
   **Flug/Transfer nie** („cruise only") – beides gehört als Zusatzposition in die Bündelung.
5. Für echte All-Inclusive-Reedereien (AIDA, TUI Cruises, Costa mit Getränkepaket,
   Hapag-Lloyd) gibt es derzeit **keine** keyless JSON-Quelle – diese Lücke ist offen
   (siehe Negativbefunde §3).

---

## 6. Empfehlung

| Aufnahme | Quellen | Begründung |
|---|---|---|
| **Ja** | `hal-cruises` (http), `rcl-cruises` (cli) | keyless, echte Live-Preise, Währung, Preisbasis und Steuernachweis belegt; im Runner end-to-end getestet (2/2 `ok`) |
| **Ja, als Zusatz** | `hal-price-api`, `royalcaribbean-web-api`, `royalcaribbean-room-selection`, `royalcaribbean-itinerary-page`, `celebrity-cruises` | liefern die kabinenweisen Preise, die Rechnung, das `isAllInclusive`-Flag und die zweite Reederei |
| **Nein** | Siloah MCP, Cruise-Itinerary MCP, VECTO, MSC, Costa, NCL, Hapag-Lloyd, Viking, TUI/AIDA, Expedia/Kayak/HolidayCheck/Check24/Cruise1, Amadeus/Google Travel/CruiseMapper | key, Login, WAF, Rate-Limit oder gar kein JSON (wörtliche Fehler in §3) |

**Nächste Schritte**

1. `providers/registry.yaml` um die beiden Blöcke aus §4 ergänzen, `runner.py`-`choices` um
   `"cruises"` erweitern (eine Zeile).
2. `{origin}`/`{destination}` für Kreuzfahrten als **Hafencode/Region** definieren
   (HAL: `MIA`/`BAHAM`; RCL: `MIA`/`BAHAM`) und im Coordinator-Prompt (`harness/current.md`)
   die Mapping-Regel ergänzen.
3. HAL-Währung dynamisch machen (aktuell im Registry-Block fixiert auf EUR, weil der
   Währungscode im Feldnamen steckt) – entweder über einen kleinen CLI-Wrapper analog zu
   `cruise_rcl.py` oder über `extract.price` mit Fallback-Pfaden.
4. All-Inclusive-Reedereien weiterverfolgen (AIDA/TUI/Costa/Hapag): lohnt sich, weil dort
   `drinks_included`/`all_inclusive` tatsächlich `true` wären.
5. Siloah-MCP in ein paar Wochen erneut prüfen – die API passt exakt zum Bedarf (keyless, MIT).

---

## 7. Installationen / Umgebungsänderungen

* **Kein** MCP-Server installiert, deinstalliert oder umkonfiguriert.
* Neu angelegt: `providers/cruise_rcl.py` (Python 3, nur Standardbibliothek + `requests`),
  `providers/registry.cruises.yaml`, `providers/cruise_candidates.json`,
  `providers/cruise_evidence/*`, `docs/SOURCES_CRUISES.md`.
* `providers/normalize.py`: additiv erweitert (neue Felder, Währungskonstante,
  `dedupe`-Key) – **keine** Änderung an bestehenden Flug-/Hotel-Feldern.
* `providers/runner.py`: **nicht** geändert (`--category cruises` fehlt noch in `choices`).
* Nur im Testverzeichnis: `/tmp/opencode/cruise/venv` mit `curl_cffi==0.16.3`
  (nur für die WAF-Tests; die ausgelieferten Skripte brauchen es nicht).
* Nichts unter `/home/batnini/mimo-agents/harness/` geändert.
