# SEO: Recherche, Bewertung, Entscheidung

Stand: 22.10.2026 · Grundlage: Google Search Central, schema.org, CrUX/web.dev, GitHub-Projekte.
Detailrecherche mit 127 Quellenlinks: `seo/agents/google_richtlinien.md` (Agent 1) und
`seo/agents/fastapi_muster_audit.md` (Agent 2, Audit der bestehenden UI).

---

## 1. Recherche-Ergebnisse (die Punkte, die unsere Architektur betreffen)

### 1.1 Indexierung von Suchergebnisseiten – der wichtigste Befund

Unsere Ergebnisseiten haben die Form `/jobs/<id>`. Das sind laut Google **interne
Suchergebnisseiten**; sie sollen **nicht** indexiert werden (Duplicate/Thin Content, endlose
Parameter-URLs). Der belegte Weg ist `noindex, follow` im HTML – **nicht** `robots.txt`.

> **Widerspruch, den wir zuerst falsch hatten:** `Disallow` **und** `noindex` gleichzeitig.
> Ist eine URL per `robots.txt` gesperrt, kann Google das `noindex` im HTML nicht lesen; die URL
> kann trotzdem als „URL-only"-Eintrag im Index landen – genau das Gegenteil des Ziels.
> Quelle: Google Search Central, „Block indexing" und „Robots meta tag – Combining".
> **Konsequenz:** `/jobs/` ist aus der robots.txt entfernt, die Seiten tragen `noindex`.
> `Disallow: /static/` ist ebenfalls entfernt – Google braucht CSS/JS zum Rendern.

### 1.2 Strukturierte Daten – was wirklich noch etwas bringt

| Typ | Status bei Google | Unsere Entscheidung |
|---|---|---|
| `FAQPage` | **seit 07.05.2026 kein Rich Result mehr** | bleibt als valides Markup (echte FAQ-Inhalte), aber **nicht** als Ranking-Hoffnung verkauft |
| `WebSite` + `SearchAction` | Sitelinks-Searchbox **seit 21.11.2024 entfernt** | bleibt (harmlos), kein erwarteter Effekt |
| `Product` + `Offer` | Rich Result **nur für Ein-Produkt-Seiten**, nicht für Kategorielisten | nur auf Seiten mit **einem** konkreten Angebot (Detailseite) bzw. auf Routenseiten mit sichtbaren Preisen |
| `AggregateOffer` | zulässig als Preisspanne, **Preis muss auf der Seite stehen** | auf Routenseiten aus genau den sichtbaren Angeboten gebaut |
| `ItemList` | Carousel nur für Course/Movie/Recipe/Restaurant – **nicht für Reisen** | rein semantisch, kein Rich-Result-Anspruch |
| `BreadcrumbList`, `Organization` | unterstützt, kein Ranking-Hebel | umgesetzt |
| `AggregateRating` | **ohne echte Nutzerbewertungen = Manual-Action-Grund** | **bewusst NICHT umgesetzt** – wir haben keine Bewertungsquelle |

**Für Flüge/Hotels in der EEA** gibt es bei Google ein eigenes, anderes Programm („Aggregator
Unit" für Vertical Search Services mit Live-API) – **nicht** Schema.org. Das ist ein
Zulassungsverfahren, kein Markup; deshalb in Abschnitt 5 als „nicht umgesetzt" vermerkt.

### 1.3 Core Web Vitals

Schwellen (75. Perzentil, mobil/desktop getrennt): **LCP ≤ 2,5 s**, **INP ≤ 200 ms**, **CLS ≤ 0,1**.
Unsere Seiten sind serverseitig gerendert, textlastig, ohne Bilder und mit ~3 KB JS – INP und CLS
sind praktisch unkritisch, der Hebel ist **TTFB** und kritisches CSS. Wichtig: `noindex`-Seiten
sind aus CrUX ausgeschlossen; fehlende Felddaten sind kein Fehler.

### 1.4 Weitere belegte Punkte

* **Sitemap:** nur kanonische, indexierbare URLs mit HTTP 200; `<lastmod>` nur wenn bekannt;
  `changefreq`/`priority` werden von Google ignoriert (deshalb entfernt).
* **Leere Ergebnisse → 404**, nicht 200 (sonst „Soft-404"). Umgesetzt für unbekannte Läufe.
* **Affiliate-Links** gehören auf `rel="sponsored"` (bereits umgesetzt) – kein Ranking-Nachteil.
* **Title/Description:** Google nennt **keine** harten Zeichenlimits (Kürzung ist pixelbasiert);
  60/~155 Zeichen sind Orientierung, kein Gesetz. Unsere Tests prüfen nur grobe Grenzen.

---

## 2. Bewertung: Maßnahmen nach Aufwand und Wirkung

| # | Maßnahme | Aufwand | Wirkung | Umgesetzt |
|---|---|---|---|---|
| 1 | Dauerhafte Kategorieseiten (`/fluege`, `/hotels`, `/faehren`, `/kreuzfahrten`) mit eigenem Inhalt | M | **hoch** – erst dadurch gibt es indexierbare Seiten | ✅ |
| 2 | Routenseiten (`/fluege/ber-fco`) aus zwischengespeicherten, echten Preisen | M | **hoch** – langlebige URLs mit echtem Preisbezug | ✅ |
| 3 | `noindex` für `/jobs/<id>`, `/alarms`; robots.txt bereinigt (kein Disallow für Jobs, `/static/` erlaubt) | S | **hoch** – verhindert Indexmüll und widersprüchliche Signale | ✅ |
| 4 | Dynamische Meta-Tags (Title/Description/Canonical/OG/Twitter) je Seite | S | mittel – Snippet-Qualität, keine Duplikate | ✅ |
| 5 | Dynamische `sitemap.xml` (nur 200 + indexierbar + kanonisch, Routen ≤ 7 Tage) | S | mittel – Crawl-Effizienz | ✅ |
| 6 | `robots.txt` mit Sitemap-Verweis, API/Admin gesperrt | S | mittel | ✅ |
| 7 | JSON-LD: Breadcrumb, Organization, ItemList/Offer/AggregateOffer (nur sichtbare Preise) | M | mittel – Rich-Result-Chance auf Routenseiten | ✅ |
| 8 | Interne Verlinkung (Kategorien im Header/Footer, Breadcrumbs, „beliebte Strecken") | S | mittel – Crawlability | ✅ |
| 9 | GZip, Cache-Header, keine externen Ressourcen, Sprungmarke, semantische H1 | S | mittel (CWV/TTFB, LCP) | ✅ |
| 10 | `AggregateRating`/`Review` | – | – | ❌ **bewusst nicht** (keine echten Bewertungen) |
| 11 | Google Aggregator Unit (EEA-Flüge) | L | hoch, aber Zulassungsverfahren | ❌ offen (Voraussetzung: VSS-Zulassung) |
| 12 | Mehrsprachigkeit/`hreflang` | L | – | ❌ nicht relevant (deutsch) |
| 13 | Blog/Ratgeber-Inhalte für Long-Tail | L | hoch | ❌ offen (Redaktion, nicht Technik) |

**Reihenfolge der Umsetzung** (war die Entscheidung): zuerst die **strukturelle Basis**
(1–3, 5, 6) – ohne indexierbare Seiten und ohne saubere Indexierungs-Signale hilft kein
Markup. Danach Meta (4), dann JSON-LD (7), dann Feinschliff (8, 9). Der Grund: Markup auf
einer `noindex`-Seite bringt nichts, und eine Sitemap mit gesperrten URLs ist schädlich.

---

## 3. Was gebaut wurde

```
seo/
  pages.py          Register der indexierbaren Seiten (Klartext, FAQ, Presets)
  meta.py           Title/Description/Canonical/OG/Twitter/Robots je Seite
  jsonld.py         WebSite, Organization, Breadcrumb, FAQ, ItemList/Offer/AggregateOffer
                    + validate() für die Pflichtfelder
  routes_cache.py   letzte echte Angebote je Route (nur mit Preis, mit Zeitstempel)
  sitemap.py        sitemap.xml + robots.txt (dynamisch, mit Altersgrenze für Routen)
  validate.py       Prüfwerkzeug: Meta, JSON-LD, Sitemap, robots, Crawl-Simulation, gzip
  tests/test_seo.py 59 Unit-/HTTP-Tests
```

**UI-Änderungen:** neue Seiten `/preisvergleich`, `/fluege`, `/hotels`, `/faehren`,
`/kreuzfahrten` und `/<kategorie>/<route>`; `/sitemap.xml`, `/robots.txt`; Meta und JSON-LD in
jedem Template; GZip-Middleware; Cache-Header; 404 für unbekannte Läufe.

**Datenfluss:** Nach jedem erfolgreichen Suchlauf legt `ui/service.py` die zehn besten Angebote
unter `ui/state/routes/<kategorie>/<START-ZIEL>.json` ab (nur was die Quellen geliefert haben).
Die Routenseite rendert daraus die Tabelle **und** das JSON-LD – Preis im Markup = Preis im HTML.

**Bewusste Grenzen (ehrlich):**
* Preise auf Routenseiten sind ein **Preisstand** mit Zeitstempel; älter als 24 h → sichtbarer
  Hinweis, älter als 7 Tage → `noindex` und raus aus der Sitemap.
* Es gibt **keine** Garantie auf ein Produkt-Snippet für Flüge – Google hat dafür kein
  Rich-Result-Format; das Markup ist korrekt, der Effekt nicht garantiert.
* `AggregateRating` fehlt absichtlich.

---

## 4. Tests

```bash
python3 seo/validate.py --base http://127.0.0.1:8077   # 78 Prüfungen gegen den laufenden Server
python3 seo/tests/test_seo.py                          # 59 Tests (ohne Server, mit TestClient)
```

Der Validator simuliert einen Crawl: er liest robots.txt, lädt die Sitemap, ruft **jede** dort
genannte URL ab und prüft HTTP-Status, `noindex`/Canonical, Title/Description-Längen, genau eine
H1, Kopf-Tags, externe Ressourcen und die JSON-LD-Pflichtfelder. Zusätzlich: `noindex` auf
Lauf-/Alarmseiten, 404 bei unbekannten Läufen, GZip, Cache-Header.

**Ergebnis:** 78/78 und 59/59 bestanden. Ein Rich-Results-Test von Google ist ohne öffentliche
Domain nicht aufrufbar (er verlangt eine erreichbare URL) – die Validierung erfolgt deshalb
gegen die dokumentierten Pflichtfelder (in `jsonld.validate()`).

---

## 4a. Audit-Befunde (Agent 2) und was daraus wurde

Der zweite Agent hat die gebaute Oberfläche geprüft; sieben Befunde waren berechtigt und sind
umgesetzt:

| Befund | Umsetzung |
|---|---|
| **Duplicate-Cluster:** `/fluege` und `/fluege/ber-fco` waren zu 85 % textgleich (Jaccard 0,852) | Kategorieseite zeigt nur **3** Angebote + Link auf die Routenseite; dort steht die volle Tabelle |
| **Canonical/Sitemap am Host-Header** (Proxy-Fehlerquelle) | `SITE_URL`-Umgebungsvariable hat Vorrang vor `request.base_url`; Fallback nur für Dev |
| **Routen ohne Qualitätsfilter** (Doorway-Risiko) | Speichern nur bei **≥ 5 Angeboten** mit Preis und plausiblen Ortsangaben; Sitemap nimmt nur Routen ≤ 7 Tage |
| **Erfundene JSON-LD-Felder** (`availability`, `priceValidUntil`) | entfernt – beides steht in keiner Quelle; `AggregateOffer` aggregiert nur noch **eine** Währung |
| **`SearchAction`** (seit 11/2024 wirkungslos) | entfernt |
| **`/docs`, `/redoc`, `/openapi.json` offen** | deaktiviert (`docs_url=None`) |
| **Reload-Loop auf fertigen Ergebnisseiten** (`app.js`, `window.location.reload()`) | Ergebnisse werden **serverseitig** gerendert; das JS pollt nur bis „done" und hört dann auf |

Zusätzlich umgesetzt: `/alarms` mit `Cache-Control: private, no-store`, `X-Robots-Tag: noindex` für
`/api/*` und `/health`, Asset-Versionierung (`?v=<mtime>`), Favicon als Datei, Affiliate-Links auf
Landingpages mit `rel="sponsored"`.

**Nachlauf (zweiter Audit-Durchgang):** drei weitere Punkte waren berechtigt und sind umgesetzt:

| Befund | Umsetzung |
|---|---|
| Duplicate-Cluster auch nach der 3-Angebote-Regel noch **Jaccard 0,825** | Kategorieseite ist jetzt ein **Hub** (Formular + Streckenliste, **keine** Preistabelle); Preise stehen nur auf der Routenseite |
| Routenseiten ohne eigenen Inhalt | **Aus den Daten berechnete Fakten** je Strecke: Anzahl Angebote, Preisspanne/Median, Nonstop-Anteil, häufigste Anbieter, wie viele Angebote einen Endpreis ausweisen |
| Title wurde mitten im Wort abgeschnitten („… Preise **vergleiche**") | kurze Ortsnamen („Berlin Brandenburg" → „Berlin") + Kürzung **an Wortgrenzen** |
| kein `og:image` | 1200×630-Karte mit Chrome erzeugt (`ui/static/og.png`), als `og:image`/`twitter:image` eingebunden |
| Impressum/Datenschutz fehlten (404) | Routen + Template + `ui/legal.yaml`; **ohne** eingetragene Betreiberdaten `noindex` und mit klarem Hinweis – erfundene Angaben wären rechtswidrig |

**Nicht umgesetzt (bewusst):** Seed-Läufe für Hotels/Fähren/Kreuzfahrten (Kosten/Quota – die
Kategorieseiten erklären ehrlich, dass Preise erst nach einer Suche erscheinen), `/jobs`-Detailseiten
als indexierbare Produktseiten (bleiben `noindex`), redaktionelle Tiefe pro Route (L1, offen).

## 5. Offene Punkte

1. **Öffentliche Domain + HTTPS** eintragen, dann `sitemap.xml` in der Google Search Console
   anmelden. Aktuell läuft alles auf `127.0.0.1` – kanonische URLs, Sitemap und robots.txt
   übernehmen automatisch die Basis-URL der Anfrage, sind also nach dem Deployment korrekt.
2. **Redaktioneller Inhalt** (Ratgeber, Preisverläufe) – der stärkste organische Hebel, aber
   kein Technik-Thema.
3. **Google Aggregator Unit** prüfen (nur mit VSS-Zulassung und Live-API).
4. **Echte Bewertungen** einführen (z. B. aus erfassten Buchungen) – erst dann ist
   `AggregateRating` zulässig.
5. **Sitemap-Index** erst ab > 50 000 URLs nötig.
