# Offizielle Standards: Was wir daraus bauen können

Stand: 24.10.2026. Ziel: eigene Datenbasis statt Lizenz-Aggregator. Diese Datei
trennt klar, was offene Standards **frei** liefern und was einen Vertrag braucht.

## Die vier relevanten Standards

| Standard | Herausgeber | Was es liefert | Preis-Daten? | Zugang |
|---|---|---|---|---|
| **IATA NDC v17.2** (New Distribution Capability) | IATA | Airline-Angebote inkl. Preis, Tarif, Segmenten | **ja** | Vertrag mit Airline/Aggregator |
| **OpenTravel (OTA)** | OpenTravel Alliance | Hotel-/Mietwagen-/Air-Verfügbarkeit (XML) | ja | Vertrag mit Supplier |
| **GTFS / GTFS-Realtime** | Google/Transit, offener Standard | Fahrpläne + Echtzeit für Fähren, Bus, Bahn | **nein** | offen, Betreiber veröffentlichen |
| **OurAirports / ICAO-Codes** | OurAirports (Public Domain) | Flughafen-Stammdaten, Koordinaten, IATA/ICAO | nein | frei |

**Kernaussage:** Flughäfen und offene Standards liefern **Stammdaten und
Fahrpläne**, aber **keine Preise**. Preise kommen ausschließlich über
NDC/OTA-Zugänge (Vertrag) oder Scraping (AGB-Verstoß, bei uns gesperrt).

## Geklonte Referenzprojekte (nur Logik/Struktur studiert)

| Repo | Lizenz | Erkenntnis | Code übernommen? |
|---|---|---|---|
| <https://github.com/davidmegginson/ourairports-data> | Public Domain | CSV-Schema: `iata_code`, `municipality`, `latitude_deg`, `scheduled_service` | nein, eigenes Laden/Parsen |
| <https://github.com/google/transit> | CC BY 4.0 (Spec) | GTFS-Dateien: `stops`, `routes`, `trips`, `stop_times`, `calendar`; Zeiten dürfen > 24:00 sein | nein, eigene Implementierung |
| <https://github.com/airtechzone/ndc-json-172> | MIT | IATA NDC v17.2 Nachrichtenformat (nur Requests im Sample) | nein |
| <https://github.com/MobilityData/gtfs-validator> | Apache-2.0 | Regelwerk für gültige GTFS-Feeds | nein |

## Was im Projekt gebaut wurde

**`providers/reference/airports.py`**
- `load_airports(path)` liest die OurAirports-CSV (Pfad über `AIRPORTS_CSV`).
- `lookup`, `search` (Stadt/Name), `nearest` (Haversine, nur Flughäfen mit
  Linienverkehr), `distance_km`.
- **Real getestet:** 9.054 Flughäfen mit IATA-Code; `TUN` → Tunis Carthage,
  nächste an Tunis: TUN 11,2 km / NBE 77,5 km / MIR 120,3 km.

**`providers/reference/gtfs.py`**
- `GtfsFeed(directory)` liest `stops/routes/trips/stop_times/calendar`.
- `departures(from_stop, to_stop, date, after)` → direkte Verbindungen mit
  Abfahrt, Ankunft, Dauer; Zeiten über 24:00 werden korrekt behandelt.
- Liefert bewusst **kein** Preisfeld.

**Tests:** `providers/tests/test_reference.py`, 11/11 grün, ohne Netzwerk.

## Wie Preise später angeschlossen werden

1. NDC-Zugang bei einer Airline oder einem Aggregator beantragen.
2. Adapter `providers/ndc.py` mit `normalize_offers()` (gleiche Zielstruktur wie
   bei Amadeus: `price`, `currency`, `stops`, `airline`, Zeiten).
3. Registry-Eintrag mit `rights.status: approved` **erst nach Vertrag**.
4. Der bestehende Filter `providers/rights.py` bleibt die Sperre.

## Ehrliche Grenze

Ein Klon eines offiziellen Projekts liefert **Code und Struktur**, keine
Datenrechte. Die frei nutzbaren Teile sind Stammdaten (OurAirports) und
Fahrpläne (GTFS). Wer Preise zeigen will, braucht einen NDC-/OTA-Vertrag.
