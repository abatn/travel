# Orts-Resolver: Recherche, Bewertung, Entscheidung

Stand: 23.10.2026 · Umsetzung: `resolver/resolver.py`, Daten: `resolver/data/`

## 1. Problem

Die Quellen brauchen **unterschiedliche Schlüssel**:

| Kategorie | Schlüssel | Beispiel | Verhalten bei Freitext (gemessen) |
|---|---|---|---|
| Flüge | IATA-Flughafencode | TLS, FRA | „frankfuhrt“ → 0 Angebote (Fehler je Quelle) |
| Hotels | Stadt (+ teils `placeId`/Koordinaten) | Rome | „Rone“ → 37 Angebote (Google-Quellen tolerant), `maqami` scheitert |
| Fähren | Hafenname | Barcelona / Palma | „Toulouse“ → 0 mit klarer Meldung |
| Kreuzfahrten | **3-stelliger Hafen-Code** | MIA, HAM | „Miami“ → **0 Angebote ohne Fehler** (still) |

Ohne Auflösung entstehen also 0-Treffer, stille Fehlschläge und – schlimmer – **verstopfte
Circuit Breaker**: Ein Tippfehler wurde als Quellenausfall gewertet und sperrte 10 Quellen für
bis zu 30 Minuten (live beobachtet).

## 2. Recherche: verfügbare Quellen

| Quelle | Inhalt | Lizenz | Abdeckung | Aktualität | Beleg |
|---|---|---|---|---|---|
| **OurAirports** | Flughäfen: `iata_code`, `municipality`, `name`, `keywords`, Koordinaten, `scheduled_service` | **Public Domain** | 8 691 mit IATA, davon 4 066 mit Linienverkehr | nächtlich | `ourairports.com/data`, `davidmegginson/ourairports-data` |
| **UN/LOCODE** (UNECE) | Orte/Häfen: `Country`+`Location`, `Name`, `Function` (1 = Hafen, 4 = Flughafen), `IATA`, Koordinaten | UNECE-Veröffentlichung; CSV-Aufbereitung **ODC-PDDL-1.0** | **17 607 Häfen** | halbjährlich + Pre-Release | `unece.org/trade/cefact/UNLOCODE-Download`, `github.com/datasets/un-locode` |
| **GeoNames** | 13 Mio. Orte, Suche mit `fuzzy`, `geonameId`, Koordinaten | **CC BY 4.0** | weltweit | täglich | `geonames.org/export/web-services.html` |
| **airportsearch** (PyPI) | fertige Fuzzy-Suche über Flughäfen | MIT | ~5 000 Verkehrsflughäfen | Paket | `github.com/bgokden/airportsearch` |
| IATA-Codeliste | amtlich | **kostenpflichtig**, Rechte unklar | – | – | – |

**Fallstricke (belegt):**
* **Reederei-Hafen-Codes ≠ UN/LOCODE**: HAL/RCL nutzen 3-stellige Codes (MIA, HAM, BCN). Für
  Miami/Hamburg/Barcelona stimmen sie mit dem LOCODE-Ortsteil überein, für z. B. Civitavecchia
  (ITCVV) nicht mit dem Flughafen (FCO). Deshalb: **Hafenname aus UN/LOCODE, Code = IATA falls
  vorhanden, sonst LOCODE-Ortsteil** – und die Anbieter-Hafenliste bleibt Gegenprobe.
* **IATA-Rechte**: OurAirports ist Public Domain, die Rechte an den IATA-Codes selbst sind
  rechtlich nicht eindeutig geklärt (die Datensatz-Pakete weisen ausdrücklich darauf hin).
  Für die interne Auflösung unkritisch; bei Weiterverbreitung prüfen.
* **Mehrflughafen-Städte** (London, Rom, Paris): mehrere gültige Codes → Alternativen anzeigen.

## 3. Vergleichsmatrix und Entscheidung

| Lösung | Lizenz | Abdeckung | Aufwand | Zuverlässigkeit | Entscheidung |
|---|---|---|---|---|---|
| OurAirports (lokal) | Public Domain | sehr gut (Flughäfen) | mittel (12,7 MB → 1,9 MB JSON) | sehr hoch (offline) | **ja, Flüge + Städte** |
| UN/LOCODE (lokal) | ODC-PDDL (UNECE) | sehr gut (Häfen) | mittel (7,3 MB → 2,7 MB JSON) | sehr hoch (offline) | **ja, Fähren + Kreuzfahrten** |
| GeoNames (API) | CC BY | exzellent (Städte) | niedrig | hoch, aber Netz + Konto | **nein** (unnötig: OurAirports-Städte reichen; optional später) |
| airportsearch (Paket) | MIT | gut | niedrig | gut | **nein** (neue Abhängigkeit; `difflib` genügt) |
| IATA-Liste | kostenpflichtig | amtlich | – | – | **nein** |
| Anbieter-Hafenlisten | – | nur je Anbieter | hoch | gut | **nur als Gegenprobe** |

**Begründung:** Zwei **offline** Datenbestände mit klaren Lizenzen decken alle vier Kategorien ab.
Keine Netzabhängigkeit im Suchpfad (die Quellen selbst sind schon fragil genug), keine neuen
Python-Pakete (`difflib`, `csv`, `json` reichen), und die Datenhoheit bleibt bei uns. GeoNames
wäre nur nötig, wenn Städte ohne Flughafen gebraucht würden – das kommt später ggf. dazu.

## 4. Umsetzung

* **Daten:** `data/airports.json` (8 691 Flughäfen mit IATA+Stadt), `data/ports.json`
  (17 607 Häfen), `data/aliases.csv` (deutsche Exonyme, kuratiert).
* **Resolver:** normalisiert (Unicode, Diakritika), prüft in dieser Reihenfolge:
  1. Kürzel direkt (IATA/LOCODE),
  2. deutsches Exonym – exakt und per Fuzzy („Wienn“ → Wien → Vienna),
  3. Kandidatentreffer mit Stufen: exakt 1,0 → ganzes Wort 0,95 → Namensanfang 0,93 →
     Wortanfang 0,85 → enthalten 0,80 → Fuzzy (nur mit gleichem Wortanfang oder ≥ 0,80).
  Zusatzsignale: Stadt schlägt Flughafenname, großer Flughafen mit Linienverkehr schlägt
  Ackerstreifen.
* **Cache:** `state/cache.json` (5 000 Einträge, Ringpuffer) – Auflösungen sind stabil.
* **UI:** Autocomplete (`/api/resolve/suggest`), Prüfung beim Verlassen (`/api/resolve`),
  Anzeige „Toulouse → TLS“ auf der Ergebnisseite.
* **Fehlerfall:** Die Kategorie wird mit klarer Meldung beendet („Ort nicht gefunden. Meintest du:
  …?“), **bevor** Quellen belastet werden.
* **Breaker:** löst nur noch bei transienten Fehlern aus (429/5xx/Timeout). Eingabefehler zählen
  nicht als Quellenausfall; die 7 vergifteten Einträge wurden entfernt.

## 5. Tests (Ergebnis)

| Eingabe | Kategorie | Erwartet | Ergebnis |
|---|---|---|---|
| Toulouse | Flüge | TLS | ✅ TLS (Toulouse-Blagnac) |
| frankfuhrt | Flüge | FRA | ✅ FRA (Score 0,81) |
| Rom | Hotels | Rom (FCO) | ✅ FCO, Stadt „Rome“ |
| Barcelona → Palma | Fähren | ESBCN / ESPMI | ✅ beide |
| Miami | Kreuzfahrten | MIA | ✅ MIA |
| Wienn | Hotels | Wien (VIE) | ✅ VIE |
| Barcleona | Flüge | BCN | ✅ BCN |
| Xyzzy | Flüge | nicht gefunden | ✅ ok=false, keine Quellenabfrage |

## 6. Offene Punkte

* **Mehrflughafen-Städte:** Der erste Treffer ist nicht immer der größte („Londn“ → LGW, LHR steht
  in den Alternativen). Eine Popularitätsquelle (z. B. OpenFlights-Routenanzahl) könnte das lösen.
* **Städte ohne Flughafen** (z. B. Utrecht): bräuchte GeoNames oder eine Stadt-GeoDB.
* **Hafen-Codes der Reedereien:** Für Häfen, deren Reederei-Code vom LOCODE abweicht, bleibt die
  Anbieter-Hafenliste die Gegenprobe (nicht automatisiert).
* **Alias-Tabelle** ist kuratiert (~110 Einträge) und muss bei Bedarf wachsen.
