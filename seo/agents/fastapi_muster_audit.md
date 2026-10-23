# FastAPI/Flask-SEO-Muster (GitHub) + Audit der Reise-Agent-UI

**Stand:** 22.10.2026, 22:20 – 23.10.2026, 12:20 (UI wurde währenddessen parallel weiterentwickelt)  
**Auftrag:** Recherche (Teil A) + reines Lese-Audit der UI (Teil B), keine Codeänderung.  
**Ergebnis:** 78/78 Prüfungen bei der Hauptbewertung (22:45), **87/87** im Nachlauf (23.10.) gegen den projektinternen `seo/validate.py`. Die verbleibenden Risiken sind **strategisch** (Duplicate Cluster, automatisch erzeugte Routenseiten, Genauigkeit der Struktur-Daten), nicht mehr formal.

---

## 0. Wichtiger Snapshot-Hinweis

Während des Audits wurde die UI **parallel von einem anderen Prozess umgebaut**. Das ist für die Nachvollziehbarkeit entscheidend:

| Zeit | Zustand |
|---|---|
| 22:26 (erster Lesevorgang) | `ui/app.py` 8.907 B, **keine** SEO-Schicht, kein `sitemap`/`robots`, statische `<title>`-Blöcke, keine Meta-Description |
| 22:11–22:38 | SEO-Schicht entsteht: `seo/{meta,jsonld,sitemap,pages,routes_cache}.py`, `GZipMiddleware`, dynamische Metas, Landing-/Routenseiten |
| **22:38–22:45 (Hauptbewertung)** | `ui/app.py` 20.823 B, `seo/validate.py` 78/78 OK. Soft-404, `robots.txt`-Widerspruch und `/static/`-Sperre wurden **während des Audits bereits behoben** |
| 23.10., Nachlauf | `seo/validate.py` **87/87** OK; `/docs`, `/redoc`, `/openapi.json` deaktiviert; echtes `/static/favicon.svg`; Asset-Versionierung `?v=`; Reload-Loop behoben; Kategorieseite auf 3 Angebote begrenzt (S2) |

Ich bewerte den Stand **22:45** und markiere Nachlauf-Änderungen separat. Zeilennummern sind Momentaufnahmen und verschieben sich durch die Parallelarbeit (seit 22:45 teils +20–40 Zeilen); Anker sind deshalb zusätzlich als Funktions-/Dateiname angegeben.

**Nachlauf 23.10. – bereits umgesetzt (nicht mehr als offene Maßnahme führen):** Soft-404 → 404, `robots.txt` ohne `/jobs/`- und `/static/`-Sperre, API-Docs deaktiviert, Favicon als Datei, `?v=`-Cache-Busting, Reload-Loop, S2-Teilmaßnahme (3 statt 10 Angebote auf der Kategorieseite).

**Umsetzungsstand bei Abgabe (23.10., ~12:15):**

| Empfehlung | Status |
|---|---|
| S1 Canonical aus `SITE_URL` | **erledigt** (`_base()` bevorzugt `SITE_URL`, Fallback `request.base_url`); in Produktion muss `SITE_URL` gesetzt sein |
| S2 Duplicate Kategorie/Route | **teilweise** (3 Angebote; Ähnlichkeit 0,825) |
| S3 Qualitätsgate | **weitgehend erledigt**: ≥ 5 Angebote, Längencheck, Hotels erzeugen keine Routen mehr, veraltete Routen > 7 Tage `noindex` + aus Sitemap. Rest: `origin == destination` und echte IATA-Prüfung fehlen |
| S4 JSON-LD | **teilweise**: `availability`/`priceValidUntil`/Währungsfilter erledigt; Detail-Preis-Mismatch offen |
| S5 SearchAction | **erledigt** |
| S6 API-Docs | **erledigt** (404) |
| S7 Routen-Metas | **weitgehend erledigt**: Kategoriename + Ortsnamen aus den Flugabschnitten (z. B. „Berlin Brandenburg – Rome Fiumicino“). **Aber:** Title ist damit 61 Zeichen und wird auf 60 abgeschnitten → „… Preise vergleiche“ (siehe 3.2) |
| S8 OG-Bild | **offen** (Favicon erledigt) |
| S9 Reload-Loop | **erledigt** |
| S10 `/alarms` privat cachen | **erledigt** (`private, no-store`) |
| S11 Brotkrumen Route | **offen** (sichtbar nur Start › Kategorie) |
| S12 `rel="sponsored"` | **erledigt** (Landing-Links) |
| S13 `X-Robots-Tag` API | **erledigt** (Middleware für `/api/`, `/health`) |
| S14 Asset-Versionierung | **teilweise** (`?v=`; Cache-Dauer noch 1 Tag) |
| L1–L8 | **offen** (strategisch) |

Messumgebung: lokaler Uvicorn auf `127.0.0.1:8100` (Hauptlauf) bzw. `:8102` (Nachlauf), nur GET-Anfragen, kein Suchlauf gestartet. Größen sind **lokal ohne CDN/Proxy** gemessen und nicht mit Produktionswerten gleichzusetzen.

---

## 1. Kurzfazit

1. **Die technische Basis ist überdurchschnittlich gut:** serverseitiges HTML, genau eine H1 pro Seite, Title 25–57 Zeichen, Description 109–144 Zeichen, Canonical, `lang`, Viewport, `theme-color`, GZip, Cache-Header, keine externen Ressourcen, 15,6 KB HTML (4,6 KB gzip), 6,6 KB CSS, 3,1 KB JS.
2. **Das größte SEO-Risiko ist selbst erzeugter Duplicate Content:** `/fluege` und `/fluege/ber-fco` waren zu **85 % textgleich** (Jaccard 0,852 bei 10 Angeboten); nach der Nachlauf-Begrenzung auf 3 Angebote sind es noch **0,825**. Der Textkörper (Intro, Formular, FAQ, Kategorien) bleibt identisch; beide sind `index,follow` und selbst-kanonisch. Das ist der Kern, nicht die Meta-Tags.
3. **Routenseiten entstanden ohne Qualitätsfilter** aus jedem Nutzer-Suchlauf (`routes_cache.save`) und landeten automatisch in der Sitemap. Belegt (Nachlauf-Zeitpunkt): `/hotels/rome-rome` war indexierbar und in der Sitemap – H1 „Rome → Rome“, Description „… mit Endpreis, **Stopps** und Quellenlage“ (Stopps sind ein Flug-Attribut). Inzwischen nachgerüstet: Mindestanzahl Angebote, Längencheck, keine Hotel-Routen, Stale-Ausschluss. Das Doorway-/Scaled-Content-Muster bleibt bei vielen echten Routen trotzdem bestehen, weil der Inhalt weiterhin templategleich ist.
4. **Strukturierte Daten sind formal gültig:** Die ursprünglich erfundenen Felder (`availability`, `priceValidUntil`) und die Währungsmischung sind im Nachlauf behoben. Verbleibend: Auf der Detailseite ist der markierte Preis ggf. `all_in`, während oben `price` als Hauptpreis steht; `Product` für eine Strecke ist semantisch gedehnt.
5. **Canonical, OG-URL und Sitemap hingen am `Host`-Header** (`request.base_url`), nicht an einer konfigurierten Site-URL – hinter Proxy/CDN eine klassische Fehlerquelle (http vs. https, intern vs. öffentlich). Im Nachlauf behoben: `_base()` bevorzugt jetzt `SITE_URL`, Fallback bleibt Dev. **Betriebsvoraussetzung:** `SITE_URL` in Produktion setzen.
6. **Drei Kategorieseiten haben keine echten Routendaten** (`/faehren` 261, `/kreuzfahrten` 272 Wörter; `/hotels` zeigt seit dem Nachlauf die unsinnige Route „Rome → Rome“) und versprechen im Title „Preise“. Sie sind nicht „dünn“ im formalen Sinn, aber schwächer als die Flugseite und ohne belastbaren Preisbeleg.
7. **Kleinere, klare Lücken:** kein `og:image`/`twitter:image`, kein Impressum/Datenschutz (404). Bereits behoben: Reload-Loop, Data-URI-Favicon, offene API-Docs, Soft-404, `robots`-Widerspruch.

---

## 2. Teil A – GitHub-Recherche

### 2.1 Suchstrategie und Einschränkung

Gesucht wurde nach `fastapi sitemap`, `fastapi robots.txt`, `fastapi seo`, `jinja2 json-ld`, `fastapi structured data` (Websuche + GitHub-API + Raw-Dateien). Zusätzlich geprüft: das offizielle `fastapi/full-stack-fastapi-template` als Gegenprobe.

**Wichtige Einschränkung:** Die Fundstücke sind klein (0–35 Sterne). Es gibt kein großes, bekanntes FastAPI-Produkt mit vorbildlicher SEO-Schicht, das als Skalierungsbeleg taugen würde. Die Muster sind konsistent, aber die Stichprobe ist klein. Das offizielle FastAPI-Template enthält **keine** `sitemap`-, `robots`- oder `seo`-Dateien (305 Dateien geprüft) – SEO ist im FastAPI-Ökosystem **nicht Default**, sondern Handarbeit.

**Flask:** Flask ist im System-Python **nicht installiert** (`import flask` schlägt fehl). Deshalb wurde kein Flask-Projekt ausgeführt; die Muster sind FastAPI/Starlette-spezifisch. Die wesentlichen Ideen (Jinja-Blöcke, `render_template`, `Response` mit `text/plain`, `send_from_directory`) sind übertragbar, aber nicht mit Code-Beleg geprüft.

### 2.2 Projekte im Überblick

| Projekt | Stand | Muster | Taugt als Vorlage? |
|---|---|---|---|
| [ForeverHYX/Homepage](https://github.com/ForeverHYX/Homepage) | aktiv, letzter Push 2026-09-24, 1 ★ | `robots.txt` + `sitemap.xml` als FastAPI-Routen mit `Cache-Control`; Canonical + `noindex` für Filter-URLs; `X-Robots-Tag` für Admin; IndexNow; SEO-Tests | **Ja, beste Vorlage** für Betriebsdetails |
| [IceWizard98/wiki-ai](https://github.com/IceWizard98/wiki-ai) | aktiv, 2026-05-29, 3 ★ | Sitemap **statisch** vom Adapter atomar geschrieben, per `FileResponse` ausgeliefert; `robots`-Route; JSON-LD `WebSite`; `llms.txt` | Ja für Sitemap-Schreibmuster, **nein** für Canonical |
| [mugendi/moosey-cms](https://github.com/mugendi/moosey-cms) | aktiv, 2026-07-17, 5 ★ | Wiederverwendbarer Jinja-Helfer `seo_tags()`; `sitemap`/`robots` als Routen; umgebungsabhängige `Disallow`-Regeln; `noindex`-Seiten aus Sitemap ausgeschlossen | Ja für Bausteine, Detailfehler beachten |
| [davestroud/ishtar_ai_app](https://github.com/davestroud/ishtar_ai_app) | 2026-03-05, 0 ★ | Sitemap aus **hartkodierter** Seitenliste; `robots`-Route; JSON-LD im Base-Template; Cache-Middleware | Nur als Anschauung, viele Anti-Patterns |
| [earonesty/fastapi-sitemap](https://github.com/earonesty/fastapi-sitemap) | letzter Push 2025-05-02, 1 ★ | Bibliothek: Routen automatisch einsammeln, `exclude_patterns`, optional `.gz` | Als Idee; **Pflege Risiko** |
| [pydanny/fastapi-blog](https://github.com/pydanny/fastapi-blog) | **archiviert** | Blog-CMS mit „SEO-friendly“ + Sitemap | **Nein**, nicht mehr gepflegt |

### 2.3 Muster im Detail (mit Beleg)

#### (a) Dynamische Meta-Tags in Jinja2

**Ishtar AI** ist das klassische Block-Muster: `app/templates/base.html:8-42` definiert Blöcke für Description, Keywords, Robots, OG und Twitter; jede Seite überschreibt sie. Canonical wird aus `canonical_url` + `canonical_path` zusammengesetzt (`base.html:36-37`). Nachteil: Die Domain steht **hartkodiert** im Template (`https://ishtar-ai.com`) und jede Seite muss die Blöcke manuell füllen – Drift ist vorprogrammiert.

**Moosey CMS** macht es zentral: `src/moosey_cms/seo.py:13-24` nimmt Title, Description, Image, Canonical, `noindex` entgegen und rendert alle Tags inkl. OG/Twitter (`seo.py:94-128`) und JSON-LD (`seo.py:137-160`). Priorität: explizites Argument > Context-Variable > Default (`seo.py:46-52`). Das ist ein gutes Muster für viele Seiten.

**WikiAI** nutzt Blöcke im Layout (`app/web/templates/layout.html:6-26`): `title`, `description`, `og_*`, `twitter_*`, `canonical`, `meta_robots`. Die Blöcke sind sauber getrennt, aber der Canonical ist fehlerhaft (siehe Anti-Patterns).

**Übertragbar:** Genau das macht die Reise-Agent-UI jetzt mit `seo/meta.py:25-53` – zentraler `build()` und `meta`-Objekt im Template (`ui/templates/base.html:1-26`). Das ist besser als Ishtars Block-Ansatz, weil Title/Description nicht pro Template gepflegt werden müssen.

#### (b) `sitemap.xml`: statisch generiert vs. Route

**Statisch (WikiAI):** `app/adapters/sitemap/xml_sitemap_writer.py:28-55` lädt die vorhandene XML, entfernt den alten Eintrag derselben URL, hängt `<url>` mit `lastmod`, `changefreq`, `priority` an und schreibt **atomar** über `.tmp` + `os.replace` (`:28-33`). Ausgeliefert wird die Datei per Route: `app/web/routes.py:134-139` (`FileResponse`, 404 wenn Datei fehlt). Vorteil: Schreiben passiert im Hintergrundjob, Auslieferung ist ein Dateizugriff. Nachteil: Zwei Wahrheiten (Datei + Datenbank), und bei mehreren Workern muss die Datei auf gemeinsamem Storage liegen.

**Dynamisch (Homepage):** `app/routers/pages.py:388-406` baut die XML bei jedem Request aus `SITEMAP_PATHS`, mit `Cache-Control: public, max-age=3600`. Das ist bei < 50.000 URLs völlig ausreichend und immer konsistent. **Moosey** macht dasselbe über eine Route (`src/moosey_cms/site.py:281-287`, Registrierung `:442-447`).

**Bibliothek (fastapi-sitemap):** `fastapi_sitemap/sitemap.py:93-113` hängt eine Route an, kann optional eine `.gz`-Variante erzeugen; `:141-158` sammelt Routen ein, überspringt dynamische Pfade (`{...}`) per Default und wendet `exclude_patterns` an. Genau hier liegt die Grenze: Die Reise-Agent-Routenseiten sind dynamisch (`/fluege/{route}`) und müssten über eine eigene `source`-Funktion kommen.

**Für die UI:** Die dynamische Route (`ui/app.py:263-268`, `seo/sitemap.py:37-60`) ist richtig. Sie ist schnell, immer aktuell und braucht keine Datei. `lastmod` wird nur für Routenseiten gesetzt (`sitemap.py:54`), nicht geraten für Kategorieseiten – das entspricht der Regel „lieber weglassen als raten“.

#### (c) `robots.txt`: statisch vs. Route

**Homepage** (`pages.py:366-384`) erzeugt sie als Route, mit `Disallow: /api/`, `/login`, `/share/`, `/upload`, Sitemap-Verweis und `Cache-Control: public, max-age=3600`. Wichtig: **`/static/` wird nicht gesperrt** – CSS/JS müssen für das Rendering abrufbar bleiben.

**WikiAI** (`routes.py:142-169`) erzeugt sie ebenfalls dynamisch, inkl. eigener Regeln für GPTBot, OAI-SearchBot, ClaudeBot, PerplexityBot und `CCBot: Disallow`. Das ist eine bewusste AI-Crawler-Politik, kein SEO-Muss.

**Moosey** (`site.py:289-316`) macht die Regeln umgebungsabhängig: In `staging`/`testing` wird `Disallow: /` ausgegeben, in `production` `Allow: /` (`site.py:292-295`). Das ist ein sehr gutes Muster gegen versehentlich indexierte Staging-Umgebungen.

**Ishtar** (`app/routes/seo.py:115-124`) ist das Gegenbeispiel: hartkodierte Domain, `Disallow: /pricing` – und die Sitemap listet `/pricing` trotzdem nicht, was konsistent ist, aber nirgends dokumentiert wird.

**Für die UI:** `seo/sitemap.py:63-88` erzeugt die Datei dynamisch, mit Sitemap-Verweis, `Disallow` für `/alarms`, `/api/`, `/health` und – seit der Korrektur um 22:38 – **ohne** `/jobs/` und **ohne** `/static/`. Das ist jetzt korrekt.

#### (d) JSON-LD in Templates

**Ishtar** legt `Organization`/`ResearchOrganization` zentral in `base.html:73-99`, `BlogPosting`/`WebSite` kommen pro Seite dazu (laut README). Vorteil: ein Ort. Nachteil: Werte sind hartkodiert und müssen bei Umzug gepflegt werden.

**WikiAI** legt `WebSite` + `SearchAction` als Block ins Layout (`layout.html:52-77`), Artikel-Seiten überschreiben ihn. Die `SearchAction` zeigt auf `/search?q={search_term_string}` – dort existiert aber nur ein **POST**-Formular (`routes.py:52-86`). Das Suchziel ist also per GET nicht erreichbar; die SearchAction ist damit wirkungslos.

**Moosey** baut JSON-LD per f-String (`seo.py:140-159`) und escaped die Werte mit MarkupSafe (`escape()`). Das ist **kein gutes Vorbild**: `escape()` erzeugt HTML-Entities (`&#34;`) innerhalb von JSON-Strings; bei fehlendem Bild entsteht `"image": "None"`. Funktioniert bei einfachen Texten, ist aber fragil.

**Für die UI:** `seo/jsonld.py:175-181` macht es richtig: `json.dumps()`, danach `</` → `<\/` gegen XSS, Ausgabe mit `|safe`. Das ist der saubere Weg.

#### (e) Canonical-URLs

**Gut:** Homepage setzt Canonical pro Seite im `meta`-Block (`app/templates/pages/daily.html:6`) und berechnet ihn aus einer **konfigurierten** `SITE_URL` (`pages.py:468`, `:493`). Filter- und ungültige Datums-URLs bekommen zusätzlich `noindex,follow` (`daily.html:7-9`, `pages.py:466-467`, `:494`).

**Schlecht:** WikiAI nimmt `request.url` als Canonical (`layout.html:25`). Damit landen Query-Strings und ggf. `http://` in der kanonischen URL. Moosey nutzt ebenfalls `str(request.url)` als Default (`seo.py:78-84`). Das ist der häufigste Fehler in kleinen FastAPI-Projekten.

**Für die UI:** `seo/meta.py:31-37` baut den Canonical aus `base_url` + **explizitem Pfad**, nicht aus der Request-URL. Das ist richtig. Der Pfad wird pro Route übergeben, Query-Parameter fallen weg. Getestet: `/fluege/BER-FCO` kanonisiert auf `/fluege/ber-fco`. Offen ist nur die Herkunft von `base_url` (siehe B2).

#### (f) `noindex` für Admin/API

**Homepage** ist hier am reifsten: Admin-Redirects und Login/Upload bekommen `Cache-Control: private, no-store` **und** `X-Robots-Tag: noindex, nofollow` (`pages.py:165-171`, `:560-580`). Zusätzlich werden Filter-URLs per Meta-`noindex` ausgeschlossen (`daily.html:7-9`). Das ist defense-in-depth: Header wirkt auch ohne HTML.

**Moosey** schließt `noindex`-Seiten aus Sitemap und Feed aus (`site.py:176`, `site.py:240-249`) – wichtig, damit Sitemap und `noindex` sich nicht widersprechen.

**Für die UI:** `seo/meta.py:57-64` setzt `noindex,follow` für Job-Seiten, `ui/app.py:378-386` für Alarme. Richtig. Aber: `/api/*` und `/health` liefern JSON ohne `X-Robots-Tag`; sie sind nur per `robots.txt` gesperrt. Für den Normalfall reicht das, für defense-in-depth nicht.

#### (g) GZip/Brotli und Cache-Header

In keinem der fünf Projekte wurde `GZipMiddleware` gefunden – die Beispiele delegieren Kompression an Nginx/CDN (Homepage: Nginx liefert `/static/*` mit 7 Tagen Cache, laut README) oder lassen sie weg. Das ist kein Beleg dafür, dass GZip unnötig ist, sondern nur, dass kleine Projekte es oft vergessen.

**Homepage** setzt Cache-Header explizit pro Antwort: `public, max-age=60` für öffentliche JSON-/HTML-Antworten (`pages.py:162`), `private, no-store` für Admin (`:169-170`), `public, max-age=3600` für robots/sitemap (`:384`, `:406`).

**Ishtar** ist das Negativbeispiel: `app/middleware.py:44-49` setzt für **alle** HTML-Antworten `no-cache, no-store, must-revalidate`. Das verhindert jedes Proxy-/CDN-Caching und ist für statische Inhalte unnötig.

**Für die UI:** `ui/app.py:44-55` setzt statisch 1 Tag, HTML 60 s. `GZipMiddleware` ist aktiv (`app.py:39`, Mindestgröße 500 B, Level 9). Gemessen: `/` 15.601 B → 4.607 B gzip; `/fluege` 15.812 B → 3.528 B; CSS 6.611 B → 2.000 B; JS 3.118 B → 1.258 B. Brotli ist installiert, wird aber nicht genutzt.

### 2.4 Bibliotheken: Was hilft, was ist installiert?

Geprüft mit `python3 -c "import ..."` (System-Python 3.12.3):

| Bibliothek | Status | Version | Nutzen für SEO |
|---|---|---|---|
| `fastapi` | ✅ installiert | 0.141.1 | Routing, `Response`, `PlainTextResponse` |
| `starlette` | ✅ | 1.6.0 | `GZipMiddleware` (min. 500 B, Level 9, setzt `Vary: Accept-Encoding`), `StaticFiles` |
| `jinja2` | ✅ | 3.1.3 | Templates, Blöcke, `|safe` für JSON-LD |
| `pydantic` | ✅ | 2.13.4 | Für SEO nicht nötig (nur Validierung) |
| `uvicorn` | ✅ | 0.27.0 | Auslieferung; `--proxy-headers` für korrekte `base_url` relevant |
| `brotli` | ✅ | 1.2.0 | **ungenutzt**; ohne Middleware/Proxy kein `br` |
| `python-multipart` | ✅ | 0.0.6 | Formulare (`request.form()`) |
| `requests` | ✅ | 2.31.0 | nur für `seo/validate.py` |
| `xml.etree.ElementTree` | ✅ stdlib | – | Sitemap-Erzeugung, korrekt genutzt in `seo/sitemap.py` |
| `gzip` / `zlib` | ✅ stdlib | – | Kompression, von Starlette genutzt |
| **`flask`** | ❌ **nicht installiert** | – | Flask-Muster hier nicht lauffähig prüfbar |

**Fazit:** Für diese Größenordnung braucht man **keine SEO-Bibliothek**. `GZipMiddleware` + `StaticFiles` + `jinja2` + `xml.etree` decken alles ab. `fastapi-sitemap` wäre eine Abhängigkeit mit Pflegerisiko (PyPI-Homepage zeigt auf `github.com/q32/fastapi-sitemap`, das **404** liefert; letzter Push 2025-05).

`StaticFiles` liefert von sich aus **ETag und Last-Modified**, aber **kein `Cache-Control`** – das muss man selbst setzen (in der UI erledigt). Das ist ein Detail, das in vielen Projekten fehlt.

### 2.5 Übertragbare Regeln / Anti-Patterns aus der Recherche

**Übernehmen:**
1. Canonical aus **konfigurierter** Site-URL + explizitem Pfad, nie aus `request.url`.
2. `robots.txt` und `sitemap.xml` als Route mit `Cache-Control` (1 h reicht).
3. `noindex`-Seiten **nicht** gleichzeitig per `robots.txt` sperren.
4. Admin/Login mit `X-Robots-Tag` **und** `private, no-store`.
5. Sitemap nur mit echten, indexierbaren 200-URLs; `lastmod` nur wenn bekannt.
6. JSON-LD mit `json.dumps` + `</`-Escaping, nicht mit HTML-Escaping.
7. Staging-Robots (`Disallow: /`) getrennt von Production.
8. SEO-Tests im Repo (Homepage: `tests/test_seo_routes.py:17-41` prüft robots, sitemap, IndexNow).

**Vermeiden:**
- Canonical aus `request.url` (WikiAI, Moosey-Default).
- Hartkodierte Domain in Sitemap/Robots (Ishtar).
- `no-store` für alle HTML-Antworten (Ishtar).
- Sitemap aus einer manuell gepflegten Liste (Ishtar) – driftet.
- `SearchAction` auf ein POST-Formular (WikiAI).
- JSON-LD per f-String + `escape()` (Moosey).
- Sitemap-/Robots-Logik in einem Riesen-`main.py` ohne Tests.

---

## 3. Teil B – Audit der bestehenden UI

### 3.1 Seiteninventar und Indexierbarkeit

Gemessen am 22:45 gegen `127.0.0.1:8100`.

| URL | Typ | Inhalt | Indexierung | In Sitemap | Risiko |
|---|---|---|---|---|---|
| `/` | Suche + Quellenliste | 624 Wörter, 15,6 KB | `index,follow` | ja | niedrig |
| `/preisvergleich` | Übersicht | 295 Wörter, 7,5 KB | `index,follow` | ja | niedrig |
| `/fluege` | Kategorie + letzte Angebote | 413 Wörter (Nachlauf 372), 15,8 KB | `index,follow` | ja | **Duplicate** zur Routenseite |
| `/hotels` | Kategorie ohne Routendaten | 280 Wörter (Nachlauf 352 mit „Rome → Rome“, inzwischen entfernt), 6,8 KB | `index,follow` | ja | thin/Preisversprechen ohne echte Hoteldaten |
| `/faehren` | Kategorie ohne Angebote | 261 Wörter, 6,5 KB | `index,follow` | ja | thin |
| `/kreuzfahrten` | Kategorie ohne Angebote | 272 Wörter, 6,7 KB | `index,follow` | ja | thin |
| `/fluege/{route}` | automatisch erzeugte Routenseite | 385 Wörter, 15,4 KB | `index,follow` | ja (nur mit Cache) | **Duplicate**, Doorway-Risiko bei Vielen |
| `/jobs/{id}` | Laufergebnis | 611 Wörter (Fehlerfall), sonst JS-Tabellen | `noindex,follow` | nein | gering (kein Index), aber JS-abhängig |
| `/jobs/{id}/detail/{cat}/{i}` | Angebotsdetail | reichhaltig | `noindex,follow` (via `for_job`) | nein | gering; Potenzial ungenutzt |
| `/alarms` | private Konfiguration | 265 Wörter | `noindex,nofollow` + `Disallow` | nein | gering |
| `/alarms/{id}` | Alarmdetail | Verlauf/Regeln | `noindex,nofollow` + `Disallow` | nein | gering |
| `/api/*` | JSON | – | `Disallow` | nein | gering (kein `X-Robots-Tag`) |
| `/health` | JSON | – | `Disallow` | nein | gering |
| `/sitemap.xml`, `/robots.txt` | technisch | – | – | – | – |
| `/docs`, `/redoc`, `/openapi.json` | FastAPI-Standard | Swagger/ReDoc | **deaktiviert (404) – behoben** | nein | keins |

**Bewertung:** Die Trennung „öffentlich = Kategorien/Routen, privat = Jobs/Alarme/API“ ist konzeptionell richtig. Sie ist auch im Code dokumentiert (`seo/pages.py:1-12`, `:104-108`). Die Docs-Lücke ist im Nachlauf geschlossen; verbleibend: Die Kategorieseiten versprechen Preise, die bei drei von vier Kategorien nicht belastbar belegt sind.

### 3.2 Meta-Tags

Gemessen (Title-/Description-Länge in Zeichen):

| Seite | Title | Len | Description | Len | Canonical | Robots |
|---|---|---|---|---|---|---|
| `/` | „Flüge, Hotels, Fähren, Kreuzfahrten – Reise-Agent“ | 49 | „Live-Preise aus über 20 Quellen …“ | 144 | `http://…/` | index,follow |
| `/preisvergleich` | „Reise-Preisvergleich: Flüge, Hotels, Fähren, Kreuzfahrten“ | 57 | „Live-Preise aus über 20 Quellen vergleichen …“ | 142 | selbst | index,follow |
| `/fluege` | „Günstige Flüge vergleichen – Live-Preise von 9 Quellen“ | 54 | „Flugpreise live aus 9 Quellen vergleichen …“ | 136 | selbst | index,follow |
| `/fluege/ber-fco` | „Flüge Berlin Brandenburg – Rome Fiumicino: Preise vergleiche“ (abgeschnitten) | 60 | „Aktuelle Preise für Flüge Berlin Brandenburg – Rome Fiumicino …“ | 140 | selbst | index,follow |
| `/hotels` | „Hotels vergleichen – Preise je Nacht mit Steuerstatus“ | 53 | „Hotelpreise je Nacht aus mehreren Quellen …“ | 118 | selbst | index,follow |
| `/alarms` | „Preisalarme – Reise-Agent“ | 25 | „Preisalarm für Flüge, Hotels, Fähren und Kreuzfahrten einrichten …“ | 110 | selbst | noindex,nofollow |

**Vorhanden:** `charset`, `viewport`, `lang="de"`, `theme-color`, Title, Description, Canonical, Robots, OG (type, site_name, title, description, url, locale), Twitter (card, title, description). Alles zentral in `ui/templates/base.html:1-26`, gespeist aus `seo/meta.py:25-53`.

**Fehlt / schwach:**
1. **`og:image` und `twitter:image` fehlen auf allen Seiten.** `base.html:18` rendert nur, wenn `meta.og_image` gesetzt ist; kein Aufrufer übergibt ein Bild (`seo/meta.py:43`). Social-Previews sind damit textonly. Kein Rankingfaktor, aber CTR/Teilen.
2. **Favicon:** war ein Data-URI-SVG, ist im Nachlauf durch `/static/favicon.svg` ersetzt (behoben). `/favicon.ico` fehlt weiterhin, ist aber mit SVG-Icon nicht zwingend.
3. **Route-Title: Ortsnamen sind da, aber der harte Cut produziert einen Tippfehler.** Inzwischen liefert die Quelle Namen („Berlin Brandenburg“, „Rome Fiumicino“); der Title ist damit **61 Zeichen** und wird in `seo/meta.py:83` auf 60 abgeschnitten: „Flüge Berlin Brandenburg – Rome Fiumicino: Preise **vergleiche**“. Das sieht wie ein Rechtschreibfehler aus und ist ein direkt sichtbarer Qualitätsverlust. Zusätzlich englische Ortsnamen („Rome“) auf einer deutschen Seite. **Empfehlung:** kürzere Labels („Berlin – Rom“) oder Title ohne hartes `[:60]` bauen.
4. **Route-Description:** Der Roh-Slug „(fluege)“ ist im Nachlauf zu „Flüge“ korrigiert. Verbleibend: Sie nennt „**Stopps**“ auch für Hotels (`/hotels/rome-rome`), wo Stopps kein sinnvolles Merkmal sind – die Beschreibung ist nicht kategoriespezifisch.
5. **`twitter:card` ist meist `summary`**, nicht `summary_large_image` (`meta.py:46`), weil kein Bild gesetzt ist.
6. **Kein `og:image:alt`, kein `twitter:site`** – für diese Seite verzichtbar.
7. **Canonical:** hing am Host-Header, ist im Nachlauf über `SITE_URL` konfigurierbar (siehe 3.6, Punkt 1).
8. **`meta robots` auf Job-Seiten ist `noindex,follow`**, auf Alarmen `noindex,nofollow` – konsistent und sinnvoll.
9. **Kein `hreflang`** – bei einsprachiger Seite korrekt.
10. **`title`-Blöcke in `results.html:2`, `search.html:2`, `alarms.html:2` etc. sind tote Blöcke**, weil `base.html` kein `{% block title %}` mehr definiert. Kein Fehler, aber verwirrend.

**Harte Zahlen in Titles:** „9 Quellen“ (Flüge) und „über 20 Quellen“ (Start) sind statische Behauptungen (`seo/pages.py:22`, `ui/app.py:120-127`). Ob sie aktuell exakt stimmen, habe ich nicht geprüft – **nicht belegt**. Wenn sich die Registry ändert, sind die Titles falsch.

### 3.3 Semantik

**Gut:**
- **Genau eine H1 pro Seite** – gemessen auf allen 7 indexierbaren Seiten (Validator prüft das ebenfalls).
- Saubere H2-Hierarchie: Landing `H1 → Preise → Formular → Strecken → FAQ → Kategorien` (`landing.html:7,12,37,67,78,88`); Übersicht `H1 → Kategorien → Ablauf → Suche`; Start `H1 → Reisearten → Quellen` (`search.html:4,82,92`).
- Tabellen mit `<thead>`/`<th>` (`landing.html:17`, `results.html:77`), nicht als Div-Grid.
- Brotkrumen sichtbar auf Landing/Übersicht (`landing.html:3-5`, `overview.html:3-5`), `aria-label="Brotkrumennavigation"`.
- Skip-Link (`base.html:28`), `nav aria-label` (`:31`), `main id="main"` (`:40`).
- FAQ als `<details>/<summary>` – Text ist im DOM und indexierbar, kein JS nötig (`landing.html:79-83`).
- **Keine Bilder** → keine fehlenden Alt-Texte. (Aber auch keine Bild-SEO und kein `og:image`.)

**Schwach:**
1. **Routen-H1 ist nur „BER → FCO“** (`ui/app.py:232` setzt `h1: label`, `landing.html:7`). Für Nutzer und Suchmaschine nicht selbsterklärend.
2. **Generische Linktexte:** „Zum Anbieter“ / „Zum Anbieter (Anzeige)“ wiederholt (`landing.html:26`), „Details“ in Ergebnistabellen (`app.js:58`). Auf noindex-Seiten egal, auf Landing-Seiten schwach.
3. **Sichtbare Brotkrumen und JSON-LD stimmen auf Routenseiten nicht überein:** sichtbar „Start › Flüge“ (`landing.html:3-5`), JSON-LD „Start › Flüge › BER → FCO“ (`ui/app.py:245-246`). Google empfiehlt Übereinstimmung.
4. **Startseiten-H1 „Reise suchen“** (`search.html:4`) ist generisch; der Title ist keyword-stärker. Kein Fehler, aber verschenkt.
5. **Kein Impressum/Datenschutz/„Über uns“** – `/impressum` und `/datenschutz` liefern 404 (getestet). Für eine kommerzielle deutsche Seite ist das ein Rechts- und Trust-Thema (E-E-A-T), unabhängig von Ranking-Faktoren.
6. **Keine Autoren-/Betreiberangabe, kein `Organization.contactPoint`/`sameAs`** – die `Organization` in `jsonld.py:46-55` hat nur Name, URL, Beschreibung, Sprache.

### 3.4 Strukturierte Daten

Vorhanden (JSON-LD, zentral gebaut in `seo/jsonld.py`, eingebunden über `ui/app.py:63-68`):

| Seite | Typen |
|---|---|
| `/` | `WebSite`, `Organization`, `BreadcrumbList` |
| `/preisvergleich` | `WebSite`, `Organization`, `BreadcrumbList` |
| `/fluege` | `BreadcrumbList`, `FAQPage`, `ItemList` (3× `Product`/`Offer` im Nachlauf), `Product`/`AggregateOffer` |
| `/fluege/ber-fco` | dito (4 Blöcke) |
| `/hotels`, `/faehren`, `/kreuzfahrten` | nur `BreadcrumbList`, `FAQPage` |
| `/jobs/{id}` | `BreadcrumbList`, `ItemList`, `AggregateOffer` (auf noindex-Seite) |
| `/jobs/{id}/detail/...` | `ItemList` mit einem `Offer` (noindex) |

**Formal gut:** `@context`, Pflichtfelder, `json.dumps` + `</`-Escaping (`jsonld.py:175-181`), keine erfundenen Bewertungen (`product_with_rating` existiert bewusst nur als Dokumentation, `:153-172`), Validierung im Repo (`:185-233`).

**Inhaltliche Probleme:**

1. **`SearchAction` (im Nachlauf entfernt):** Sie zeigte auf `/?origin=…`, während die Suche ein POST auf `/api/search` ist – ein nicht funktionsfähiges Suchziel. Zusätzlich ist die Sitelinks-Searchbox seit 2024 abgekündigt. Jetzt ist nur noch `WebSite` übrig (`jsonld.py:32`). Behoben.
2. **`FAQPage` bringt voraussichtlich kein Rich Result mehr.** Laut Google-Changelog (im Projekt-Dokument `seo/agents/google_richtlinien.md:13` referenziert, Stand 07.05.2026) wurde das FAQ-Rich-Result entfernt; ich habe das **nicht unabhängig verifiziert**. Der sichtbare FAQ-Text bleibt sinnvoll; das Markup ist harmlos, aber wirkungslos.
3. **Erfundene Felder (im Nachlauf behoben):** `availability` und `priceValidUntil` sind entfernt (`jsonld.py:103-109`). Verbleibend: `valid_until` wird in `offer_list` noch berechnet, aber nicht mehr verwendet (`jsonld.py:89`) – toter Code, kein Risiko.
4. **Währungsmischung (im Nachlauf behoben):** `aggregate_offer` filtert jetzt auf Angebote derselben Währung (`jsonld.py:129-133`) und setzt `priceCurrency` konsistent (`:144`). Bei reinen EUR-Daten unauffällig; der Filter ist die richtige Lösung.
5. **Preis-Mismatch auf der Detailseite:** `ui/app.py:361-367` setzt als `Offer.price` bevorzugt `all_in`; die sichtbare Hauptpreiszeile ist aber `item.price` (`detail.html:11`), `all_in` steht nur als Zusatz darunter (`:13`). Google verlangt, dass das markierte Preis-Feld dem prominent sichtbaren Preis entspricht. Beide Werte sind sichtbar, aber die Hierarchie ist uneindeutig.
6. **`Product` für eine Strecke ist semantisch gedehnt:** `aggregate_offer` nennt das Produkt „Reisepreise auf /fluege/ber-fco“ (`jsonld.py:140`). Ein `Product` ist das nicht. Für Vergleichsseiten ist `ItemList` ohne `Product` oft passender; Price-/Availability-Rich-Results sind für Händler-Listings gedacht, nicht für Vermittler.
7. **Breadcrumb-Mismatch** (siehe 3.3, Punkt 3).
8. **Kein `image` in `Product`/`Offer`** – bei fehlendem Bild zulässig, aber schwächer.
9. **Markup auf noindex-Seiten** (`/jobs/*`, Detail) ist ohne SERP-Wirkung. Nicht schädlich, aber Wartungslast; die `ItemList` auf der Detailseite mit genau einem Angebot ist besonders wenig wertvoll.

### 3.5 Performance

Gemessen lokal am 22.10. um 22:45, ohne CDN/Proxy (Nachlauf: `app.js` wuchs auf 3.538 B / 1.425 B gzip; `/fluege` wurde durch das 3-Angebote-Limit kleiner, nicht neu gemessen):

| Ressource | Roh | gzip | Anteil |
|---|---|---|---|
| `/` HTML | 15.601 B | 4.607 B | 100 % |
| `/fluege` HTML | 15.812 B | 3.528 B | – |
| `/fluege/ber-fco` | 15.392 B | 3.434 B | – |
| `/hotels` | 6.785 B | 2.420 B | – |
| `app.css` | 6.611 B | 2.000 B | render-blocking |
| `app.js` | 3.118 B | 1.258 B | `defer` |
| Summe Startseite | ≈ 25,3 KB | ≈ 7,9 KB | – |

**Gut:**
- **Keine externen Ressourcen** – keine Fonts, kein CDN, keine Tracker, keine Bilder. Der Validator prüft das und bestätigt es.
- **GZip aktiv** für HTML/CSS/JS (`app.py:39`), `Vary: Accept-Encoding` wird von Starlette gesetzt (verifiziert).
- **Cache-Header:** `/static/*` 1 Tag (`app.py:49-50`), HTML 60 s (`:51-52`), Sitemap/Robots 1 h (`app.py:263-273`). Statische Dateien liefern zusätzlich ETag/Last-Modified über `StaticFiles`.
- **JS ist klein und `defer`** (`base.html:53`), CSS ist eine Datei.
- **Kein Layout-Springen durch Bilder/Fonts**, weil keine geladen werden.

**Schwach:**
1. **Statische Assets sind nicht versioniert.** `/static/app.css` mit `max-age=86400` heißt: Nach einem Deploy können Nutzer bis zu 24 h altes CSS sehen. Bei einem 6,6-KB-File ist das kein Performance-, aber ein Korrektheitsproblem. Üblich: Hash im Dateinamen (`app.abc123.css`) + `immutable`, 1 Jahr.
2. **Kein Brotli.** `brotli` ist installiert, `GZipMiddleware` kann es nicht. Ohne Nginx/CDN bleibt es bei gzip. Der Unterschied bei 15-KB-HTML ist klein (**nicht quantifiziert**).
3. **`Cache-Control: public, max-age=60, must-revalidate`** ist widersprüchlich formuliert (`must-revalidate` ist erst nach Ablauf relevant), aber funktional harmlos.
4. **`/alarms` wird 60 s `public` gecacht**, obwohl es private Konfiguration zeigt (`app.py:51-52` greift für alle HTML-Seiten). Bei einem gemeinsamen Proxy/CDN könnten fremde Alarmnamen kurz sichtbar werden. Kein Auth-System, daher derzeit theoretisch – aber `private, no-store` wäre korrekt.
5. **Endlos-Reload (behoben im Nachlauf):** `app.js` rief bei `done` `window.location.reload()` auf; jetzt setzt es `finished = true` und schreibt nur einen Hinweis. Verbleibend: Die Tabelle wird weiterhin ausschließlich per JS gefüllt (`results.html:76-81`, `app.js:40-59`) – ohne JS bleibt sie leer (auf `noindex`-Seiten verkraftbar).
6. **Ergebnisseite ist ohne JS leer** („Ergebnisse werden nachgeladen …“, `results.html:79`). Für noindex-Seiten verkraftbar, für Nutzer mit JS-Fehler nicht.
7. **Keine Produktionsmesswerte** (TTFB, LCP, CLS) – **nicht belegt**. Lokal: 80 ms TTFB, ohne Aussagekraft.

### 3.6 Crawlbarkeit

**Vorhanden und gut:**
- `robots.txt` und `sitemap.xml` sind dynamische Routen (`app.py:259-273`), die Sitemap nannte bei der Hauptbewertung 7 URLs, im Nachlauf 8 (inkl. `/hotels/rome-rome`) – alle absolut, alle 200, alle selbst-kanonisch (Validator).
- Sitemap enthält Start, Übersicht, 4 Kategorien und **nur** Routenseiten mit echtem Cache-Inhalt (`sitemap.py:48-56`).
- Kernseiten sind **serverseitig gerendert** und über Header-Nav + Footer verlinkt (`base.html:31-38`, `:50-51`). Kein JS nötig, um sie zu erreichen.
- Interne Links: Start → Kategorien (`search.html:80-88`), Übersicht → Kategorien, Kategorie → Routen (`landing.html:65-75`), Kategorie → andere Kategorien (`:87-94`). Crawl-Tiefe ≤ 2.
- `lastmod` nur für Routen, nicht geraten für Kategorien (`sitemap.py:54`).
- Trailing Slash: `/fluege/` → 307 auf `/fluege` (getestet), Canonical bleibt korrekt. Kein Duplicate.

**Probleme:**
1. **`base_url` kam aus dem Request** (`_base()`): Canonical, `og:url`, Sitemap und JSON-LD hingen am `Host`-Header. Ohne korrekt konfigurierten Proxy (`--proxy-headers`, `X-Forwarded-Proto`) entstanden `http://`-Canonicals oder interne Hostnamen. Im Nachlauf behoben: `SITE_URL` hat Vorrang. **Verbleibend:** In Produktion muss `SITE_URL` gesetzt sein, sonst greift wieder der Host-Fallback.
2. **`/docs`, `/redoc`, `/openapi.json` waren offen** (alle 200, getestet) – im Nachlauf deaktiviert (`app.py:39`, `docs_url=None`). Behoben.
3. **Sitemap wuchs mit Nutzer-Suchläufen (im Nachlauf gebremst).** `routes_cache.save` schrieb jede Route mit mindestens einem Preis; `sitemap.py` nahm sie automatisch auf. Jetzt: ≥ 5 Angebote, Längencheck, keine Hotel-Routen, Ausschluss nach 7 Tagen. **Verbleibend:** keine Prüfung auf `origin == destination`, keine echte IATA-Validierung, keine Nachfrage-/Qualitätsbewertung; Tippfehler-Routen wie „XXX-YYY“ bestehen den Längencheck.
4. **Routenseiten sind Leaf-Nodes ohne Cross-Links:** „Beliebte Strecken“ gibt es nur auf der Kategorieseite (`landing.html:65-75`), nicht auf der Routenseite. Erreichbar sind sie über Sitemap + Kategorie, aber nicht untereinander.
5. **„Beliebte Strecken“ ist unbegrenzt** (`_route_entries` listet alle, `app.py:118-125`): Bei vielen Routen wird die Kategorieseite zur Linkliste, und alle Routenseiten teilen denselben Block – ein zusätzliches Duplicate-Signal.
6. **API/Health ohne `X-Robots-Tag`** – nur `robots.txt`. Reicht meist, ist aber nicht defense-in-depth.
7. **Soft-404 war vorhanden und ist behoben (22:38):** `job_page` rendert bei unbekanntem Lauf jetzt `status_code=404` (`app.py:319-324`). Der laufende Server von 22:27 zeigte noch 200; der neueste Stand liefert 404 (verifiziert). **Beim Deploy prüfen.**
8. **`/fluege/BER-FCO`** wird per Canonical auf `/fluege/ber-fco` normalisiert (verifiziert) – gut. Groß-/Kleinschreibung erzeugt aber unnötige 200-Antworten statt Redirects.

### 3.7 Konkrete Risiken: Duplicate, Thin Content, nutzlose Seiten

**1. Duplicate-Cluster Kategorie ↔ Route (hoch).**  
`_landing` nimmt die **neueste** Route und zeigt deren Angebote direkt auf der Kategorieseite (`app.py:146-147`; im Nachlauf auf 3 begrenzt, `app.py:173`), inklusive derselben Tabelle und derselben FAQ. Die Routenseite rendert dasselbe Template mit denselben Angeboten. Gemessen:

- 22:41 (10 Angebote): `/fluege` 413 Wörter, `/fluege/ber-fco` 385 Wörter, Jaccard **0,852**
- Nachlauf (3 Angebote): 372 vs. 399 Wörter, Jaccard **0,825** – die Begrenzung allein löst das Problem nicht
- beide `index,follow`, beide selbst-kanonisch, beide in der Sitemap

Google sieht zwei fast identische Seiten mit unterschiedlichen URLs und ohne konsolidierendes Canonical. Das führt typischerweise zu „Duplicate, Google chose different canonical“ oder „Crawled – currently not indexed“ – **welche der beiden Seiten betroffen ist, ist nicht vorhersagbar** und nicht belegt. Der Effekt ist aber strukturell angelegt.

**2. Doorway-/Scaled-Content-Risiko durch automatische Routen (hoch, skalierend).**  
Jede erfolgreiche Suche erzeugt eine indexierbare Seite + Sitemap-Eintrag (`routes_cache.py:40-76`, `sitemap.py:48-56`). Bei 100 Suchen entstehen 100 Seiten mit demselben Template, derselben FAQ, wechselnden Preisen und ohne redaktionellen Mehrwert. Das ist genau das Muster, das Googles Spam-Policy „Doorway Abuse“ beschreibt („substantially similar pages that are closer to search results than a clearly defined, browseable hierarchy“).

**Belegt statt theoretisch (Nachlauf-Zeitpunkt):** `/hotels/rome-rome` lag in der Sitemap, war `index,follow`, hatte 372 Wörter und die H1 „Rome → Rome“. Die zugehörige JSON-Datei `ui/state/routes/hotels/ROME-ROME.json` speicherte `origin: Rome`, `destination: Rome`, obwohl die Suchparameter `origin: BER`, `destination: FCO`, `city: Rome` waren. Für Hotels wurde also die **Stadt als Origin und Destination** verwendet – ein Datenfehler, der eine sinnlose, indexierbare Seite erzeugte. Inzwischen entfernt und in `ui/service.py:287-289` mit `if cat == "hotels": continue` behoben; die Description nennt aber weiterhin „Stopps“ für alle Kategorien.

**3. Thin Content bei drei Kategorien (mittel).**  
`/faehren` und `/kreuzfahrten` haben 261–272 Wörter und keinen Routen-Cache; `/hotels` hatte kurzzeitig die unsinnige Route „Rome → Rome“ (inzwischen entfernt und per Sonderfall verhindert), zeigt aber weiterhin keine echten Hoteldaten. Der Text ist unique (Intro + FAQ), also kein klassisches Duplicate – aber die Seiten belegen ihr Preisversprechen nicht. Bei Wettbewerbern mit echten Preisen sind sie schwach; Google kann sie als „thin“ einstufen, muss es aber nicht.

**4. Nutzlose Seiten für Suchmaschinen:**
- `/jobs/{id}`: kurzfristig, nutzerspezifisch, JS-Tabellen → zu Recht `noindex`. Richtig so.
- `/jobs/{id}/detail/...`: inhaltlich die reichhaltigsten Seiten, aber `noindex` und ohne interne Verlinkung von indexierbaren Seiten. Das verschenkt Long-Tail-Potenzial (z. B. „Ryanair BER-FCO Gepäck“), ist aber eine bewusste Architekturentscheidung.
- `/alarms*`: privat, `noindex` + `Disallow`. Richtig.
- `/api/*`, `/health`: technisch. Richtig gesperrt.
- `/docs`, `/redoc`: waren offen, sind im Nachlauf deaktiviert (404).
- `/fluege/ber-fco` mit nur einem Preis: Grenzfall. Mit 10 Angeboten okay, mit 1 Angebot thin.

**5. Struktur-Daten-Restrisiko (niedrig–mittel).**  
`availability`, `priceValidUntil` und die Währungsmischung sind im Nachlauf behoben. Verbleibend: der Preis-Mismatch auf Detailseiten (`all_in` vs. sichtbarer Hauptpreis), `Product` für eine Strecke statt eines konkreten Produkts und `FAQPage` ohne Rich-Result-Wirkung. Kein Ranking-Faktor, aber ein Genauigkeits- und Wartungsthema.

**6. Vertrauens-/E-E-A-T-Lücke (mittel).**  
Kein Impressum, keine Datenschutzerklärung, kein „Über uns“, kein Kontakt, kein `Organization.contactPoint`. Für eine Seite, die Reisen vermittelt und Affiliate-Provisionen nennt, ist das dünn. Google bewertet bei kommerziellen/YMYL-Themen Betreibertransparenz; unabhängig davon ist es in Deutschland rechtlich relevant.

---

## 4. Priorisierte Maßnahmen

### 4.1 Schnell umsetzbar (S/M)

| # | Maßnahme | Prio | Aufwand | Erwartete Wirkung |
|---|---|---|---|---|
| S1 | **Canonical/Sitemap aus `SITE_URL`-Env statt `request.base_url`** (`_base()`): erledigt. **Rest:** `SITE_URL` in Produktion setzen und in der Start-Doku erwähnen. | hoch | S | Verhindert falsche Canonicals/Sitemaps hinter Proxy; Voraussetzung für belastbare Indexierung |
| S2 | **Duplicate-Cluster entschärfen:** Kategorieseite zeigt nur 3 Angebote + Link „alle Preise für BER–FCO“, Routenseite die volle Tabelle. Oder Routenseiten `noindex` bis ausreichend Unique-Content. **Teilweise umgesetzt (3 Angebote), Ähnlichkeit bleibt 0,825** – der gemeinsame Textkörper (Intro/Formular/FAQ) muss zusätzlich differieren. | hoch | S–M | Beseitigt die 0,85-Ähnlichkeit; klarere Canonical-Hierarchie |
| S3 | **Qualitätsgate für `routes_cache.save`:** weitgehend erledigt (≥ 5 Angebote, Längencheck, keine Hotel-Routen, Stale-Ausschluss). **Rest:** `origin == destination` verbieten, echte IATA-Prüfung, Sitemap nur für freigegebene Routen. | hoch | S | Verhindert Doorway-/Scaled-Content-Wachstum, hält Sitemap sauber |
| S4 | **JSON-LD bereinigen:** `availability`/`priceValidUntil` und Währungsmischung sind erledigt. **Verbleibend:** auf der Detailseite `price` = sichtbarer Hauptpreis (`all_in` nicht bevorzugen), toten `valid_until`-Code entfernen. | hoch | S | Guideline-Konformität, kein Mismatch-Risiko |
| S5 | **`SearchAction` entfernen** – erledigt. Verbleibend: `FAQPage` bewusst behalten oder entfernen (kein Rich Result, nur Wartung). | mittel | S | Keine falsche Erwartung, weniger toter Code |
| S6 | **`/docs`, `/redoc`, `/openapi.json` deaktivieren** (`docs_url=None`, `redoc_url=None`, `openapi_url=None`) oder in `robots.txt` sperren + `X-Robots-Tag`. **Erledigt im Nachlauf (404).** | mittel | S | Weniger wertlose Duplicates |
| S7 | **Routen-Title/Description verbessern:** weitgehend erledigt (Kategorie, Ortsnamen, „(fluege)“ weg). **Rest:** 61-Zeichen-Title wird zu „… Preise vergleiche“ abgeschnitten; englische Ortsnamen; Description nennt „Stopps“ für alle Kategorien. | mittel | S | CTR/Relevanz auf Long-Tail |
| S8 | **`og:image` + echtes Favicon**: Favicon ist erledigt (`/static/favicon.svg`); **`og:image`/`twitter:image` fehlen weiterhin**. | mittel | S | Social-Previews |
| S9 | **Reload-Loop fixen** (`tick()` in `app.js`): erledigt im Nachlauf (`finished`-Flag, kein Reload). | mittel | S | UX, Serverlast |
| S10 | **`/alarms` auf `private, no-store`** statt public 60 s – erledigt. | niedrig | S | Kein versehentliches Caching privater Daten |
| S11 | **Sichtbare Brotkrumen auf Routenseiten** um die Route ergänzen (`landing.html:3-5`), passend zum `breadcrumb()`-Aufruf in `_route_view`. | niedrig | S | Konsistenz Markup/UI |
| S12 | **Affiliate-Links auf Landing-Seiten** von `rel="nofollow noopener"` auf `rel="sponsored noopener"` – erledigt. | niedrig | S | Policy-Präzision |
| S13 | **`X-Robots-Tag: noindex`** für `/api/*` und `/health` als zweite Ebene – erledigt. | niedrig | S | Defense-in-depth |
| S14 | **Statische Assets versionieren**: erledigt (`?v=<mtime>`); verbleibend: `Cache-Control` auf `immutable` + 1 Jahr erhöhen. | mittel | S | Kein veraltetes CSS nach Deploys |

### 4.2 Aufwendig (M/L)

| # | Maßnahme | Prio | Aufwand | Erwartete Wirkung |
|---|---|---|---|---|
| L1 | **Unique Content pro Route:** Streckenbeschreibung, typische Airlines, Flugdauer, Saisonalität, Preisverlauf der letzten Tage, FAQ spezifisch. | hoch | L | Löst Duplicate **und** Doorway-Problem an der Wurzel; Voraussetzung für Indexierung vieler Routen |
| L2 | **Impressum, Datenschutz, „Über uns“, Kontakt** + `Organization.contactPoint`/`sameAs`. | hoch | M | Trust/E-E-A-T, Rechtskonformität |
| L3 | **Echte Preisdaten für Hotels/Fähren/Kreuzfahrten** in den Cache bringen (Seed-Läufe) oder diese Kategorien bis dahin `noindex` setzen. | mittel–hoch | M | Beseitigt Preisversprechen ohne Preis; stärkere Kategorieseiten |
| L4 | **Interne Verlinkung ausbauen:** Routenseite → verwandte Routen (begrenzt), Kategorie → Top-Routen (kuratiert statt „alle“), Detailseite → Route. | mittel | M | Crawl-Tiefe, Relevanzsignale, weniger Leaf-Nodes |
| L5 | **Struktur-Daten-Strategie neu:** `ItemList` statt `Product` für Vergleichsseiten; `Product`/`Offer` nur, wo ein konkretes Produkt vorliegt; `WebPage`/`isPartOf` ergänzen. | mittel | M | Semantisch korrekt, weniger Manual-Action-Risiko |
| L6 | **Brotli/HTTP2/CDN** vor die App (Nginx/Caddy) und HTML-Caching dort. | niedrig | M | Wenige KB, eher Betriebsstandard |
| L7 | **Eigene 404-Seite als Template** statt JSON/Plain-Text, mit Navigation und Status 404. | niedrig | S–M | UX, keine Soft-404-Verwirrung |
| L8 | **Preisverlaufs-Seiten** („BER–FCO im Oktober“) aus dem Watcher-Verlauf, nur bei echter Datenlage. | mittel | L | Einzigartiger Content, Long-Tail; **nur wenn Daten vorhanden** |

### 4.3 Reihenfolge (Empfehlung)

1. **S1, S3, S2** – zuerst die strukturellen Duplicate-/Canonical-Probleme, sonst optimiert man Metas auf Seiten, die Google nicht indexiert.
2. **S4-Rest, S5-Rest, S7, S8, S10–S13** – Struktur-Daten, Metas und Sichtbarkeit (S6/S9/S14 sind erledigt).
3. **S2-Rest, L1** – Duplicate an der Wurzel lösen; das ist der Hebel mit der größten Wirkung.
4. **L1, L2, L3** – Content und Trust; danach lohnt sich Sitemap-Wachstum überhaupt.
5. **L4, L5, L8** – Ausbau.

---

## 5. Was ich nicht belegt habe / offene Punkte

- **Produktionswerte** (TTFB, LCP, CLS, echte Crawl-Statistik, Indexierungsquote) lagen nicht vor. Alle Größen sind lokal gemessen.
- **„9 Quellen“ / „über 20 Quellen“** in Titles und Text: nicht gegen die Provider-Registry geprüft.
- **FAQ-Rich-Result-Abschaltung (07.05.2026)** und **Sitelinks-Searchbox-Abschaltung (2024)**: aus dem Projekt-Dokument `seo/agents/google_richtlinien.md` übernommen, nicht unabhängig gegen Google Search Central verifiziert.
- **Duplicate-Folgen** (welche URL Google verwirft) sind nicht vorhersagbar; die Ähnlichkeit ist gemessen, die Indexierungsentscheidung nicht.
- **Doorway-/Scaled-Content-Bewertung** ist eine Risiko-Einschätzung anhand der Muster, keine festgestellte Maßnahme.
- **`/jobs/{id}`-Reload-Loop**: war im Code eindeutig, ist im Nachlauf behoben; nicht im Browser nachgestellt.
- **`/hotels/rome-rome`**: als Zustand beobachtet; Ursache war die Hotel-Routenbildung in `ui/service.py:285-290` (Stadt als Origin/Destination). Inzwischen per `if cat == "hotels": continue` behoben und die Datei entfernt.
- **GitHub-Stichprobe** ist klein (0–35 ★); die Muster sind konsistent, aber nicht repräsentativ für große Produktionen.

---

## 6. Quellen (Code-Belege)

**GitHub (alle Links zuletzt geprüft 22.10.2026):**

- ForeverHYX/Homepage – `app/routers/pages.py:366-406` (robots/sitemap + Cache), `:165-171` und `:560-580` (`X-Robots-Tag`), `:460-495` (Canonical/`noindex` für Filter), `app/templates/pages/daily.html:4-9`, `tests/test_seo_routes.py:17-41`. <https://github.com/ForeverHYX/Homepage>
- IceWizard98/wiki-ai – `app/web/routes.py:134-139` (Sitemap-`FileResponse`), `:142-169` (robots), `app/web/templates/layout.html:6-26` (Meta/Canonical), `:52-77` (JSON-LD), `app/adapters/sitemap/xml_sitemap_writer.py:28-55` (atomar schreiben). <https://github.com/IceWizard98/wiki-ai>
- mugendi/moosey-cms – `src/moosey_cms/seo.py:13-24`, `:94-128`, `:137-160`; `src/moosey_cms/site.py:281-316`, `:442-454`. <https://github.com/mugendi/moosey-cms>
- davestroud/ishtar_ai_app – `app/routes/seo.py:40-124`, `app/templates/base.html:8-42`, `:73-99`, `app/middleware.py:44-49`. <https://github.com/davestroud/ishtar_ai_app>
- earonesty/fastapi-sitemap – `fastapi_sitemap/sitemap.py:93-113`, `:141-158`. <https://github.com/earonesty/fastapi-sitemap> (PyPI-Homepage `github.com/q32/fastapi-sitemap` → 404)
- pydanny/fastapi-blog – **archiviert**. <https://github.com/pydanny/fastapi-blog>
- fastapi/full-stack-fastapi-template – Gegenprobe: 305 Dateien, keine `sitemap`/`robots`/`seo`-Dateien. <https://github.com/fastapi/full-stack-fastapi-template>

**Lokaler Code (Anker; Zeilennummern haben sich im Nachlauf verschoben):**

- `ui/app.py` – `app.add_middleware(GZipMiddleware)`, `seo_headers`-Middleware, `_base()`, `_render()`, `search_form()`, `_landing()`, `overview_page()`, `sitemap_xml()`, `robots_txt()`, `job_page()`, `detail_page()`, `alarms_page()`, `alarm_page()`.
- `seo/meta.py` – `build()`, `for_job()`, `for_landing()`, `for_route()`.
- `seo/jsonld.py` – `website()` (ohne SearchAction), `organization()`, `breadcrumb()`, `faq()`, `offer_list()`, `aggregate_offer()`, `to_script_tag()`.
- `seo/sitemap.py` – `build()`, `robots()`, `write_static()`.
- `seo/pages.py` – `CATEGORIES`, `STATIC_PATHS`, `NOINDEX_PREFIXES`.
- `seo/routes_cache.py` – `save()`, `load()`, `list_routes()`, `all_routes()`, `age_hours()`.
- `ui/templates/base.html` – Head (Z. 1–26), Navigation/Footer (Z. 31–51).
- `ui/templates/landing.html` – Brotkrumen (3–5), H1 (7), Preise (12–33), Formular (37–62), Strecken (65–75), FAQ (78–84).
- `ui/templates/results.html` – H1 (4), Live-Box (34–36), Tabellen-Platzhalter (76–81).
- `ui/static/app.js` – Tabellen (40–59), Polling/Abschluss (62–74).
- `seo/validate.py` – projektinterner Prüfer: 78/78 OK (22:45, `:8100`), 87/87 OK (Nachlauf, `:8102`).
