# ALERT_RESEARCH — Preis-Alarm / Zeitpunkt-Optimierung (Fähigkeit 3)

**Recherche-Datum:** 2026-10-21
**Ziel:** umsetzungsreifes Design für einen flexiblen, anbieterneutralen Preiswächter
(Preisbeobachtung über definierten Zeitraum, z. B. 7 Tage), der **Budget-Überschreitung
UND Tiefpunkt-Erkennung** regelbasiert alarmiert.

**Kernaussage:** Es wird **kein** externes Scraping-Tool gebaut. `trvl` (lokal installiertes
Binary, `/home/batnini/.local/bin/trvl`, v1.27.0) bringt bereits eine vollständige,
transaktionale Preis-Historie, ein Budget-Alarm-Signal (`below_price` → `DEAL`), ein
proaktives Drop-Signal (`--alert-drop` → `PRICE DROP`), eine Statistik (`price_position`)
und eine empirische Kauf-vs-Warten-Wahrscheinlichkeit (`trvl forecast`) mit.
Der externe Watcher ergänzt **nur** das, was fehlt: **Tages-Snapshots** (einmal pro Tag
ein Punkt je Route), die **Regel-Auswertung über mehrere Quellen hinweg** und einen
**Cooldown-/State-Mechanismus**, der Doppelalarme verhindert.

---

## 1. Kurzfassung / Empfehlung

| Frage | Antwort |
|---|---|
| Welche Basis? | **Native `trvl`-Signale.** Kein Fremd-Scraper, kein Vendor-Lock-in. |
| Budget-Alarm | `trvl watch add … --below <BUDGET>` → `DEAL`-Event + `below_price` in `trvl watch list --format json` + Webhook-Payload `below_goal:true`. |
| Tiefpunkt-Alarm | `trvl watch add … --alert-drop <PCT>` (nativ, High-Water-Marke + Dedup) **und/oder** `price_position.verdict=="buy"` / `band=="low"` (Median/Terzil aus eigener Historie) **und/oder** `trvl forecast` (empirische CDF, ≥30 Samples). |
| Scheduler | **systemd User-Timer** (empfohlen) — Umgebung hat systemd 255 mit laufendem User-Timer-Support; cron als vollwertige Alternative (Beispiel im Kapitel). |
| Dedup/Cooldown | `state`-Datei (JSON) pro `(rule_id, source_key)` mit `baseline` (High-Water-Marke), `last_alerted_price`, `last_fired_at`. Semantik identisch zur nativen `pricealert.Evaluate`-Logik. |
| Rate-Limits | `trvl` bringt eigene Cooldowns mit (Google: 60 s Floor / 15 min Cap, persistent in `~/.trvl/cache/google-refusal`); Watcher zusätzlich mit `flock` + `min_interval` je Provider. |
| Lizenz-Risiko | `trvl` selbst ist **PolyForm Noncommercial 1.0.0** (source-available, nicht OSI-OSS) — für den Einsatz relevant, aber kein Laufzeit-Lock-in (lokales Binary, keine SaaS-Zwang). |

---

## 2. Geprüfte externe Open-Source-Werkzeuge

### 2.1 Scheduler / Orchestrierung

| Werkzeug | Lizenz | Letzte Aktivität | Installationsaufwand | Eignung „beobachten → Snapshot → bei Regel alarmieren" | Urteil |
|---|---|---|---|---|---|
| **cron (cronie/Vixie)** | BSD-artig / GPL (Debian-Paket) | Paket `cron` lokal vorhanden (`/usr/sbin/cron`, `/usr/bin/crontab`) | **0** — `crontab -l` zeigt „no crontab for batnini", also sofort nutzbar | ★★★★☆ Timer-Auslöser ja; Snapshot/State/Cooldown **nein** (muss selbst gebaut werden); kein Retry, kein Logging, kein Alarm-Dispatcher | **Empfohlen als Fallback** — einfachster Auslöser, wenn keine systemd-User-Session garantiert ist |
| **systemd timer** (system- *und* user) | GPL (systemd selbst) | systemd 255 (Ubuntu 24.04) aktiv; `systemctl list-timers` zeigt 11 System-Timer, `systemctl --user list-timers` 1 User-Timer; `loginctl show-user batnini` → `State=active`, `Service=user@1000.service` | ★★★★★ `systemctl --user enable --now`; User-Timer braucht `loginctl enable-linger` für Betrieb ohne Login | ★★★★★ `Persistent=true` (überholt Läufe werden nachgeholt), `OnCalendar` + `RandomizedDelaySec`, Journal-Logging (`journalctl -u`), `OnFailure=`-Hook, `AccuracySec`, `MaxRuntimeSec` | **Klare Empfehlung** — bietet Retry (`RestartSec`), Logs, Dependency-Konventionen ohne Zusatz-Dienst |
| **APScheduler** | MIT | pushed 2026-10-12 | ★★★☆ `pip install apscheduler`; braucht eigenen Daemon oder `systemd`-Unit | ★★★★☆ Coalescing, `max_instances`, `misfire_grace_time`, `MemoryJobStore` (Persistenz) — exakt die Semantik, die wir brauchen | **Gute Wahl, wenn ein Python-Prozess ohnehin läuft**; für einen einzelnen Watcher Overkill (zusätzlicher Daemon = zusätzliche Ausfallfläche) |
| **Celery + beat** | BSD-3-Clause | pushed 2026-10-20 | ★★☆☆☆ braucht Broker (Redis/RabbitMQ) + Worker + Beat | ★★☆☆☆ Task-Queue ist Overkill; sinnvoll erst ab Task-Fan-out | **Verworfen** — Broker-Abhängigkeit ohne Nutzen |
| **Apache Airflow** | Apache-2.0 | pushed 2026-10-21 | ★☆☆☆☆ (Webserver, DB, Scheduler, Worker) | ★☆☆☆☆ DAG-Orchestrierung für Datenpipelines; für 1 Watcher viel zu schwer | **Verworfen** |
| **Prefect** | Apache-2.0 | pushed 2026-10-21 | ★★☆☆☆ Server + Worker | ★★☆☆☆ Stark bei dynamischen Flows, hier Overkill | **Verworfen** |
| **Dagster** | Apache-2.0 | pushed 2026-10-21 | ★★☆☆☆ | ★★☆☆☆ Asset-Pipeline-Semantik, hier Overkill | **Verworfen** |
| **n8n** | **Sustainable Use License** (Fair-Use, *kein* OSI-Open-Source) + `.ee`-Dateien proprietär | pushed 2026-10-21 | ★★☆☆☆ Docker-Compose + Postgres | ★★★☆☆ Cron-Node + HTTP-Request + Code-Node vorhanden; ABER Lizenz ist „source-available, nicht OSS" → **Vendor-Lock-in-Risiko** (n8n darf nicht als White-Label-SaaS weitervertrieben werden) | **Verworfen für den Kern**, nur als Integrations-Gateway denkbar |

### 2.2 Preis-Monitoring / Scraping

| Werkzeug | Lizenz | Letzte Aktivität | Installationsaufwand | Eignung | Urteil |
|---|---|---|---|---|---|
| **changedetection.io** | Apache-2.0 | pushed 2026-10-19 (35 k★) | ★★★☆ Docker oder `pip install changedetection.io` | ★★★☆ Tolle HTML-Preis-Erkennung (JSON-LD/CSS/XPath), JSONPath-Monitoring, 85+ Notification-Kanäle, **aber**: preis-agnostisch (er detects *Änderungen*, keine Preis-Semantik), keine Median-/Tiefpunkt-Logik, keine Flüge-/Hotel-API | **Nur als Fallback für eine einzelne HTML-Website**; für strukturierte Preise aus `trvl` **overkill** |
| **Autobrr** | GPL-2.0 | pushed 2026-10-21 (3,2 k★) | ★★★☆ Single-Binary, `config.toml` | ★★☆☆☆ Release-/Indexer-Tracker (Sonarr/Radarr-Ökosystem), `$`-Filter auf Releases, **keine Preis-Historie** | **Verworfen** — falsches Domänenmodell |
| **Scrapy + Scrapyd** | BSD-3-Clause (beide) | Scrapy pushed 2026-10-21; Scrapyd pushed 2026-10-06 | ★★★☆ `pip install scrapy scrapyd`; Scrapyd braucht Scrapyd-Client + Deploy-Server | ★★★☆ Sauberes Crawl-Framework mit Scheduler, `JOBDIR`-Persistenz, Retry/Middleware — **aber** wir bauen keinen Crawler, weil `trvl` die Provider bereits absteckt | **Verworfen als Hauptweg**; Muster (JOBDIR/Resume, Retry-Middleware) als Referenz |
| **Playwright** (Microsoft) | Apache-2.0 | aktiv | ★★★★☆ Browser-Binaries + Node/Python-Binding | ★★☆☆☆ Für JS-Seiten nötig, aber hochohmaktiv gegenüber Rate-Limits; in dieser Umgebung bereits vorhanden (`.playwright-mcp`) | **Nur wenn eine Provider-Seite HTML-only ist** — nicht für den Kern |
| **Browsertrix Crawler** | AGPL-3.0 | pushed 2026-10-19 | ★★★☆ (Node + WACZ-Ausgabe) | ★★☆☆☆ Web-Archiv mit Zeit-Replay — hervorragend für *Beweis-Sicherung*, nicht für Alarm-Logik | **Verworfen** (Lizenz + Zweck) |
| **CamelCamelCamel / Keepa** | **proprietär** (kein OSS) | – | – | ★★☆☆☆ Referenz-*Semantik* (Allzeittief, 30/90-Tage-Tief, Verlauf), aber closed source | **Nur als Semantik-Vorbild** — genau diese Statistik wird unten mit nativen Signalen nachgebaut |

### 2.3 Spezialisierte Flug-/Hotel-Preis-Tracker (Referenz)

| Projekt | Lizenz | Letzte Aktivität | Eignung | Urteil |
|---|---|---|---|---|
| **kiinami/vfd** | MIT | pushed 2025-03-08 (letzte Aktivität ~1,5 J. her) | Google-Flights-Scraper + Streamlit + Apprise, Preis-Historie stündlich, Docker | **Muster-Quelle**: „neuer Bestpreis ⇒ genau 1 Alarm" + gestaffelte Queries gegen Google. Technisch überholt → nicht einsetzen |
| **affromero/flight-finder** | MIT | pushed 2026-10-19 (173★) | Voller Self-Host-Tracker, Postgres + Prisma, Cron alle 3 h, **Channel-Dedup**: „Channels that already accepted an alert are not sent it again" | **Muster-Quelle**: genau die Cooldown-/Dedup-Semantik, die wir brauchen; viel zu schwer (Postgres + Next.js) |
| **asaji/Flight-Price-Tracker** | keine Lizenz im Repo | pushed 2026-10-18 | Flask + **APScheduler** + SQLite, Pushover, Poll-Intervall 15 min–24 h konfigurierbar | **Muster-Quelle**: APScheduler + SQLite = minimale, robuste Kombination |
| **KaitlynOoi/flighttrack** | keine Lizenz im Repo | pushed 2026-08-13 | Telegram + MCP-Server, Postgres, `CHECK_INTERVAL_MINUTES`, **Cooldown: „if they haven't been alerted for this flight recently"** | **Muster-Quelle**: „recently"-Cooldown pro Flug |
| **jeancsil/flight-spy** | MIT | pushed **2017-04-10** (tote Entwicklung) | JSON-Config, Elasticsearch + Kibana, alle 15 min | **Verworfen** — 9 Jahre kein Commit, ES-Overkill |
| **andrewschultzw/price-tracker** | MIT | 2026 | Generischer Retail-Tracker (Node + SQLite), **30-Tage-/90-Tage-/Allzeittief aus eigener daily-min-Historie**, „10th percentile of recent daily lows" als Zielpreis-Vorschlag, **Per-Seller-Cool downs** | **Wichtigste Statistik-Referenz**: „Ziel = 10. Perzentil der letzten Tiefs" + „Coverage-Gate, damit junge Tracker still bleiben" |
| **clucraft/PriceGhost** | Apache-2.0 (Self-Host, Web-UI) | 2026 | Multi-Strategy-Extraktion, 7-Tage-Sparkline, Preis-Statistik min/max/avg, Telegram/Discord/Pushover/ntfy/Gotify | Referenz für Extraktions-Strategien und Benachrichtigungskanäle |
| **ds-sebastian/pricecious** | GPL-3.0 | pushed 2025-11-18 | LLM-Vision-Extraktion + Prophet-Forecast, „lowest seen / lowest in 90 days", Apprise | **Verworfen** (Vibe-Coded, LLM-Kosten); aber Referenz für „neues 90-Tage-Tief" als Alarmtyp |
| **jez500/pricebuddy** | „Other" laut Repo-Metadaten | 2026-02 | Docker, Scheduler integriert, Pushover/Gotify/Apprise/Telegram/Discord/ntfy | Referenz für Multi-Kanal-Notification |
| **luciodaou/fairtrail**, **alexander-vyh/ticket-tracker** (GPL-3.0), **loga77/flightclaw** (MCP-Skill), **nimish-html/pricewatch** (MIT) | div. | 2026 | Natural-Language-Flugtracker, MCP-Server, Amazon/Walmart | **Muster-Quelle für MCP-Anbindung** (flightclaw: `search_flights`/`track_flight`/`check_prices` als MCP-Tool-Set) |
| **AsierDev/price-history-tracker** | MIT | 2025-11 | Chrome-Extension, **exponentielles Backoff pro Domain** (1 m → 5 m → 30 m → 2 h) | **Muster-Quelle**: Backoff-Schema gegen Sperren |

**Fazit zur Werkzeugauswahl:** Keines der geprüften externen Tools ersetzt `trvl`. Sie liefern
zwei Dinge, die wir übernehmen: (a) das **Dedup-/Cooldown-Muster**
(„genau ein Alarm pro neuem Tief", „ein Sender pro Alarm") und (b) das **Statistik-Muster**
(„neues 30-/90-Tage-Tief", „Ziel = 10. Perzentil der recent daily lows").
Beides ist unten nativ bzw. mit reiner Python-Standardbibliothek umgesetzt — ohne neue
Abhängigkeiten, ohne zusätzlichen Dienst.

### 2.4 Abgleich mit der **bereits vorhandenen** Provider-Registry im Projekt

Im Zielordner existiert bereits eine Provider-Registry
(`/home/batnini/mimo-agents/providers/registry.yaml`) mit `transport: mcp_stdio | mcp_http | http | cli`
und u. a. diesen Quellen:

| Registry-ID | Kategorie | Transport | Aktiv | Native Herkunft |
|---|---|---|---|---|
| `trvl_flights` | flights | `mcp_stdio` → `trvl mcp`, Tool `travel`, `intent=search_flights` | ja | Google Flights + Kiwi + Skiplagged (Merge) |
| `fli_flights` | flights | `mcp_stdio` → `fli-mcp` | ja | zweite Google-Flights-Engine |
| `skiplagged_flights` | flights | `mcp_http` → `mcp.skiplagged.com/mcp`, `parser: table` | ja | Skiplagged (Markdown-Tabelle) |
| `stays_hotels` | hotels | `mcp_stdio` → `stays mcp` | ja | Google Hotels |
| `rome_hotel_taxes` | hotels | `mcp_stdio` → `rome_hotel_taxes_mcp.py` | ja | Google-Hotels-Herkunft mit steuerinklusive Endsumme |
| `skiplagged_hotels` | hotels | `mcp_http` | **nein** | Server antwortete beim Erstellen nicht |

**Verifiziert:** die `params` des Registry-Eintrags `trvl_flights`
(`origin`, `destination`, `departure_date`, `return_date`, `currency`, `max_stops`,
`carry_on_bags`, `checked_bags`) sind **alle** im MCP-Schema von `travel` vorhanden
(`trvl search_flights --describe` bestätigt `carry_on_bags`, `checked_bags`,
`require_checked_bag`, `max_stops ∈ {any,nonstop,one_stop,two_plus}`).
Die `extract`-Pfade `all_in_cost`, `bag_breakdown`, `price_warnings` sind ebenfalls echte
JSON-Felder des trvl-Flugmodells (`internal/models/flight.go`:
`json:"all_in_cost"`, `json:"bag_breakdown,omitempty"`, `json:"price_warnings,omitempty"`,
`json:"carry_on_included"`).

**Konsequenz für dieses Design:** die Anforderung „Provider-Liste konfigurierbar (nicht auf
eine Website festgelegt)" ist mit der Registry bereits erfüllt — eine neue Quelle = ein
YAML-Eintrag, kein Code. Der Watcher liest die Registry, filtert nach `providers[]`
(leer = alle aktiven Quellen der Kategorie) und benutzt `enabled: false` als
**manuelles Rate-Limit-Gate** (z. B. `skiplagged_hotels`).

Die native `trvl`-Preisüberwachung kommt als **Kontext-/Referenzquelle** obendrauf
(`trvl watch list|history --format json`, `trvl rate-status`, `trvl dates`), nicht als
Ersatz für die Registry.

---

## 3. Native `trvl`-Signale (verifiziert mit echten Aufrufen)

### 3.0 Version, Speicherorte, Grundbefehle

```
$ trvl --version
trvl 1.27.0
```

Speicherorte unter `~/.trvl/`:

| Datei | Inhalt | Wird geschrieben von |
|---|---|---|
| `watch.db` | **bbolt**-Datenbank (nicht SQLite!) mit Buckets `meta`, `history-watch/<watch_id>`, `history-watch-all`, `history-route/<ROUTE_KEY>`, `history-route-all` | `trvl watch add/check`, jeder Preis-Suchlauf |
| `watch.db` (Legacy-Pfad) | `~/.trvl/price-history.json` — **Altbestand** vor der bbolt-Migration (1.21.0) | wird nach der Migration nicht mehr fortgeschrieben |
| `deal-history.json` | Deal-Quality-Samples: `[{route:"HEL-BCN", season:"Q1", date, price, kind}]` | `internal/dealquality` (Digest/Opportunity-Pipeline) |
| `date-grids.json` | Preis-Raster: `{route_key, currency, points:[{date, return_date, price, currency}], updated_at}` | `trvl grid` |
| `last_search.json` | letzte Suche (`command`, `timestamp`, `destination`, `depart_date`, `return_date`, `hotel_price`, `hotel_currency`, `total_price`, `total_currency`) | jede Hotelsuche |
| `preferences.json` | `home_airports`, `currency`, `deal_tolerance`, `preferred_alliance`, `calendar_blocked`, … | `trvl prefs` |
| `health.jsonl` | JSONL-Health-Log pro Provider/Op (`status`, `latency_ms`, `error_class`, `hint_code`) | jeder Provider-Call |
| `cache/google-refusal` | **Cooldown-Deadline** (ISO-Timestamp) des Google-Quota-Refusals | `internal/batchexec/refusal.go` |
| `scheduler.lock` | **prozessübergreifender Singleton-Lock** des Preis-Schedulers (flock) | `trvl watch daemon` / jeder `trvl mcp`-Prozess |

### 3.1 Signal A — **Budget-Alarm** (absolutes Preisziel)

**Anlegen:**

```
$ trvl watch add BER FCO --depart 2026-12-01 --return 2026-12-08 --below 150 --format json
Added flight watch f5f53ed0: BER -> FCO on 2026-12-01 (return 2026-12-08) [alert below 150 ]
```

**Zustand auslesen (JSON!):**

```
$ trvl watch list --format json
[
  {
    "id": "f5f53ed0",
    "type": "flight",
    "origin": "BER",
    "destination": "FCO",
    "depart_date": "2026-12-01",
    "return_date": "2026-12-08",
    "below_price": 150,
    "currency": "EUR",
    "created_at": "2026-10-21T17:52:14.553358601+02:00",
    "last_check": "2026-10-21T17:52:57.624395126+02:00",
    "last_price": 126.9,
    "lowest_price": 126.9,
    "cheapest_date": "2026-12-01",
    "renewed_at": "2026-10-21T17:52:14.553358601+02:00",
    "last_minute_drop_pct": 25,
    "baseline_price": 126.9
  }
]
```

**Felder (exakt):** `id`, `type` (`flight|hotel|room|opportunity`), `origin`, `destination`,
`depart_date`, `return_date`, `depart_from`, `depart_to`, `below_price`, `currency`,
`created_at`, `last_check`, `last_price`, `lowest_price`, `cheapest_date`, `renewed_at`,
`baseline_price`, `alert_drop_pct`, `alert_drop_abs`, `last_alerted_price`, `webhook_url`,
`last_minute_mode`, `last_minute_drop_pct`, `favourites`, `window_from`, `window_to`,
`min_score`, `min_nights`, `max_nights`, `hotel_name`, `room_keywords`.

**Preis-Historie je Watch (JSON!):**

```
$ trvl watch history f5f53ed0 --format json
[
  {
    "watch_id": "f5f53ed0",
    "price": 126.9,
    "currency": "EUR",
    "timestamp": "2026-10-21T17:52:57.624416996+02:00"
  }
]
```

**Prüflauf (Textausgabe, `trvl watch check` hat KEIN `--format json`!):**

```
$ trvl watch check
…
DEAL  BER -> FCO  127 EUR (below 150 EUR goal!)
      Book: https://www.google.com/travel/flights?q=Flights+to+FCO+from+BER+on+2026-12-01
```

Reichweite der Modi:

* **Fixes Datum** `--depart` (+ `--return`) → ein Datum
* **Datumsbereich** `--from`/`--to` → billigster Tag im Fenster
* **Routen-Watch** (ohne Datumsangaben) → nächste 60 Tage, billigstes Datum
* **Hotel-Watch** `--type hotel --depart/--return` → Preis pro Nacht
* **Room-Watch** `trvl watch rooms "Hotel, City" --checkin … --checkout … --keywords "…"`

**Webhook-Payload** (`--webhook URL`, fire-and-forget, 10 s Timeout, nur http/https):

```json
{
  "watch_id": "f5f53ed0", "type": "flight", "origin": "BER", "destination": "FCO",
  "new_price": 126.9, "prev_price": 149.0, "currency": "EUR", "price_drop": -22.1,
  "below_goal": true, "timestamp": "2026-10-21T17:52:57+02:00"
}
```

### 3.2 Signal B — **Tiefpunkt-Erkennung, nativ** (`PRICE DROP`)

```
$ trvl watch add BER FCO --depart 2026-12-01 --return 2026-12-08 --alert-drop 12
$ trvl watch update f5f53ed0 --alert-drop-abs 30      # absolute Alternative
```

Semantik (Quelle: `internal/pricealert/pricealert.go`, verifiziert im Upstream-Repo):

* `baseline` = **High-Water-Marke**: erster Wert setzt die Baseline; jeder Wert
  `>= baseline` hebt sie an und **re-armt** den Dedup (LastAlertedPrice := 0).
* Alarm feuert, wenn **UND**
  1. `current < baseline` **und**
  2. `drop_pct >= alert_drop_pct` **oder** `drop_abs >= alert_drop_abs`
     (Standard, wenn keine Limbe gesetzt: `DefaultDropPercent = 10 %`)
  3. **und** `current < last_alerted_price` → **neues Tief**, sonst kein Alarm.
* Ein flacher Preis oder eine Erholung bleiben still; ein noch tieferer Wert
  feuert erneut (genau 1 Alarm pro neuem Tief).

Textausgabe:

```
PRICE DROP  BER -> FCO  127 EUR (12.0% below baseline 150 EUR)
      Book: https://www.google.com/travel/flights?…
```

### 3.3 Signal C — **`price_position`** (Statistik aus der *eigenen* Historie)

Quelle: `internal/pricesignal/pricesignal.go` (dependency-frei, in CLI + MCP + Counterfactual geteilt).

**Echtes Kommando und echte Ausgabe** (Flug-Suche über einen Nicht-Google-Provider,
weil Google-Flights in diesem Moment ein Quota-Refusal lieferte):

```
$ trvl flights BER FCO 2026-12-01 --provider skiplagged --format json
{
  "success": true,
  "count": 12,
  "trip_type": "one-way",
  "flights": [ { "price": 82, "currency": "USD", "duration": 1335, "stops": 1,
                 "provider": "skiplagged", "warnings": ["standard","one-stop"],
                 "legs": [ { "departure_airport": {"code":"BER"},
                             "arrival_airport": {"code":"FCO"},
                             "departure_time": "2026-12-01T12:30:00+01:00",
                             "arrival_time":   "2026-12-02T10:45:00+01:00",
                             "airline": "Norwegian Air Sweden AOC" } ],
                 "booking_url": "https://skiplagged.com/flights/BER/FCO/2026-12-01?…" } ],
  "completeness": { "state": "", "queried": 0, "succeeded": 0 },
  "destination":  { "location": "Aeroporto di Roma-Fiumicino, …", "weather": { … } },
  "price_position": {
    "band": "unknown",
    "verdict": "unknown",
    "current": 82,
    "low": 82,
    "high": 82,
    "median": 82,
    "observations": 1,
    "confident": false
  }
}
```

`price_position` liegt **auf Top-Level** des Suchergebnisses (nicht pro Flug-Option) und
hat **immer** genau diese Felder:

```json
{
  "band": "low|typical|high|unknown",
  "verdict": "buy|wait|neutral|unknown",
  "current": 126.9,
  "low": 118.0,
  "high": 268.0,
  "median": 146.0,
  "vs_median_pct": -13.08,
  "observations": 42,
  "confident": true
}
```

> Das obige echte Beispiel zeigt den **Mindestdaten-Fall**: `observations: 1`,
> `confident: false`, `band/verdict: "unknown"` — aber `low/high/median` sind trotzdem
> gefüllt. Genau das Verhalten, das die Regel-Semantik braucht: **unterhalb der
> Confidence-Floor kein Alarm** (Coverage-Gate), aber transparente Zahlen.

* **Tertil-Bänder**: `q(1/3)` / `q(2/3)` der sortierten Historienpreise.
  `current <= q33` → `band=low`, `verdict=buy`; `current >= q67` → `band=high`, `verdict=wait`.
* **Confidence-Floor**: `DefaultConfidenceFloor = 10` Beobachtungen. Darunter:
  `band=unknown`, `verdict=unknown`, `confident=false` — aber `low/high/median/vs_median_pct`
  werden **trotzdem** gefüllt (Transparenz ohne Empfehlung).
* **Währung strikt**: `RoutePrices(routeKey, currency)` filtert **exakt** nach Währung.
  Eine Beobachtung ohne Währung wird nie in die Serie gemischt (Bug #564).
* Erscheint in Flug-Suchergebnissen, in `trvl prices --format json` (Hotel-Providerpreise,
  zusammen mit `booking_readiness`) und in Hotel-Suchen.

### 3.4 Signal D — **`trvl forecast`** (empirische CDF, Kauf-jetzt-vs-warten)

```
$ trvl forecast BER-FCO --kind flight --price 127 --format json
{"route":"BER-FCO","kind":"flight","season":"Q4","price":127,
 "forecast":{"CommitNowConfidence":50,"DropProbability":0,"HorizonProbability":0,
             "ExpectedSavingsIfWait":0,"HorizonDays":7,"Samples":0,
             "InsufficientData":true,"Reason":"insufficient history (0/30 samples)"},
 "curve":{"Min":0,"Max":0,"Buckets":null,"Threshold":127},"samples":0}
```

Felder: `CommitNowConfidence` (0–100), `DropProbability` (CDF), `HorizonProbability`
(1-(1-p)^horizon), `ExpectedSavingsIfWait`, `HorizonDays` (Default 7), `Samples`,
`InsufficientData`, `Reason`, plus Histogramm `curve`.
**Gate:** `MinSamplesForForecast = 30`, Fenster `HistoryWindowDays = 90`, Quelle
`~/.trvl/deal-history.json` (override: `--history-path`).

### 3.5 Signal E — **Datumsfenster / Raster / Vorschläge**

```
$ trvl dates BER FCO --from 2026-11-02 --to 2026-11-06 --format json
$ trvl dates BER FCO --from 2026-11-02 --to 2026-11-06 --round-trip --duration 7 --format json
$ trvl grid  BER FCO --depart-from 2026-11-01 --depart-to 2026-11-07 \
                    --return-from 2026-11-08 --return-to 2026-11-14 --format json
$ trvl suggest BER FCO --around 2026-07-15 --flex 7 --format json
$ trvl trip-cost BER FCO --depart 2026-12-01 --return 2026-12-08 --guests 2 --format json
$ trvl optimize BER FCO --depart 2026-12-01 --return 2026-12-08 --flex 5 --format json
```

**Echte Ausgabe von `trvl dates` (JSON-Hülle verifiziert):**

```
$ trvl dates BER FCO --from 2026-11-02 --to 2026-11-06 --legacy --format json
{
  "success": true,
  "count": 0,
  "trip_type": "one_way",
  "date_range": "2026-11-02 to 2026-11-06",
  "dates": null
}
```

> `dates` war `null`, weil im Testfenster der **aktive Google-Quota-Refusal** griff
> (siehe 3.8) — `count: 0` und `dates: null` sind also **Datenmangel, kein leerer Markt**.
> Die Hülle (`success`, `count`, `trip_type`, `date_range`, `dates[]`) ist damit real
> belegt; die Belegung von `dates[]` (je Tag: `date`, `price`, `currency`,
> `return_date`) ist aus der Upstream-Quelle `internal/dategrid/dategrid.go` +
> `internal/flights/dates.go` abgeleitet.

`trvl grid` war im selben Fenster komplett blockiert:

```
$ trvl grid BER FCO --depart-from 2026-12-01 --depart-to 2026-12-03 \
        --return-from 2026-12-08 --return-to 2026-12-10 --format json
Error: city resolution request: google refused further requests until the cooldown ends
# -> ~/.trvl/date-grids.json wurde (noch) nicht angelegt
```

`trvl dates` nutzt per Default Googles `CalendarGraph`-API (1 Request), fällt sonst auf
Per-Date-Suche zurück (`--legacy`). Das Raster (`grid`) wird in `~/.trvl/date-grids.json`
persistiert (`route_key`, `currency`, `points[]`, `updated_at`) und treibt die
Shift-Day-Counterfactuals.

> **Konsequenz für die Regel-Auswertung:** „billigster Tag im 7-Tage-Fenster" ist über
> `trvl dates/grid` nur verfügbar, wenn Google antwortet. Der Watcher braucht deshalb
> eine **Fallback-Quelle** (siehe `lowpoint_window` über eigene Tages-Snapshots) und muss
> `count: 0 / dates: null` als **`status: "no_data"`** behandeln — **nicht** als
> „0 € gefunden" und **nicht** als Alarm.

**Realer Beleg für die Provider-Redundanz (wichtig für die Regelauswertung):**
Während Google-Flights im Quota-Refusal stand, lieferte der Hotel-Pfad weiterhin Preise —
über den Agoda-Provider. Derselbe Lauf protokolliert auf stderr:

```
$ trvl hotels "Rome" --checkin 2026-10-31 --checkout 2026-11-01 --format json
2026/10/21 18:18:59 WARN hometogo search failed error="hometogo resolve: unexpected status 403 …"
2026/10/21 18:18:59 WARN landing search failed error="landing resolve: unexpected status 403 …"
2026/10/21 18:18:59 WARN blueground search failed error="blueground fetch: unexpected status 404 …"
2026/10/21 18:18:59 WARN wunderflats search failed error="wunderflats fetch: unexpected status 404 …"
2026/10/21 18:19:10 WARN trivago search failed error="trivago accommodation search: trivago: HTTP 503"
{
  "success": true,
  "count": 172,
  "hotels": [
    {
      "name": "Ibis Roma Fiera",
      "hotel_id": "74494",
      "rating": 7.7, "review_count": 608, "stars": 3,
      "price": 60.18, "currency": "EUR", "comparable_price": 60.18,
      "room_types": [
        { "name": "Agoda room rate", "price": 60.18, "nightly_price": 60.18,
          "total_price": 78.2, "taxes_and_fees": 18.02,
          "taxes_fees_included": true, "currency": "EUR", "provider": "agoda",
          "provider_url": "https://www.agoda.com/ibis-roma-fiera/hotel/rome-it.html",
          "match_confidence": "similar_room_match",
          "price_basis": "tax_inclusive_total",
          "price_confidence": "verified",
          "refundable": false, "cancellation_policy": "Non-refundable" }
      ],
      "lat": 41.8223, "lon": 12.3938, "distance_km": 10.8, "property_type": "hotel",
      "booking_url": "https://www.agoda.com/ibis-roma-fiera/hotel/rome-it.html",
      "sources": [
        { "provider": "agoda", "price": 60.18, "currency": "EUR",
          "booking_url": "https://www.agoda.com/ibis-roma-fiera/hotel/rome-it.html",
          "price_basis": "room_nightly", "price_confidence": "unverified",
          "retrieved_at": "2026-10-21T18:19:10.99043579+02:00", "freshness": "live" }
      ],
      "price_basis": "room_nightly",
      "price_confidence": "unverified",
      "retrieved_at": "2026-10-21T18:19:10.99043579+02:00",
      "freshness": "live",
      "confidence": { "rated": true, "score": 0.7428, "label": "medium",
                      "freshness": "live",
                      "basis": "74% likely bookable — live price, 1-source corroboration",
                      "signals": ["freshness:live", "sources:1", "verification:unverified"] }
    }
  ],
  "provider_statuses": [ … ],
  "completeness": { … },
  "destination": { … }
}
```

Relevanz für das Regelwerk:
* `sources[]` ist **pro Provider** gefüllt ⇒ `provider`-Feld der Beobachtung ist nativ
  verfügbar (Grundlage für die konfigurierbare Provider-Liste und das
  `group_by_source_key`-Dedup).
* `price_confidence` ∈ `verified|room_level|unverified` und `freshness` ∈ `live|recent|stale`
  sind **Qualitäts-Gates** — ein Watcher sollte `unverified`/`stale` nicht als
  Alarm-Trigger werten.
* `price_basis` ∈ `lead_in|room_nightly|room_total|tax_inclusive_total` sagt, **worauf** sich
  der Preis bezieht (Budget-Vergleich braucht dieselbe Basis!).

### 3.6 Signal F — **Opportunity-Watch** (rollierendes Fenster, Ziel-Score)
```
$ trvl opportunities create --favourites "FCO,CDG" --window-from next_30d --window-to next_90d --min-score 90
Created opportunity watch 465e336c
  Favourites: FCO, CDG
  Window: next_30d → next_90d
  Min score: 90 | Nights: 3-14

$ trvl opportunities --format json
[
  {
    "id": "465e336c",
    "type": "opportunity",
    "below_price": 0,
    "currency": "",
    "last_check": "0001-01-01T00:00:00Z",
    "last_price": 0,
    "lowest_price": 0,
    "favourites": ["FCO", "CDG"],
    "window_from": "next_30d",
    "window_to": "next_90d",
    "min_score": 90,
    "min_nights": 3,
    "max_nights": 14
  }
]
```

### 3.7 Signal G — **MCP-Zugriff** (Agenten-tauglich)

Der MCP-Server exponiert **ein** Meta-Tool `travel`; die historischen Tool-Namen sind
als `intent` weiterhin gültig (legacy-kompatibel):

```
$ printf '…initialize…{"jsonrpc":"2.0","id":2,"method":"tools/list"}…' | trvl mcp
→ serverInfo {"name":"trvl","version":"1.27.0"}; tools: [ "travel" ]

$ travel {"intent":"list_watches"}
1 active watch(es):
  [f5f53ed0] BER→FCO 2026-12-01→2026-12-08 — target: 150 EUR, last: 127
Use check_watches to re-check prices now.

$ travel {"intent":"watch_price","action":"describe"}
watch_price arguments (pass inside params; required: type):
- type (string, required): Watch type: "flight" or "hotel"
- alert_drop (number) / alert_drop_abs (number) / target_price (number)
- currency, date, return_date, depart_from, depart_to, origin, destination,
  location, check_in, check_out, last_minute, last_minute_drop_pct, webhook

$ travel {"intent":"search_dates","action":"describe"}
search_dates arguments (required: origin, destination, start_date, end_date):
- is_round_trip (boolean), trip_duration (integer)

$ travel {"intent":"suggest_dates","action":"describe"}
suggest_dates arguments (required: origin, destination, target_date):
- flex_days (integer), duration (integer), round_trip (boolean)
```

### 3.8 Native **Taktung, Cooldowns, Sperren** (relevant für den Scheduler)

| Mechanismus | Wert | Fundstelle |
|---|---|---|
| `trvl watch daemon --every` | Default **6h** | `cmd/trvl/watch_daemon.go` |
| In-Process-Scheduler-Default | **30 min** (`NewScheduler`) | `internal/watch/scheduler.go` |
| Scheduler-Singleton | `~/.trvl/scheduler.lock` (flock, prozesslifetime) — **jeder `trvl mcp`-Prozess startet einen** | `internal/watch/lock.go` |
| Pause zwischen Watches | **3 s** je Watch (`CheckAll`) | `internal/watch/check.go` |
| Beobachtungs-Throttle | **15 min** + Epsilon **0,5 %** (`observationEpsilonPct = 0.005`): fast gleiche Preise werden nicht geschrieben | `internal/watch/store.go` |
| Google-Cooldown Floor | **60 s** (HTTP 429) | `internal/batchexec/refusal.go` |
| Google-Cooldown Long/Cap | **15 min** (wrb.fr-Status 13 / Quota-Refusal) | ebd. |
| Cooldown-Persistenz | `~/.trvl/cache/google-refusal` (Deadline-Timestamp, **cross-process**) | ebd. |
| Provider-Rate-Limiter | 1 Request / 500 ms, Burst 1, pro Provider serialisiert | `internal/providers/provider_limiter.go` |
| Retention-Caps | `TRVL_WATCH_MAX_POINTS_PER_WATCH` (1000), `TRVL_WATCH_MAX_POINTS_TOTAL` (50000), `TRVL_WATCH_ROUTE_TTL_DAYS` (90), `maxRouteObservations = 20000` (fair evicten) | `internal/watch/store.go` |
| Route-Key-Format | `FLIGHT\|BER\|FCO\|2026-12-01`, Hotels `HOTEL\|<hotel_id>\|<leer>\|<checkin>` | `internal/watch/store_route_history.go`, `internal/obslog/obslog.go` |

**Beobachtung aus dem Testlauf:** `trvl watch check` produzierte parallel
`WARN … skiplagged init: HTTP 429` und `WARN wizzair … InvalidMarket` auf **stderr** —
Fehler/Nebenmeldungen landen also in **stderr**, das Nutzsignal (DEAL/PRICE DROP) auf
**stdout**. Der Watcher muss stdout und stderr getrennt auswerten.

**Beobachtung aus dem Testlauf 2 — Google-Quota-Refusal (real, 2026-10-21 18:18):**

```
$ trvl dates BER FCO --from 2026-11-02 --to 2026-11-06 --format json
2026/10/21 18:18:42 WARN google_refused status=200 cooldown_s=900
Error: google flights quota refusal (code 13): upstream provider rate-limited or temporarily unavailable
```

* `wrb.fr`-Status **13** = Quota-Refusal ⇒ **15 min** Cooldown (`googleRefusalLong`).
* Der Cooldown wird **self-extending**: ein Probe-Versuch während des Cooldowns
  schreibt eine **neue** Deadline (im Test 18:02:52 → 18:18:03).
* `city resolution request: google refused further requests until the cooldown ends`
  ⇒ **auch die Flughafen-/Stadtauflösung** ist gesperrt, nicht nur die Preissuche.
* **Konsequenz für den Watcher:** bei aktivem Cooldown **nicht pollen** (sonst hält man
  die Sperre selbst am Leben). Stattdessen:
  1. `~/.trvl/cache/google-refusal` lesen und `deadline > now` ⇒ **google-Quellen überspringen**,
     andere Provider (`skiplagged`, `agoda`, `wizzair`, …) laufen lassen;
  2. `trvl rate-status` als Gegenprobe;
  3. das Ergebnis als `status: "skipped_cooldown"` protokollieren, **ohne** Alarm.

  Beispiel aus demselben Fenster: Google-Flights gesperrt, aber
  `trvl flights --provider skiplagged` lieferte 12 Optionen und
  `trvl hotels "Rome"` lieferte 172 Hotels über Agoda. Genau deshalb ist die
  **Provider-Liste konfigurierbar** und der Watcher providerweise geplant.

---

## 4. Regelsemantik

### 4.1 Grundprinzip

> **Alarm nur bei Regelerfüllung.** Kein Alarm bei „Preis hat sich geändert", „Check lief",
> „Provider kaputt". Jeder Alarm muss eine konkrete, benannte Regel erfüllen.

Jede Beobachtung bekommt einen **`source_key`** (stabiler Schlüssel je Quelle/Route/Datum,
z. B. `flight:BER:FCO:2026-12-01`). Regeln beziehen sich auf `source_key` oder auf
eine Provider-Liste (`providers: [google, skiplagged, wizzair, …]`), damit die
**Provider-Liste konfigurierbar** bleibt und nicht auf eine Website festgelegt ist.

### 4.2 Regel-Typen

| Regel | Formel | Zusatzbedingung | Native Entsprechung |
|---|---|---|---|
| `budget` | `price <= budget` (+ `currency == rule.currency`) | Preis > 0 | `below_price` → `DEAL` |
| `budget_drop` | `price <= baseline * (1 - drop_pct/100)` **oder** `price <= baseline - drop_abs` | `baseline` gesetzt (High-Water-Marke) | `alert_drop_pct` / `alert_drop_abs` → `PRICE DROP` |
| `lowpoint_median` | `price <= median(window) * (1 - pct/100)` | `n >= min_observations` **und** `confident == true` | `price_position.median` + `vs_median_pct` |
| `lowpoint_percentile` | `price <= percentile(window, p)` (p z. B. 10) | `n >= min_observations` | eigene Snapshot-Historie |
| `lowpoint_window` | `price <= min(window)` **und** `price < last_alerted_price` | Fenster gefüllt (z. B. 7 Tage) | `lowest_price` / `cheapeste_date` |
| `native_forecast` | `forecast.CommitNowConfidence >= X` **und** `!InsufficientData` | `Samples >= 30` | `trvl forecast` |
| `score` | Opportunity-Score `>= min_score` | Fenster/Ort passt | `trvl opportunities` |

**Empfehlung „7 Tage“:** Lookback-Fenster `lookback_days: 7` auf **eigene
Tages-Snapshots** (ein Snapshot/Tag/Route). Der native Store liefert Beobachtungen
pro *Poll*, nicht pro Tag — deshalb ergänzt der externe Watcher genau diese
einmal-täglich-Punkte. Er nutzt dafür `trvl watch history` (Watch-Punkte) bzw. den
Route-Bucket `history-route/<ROUTE_KEY>` in `watch.db`.

### 4.3 Statistik ohne Zusatzpakete (Python-Standardbibliothek)

```python
def median(xs):                 # sortiert, Mittel der zwei mittleren bei gerader Länge
    s = sorted(xs); n = len(s)
    if not n: return None
    return s[n//2] if n % 2 else (s[n//2-1] + s[n//2]) / 2

def percentile(xs, p):          # nearest-rank, wie trvl pricesignal.quantile
    s = sorted(xs); n = len(s)
    if n == 0: return None
    if n == 1: return s[0]
    pos = (p/100.0) * (n - 1); lo = int(pos)
    if lo >= n - 1: return s[-1]
    f = pos - lo
    return s[lo] * (1 - f) + s[lo+1] * f
```

Weil `pricesignal.quantile` genau so interpoliert, sind unsere Perzentile mit den
nativen `price_position`-Bändern konsistent.

**Kostenlos verfügbare native Statistik (kein Eigenbau nötig):**

* `price_position.median` / `.low` / `.high` / `.vs_median_pct` / `.observations` / `.confident`
* `price_position.band` (Tertile) und `.verdict` (buy/wait/neutral)
* `watch list` → `lowest_price`, `cheapest_date`, `baseline_price`, `last_price`
* `trvl forecast` → empirische CDF, `DropProbability`, `CommitNowConfidence`, `ExpectedSavingsIfWait`
* `trvl dates` / `trvl grid` → billigster Tag im Fenster, Preis-Raster

**Eigenbau nur für:** (a) 7-Tage-Snapshots (ein Punkt/Tag), (b) „x % unter dem
7-Tage-Median" über *diese* Snapshot-Serie, (c) Perszentil über die Snapshot-Serie,
(d) Cooldown/State.

### 4.4 Cooldown / Anti-Doppel-Alarm

Zwei Ebenen:

**(1) Native Ebene** — `pricealert.Evaluate` verhindert bereits, dass derselbe Preis
zweimal alarmiert: Alarm nur, wenn `price < last_alerted_price`. Das ist ein
**Preis-Dedup**, kein Zeit-Dedup.

**(2) Watcher-Ebene** — zusätzlich ein **Zeit-Cooldown** je `(rule_id, source_key)`:

```
fire_allowed = rule_fired
              and now - last_fired_at >= cooldown
              and ( price < last_alerted_price - epsilon     # neues Tief
                   or price <= budget and force_repeat )      # Budget immer melden
```

Regeln:

* `cooldown_hours` (Default **24 h**) verhindert Wiederholung desselben Ereignisses.
* **Ausnahme:** ein *neues* Tief (`price < last_alerted_price`) bypasses den Cooldown
  → „Tiefpunkt-Alarm" feuert auch zweimal am Tag, wenn der Preis weiter fällt.
* **Budget:** firet bei jedem neuen Tief unterhalb des Budgets; Cooldown gilt, aber
  ein *weiterer* Preisabfall unter Budget meldet erneut (kein Spam bei flachem Preis).
* `last_alerted_price` wird **nur bei ausgelöstem Alarm** aktualisiert, nicht bei
  jedem Poll → identisch zur nativen Semantik.
* **`baseline`** (High-Water-Marke) wird bei jedem Poll aktualisiert:
  `baseline = max(baseline, price)`. Preis-Erholung re-armt den Dedup.
* **Provider-Dedup:** derselbe Preis aus zwei Providern für dieselbe `source_key`
  erzeugt **einen** Alarm (gruppiert nach `source_key`, nicht nach Provider).
* **Alert-Routing-Dedup** (Muster flight-finder): pro Alarm wird ein
  `delivered_to[]`-Setz geführt; ein Kanal, der den Alarm schon bestätigt hat,
  bekommt ihn nicht erneut.

### 4.5 State-Datei

Siehe `alerts/alert_design.json` → `state_file`. Kern:

```json
{
  "version": 1,
  "sources": {
    "flight:BER:FCO:2026-12-01": {
      "currency": "EUR",
      "baseline": 268.0,
      "last_price": 126.9,
      "last_alerted_price": 126.9,
      "last_fired_at": "2026-10-21T17:52:57+02:00",
      "observations": 42,
      "last_snapshot_date": "2026-10-21",
      "rules_fired": { "budget:ber-fco": "2026-10-21T17:52:57+02:00" }
    }
  },
  "alerts": []
}
```

---

## 5. Scheduler-Empfehlung

### 5.1 Begründung

Die Umgebung: Linux, **systemd 255** aktiv, `systemctl --user list-timers` zeigt laufende
User-Timer, `loginctl show-user batnini` → `State=active`, `Service=user@1000.service`.
`cron` ist installiert, hat aber **kein** Crontab. Docker ist vorhanden, wäre hier aber
eine zusätzliche Abhängigkeit ohne Mehrwert.

**Empfehlung: systemd User-Timer** (`systemd --user`), weil:

1. **Kein zusätzlicher Dienst/Container** nötig — der Watcher ist ein Einmal-Skript.
2. `Persistent=true` holt **verpasste Läufe** nach (Suspend/ReBoot) — cron ohne
   Wrapper macht das nicht.
3. `OnCalendar` + `RandomizedDelaySec` streut die Last (wichtig gegen Google-Rate-Limits).
4. `journalctl --user -u …` liefert **Logging** ohne eigene Log-Infrastruktur.
5. `AccuracySec=1m` + `RandomizedDelaySec=…` + `OnFailure=` sind deklarativ.
6. `systemd` respektiert `Nice=`/`IOSchedulingClass=` → der Watcher konkurriert nicht
   mit dem Desktop.
7. **User-Timer statt System-Timer**, weil `trvl` und `~/.trvl` dem Benutzer
   `batnini` gehören — kein `sudo`, kein Root-Kontext, kein Sicherheitsrisiko.

**Voraussetzung:** `loginctl enable-linger batnini`, damit der User-Timer auch ohne
eingeloggte Session läuft (Session läuft aktuell, aber Linger sichert es ab).

**Abgleich mit der bereits vorhandenen Unit** (`alerts/price-watcher.service` /
`alerts/price-watcher.timer`, von einem parallelen Arbeitsstand):

| Aspekt | vorhandene Unit | Empfehlung dieses Dokuments |
|---|---|---|
| Ebene | **System**-Unit (`WantedBy=multi-user.target`) ⇒ braucht `sudo`/root | **User**-Unit (`~/.config/systemd/user/`, `WantedBy=default.target`/`timers.target`) ⇒ kein root, läuft mit dem Benutzer, der `~/.trvl` besitzt |
| Takt | `OnBootSec=10min` + `OnUnitActiveSec=1h` | `OnCalendar=*-*-* 00/6:17:00` + `RandomizedDelaySec=20min` (Laststreuung gegen Google-Rate-Limits) + `Persistent=true` |
| Aufruf | `watcher.py --once` (stündlich) | gleicher Einmal-Aufruf, aber 6 h Takt; **Snapshot-Takt** (stündlich) und **Regel-Takt** (6 h) bewusst getrennt denken: Statistik braucht Tage, Budget braucht Aktualität |
| Konkurrenz | keine `flock`-Sicherung, kein `TimeoutStartSec` | `flock` auf `state/.runner.lock` + `TimeoutStartSec=15min` + `Nice=10`/`IOSchedulingClass=idle` |

Ein System-Timer wäre nicht falsch, aber er erzeugt einen Root-Kontext für ein Werkzeug,
das ausschließlich in `$HOME` des Benutzers liest und schreibt — und er startet **auch
ohne** den User-Kontext, in dem `~/.trvl` liegt, falls `HOME` nicht korrekt gesetzt ist.
Deshalb: **User-Timer** (mit `loginctl enable-linger`), crontab als vollwertige Alternative.

**Fallback cron** (wenn kein Linger/kein systemd-User möglich):

```
17 */6 * * * /home/batnini/mimo-agents/alerts/alert_runner.sh >> /home/batnini/mimo-agents/alerts/runner.log 2>&1
```

### 5.2 Fertiges Beispiel — systemd **User**-Timer

`~/.config/systemd/user/trvl-price-alert.service`

```ini
[Unit]
Description=trvl Preiswächter — Snapshot + Regelprüfung
Documentation=file:///home/batnini/mimo-agents/docs/ALERT_RESEARCH.md
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
WorkingDirectory=/home/batnini/mimo-agents/alerts
Environment=TRVL=/home/batnini/.local/bin/trvl
Environment=ALERT_CONFIG=/home/batnini/mimo-agents/alerts/ALERT_CONFIG.yaml
Environment=ALERT_STATE=/home/batnini/mimo-agents/alerts/state/alert_state.json
ExecStart=/home/batnini/mimo-agents/alerts/alert_runner.sh
# Provider-freundlich: niemals zwei Läufe gleichzeitig
ExecStartPre=/usr/bin/flock -n /home/batnini/mimo-agents/alerts/state/.runner.lock -c true
TimeoutStartSec=15min
Nice=10
IOSchedulingClass=idle
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=default.target
```

`~/.config/systemd/user/trvl-price-alert.timer`

```ini
[Unit]
Description=trvl Preiswächter — alle 6 Stunden

[Timer]
OnCalendar=*-*-* 00/6:17:00
# Last streuen (Google-/Provider-Limits)
RandomizedDelaySec=20min
Persistent=true
AccuracySec=1min
Unit=trvl-price-alert.service

[Install]
WantedBy=timers.target
```

Aktivieren:

```bash
loginctl enable-linger batnini          # User-Timer ohne Login
systemctl --user daemon-reload
systemctl --user enable --now trvl-price-alert.timer
systemctl --user list-timers trvl-price-alert.timer
journalctl --user -u trvl-price-alert.service -n 50
```

### 5.3 Fertiges Beispiel — crontab

```bash
cat > /home/batnini/mimo-agents/alerts/alert_runner.sh <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
BASE=/home/batnini/mimo-agents/alerts
exec 9>"$BASE/state/.runner.lock"
flock -n 9 || { echo "run already in progress"; exit 0; }
exec /usr/bin/python3 "$BASE/alert_runner.py" --config "$BASE/ALERT_CONFIG.yaml"
EOF
chmod +x /home/batnini/mimo-agents/alerts/alert_runner.sh

(crontab -l 2>/dev/null; echo '17 */6 * * * /home/batnini/mimo-agents/alerts/alert_runner.sh >> /home/batnini/mimo-agents/alerts/runner.log 2>&1') | crontab -
```

### 5.4 Ablauf je Lauf

```
1. flock auf state/.runner.lock          → kein Parallel-Lauf
2. cooldown-Gate je Provider             → min_interval je Quelle
3. trvl watch check                      → native Budget-/Drop-Events (stdout)
4. trvl watch list --format json         → last_price, lowest_price, baseline_price
5. trvl watch history <id> --format json → Beobachtungsserie
6. optional: trvl dates / grid / forecast → Datumsfenster + CDF
7. Snapshot schreiben (1 Zeile/Tag/Route) → eigene 7-Tage-Serie
8. Regeln auswerten (Budget/Tiefpunkt)   → nur bei Erfüllung
9. Alarm dispatchen (Webhook/ntfy/Mail)  → 1× je (rule, source_key, channel)
10. State atomar schreiben (tmp + rename)
```

### 5.5 Rate-Limit-/Cooldown-Strategie

| Ebene | Maßnahme |
|---|---|
| Provider | `min_interval` je Provider in der Config (Default 15 min); `trvl` serialisiert ohnehin 1 Request/500 ms pro Provider |
| Google | `trvl` kühlt selbst herunter (60 s / 15 min, persistent in `~/.trvl/cache/google-refusal`); der Watcher **liest** `trvl rate-status` und überspringt den Lauf bei aktivem Cooldown |
| Gesamt | `trvl watch check` pausiert 3 s zwischen Watches; Scheduler-Intervall 6 h ≫ Provider-Limits |
| Eigen | `Persistent=true` + `RandomizedDelaySec` verhindert Burst nach Reboot |
| Idempotenz | Snapshot-Datum = `(source_key, date)` → ein Snapshot/Tag, Duplikate werden überschrieben |

---

## 6. Quellen der Verifikation

* Native Kommandos: lokal ausgeführt gegen `/home/batnini/.local/bin/trvl` v1.27.0
  (`~/.trvl/watch.db`, `~/.trvl/cache/google-refusal`, `~/.trvl/last_search.json`).
* Store-Schema: mit einem eigenen bbolt-v2-Leser (`/tmp/opencode/bbolt2.py`) auf einer
  **Kopie** von `~/.trvl/watch.db` verifiziert — Buckets und JSON-Felder.
* Upstream-Quellcode (Lizenz PolyForm Noncommercial 1.0.0):
  `internal/pricesignal/pricesignal.go`, `internal/pricealert/pricealert.go`,
  `internal/watch/{watch,store,store_route_history,scheduler,lock,check,notify,webhook}.go`,
  `internal/batchexec/refusal.go`, `internal/providers/provider_limiter.go`,
  `internal/forecast/forecast.go`, `internal/obslog/obslog.go`, `internal/pricefeed/pricefeed.go`,
  `internal/dealquality/dealquality.go`, `internal/dategrid/dategrid.go`,
  `cmd/trvl/{watch,forecast}.go`.
* Externe Werkzeuge: GitHub-API-Metadaten (Lizenz, `pushed_at`, `archived`) am 2026-10-21.

---

## 7. Grenzen / offene Punkte

1. **`trvl watch check` hat kein `--format json`** — die Ausgabe ist nur Text
   (`DEAL`, `PRICE DROP`, `Flight BER -> FCO 127 EUR (…)`). Maschinenlesbar sind
   `trvl watch list --format json` und `trvl watch history --format json`;
   `watch check` muss über Text-Parsing (stdout) oder über den Webhook-Pfad
   angebunden werden.
2. **`watch.db` ist bbolt, kein SQLite.** Ein direkter Fremd-Read (z. B. mit `sqlite3`)
   scheitert. Für den externen Watcher: entweder CLI nutzen oder einen bbolt-Leser
   mitbringen (nur lesend, mit `flock` auf `~/.trvl/.lock`).
3. **Route-Historie wird nur bei Suchläufen gefüllt**, nicht bei jedem `watch check`
   (Watch-Punkte und Route-Punkte sind getrennte Buckets). Für eine flugplanbezogene
   7-Tage-Serie braucht der Watcher eigene Tages-Snapshots.
4. **`price_position` braucht ≥ 10 Beobachtungen** (`confident`), `trvl forecast`
   braucht **≥ 30** (`Samples`, Fenster 90 Tage) und eine `deal-history.json`, die
   aktuell **nicht existiert** (`~/.trvl/` enthält sie nicht) — die Forecast-Aussage
   ist bis dahin `InsufficientData: true`.
5. **Google-Cooldown ist self-extending**: jeder Probe-Versuch während des Cooldowns
   verlängert die Deadline um 15 min. Ein Watcher darf im Cooldown **nicht** pollen
   (sonst verlängert er die Sperre selbst).
6. **`trvl` ist PolyForm Noncommercial 1.0.0** — source-available, kein OSI-OSS.
   Für den internen Einsatz unkritisch, bei Weitergabe/Produktivbetrieb zu prüfen.
7. **Währungs-Mischung**: `price_position` ist währungsstreng. Ein Watcher muss
   Währungswechsel abfangen (wie `trvl`: 2 aufeinanderfolgende Polls in einer neuen
   Währung ⇒ Reset der Schwellen).
8. **Statistische Mindestabdeckung**: „7-Tage-Median" braucht ≥ 7 (besser ≥ 10)
   Tages-Snapshots; in der ersten Woche läuft der Watcher also im `insufficient_data`-Modus
   und darf **nicht** alarmieren (Coverage-Gate).
