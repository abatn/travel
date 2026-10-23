# Architektur-Erweiterung: drei Fähigkeiten

Stand 21.10.2026 · alle Preise ausschließlich aus den gebundenen MCP-/CLI-Werkzeugen.

```
providers/                 Fähigkeit 1 – dynamische API-Abdeckung
  registry.yaml              Konfiguration aller Quellen (Flüge/Hotels) – einziger Ort für Erweiterungen
  runner.py                  fragt alle aktiven Quellen parallel ab, normalisiert, rankt
  normalize.py               Pfad-/Spalten-Extraktion, Dedupe, Ranking
  mcp_stdio.py               MCP-Client (stdio)
  mcp_http.py                MCP-Client (Streamable HTTP)
bundling/                  Fähigkeit 2 – intelligente Kombination
  compare.py                 Paket vs. Rundflug+Hotel vs. Gabelflug, mit Belegzitaten
  evidence.json              recherchierte Belege (TRIZ-Recherche), wird von compare.py zitiert
alerts/                    Fähigkeit 3 – Preis-Alarm
  watcher.py                 Snapshot über alle Quellen, Regelprüfung, Cooldown, State
  alert_config.example.yaml  Regeln/Quellen/Scheduler (Beispiel)
  price-watcher.service|.timer, crontab.example
docs/                      Recherche- und Architekturdokumentation
```

## Fähigkeit 1 – Dynamische API-Abdeckung

* **Eine Registry, kein Code.** Jede Quelle ist ein YAML-Eintrag in `providers/registry.yaml`:
  `transport` (`mcp_stdio` | `mcp_http` | `http` | `cli`), Kommando/URL, Tool, Parameter mit
  Platzhaltern (`{origin}`, `{destination}`, `{city}`, `{depart_date}`, `{adults}`, …), Typ-Korrekturen (`coerce`)
  und Extraktionspfade (`extract`) für Preis, Währung, Stopps, Endpreis, Koordinaten, Sterne, Link.
  **Neue API = ein YAML-Block.** Es ist kein Python-Code anzufassen.
* **Aktuell 22 Quellen** (Registry, davon 20 aktiv) in **vier Kategorien**: Flüge `trvl_flights`, `fli_flights`,
  `skiplagged_flights`, `maqami-travel`, `octotrip-flights`, `alice-flights`, `flights-gf`, `googleflights-local`,
  `easygroupflights`; Hotels `stays_hotels`, `rome_hotel_taxes`, `maqami-travel-hotels`, `callstay`,
  `pilotplans-hotels`, `bookresorts`; **Fähren** `ferryhopper_mcp`, `trvl_ferries`, `finnlines_ferry`;
  **Kreuzfahrten** `hal-cruises`, `rcl-cruises` (+ `skiplagged_hotels` und `hal-price-api` derzeit deaktiviert).
  Details zu den Schiffskategorien: `docs/SCHIFFSREISEN.md`.
  Recherche und Einzeltests: `docs/SOURCES_FETCH.md`, Rohdaten: `providers/registry.candidates.json` (33 geprüfte Kandidaten).
* **Preis-Scope-Normalisierung.** Quellen mischen **pro Person** (trvl, fli, Ferryhopper, HAL, RCL), **pro Reise**
  (maqami, octotrip, alice, flights-gf), **pro Nacht** (Hotels) und **pro Aufenthalt** (maqami-Hotels). Jede Quelle
  deklariert `price_scope`; der Runner rechnet alles auf eine vergleichbare Basis (je Person) und führt
  `price_total`/`price_per_person` mit – sonst wäre der „günstigste“-Vergleich bei 2 Personen schlicht falsch.
  Fährpreise kommen in Cent → `extract.price_divisor` (100).
* **Parallelität.** Der Runner fragt alle aktiven Quellen einer Kategorie gleichzeitig ab
  (`ThreadPoolExecutor`, `max_workers` aus `defaults`) und liefert je Quelle Status, Dauer und Fehlerbild.
* **Robustheit (Benchmark-Erweiterung).** Ein blockierter Anbieter degradiert die Abfrage, statt sie zu beenden:
  Status `error` mit wörtlichem Fehlerbild, die übrigen Quellen liefern weiter. Vier zusätzliche Mechanismen
  (Muster aus der Benchmark-Recherche, siehe `benchmark/vergleich.md`):
  * **Circuit Breaker** – eine Quelle, die kürzlich 429/Timeout hatte, wird für ein exponentiell wachsendes Fenster
    übersprungen (`providers/state/breakers.json`).
  * **Retry mit Backoff + Jitter** – nur bei transienten Fehlern (429/5xx/Timeout); ein 401/403 gilt als Quellendefekt
    und wird *nicht* wiederholt.
  * **Rate-Limit-Governor** (`min_interval_seconds`) und **Kontingent je Quelle und Stunde** (`max_calls_per_hour`)
    – **adaptiv**: bei Drosselung halbiert, nach drei guten Läufen mit 1,5 multipliziert, nie über dem
    konfigurierten Maximum (`providers/state/quota.json`).
  * **„Terminal ≠ finished“** – Werkzeugfehler werden als Fehler gemeldet (nicht als „0 Angebote“), und liefert eine
    Quelle ein anderes Format (Text statt JSON), greift eine konfigurierte Rückfallebene (`extract.fallback`).
* **Plausibilitätsprüfung gegen kaprupte Preise.** Eine Quelle kann formal gültig antworten und dabei
  Unsinn melden (0,01 EUR statt 180 EUR). `providers/plausibility.py` verwirft solche Angebote, meldet die
  Quelle als **korrupt** und nimmt ihre Tarife nicht in den Vergleich auf:
  * *absolute Untergrenze* (1,00 €) und *fachliche Untergrenzen je Kategorie* (Flug 4,99 €, Fähre 3,00 €,
    Kreuzfahrt 40,00 €, Hotel 5,00 €) – darunter kann der Preis nicht echt sein;
  * *typische Fehlerwerte* (0,01 / 0,10 / 0,50 / 1,00);
  * *Ausreißer innerhalb einer Quelle* – ein Preis unter 15 % des Medians der **eigenen** Quelle ist ein
    Datenfehler (um Größenordnungen daneben).
  Der Vergleich mit dem **Marktmedian** ist bewusst abgeschaltet: er hängt davon ab, welche Quellen antworten
  und welche Tarife sie liefern – im Test wurde ein korrekter Preis von 29,58 € fälschlich verworfen, weil zwei
  Quellen nur teure Tarife (143–216 €) gemeldet hatten. Sind **alle** Quellen korrupt, liefert das System
  **keine** Preisauskunft (`cheapest: null`) statt eines erfundenen Preises; die Bündelung weist die
  Datenqualität unter `data_quality` aus.
* **Angebotsbewertung statt reiner Preissortierung.** `providers/score.py` gewichtet Preis, Stopps, Dauer, Abfahrtszeit
  und Gepäck zu einem Score (0..1); harte Gates (`max_stops`, `max_duration`) schließen ein Angebot aus
  (`gate_failed`). Gewichte und Profile (`budget`, `comfort`) stehen in der Registry, `rank_by: score|value`
  („knappster statt billigster“ = Preis je Person und Tag).
* **Währungen.** Fremdwährungsangebote werden mit **belegtem** Kurs umgerechnet (`tools/fx.py`, keyless, mit Quelle
  und Stand) und als umgerechnet gekennzeichnet; ohne belegten Kurs wird nicht umgerechnet, sondern die Abweichung
  ausgewiesen. Quellen mit unbestätigter Preisbasis (`price_scope_confidence: unverified`) erscheinen in der Liste,
  besetzen aber nicht den „günstigsten“-Platz.
* **Sonderfälle ohne Code:** Markdown-Tabellen statt JSON (`extract.parser: table` mit Spaltenzuordnung),
  Angebote mit Ratelliste je Hotel (`extract.expand`, auch **mehrebenig** `[roomTypes, rates]`),
  Hüllen, die JSON als String enthalten (werden entpackt), und **zweistufige Quellen** (`followup`:
  je Ergebnis ein Follow-up wie `callstay` (`search_stays` → `price_stay`) **oder** als Sammelaufruf
  (`followup.mode: batch`, z. B. `maqami-travel-hotels`: `get_data_hotels` → `post_hotels_rates`
  mit allen Hotel-IDs; Suchtreffer und Ratenantwort werden an der Hotel-ID verschmolzen).

Beispiel:
```bash
python3 providers/runner.py --category flights --origin BER --destination FCO \
    --depart-date 2026-10-31 --return-date 2026-11-02 --adults 2 --currency EUR
```

**Schiffsreisen** (eigene Kategorien, siehe `docs/SCHIFFSREISEN.md`): Fähren `ferryhopper_mcp` (Preise in Cent,
`hasCabin/hasVehicles`-Flags), `trvl_ferries` (EUR), `finnlines_ferry` (GraphQL, `chargeTotal`, `isAvailable`);
Kreuzfahrten `hal-cruises` (Kabinenpreis inkl. Steuern, `taxesAndFeesCombined_EUR`, `soldOut`) und `rcl-cruises`
(Basis- und Endpreis, `taxesAndFeesBundled`, `potentialBeveragePackage`, `refundability`).

**Steuerfähige Quellen** (Ergebnis der Recherche, siehe `docs/SOURCES_FETCH.md`):
* Flüge: nur `maqami-travel` weist Steuern/Gebühren aus (`pricing.display = {base, taxes, fees, total}`).
  Alle übrigen Flugquellen liefern **kein** Steuerfeld (trvl: `all_in_cost` = Preis + **Gepäck**, nicht Steuern).
* Hotels: `maqami-travel-hotels` (`taxesAndFees[].amount` + `included`), `callstay` (`rooms[].total_all_in`
  + `fees[].included_in_total` + `due_at_property`), `rome-hotel-taxes` (`rates[].total` + `tax` + `fees`),
  `stays` (`includes_taxes_and_fees` – im Paket ein **toter Schalter**, nie `true`).

## Fähigkeit 2 – Intelligente Kombination

`bundling/compare.py` rechnet aus denselben Runner-Ergebnissen drei Varianten:

| Variante | Rechnung |
|---|---|
| `separate_roundtrip` | günstigster Rundflug × Personen + günstigstes Hotel × Nächte |
| `split_roundtrip` | günstigster Einweg (Hin) + günstigster Einweg (Rück), je × Personen + Hotel |
| `package` | Pauschalpreis aus einer Paketquelle (optional) |

Die Empfehlung ist die **billigste** Variante, zusammen mit Differenz zu jeder Alternative, den Risiken der
gewählten Variante (getrennte Tickets = kein Anschlussanspruch, Gepäck neu einchecken) und den Belegzitaten aus
`bundling/evidence.json`. Die Belege stammen aus der Recherche (Luftfahrt-/Verbände, Behörden, Reiseanalyse);
`evidence.json` ist mit ID (E1, E2, …), Verlag, Datum, URL und **wörtlichem Zitat** hinterlegt, damit die
Begründung des Agenten belegbar bleibt. Gegenpositionen werden mitgeführt, damit die Logik nicht einseitig ist.

**Ehrliche Grenze der Evidenz** (aus `evidence.json.gap_notes`): Die Belege zeigen ein **mögliches**
Sparpotenzial getrennter Buchung (E1: bis 30 % international, E2/E7/E9 Mechanik „Hacker Fare“), tragen aber
**keine** allgemeine Regel „getrennt ist in der Regel günstiger“ – E6 desselben Anbieters zeigt das Gegenteil
als Regelfall. Ebenso gibt es **keinen** belastbaren Prozent-/Eurobeleg für „Flug+Hotel getrennt vs. Pauschale“
im deutschen Markt (E10 belegt nur die Marktverteilung). Deshalb ist die Runtime-Logik bewusst
**vergleichend statt behauptend**: sie rechnet live, zitiert die Belege und weist die Grenze aus.

## Fähigkeit 3 – Preis-Alarm

`alerts/watcher.py` beobachtet denselben Quellenbestand wie die Suche (konfigurierbar über `providers:` in der
Alarm-Config) und schreibt pro Lauf einen Snapshot (Zeit, günstigster Preis, Endpreis, Quelle, Einzelwerte je
Quelle, optionale Zusatzsignale) in `state/history.jsonl`.

Regeln (alle in `alerts/alert_config.example.yaml`):
* **Budget**: Alarm, sobald der Preis ≤ Nutzerbudget (je Person oder für die ganze Reise).
* **Tiefpunkt**: Alarm, sobald der Preis ≤ Referenz aus dem Beobachtungsfenster
  (`mode: median_x | min_over_lookback | percentile`, `lookback_days`, `min_drop_pct`).
* **Cooldown**: kein Alarm innerhalb `cooldown_hours` – außer der Preis sank um ≥ `alert_on_improvement_pct`.
  Preis-Dedup: derselbe Preis alarmiert nicht erneut; ein **neuer Tiefpunkt** durchbricht den Cooldown
  (High-Water-Baseline, wie im nativen trvl-Wächter).
* **State**: `history.jsonl` (Verlauf), `alerts.jsonl` (ausgelöste Alarme), `last_alert.json` (Cooldown-Logik).
* **Native Provider-Signale** (verifiziert, `docs/ALERT_RESEARCH.md`): `trvl watch list --format json` (Zustand:
  `below_price`, `last_price`, `lowest_price`, `baseline_price`, `alert_drop_pct`, `last_alerted_price`),
  `trvl watch history <id> --format json` (Historie), `trvl watch add … --below <Ziel> [--webhook URL]`
  (persistenter Schwellwert-Wächter mit strukturiertem Push), `trvl watch check` (Deal-Events),
  `price_position` (Band/Verdict/Median/Confidence in der Suchantwort), `trvl forecast` (Kauf-Jetzt-Konfidenz,
  Drop-Wahrscheinlichkeit), `trvl rate-status` (Provider-Cooldowns). Der Wächter übernimmt die native Historie
  **zusätzlich** zu seiner eigenen, rechnet ein Coverage-Gate (`min_observations`) und nutzt die
  High-Water-Baseline – dieselbe Semantik wie trvls eigener Wächter.

Betrieb: systemd-Timer (`price-watcher.service|.timer`, stündlich) oder cron (`crontab.example`) oder
Dauerbetrieb `--loop --interval 3600` (Container). Alarmzustellung optional über `notify.command`
(JSON auf stdin). Der Wächter nutzt zusätzlich native Signale des Providers (z. B. `trvl dates`,
`trvl forecast`, `price_position`) als Kontext – konfigurierbar über `context_commands`.

## Weboberfläche (`ui/`)

Die Oberfläche ist eine **dünne Schicht** über den vorhandenen Modulen – sie enthält keine eigene
Reiselogik:

```
Browser ──HTTP──> ui/app.py (FastAPI) ──> ui/service.py ──> providers/runner.py   (Suche)
                                        ├─> bundling/compare.py (Bündelung)
                                        └─> alerts/watcher.py    (Alarme, als Unterprozess)
```

* **Warum FastAPI + Jinja2:** Beides ist im System-Python vorhanden, es braucht keinen Build-Schritt
  und keine neue Abhängigkeit – passend zu einem System, dessen Logik reines Python ist.
* **Job-Modell:** Eine Suche über 22 Quellen dauert 1–2 Minuten; eine synchrone HTTP-Antwort wäre
  unbrauchbar. Der Suchlauf läuft deshalb im Hintergrundthread, die Ergebnisseite pollt
  `/api/jobs/<id>` und zeigt währenddessen **live** je Quelle, ob sie antwortet, übersprungen oder
  blockiert ist. Dafür hat `providers/runner.py` einen optionalen Parameter `progress` bekommen
  (Callback je abgeschlossener Quelle) – ohne Callback ist das Verhalten unverändert.
* **Bündelung:** Die Empfehlung kommt aus `compare()`; die Oberfläche zeigt Varianten, Begründung
  und Evidenzgrenze unverändert an.
* **Alarme:** Die Oberfläche schreibt eine Wächter-Konfiguration (`ui/state/alarms/<id>/watcher.yaml`)
  und startet den vorhandenen Wächter; die Regelauswertung bleibt im Wächter.
* **Buchen:** Das System hat keine Buchungs-, Zahl- oder Reservierungsfunktion. Die Oberfläche führt
  deshalb zum Anbieter (`booking_url`, nur `http(s)`-Links); sie erfindet keine Zahlungsstrecke.
* **Datenqualität sichtbar:** Blockierte Quellen, korrupte Preise und die ausgewiesenen
  Einschränkungen stehen in der Ergebnis- und Detailansicht – nicht in einem Kleingedruckten.

## Orts-Resolver (`resolver/`)

```
Nutzereingabe ──> resolver.resolve(text, kategorie)
                   ├─ Kürzel direkt (IATA / UN/LOCODE)
                   ├─ deutsches Exonym (exakt + Fuzzy: „Wienn“ -> Vienna)
                   └─ Kandidaten: exakt > ganzes Wort > Namensanfang > enthalten > Fuzzy
                                  (Stadt schlägt Flughafenname; großer Flughafen schlägt Ackerstreifen)
                                 ↓
              flights: IATA · hotels: Stadt+Koordinaten · ferries: Hafenname · cruises: Hafen-Code
```

* **Offline:** `data/airports.json` (OurAirports, Public Domain, 8 691 Flughäfen mit IATA) und
  `data/ports.json` (UN/LOCODE, 17 607 Häfen) sowie `data/aliases.csv` (deutsche Exonyme).
  Kein Netz im Suchpfad, keine neuen Abhängigkeiten (`difflib`, `csv`, `json`).
* **Cache:** `resolver/state/cache.json` (Ringpuffer 5 000).
* **UI:** Autocomplete, Anzeige der Auflösung, klare Meldung bei unbekannten Orten.
* **Fail-fast:** Ist ein Ort nicht auflösbar, wird die Kategorie beendet, **bevor** Quellen laufen.
* **Breaker:** löst nur bei transienten Fehlern (429/5xx/Timeout) aus – Eingabefehler nicht.

## Suchmaschinen-Schicht (`seo/`)

```
Suchlauf ──> ui/service.py ──> seo/routes_cache.py  (letzte echte Angebote je Route)
                                      │
Seitenaufruf ──> ui/app.py ──> seo/meta.py + seo/jsonld.py ──> HTML (Meta, JSON-LD)
                              seo/pages.py      (indexierbare Seiten)
                              seo/sitemap.py    (sitemap.xml, robots.txt)
```

* **Zwei Sorten Seiten:** dauerhaft (Start, Kategorien, Routen) = indexierbar; Lauf-Ergebnisse
  (`/jobs/<id>`) und Alarme = `noindex`. `/jobs/` steht bewusst **nicht** in der robots.txt,
  weil `Disallow` das `noindex` unwirksam macht.
* **Preise im Markup = Preise im HTML:** JSON-LD wird aus den sichtbaren Angeboten gebaut,
  mit `priceValidUntil` (1 Tag). Routen älter als 7 Tage fliegen aus der Sitemap und werden
  `noindex`.
* **Keine erfundenen Bewertungen:** `AggregateRating` ist nicht implementiert (Manual-Action-Risiko);
  `seo/jsonld.py` enthält die Regel als testbare Funktion.
* **Prüfwerkzeug:** `seo/validate.py` simuliert einen Crawl (robots → Sitemap → jede URL: Status,
  Canonical, `noindex`, H1, JSON-LD, gzip); `seo/tests/test_seo.py` prüft die Bausteine ohne Server.

## Affiliate-Schicht (`affiliate/`)

Buchungslinks können mit einer Partnerkennung versehen werden – **ohne** die Reislogik zu verändern:

```
booking_url ──> affiliate/builder.py ──> affiliate/verify.py ──> UI (mit Disclosure)
                 Domain-Bindung           Struktur + Erreichbarkeit
```

* **Entscheidung und Quellen:** `affiliate/ENTSCHEIDUNG.md` (Travelpayouts, Awin, Direct Ferries,
  12Go, CruiseDirect; Provisionen, Cookies, Rechtslage).
* **Domain-Bindung:** Ein Partner taggt nur Hosts aus seiner `domains`-Liste. Ein Hotel-Partner kann
  keinen Airline-Link taggen; Billigflieger (keine Provision) bleiben ungetaggt.
* **Keine erfundenen Kennungen:** ohne `id`/`link_template` in `affiliate/config.yaml` wird nicht
  getaggt; die UI nennt den Grund.
* **Prüfung vor Anzeige:** Struktur (ID im Link, Ziel eingebettet) + Erreichbarkeit (HEAD/GET, 6 s,
  Cache 1 h, Host-Allowlist). Nur geprüfte Links werden als Affiliate-Link ausgewiesen.
* **Recht:** Disclosure „Anzeige · Affiliate-Link“ am Link (§ 5a UWG, § 6 DDG), `rel="sponsored"`,
  Rechtshinweis (Vermittler nach §§ 651b/651c/651w BGB, keine Zahlung, kein Gesamtpreis-Angebot).
  `affiliate/legal.py` enthält die Texte und `ui_guard()`, das gerendertes HTML auf Zahlungs- und
  Paketbuchungs-Elemente prüft.

## Preiswächter – Stand nach der Benchmark-Recherche

Der Wächter (`alerts/watcher.py`) ist quellen- und kategorien-agnostisch (Konfiguration) und nutzt denselben
Provider-Runner wie die Suche. Vier Mechanismen kamen aus dem Benchmark-Vergleich dazu:

* **Durable Alarm-Outbox.** Ein Alarm wird nicht direkt „feuer-und-vergessen“ verschickt, sondern zuerst in
  `alerts_pending.jsonl` abgelegt (`event_key` = SHA-256 aus Kategorie, Regel, Preis, Regel-Fassung und
  Anfrage-Hash; `rule_revision` = Hash der Regelfassung). Danach wird zugestellt; der Status (`pending`,
  `acked`, `failed`, `discarded`) und die Versuchszahl stehen in der Outbox. Offene Zustellungen werden im
  nächsten Zyklus erneut versucht (Backoff 5/15/60 min). **Idempotenz:** derselbe Alarm erzeugt genau eine
  Zustellung. **Revisions-Fencing:** wurde die Regel zwischen Auslösung und Zustellung geändert, wird der
  Alarm verworfen statt unter der alten Regel verschickt.
* **Coverage-Gate.** Bevor geschichtsabhängige Regeln (Tiefpunkt, Preissturz) feuern, prüft der Wächter die
  Datenlage: `min_sources` (verschiedene Quellen im Fenster), `max_snapshot_age_hours` (Aktualität) und
  `min_success_ratio` (Anteil erfolgreicher Quellen im letzten Lauf). Bei dünner Lage wird nicht alarmiert,
  sondern die Lage ausgewiesen. Das Budget-Alarm bleibt unabhängig vom Beobachtungsfenster.
* **Ringpuffer** (`history_max_entries`) für die Historie – die Datei wächst nicht unbegrenzt.
* **Zeitfilter vor dem JSON-Parsen** (`read_jsonl`): bei sehr großen Verläufen ist das Lesen der Engpass,
  nicht das Rechnen. Ein grober Datums-Vorfilter überspringt alte Zeilen ohne Parsen.
* **Zwei Ablagen, eine Schnittstelle** (`alerts/history_db.py`): JSONL (Standard, grep-freundlich) oder SQLite
  mit Index auf (Kategorie, Zeitpunkt). Gemessen (`alerts/bench_history.py`): Fensterabfrage 7 Tage bei
  200 000 Punkten – JSONL 211 ms, SQLite 0,5 ms; Schreiben einzeln – JSONL 10,5 s, SQLite 45,2 s
  (Commit je Punkt), im Sammelschreiben SQLite 0,56 s gegenüber JSONL 2,19 s. Empfehlung: SQLite ab
  ~1000 Punkten oder bei minütlicher Messung, sonst JSONL.
* **Mehrkanal-Zustellung mit HMAC** (`alerts/notify.py`): command, webhook, slack, ntfy, gotify, telegram,
  email. Signatur: HMAC-SHA256 über Nutzlast + Zeitstempel (`X-Signature`, `X-Timestamp`). Je Kanal ein eigener
  Status in der Outbox – ein toter Kanal blockiert die anderen nicht.
* **Scheduler-Jitter** (`schedule.jitter_pct`, Standard ±10 %): feste Pausen erzeugen sonst gleiche Lastspitzen.

## Prüfrahmen (Harness) – Stand nach der Benchmark-Recherche

* `harness/tools/end_state.py` berechnet je Runde die **objektiven Fakten** (günstigster Tarif, Endpreis, Stopps,
  gewähltes Hotel, Haversine-Distanz, Steuerstatus, Provider-Status) nach `end_state.json`. Der Evaluator vergleicht
  das Protokoll damit, statt zu raten.
* Der Evaluator liefert nach der Score-Zeile einen **JSON-Block** (Kriterien, Deckel, harte Kriterien);
  `harness/tools/eval_json.py` wertet ihn aus und setzt den Score **auf 0**, wenn ein hartes Kriterium
  (K1 echte Flugdaten, K4 Herkunftsnachweis der Koordinate) nicht erfüllt ist.
* Der Proposer bekommt die nicht erfüllten Kriterien **mit Belegstelle** plus das **Regel-Ledger**
  (`harness/tools/rules_ledger.py`: helpful/harmful je Regel-ID) und soll schädliche Regeln entfernen –
  das verhindert Prompt-Wachstum.
* Wartezeiten mit Jitter statt festem `sleep` (Runner und Schleife).
* **Modell verankert:** `MODEL` (Vorgabe `nvidia/nemotron-3-ultra-550b-a55b`) wird an jeder Stelle gesetzt –
  Läufe sind damit reproduzierbar, statt von einer stillen Vorgabe abhängig zu sein.
* **Re-Grading:** Ein Lauf, der am Provider scheitert (Timeout, Rate-Limit, leere Antwort), ist ein
  **Infra-Fehler** und zählt nicht als Modellfehler; eine Bewertung, die unbrauchbar war, wird in eine
  Warteschlange gestellt und am Ende der Schleife nachbewertet, statt die ganze Runde zu wiederholen.
* **Proposer-Delta:** Der Vorschlags-Agent schickt `ADD`/`MODIFY`/`REMOVE` mit stabilen Regel-IDs statt des
  ganzen Prompts (`harness/tools/apply_delta.py`). Unbekannte oder doppelt vergebene IDs verwerfen das Delta –
  der Prompt bleibt dann unverändert.

## Bekannte Grenzen (Stand der Recherche)
* Kein Anbieter liefert für **Flüge** eine steuerinklusive Position; Hotel-Steuerpositionen liefern nur
  Booking.com und Google-Hotels-Deeplink (siehe `docs/SOURCES_FETCH.md`).
* „Resortgebühr“ existiert in den Quellen nicht als Feld – belegbar ist nur „Steuern und Gebühren enthalten“.
* Der kostenlose Provider-Pool ist rate-limit-anfällig (Google-Hotels-Cooldown, Cloudflare 429, Akamai 429);
  die Mehrquellen-Abfrage ist die Gegenmaßnahme, nicht die Vermeidung.
