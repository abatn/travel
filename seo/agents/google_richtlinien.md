# Technisches SEO & strukturierte Daten für einen Reise-Preisvergleich

**Recherche-Stand:** 22.10.2026
**Scope:** FastAPI, serverseitig gerendert, ~10 statische Kategorieseiten + viele kurzlebige Ergebnis-URLs (`/jobs/<id>`)
**Methode:** Primärquellen (Google Search Central, schema.org, web.dev, Chrome/CrUX, Gesetzestexte), ergänzt um Sekundärdaten (HTTP Archive Web Almanac, Ahrefs, Search Engine Land). Jede Aussage ist mit URL belegt; Schätzungen und nicht belegte Punkte sind als solche markiert.

---

## 0. Kernbefunde (TL;DR)

1. **`robots.txt` und `noindex` dürfen nicht kombiniert werden, wenn `noindex` wirken soll.** Ist eine URL per `Disallow` gesperrt, kann Google das `noindex` nicht lesen – die URL kann trotzdem (ohne Inhalt) im Index landen. Google dokumentiert das explizit. ([block-indexing](https://developers.google.com/search/docs/crawling-indexing/block-indexing), [robots-meta-tag](https://developers.google.com/search/docs/crawling-indexing/robots-meta-tag#combining))
2. **Ergebnisseiten mit Lauf-ID sind laut Google "interne Suchergebnisseiten"** und sollten nicht indexiert werden – außer man wählt eine kleine, kuratierte Menge mit echtem Eigenwert aus. ([Community-Guide auf Search-Central](https://support.google.com/webmasters/community-guide/297497016/what-to-do-about-internal-site-search-spam?hl=en), [Mueller via SERoundtable](https://www.seroundtable.com/google-index-search-results-35232.html))
3. **`FAQPage` bringt seit 7. Mai 2026 kein Rich Result mehr** – für *alle* Seiten. `HowTo` ist seit Sept. 2023 tot, die Sitelinks-Searchbox (`WebSite` + `SearchAction`) seit 21. Nov. 2024. ([Changelog](https://developers.google.com/search/updates), [FAQ/HowTo-Blogpost](https://developers.google.com/search/blog/2023/08/howto-faq-changes), [Sitelinks-Box](https://developers.google.com/search/blog/2024/10/sitelinks-search-box))
4. **`Product`-Rich-Results sind ausdrücklich nur für Seiten mit *einem* Produkt** gedacht, nicht für Listen- oder Kategorieseiten. ([product-snippet](https://developers.google.com/search/docs/appearance/structured-data/product-snippet#technical-guidelines))
5. **`AggregateRating` ohne echte Nutzerbewertungen ist ein dokumentierter Manual-Action-Grund.** Ebenso: Bewertungen von *anderen* Websites aggregieren. ([sd-policies](https://developers.google.com/search/docs/appearance/structured-data/sd-policies#completeness), [review-snippet](https://developers.google.com/search/docs/appearance/structured-data/review-snippet#technical-guidelines))
6. **Ein Structured-Data-Manual-Action kostet nur die Rich-Result-Eligibility, nicht das Ranking.** Das eigentliche Ranking-Risiko liegt in den Spam-Policies (Thin Affiliation, Doorway, Scaled Content), nicht im Schema. ([sd-policies](https://developers.google.com/search/docs/appearance/structured-data/sd-policies))
7. **Core Web Vitals sind keine harten Gates:** Google sagt selbst, andere Page-Experience-Aspekte "don't directly help your website rank higher", und CWV werden nur als ein Signal unter vielen verwendet. ([page-experience FAQ](https://developers.google.com/search/docs/appearance/page-experience))
8. **Für Flüge/Hotels in der EU gibt es einen offiziellen, aber anderen Weg als JSON-LD:** die *Aggregator Unit* im EEA – Zulassung als Vertical Search Service + Live-API/Feed, nicht Schema.org. ([aggregator-unit](https://developers.google.com/search/docs/appearance/aggregator-unit))

---

## 1. Indexierung & Crawling

### 1.1 Was entscheidet, ob eine Seite indexiert wird

Google nennt drei technische Mindestvoraussetzungen – und stellt klar, dass sie Indexierung *ermöglichen*, nicht garantieren:

> "Googlebot isn't blocked. The page works, meaning that Google receives an HTTP 200 (success) status code. The page has indexable content. Just because a page meets these requirements doesn't mean that a page will be indexed; indexing isn't guaranteed."
> — [Search technical requirements](https://developers.google.com/search/docs/essentials/technical)

Darüber hinaus wirken:

| Faktor | Wirkung | Beleg |
|---|---|---|
| Interne Verlinkung | Google leitet relative Wichtigkeit aus Linktiefe und Linkanzahl ab; nicht verlinkte Seiten werden oft nicht gefunden | [Ecommerce-Struktur](https://developers.google.com/search/docs/specialty/ecommerce/help-google-understand-your-ecommerce-site-structure) |
| Canonical | Konsolidiert Signale; Google darf anders entscheiden ("hint, not a rule") | [Canonicalization](https://developers.google.com/search/docs/crawling-indexing/canonicalization) |
| Duplicate/Thin Content | Kann zu "Crawled – currently not indexed" führen; Google indexiert nicht jede gefundene URL | [Search Console Page Indexing](https://support.google.com/webmasters/answer/7440203?hl=en) |
| `noindex` | Entfernt die Seite aus den Ergebnissen – *nur wenn crawlbar* | [block-indexing](https://developers.google.com/search/docs/crawling-indexing/block-indexing) |
| Sitemap | Schwaches Canonical-Signal, beschleunigt Entdeckung, garantiert nichts | [consolidate-duplicate-urls](https://developers.google.com/search/docs/crawling-indexing/consolidate-duplicate-urls), [sitemaps](https://developers.google.com/search/docs/crawling-indexing/sitemaps/overview) |
| `robots.txt` | Verhindert Crawling, **nicht** Indexierung | [robots.txt intro](https://developers.google.com/search/docs/crawling-indexing/robots/intro) |

Wichtig für die Erwartungssteuerung: Google indexiert auch bei sauberer Technik nur einen Teil der URLs. Eine Auswertung von ~50 Search-Console-Konten kommt auf durchschnittlich **16,5 % indexierte URLs** – mit dem Hinweis, dass ein hoher "Not indexed"-Anteil normal ist und nicht per se ein Problem. Das ist eine **Stichprobe eines Beraters, keine Google-Statistik** ([matthewedgar.net](https://www.matthewedgar.net/google-search-console-page-indexing/)); die häufigsten Gründe dort: Redirect 26,6 %, "Alternate page with proper canonical" 22,6 %, noindex 17,3 %, "Crawled – currently not indexed" 16,4 %.

### 1.2 Facettensuche, Parameter-URLs und `/jobs/<id>`

**Was Google über Facetten-/Parameter-URLs sagt** ([Managing crawling of faceted navigation URLs](https://developers.google.com/search/docs/crawling-indexing/crawling-managing-faceted-navigation)):

- Facetten erzeugen "infinite URL spaces" → zwei konkrete Schäden: **Overcrawling** und **langsamere Discovery** neuer, nützlicher URLs.
- Zwei Strategien, explizit als Entscheidung formuliert:
  - *"If you don't need the faceted navigation URLs potentially indexed, prevent crawling of these URLs."* → `robots.txt`-Disallow, und nur die Einzelseiten + eine ungefilterte Übersichtsseite crawlbar lassen.
  - *"If you need the faceted navigation URLs to be potentially indexed"* → dann technische Regeln einhalten: `&` als Parametertrenner, stabile Filterreihenfolge, **404 bei leerer Filterkombination** (nicht auf eine generische Fehlerseite redirecten).
- `rel="canonical"` und `rel="nofollow"` werden als *schwächere* langfristige Signale eingeordnet ("generally less effective in the long term").

**Zusätzlich relevant:** Der Pagination-Leitfaden sagt explizit:

> "Avoid indexing URLs with filters or alternative sort orders … block unwanted URLs from being indexed with the noindex robots meta tag or discourage crawling of particular URL patterns with a robots.txt file."
> — [Pagination & incremental page loading](https://developers.google.com/search/docs/specialty/ecommerce/pagination-and-incremental-page-loading)

Das betrifft `?order=price`, `?sort=…`, `?page=…`-Varianten einer Preissortierung direkt.

**Sind `/jobs/<id>`-Seiten "Facetten"?** Technisch nein, in der Wirkung ja: sie erzeugen einen großen, kurzlebigen URL-Raum mit weitgehend identischem Template und dünnem Inhalt. Google behandelt solche Seiten als **interne Suchergebnisseiten**. John Mueller (Google) in einem Reddit-Statement, wiedergegeben von SERoundtable (Forum-Aussage, **keine** Dokumentation):

> "If you can't limit the indexable search results pages, I would strongly recommend noindexing or robotting *all* the search pages. It's still a regular occurrance that we see sites spam the search results with open search results pages."
> — [SERoundtable, 18.04.2023](https://www.seroundtable.com/google-index-search-results-35232.html)

Und in einem Community-Guide auf der Google-Search-Central-Plattform (kein Produktdokument, sondern ein von der Community gepflegter Beitrag – inhaltlich deckungsgleich mit der Doku):

> "Mark all result page(s) as 'noindex'. … Block in robots.txt – you can do this, particularly if crawl budget is concern. But its not usually a good plan. While blocks crawling, it does NOT block indexing."
> — [Search Central Community Guide](https://support.google.com/webmasters/community-guide/297497016/what-to-do-about-internal-site-search-spam?hl=en)

**Zwei Policy-Risiken, die über "wird halt nicht indexiert" hinausgehen:**

1. **Doorway Abuse** – ausdrücklich: *"Creating substantially similar pages that are closer to search results than a clearly defined, browseable hierarchy."* ([spam-policies](https://developers.google.com/search/docs/essentials/spam-policies#doorway-abuse))
2. **Scaled Content Abuse** – *"Scraping feeds, search results, or other content to generate many pages … where little value is provided to users."* ([spam-policies](https://developers.google.com/search/docs/essentials/spam-policies#scaled-content))

Beides ist primär auf Seiten gemünzt, die **rankingswirksam** sind. `noindex` entzieht einer Seite die Ranking-Funktion und damit die Hauptangriffsfläche – es macht die Muster aber nicht per se unbedenklich: Sobald dieselbe Massen-Generierung auf **indexierbare** Seiten angewendet wird (z. B. tausende generierte Routenseiten mit Template-Text), greifen die Policies direkt. `noindex` ist also die richtige Absicherung für `/jobs/<id>`, aber kein Ersatz für inhaltliche Eigenleistung auf den Seiten, die indexiert werden sollen.

**Empfehlung für `/jobs/<id>` (begründet, nicht dogmatisch):**

| Situation | Empfehlung |
|---|---|
| Standardfall (nutzerspezifische/kurzlebige Suche) | `noindex, follow` + **kein** `Disallow` in robots.txt. Links werden verfolgt, Seite fliegt aus dem Index. |
| Falls Crawl-Last das Problem ist | `Disallow: /jobs/` **statt** `noindex` – dann bewusst akzeptieren, dass einzelne URLs ohne Inhalt indexiert werden können ("Indexed, though blocked by robots.txt"). |
| Kuratierte Ausnahme | Einzelne, stabile Seiten mit echtem Eigenwert (z. B. Route mit Preisverlauf) als eigene, kanonische Landingpage bauen – nicht die ID-URL indexieren. |

Der letzte Punkt ist genau Muellers Formulierung: *"or to only allow a hand-selected set to be indexed (eg, known product-type queries, where the results are more like category pages)."*

**Zusätzlich:** Bei leerem Ergebnis **404** liefern (nicht 200 mit "keine Treffer"), bei dauerhaft abgelaufenen Suchen eher 404/410 als 200. Das ist in der Facetten-Doku explizit gefordert. Die Alternative `unavailable_after` im Robots-Meta existiert, ist aber ein Sonderfall ([robots-meta-tag](https://developers.google.com/search/docs/crawling-indexing/robots-meta-tag)).

### 1.3 `robots.txt` vs. `noindex` – der Unterschied, der wirklich zählt

| | `robots.txt` (`Disallow`) | `noindex` (Meta/Header) |
|---|---|---|
| Ebene | Crawling (Zugriff) | Indexierung (Aufnahme) |
| Wirkung | Googlebot holt die URL nicht | Googlebot holt sie, nimmt sie nicht in den Index |
| URL in SERPs? | **Kann erscheinen**, ohne Snippet ("No page information") | Nein, wird entfernt |
| Voraussetzung | – | Seite **muss crawlbar** sein |
| Gedacht für | Crawl-Budget, Serverlast, endlose Räume | Inhaltliche Steuerung |

Belege: [robots.txt intro](https://developers.google.com/search/docs/crawling-indexing/robots/intro) – *"it is not a mechanism for keeping a web page out of Google"*; [block-indexing](https://developers.google.com/search/docs/crawling-indexing/block-indexing); [Search-Console-Hilfe zu "No page information"](https://support.google.com/webmasters/answer/7489871?hl=en).

**Die Kombinationsfalle** (wichtigster technischer Punkt dieser Recherche):

> "If a page is disallowed from crawling through the robots.txt file, then any information about indexing or serving rules will not be found and will therefore be ignored."
> — [robots-meta-tag § Combining](https://developers.google.com/search/docs/crawling-indexing/robots-meta-tag#combining)

Und in den Canonical-Best-Practices: *"Don't use the robots.txt file for canonicalization purposes."* ([consolidate-duplicate-urls](https://developers.google.com/search/docs/crawling-indexing/consolidate-duplicate-urls#best-practices))

**Empfehlung:** Pro URL-Typ **genau eine** Methode wählen. `noindex` ist die richtige Wahl, wenn die URL wirklich aus dem Index soll. `robots.txt` nur, wenn Crawl-Budget das Problem ist und ein URL-only-Indexeintrag akzeptabel ist.

Zweite Falle: **`Disallow` auf CSS/JS.** Google sagt zu Resource-Dateien:

> "You can use a robots.txt file to block resource files … **if** you think that pages loaded without these resources won't be significantly affected by the loss. However, if the absence of these resources make the page harder for Google's crawler to understand the page, don't block them."
> — [robots.txt intro](https://developers.google.com/search/docs/crawling-indexing/robots/intro)

Ein pauschales `Disallow: /static/` kann also das Rendering und damit die Bewertung der Seite verschlechtern. Wenn statische Assets nicht als eigene Treffer erscheinen sollen, ist `X-Robots-Tag: noindex` auf Asset-Ebene der passendere Weg ([robots-meta-tag](https://developers.google.com/search/docs/crawling-indexing/robots-meta-tag#xrobotstag)).

### 1.4 Canonical

- Canonical ist ein **Hinweis**, keine Anweisung. Google wählt ggf. anders: *"indicating a canonical preference is a hint, not a rule."* ([canonicalization](https://developers.google.com/search/docs/crawling-indexing/canonicalization))
- Signalstärke: **Redirect > `rel="canonical"` > Sitemap-Eintrag** ([consolidate-duplicate-urls](https://developers.google.com/search/docs/crawling-indexing/consolidate-duplicate-urls)).
- Best Practices, relevant hier:
  - **Selbstreferenzieller Canonical** auf der kanonischen Seite selbst.
  - Keine widersprüchlichen Signale (Sitemap ≠ Canonical ≠ Redirect-Ziel).
  - Intern auf die kanonische URL verlinken, nicht auf Varianten.
  - **Kein `noindex` zur Canonical-Steuerung** ("we don't recommend using noindex to prevent selection of a canonical page within a single site").
- Bei Paginierung: **nicht** Seite 1 als Canonical aller Folgeseiten; jede Seite hat eigene kanonische URL ([pagination](https://developers.google.com/search/docs/specialty/ecommerce/pagination-and-incremental-page-loading)). `rel="next"/"prev"` nutzt Google **nicht mehr**.

### 1.5 Thin/Duplicate Content – was Google tatsächlich als Problem sieht

Doppelter Inhalt ist per se **keine** Policy-Verletzung: *"Some duplicate content on a site is normal and it's not a violation of Google's spam policies."* ([canonicalization](https://developers.google.com/search/docs/crawling-indexing/canonicalization))

Relevant wird es über zwei Wege:
1. **Qualität/Discovery**: identische Templates ohne Eigenwert → "Crawled – currently not indexed".
2. **Policies**: Doorway, Scaled Content, Thin Affiliation (siehe 1.2 und 6).

Der für Preisvergleich zentrale Satz steht in der Spam-Policy zu **Thin Affiliation**:

> "Good affiliate sites add value by offering meaningful content or features. Examples of good affiliate pages include offering additional information about price, original product reviews, rigorous testing and ratings, navigation of products or categories, and product comparisons."
> — [spam-policies § Thin Affiliation](https://developers.google.com/search/docs/essentials/spam-policies#thin-affiliation)

Ein Preisvergleich ist damit ausdrücklich **kein** Policy-Problem, solange er eigene Leistung zeigt (Preisverlauf, Quellenlage, Filter, eigene Tests) und nicht Merchant-Texte kopiert.

---

## 2. Sitemaps

### 2.1 Harte Anforderungen

| Anforderung | Wert/Regel | Beleg |
|---|---|---|
| Max. Größe | 50 MB (unkomprimiert) **oder** 50.000 URLs pro Datei | [build-sitemap](https://developers.google.com/search/docs/crawling-indexing/sitemaps/build-sitemap#sitemap-best-practices) |
| Mehr URLs | Aufteilen, optional Sitemap-Index | ebd. |
| Encoding | UTF-8 | ebd. |
| URLs | **Vollqualifiziert, absolut** ("Google will attempt to crawl your URLs exactly as listed") | ebd. |
| Inhalt | Nur URLs, die im Index erscheinen sollen – **kanonisch** | ebd. |
| Ort | Beliebig, aber ohne Search Console wirkt die Sitemap nur für Unterverzeichnisse → **Site-Root empfohlen** | ebd. |
| `<lastmod>` | Wird nur genutzt, wenn "consistently and verifiably accurate"; Zeitpunkt der **letzten inhaltlichen** Änderung, nicht Copyright-Datum | ebd. |
| `<priority>` / `<changefreq>` | **Von Google ignoriert** | ebd. |
| Reihenfolge | Irrelevant | ebd. |

**Nicht explizit in der Sitemap-Doku, aber logisch zwingend und in der Search-Console-Hilfe so beschrieben:** Sitemaps sollen keine Redirects, 404 oder `noindex`-URLs enthalten – "Page with redirect" und "Excluded by noindex" sind eigene Fehlerkategorien im Page-Indexing-Report ([Search Console Help](https://support.google.com/webmasters/answer/7440203?hl=en)). Google formuliert es positiver: *"Include the URLs in your sitemap that you want to see in Google's search results."*

### 2.2 Einbindung

Drei offiziell gleichwertige Wege ([build-sitemap § Submit](https://developers.google.com/search/docs/crawling-indexing/sitemaps/build-sitemap#submit)):

1. **Search Console → Sitemaps** (zeigt Abrufzeitpunkt und Verarbeitungsfehler).
2. **Search Console API** (programmatisch).
3. **`robots.txt`**: Zeile `Sitemap: https://example.com/sitemap.xml`, beliebig viele Zeilen erlaubt.

Sitemaps sind ein **Hinweis**: *"submitting a sitemap is merely a hint: it doesn't guarantee that Google will download the sitemap or use the sitemap for crawling URLs on the site."*

### 2.3 Für dieses Projekt relevant

- Bei ~10 Kategorieseiten + N Routenseiten ist eine Sitemap **nicht zwingend** – Google sagt, unter ~500 Seiten und bei guter interner Verlinkung ist sie entbehrlich ([sitemaps overview](https://developers.google.com/search/docs/crawling-indexing/sitemaps/overview)). Sie ist trotzdem sinnvoll als **Diagnoseinstrument** (Search Console zeigt Fehler pro URL).
- **Nur Seiten aufnehmen, die garantiert 200 + indexierbar sind.** Ein Sitemap-Eintrag für eine abgelaufene Route ist ein Signal für Vernachlässigung, kein Ranking-Killer – aber er verschwendet Crawl-Budget und erzeugt Fehlerreports.
- `<changefreq>`/`<priority>` kann man weglassen; sie ändern nichts.

---

## 3. Strukturierte Daten

### 3.1 Was Google 2026 für Reise-/Preisvergleichsseiten noch unterstützt

Grundlage: [Structured Data Gallery](https://developers.google.com/search/docs/appearance/structured-data/search-gallery). **In der Liste gibt es keinen Flug-, Ticket- oder Transport-Rich-Result-Typ.**

| Typ | Rich Result für Flüge/Preisvergleich? | Bewertung | Beleg |
|---|---|---|---|
| `Product` + `Offer` | Nur für **Ein-Produkt-Seiten**; "product rich results only support pages that focus on a single product" | Bedingt geeignet (z. B. eine konkrete Reise/ein Angebot), **nicht** für Listen | [product-snippet](https://developers.google.com/search/docs/appearance/structured-data/product-snippet#technical-guidelines) |
| `Product` + `AggregateOffer` | Ja, für Aggregator-Seiten mit einem Produkt und mehreren Händlern – Google hat ein eigenes Beispiel "Shopping aggregator page" | Passend für "eine Reise, viele Anbieter" | ebd. |
| `Merchant listing` | Nein für Vergleichsseiten – setzt voraus, dass **du** Verkäufer bist, inkl. `image`, Shipping/Return | Nicht anwendbar | [merchant-listing](https://developers.google.com/search/docs/appearance/structured-data/merchant-listing) |
| `AggregateRating` | Ja, aber nur mit echten Bewertungen | **Hochrisiko ohne echte Reviews** | [review-snippet](https://developers.google.com/search/docs/appearance/structured-data/review-snippet) |
| `Review` | Ja, aber inhaltliche Hürden (Autor, spezifischer Gegenstand) | Nur für redaktionelle Einzelbewertungen | ebd. |
| `ItemList` | **Kein** Carousel für Reisen – Carousel nur mit Course/Movie/Recipe/Restaurant | Semantisch sinnvoll, **kein** Rich Result | [carousel](https://developers.google.com/search/docs/appearance/structured-data/carousel) |
| `BreadcrumbList` | Ja, universell | Günstig, empfohlen | [breadcrumb](https://developers.google.com/search/docs/appearance/structured-data/breadcrumb) |
| `FAQPage` | **Nein** (seit 07.05.2026 komplett entfernt) | Nicht mehr investieren | [Changelog](https://developers.google.com/search/updates) |
| `WebSite` + `SearchAction` | **Nein** (Sitelinks-Searchbox seit 21.11.2024 entfernt) | Kein Effekt; `WebSite` bleibt für Site-Name relevant | [Blogpost](https://developers.google.com/search/blog/2024/10/sitelinks-search-box) |
| `Organization` | Kein klassisches Rich Result, beeinflusst Knowledge Panel / Logo / Site-Name | Sinnvoll als Vertrauenssignal | [organization](https://developers.google.com/search/docs/appearance/structured-data/organization) |
| `VacationRental` | Nur Early-Adopters-Programm mit Technical Account Manager | Praktisch nicht zugänglich | [vacation-rental](https://developers.google.com/search/docs/appearance/structured-data/vacation-rental) |

**Wichtige Konsequenz:** Für ein Flug-Preisvergleichsportal ist die *Aggregator Unit* das **einzige dokumentierte reise-spezifische SERP-Feature** in der EEA – und sie funktioniert nicht über Schema.org, sondern über Zulassung + Live-Daten. Daneben bleibt nur normales SEO (Inhalt, Links, Technik):

> "The aggregator unit is a multi-provider feature designed for Vertical Search Services (VSSs), including Online Travel Agencies (OTAs), Comparison Shopping Services, metasearch engines, and directories … available to users in the EEA for queries related to hotels, flights, long distance trains or buses, products, and local businesses."
> — [aggregator-unit](https://developers.google.com/search/docs/appearance/aggregator-unit)

Voraussetzungen: Zulassung als VSS, Qualitätsstandards, Daten per **Live-API** (Flüge) bzw. **Feed** (Hotels/POI). Das ist ein Business-/Integrationsprojekt (L), kein Markup-Task.

### 3.2 Pflichtfelder – die exakten Google-Anforderungen

#### `Product` (Product Snippet)

| Eigenschaft | Status | Anmerkung |
|---|---|---|
| `name` | **Pflicht** | – |
| `review` **oder** `aggregateRating` **oder** `offers` | **Pflicht** (mind. eines) | `offers` ohne Bewertung *kann* eine Warnung im Rich-Results-Test erzeugen |
| `image` | Nicht Pflicht beim Snippet | Pflicht erst beim **Merchant Listing**; empfohlen: mehrere, ≥ 50k Pixel, 16:9/4:3/1:1 |
| `brand`, `sku`, `gtin`, `description` | Optional | – |
| `offers.price` | **Pflicht**, wenn `offers` genutzt wird | Zahl oder String |
| `offers.priceCurrency` | **Empfohlen** beim Snippet, **Pflicht** beim Merchant Listing | ISO 4217, dreistellig |
| `offers.availability` | Empfohlen | z. B. `https://schema.org/InStock` |
| `offers.url` | **Nicht** in Googles Pflicht-/Empfehlungsliste; bei Merchant Listing ausdrücklich optional ("The URL can be omitted.") | Trotzdem Best Practice, da es in allen Google-Beispielen steht |
| `offers.priceValidUntil` | Empfohlen, *"if applicable"* | **Vergangenes Datum → Snippet kann ausbleiben** |

Quelle: [product-snippet § Structured data type definitions](https://developers.google.com/search/docs/appearance/structured-data/product-snippet#structured-data-type-definitions)

#### `AggregateOffer`

| Eigenschaft | Status |
|---|---|
| `lowPrice` | **Pflicht** |
| `priceCurrency` | **Pflicht** |
| `highPrice` | Empfohlen |
| `offerCount` | Empfohlen |

Und zwei harte Regeln:
- *"Don't use `AggregateOffer` to describe a set of product variants."* ([product-snippet](https://developers.google.com/search/docs/appearance/structured-data/product-snippet#aggregateoffer))
- Für die **Price-Drop**-Enhancement muss `Offer` (nicht `AggregateOffer`) verwendet werden.

Schema.org bestätigt die Semantik: *"When a single product is associated with multiple offers (for example, the same pair of shoes is offered by different merchants), then AggregateOffer can be used."* ([schema.org/AggregateOffer](https://schema.org/AggregateOffer))

#### `AggregateRating`

| Eigenschaft | Status |
|---|---|
| `ratingValue` | **Pflicht** |
| `ratingCount` **oder** `reviewCount` | **Pflicht** (mind. eines) |
| `itemReviewed` (bzw. `name` bei verschachtelter Nutzung) | **Pflicht** |
| `bestRating` / `worstRating` | Nur bei anderer Skala als 5 |

Quelle: [review-snippet § AggregateRating](https://developers.google.com/search/docs/appearance/structured-data/review-snippet#aggregaterating)

#### `Review`

| Eigenschaft | Status |
|---|---|
| `author` | **Pflicht** – "must be a valid name", **< 100 Zeichen**, sonst keine Eligibility |
| `reviewRating` | **Pflicht** |
| `itemReviewed` | **Pflicht**, außer der Review ist in ein Produkt verschachtelt |
| `reviewBody`, `datePublished` | Empfohlen |

Quelle: [review-snippet § Review](https://developers.google.com/search/docs/appearance/structured-data/review-snippet#review)

#### `BreadcrumbList`

`itemListElement` (Pflicht) → je `ListItem`: `position` (Pflicht, 1-basiert), `name` (Pflicht), `item` (Pflicht außer beim letzten Element). ([breadcrumb](https://developers.google.com/search/docs/appearance/structured-data/breadcrumb))

#### `Organization`

> "There are no required properties; instead, we recommend adding as many properties that are relevant to your organization."
> — [organization](https://developers.google.com/search/docs/appearance/structured-data/organization)

Sinnvoll: `name`, `url`, `logo`, `sameAs`. Wirkung: Knowledge Panel / Logo / Disambiguation – **kein** Rich Result im engeren Sinne.

### 3.3 Preisangaben – die Regeln, die wirklich gelten

1. **Der Preis muss auf der Seite sichtbar sein.** *"Don't mark up content that is not visible to readers of the page."* ([sd-policies § Content](https://developers.google.com/search/docs/appearance/structured-data/sd-policies#content)) Und: *"The structured data is not representative of the main content of the page, or is potentially misleading"* ist ein Ausschlussgrund.
2. **`priceValidUntil`** nur setzen, wenn es ein echtes Ablaufdatum gibt. Ein Datum in der Vergangenheit kann das Snippet verhindern ([product-snippet](https://developers.google.com/search/docs/appearance/structured-data/product-snippet#offer)).
3. **Mehrere Anbieter für dasselbe Objekt → `AggregateOffer`** mit `lowPrice` + `priceCurrency`; `highPrice`/`offerCount` ergänzen.
4. **Mehrere Währungen → getrennte URLs.** *"When offering products for sale in multiple currencies, have a distinct URL per currency."* ([product-snippet § Technical guidelines](https://developers.google.com/search/docs/appearance/structured-data/product-snippet#technical-guidelines)) – relevant, wenn USD-Quellen umgerechnet werden.
5. **`price` gewinnt gegen `priceSpecification.price`**, wenn beides gesetzt ist.
6. **Kein `AggregateOffer` für Varianten** (z. B. verschiedene Abflugtage als "Varianten" eines Produkts).

### 3.4 Bewertungen: das größte Risiko in diesem Setup

Google ist hier ungewöhnlich deutlich:

> "Don't aggregate reviews or ratings from other websites."
> "Don't include fake or undisclosed incentivized reviews on your page or in your structured data markup."
> "Provide review information about a specific item, not about a category or a list of items."
> "If you include multiple individual reviews, also include an aggregate rating of the individual reviews."
> — [review-snippet § Technical guidelines](https://developers.google.com/search/docs/appearance/structured-data/review-snippet#technical-guidelines)

Und in den allgemeinen Guidelines:

> "users prefer recipes with actual user reviews and genuine star ratings (**note that reviews or ratings not by actual users may result in manual action**)."
> — [sd-policies § Completeness](https://developers.google.com/search/docs/appearance/structured-data/sd-policies#completeness)

**Konkret für einen Reise-Preisvergleich ohne eigene Bewertungen:**
- `AggregateRating` aus OTA-/Airline-Sternen **aggregieren ist untersagt** ("Don't aggregate reviews or ratings from other websites").
- `AggregateRating` ohne Beleg auf der Seite ist zusätzlich ein Sichtbarkeitsproblem ("users should be able to see that aggregate rating on the page").
- **Korrekte Option:** gar kein Rating-Markup, oder echte, eigene Bewertungen (mit sichtbarem Text, Autor, Datum) – dann aber `Review` + `AggregateRating` konsistent.
- „Self-serving reviews" (Unternehmen bewertet sich selbst) sind ein separater Ausschlussgrund, hier nicht relevant, weil es um Produkte geht.

### 3.5 Was passiert bei fehlenden/falschen Angaben

Drei verschiedene Ebenen, oft vermischt:

| Fehlerart | Konsequenz | Beleg |
|---|---|---|
| Fehlende Pflichtfelder | **Kein Rich Result**, keine Strafe | [sd-policies § Completeness](https://developers.google.com/search/docs/appearance/structured-data/sd-policies#completeness) |
| Syntaxfehler | Wird im Rich-Results-Test / "Unparsable structured data"-Report gemeldet; Feature entfällt | ebd. |
| Qualitätsverstoß (fake reviews, unsichtbare Daten, Irrelevanz) | **Manual Action auf Structured Data** → Seite verliert Rich-Result-Eligibility | [sd-policies](https://developers.google.com/search/docs/appearance/structured-data/sd-policies) |
| Spam-Policy-Verstoß (Thin Affiliate, Doorway, Scaled Content) | **Ranking-/Sichtbarkeitsverlust**, unabhängig vom Schema | [spam-policies](https://developers.google.com/search/docs/essentials/spam-policies) |

Der entscheidende Satz zur Entdramatisierung:

> "A structured data manual action means that a page loses eligibility for appearance as a rich result; **it doesn't affect how the page ranks in Google web search**."
> — [sd-policies](https://developers.google.com/search/docs/appearance/structured-data/sd-policies)

Das heißt umgekehrt **nicht**, dass Schema-Missbrauch folgenlos ist: Erfundene Sterne können zusätzlich unter die Spam-Policies fallen (irreführende Inhalte) und sind in Deutschland auch wettbewerbsrechtlich angreifbar. Die Google-Doku trennt die Mechanismen sauber – die Rechtslage tut das nicht.

### 3.6 Empfehlung für die Typen (bezogen auf diese Seite)

| Seite | Markup | Begründung |
|---|---|---|
| Alle Seiten | `Organization` (Home), `BreadcrumbList` | Dokumentiert, verlustfrei, keine Übertreibung |
| Kategorieseiten (`/fluege`, `/hotels`, …) | `ItemList` (optional) + `BreadcrumbList` | `ItemList` erzeugt **kein** Carousel; nur semantischer Nutzen. `Product` hier **nicht** – Google will Ein-Produkt-Seiten |
| Stabile Routenseiten (`/fluege/berlin-barcelona`) | `Product` + `AggregateOffer` (**nur** wenn ein konkretes, buchbares Objekt mit echtem Preis verglichen wird) | Entspricht Googles "Shopping aggregator page"-Muster |
| `/jobs/<id>` | kein JSON-LD nötig (oder identisch, aber `noindex`) | Kein Rich Result auf noindex-Seiten; CrUX schließt sie ebenfalls aus |
| FAQ-Bereich | sichtbarer Text, **kein** `FAQPage` | Feature seit 07.05.2026 entfernt |
| Website-Suche | `WebSite` (ohne `SearchAction`) | Searchbox-Feature existiert nicht mehr |

**Wichtige Einschränkung, die ich nicht belegen kann:** Ob Google `Product`/`AggregateOffer` auf einer **Flugstrecken-Seite** tatsächlich als Produkt-Snippet behandelt, ist nicht dokumentiert. Die Doku spricht von "product", die Beispiele sind Waren. Die Markup-Form ist konform, der **Erfolg ist ungewiss** und sollte nicht als geplanter Effekt in eine Roadmap geschrieben werden. (Siehe § 8.)

---

## 4. Core Web Vitals

### 4.1 Schwellenwerte (aktuell, unverändert)

| Metrik | "Good" | "Needs improvement" | "Poor" | Beleg |
|---|---|---|---|---|
| **LCP** | ≤ 2,5 s | 2,5–4,0 s | > 4,0 s | [web.dev/vitals](https://web.dev/articles/vitals#core_web_vitals) |
| **INP** | ≤ 200 ms | 200–500 ms | > 500 ms | ebd. |
| **CLS** | ≤ 0,1 | 0,1–0,25 | > 0,25 | ebd. |

Bewertet wird das **75. Perzentil** der Seitenaufrufe, getrennt nach Mobile/Desktop; eine Seite besteht, wenn **alle drei** Werte im grünen Bereich liegen ([web.dev/vitals](https://web.dev/articles/vitals#core_web_vitals)). INP hat FID im März 2024 ersetzt ([web.dev](https://web.dev/articles/vitals)).

### 4.2 Messung – und die Fallstricke

| Tool | Datentyp | Wichtig |
|---|---|---|
| **CrUX** (Search Console, PSI, BigQuery) | Felddaten (echte Nutzer, 28-Tage-Fenster) | Nur Origins/Seiten, die **öffentlich indexierbar** und **"sufficiently popular"** sind |
| **Lighthouse** | Labordaten, simuliertes Mobile | Kann **INP nicht messen** (keine Interaktion); TBT ist der Proxy |
| **PageSpeed Insights** | beides | Felddaten nur, wenn die URL im CrUX-Datensatz ist |

Quellen: [CrUX methodology](https://developer.chrome.com/docs/crux/methodology), [web.dev/vitals](https://web.dev/articles/vitals).

**Zwei Konsequenzen, die oft übersehen werden:**

1. **`noindex`-Seiten sind aus CrUX ausgeschlossen.** CrUX verlangt "publicly discoverable" und listet `noindex` explizit als Ausschlusskriterium ([CrUX methodology](https://developer.chrome.com/docs/crux/methodology)). `/jobs/<id>` wird also nie Felddaten haben – CWV-Optimierung dort ist nur über Lighthouse messbar und ohnehin nachrangig.
2. **Neue/small Sites haben keine CrUX-Daten.** "Sufficiently popular" ist eine nicht veröffentlichte Mindestbesucherzahl. Fehlende Felddaten sind **kein** Fehler und **kein** Ranking-Signal.

### 4.3 Realistische Optimierung für eine textlastige SSR-Seite

Ohne Bilder/JS ist das Profil günstig: INP ist bei serverseitigem HTML mit wenig JS praktisch unkritisch, CLS entsteht fast nur durch nachgeladene Elemente.

| Hebel | Warum | Aufwand |
|---|---|---|
| **TTFB** (DB-/API-Cache, `Cache-Control`, gzip/brotli) | TTFB ist Teil des LCP-Kritikpfads; bei SSR der dominierende Faktor | S |
| **Render-blockierendes CSS reduzieren** (kritisches CSS inline, Rest defer) | Ohne Bilder ist das häufigster LCP-Bremser | M |
| **Fonts**: `font-display: swap`, `preload`, selbst hosten | Verhindert FOIT und spätes Text-Rendering | S |
| **Keine Layout-Shifts** durch Preise, die nach dem Load nachrutschen; feste Höhen für Preiszeilen/Badges | Direkt CLS | S |
| **Kein Lazy-Loading für above-the-fold Preise** | Preise sind der LCP-Kandidat | S |
| **Keine Ads/Consent-Banner, die den Content verschieben** | CLS + Intrusive-Interstitials-Policy | S–M |
| **Kein Client-JS für Preise** | Server-gerendert = schneller LCP **und** robuster für Indexierung | – |

Zur Einordnung: Felddaten zeigen, dass LCP mobiler der schwächste Wert ist. Im CrUX-Datensatz 12/2025 hatten 67,6 % der Origins gutes LCP, 80,3 % gutes CLS, 85,6 % gutes INP, **54,4 % alle drei** ([CrUX Release Notes 12/2025](https://developer.chrome.com/docs/crux/release-notes)). Der Web Almanac 2025 (Sample, Juli 2025) nennt 48 % Mobile / 56 % Desktop "good CWV" ([Web Almanac 2025 – Performance](https://almanac.httparchive.org/en/2025/performance)). Beide Zahlen sind **Populationsschätzungen**, keine Benchmarks für eine einzelne Seite.

**Und die Einordnung von Google selbst:**

> "Beyond Core Web Vitals, other page experience aspects don't directly help your website rank higher in search results."
> "trying to get a perfect score just for SEO reasons may not be the best use of your time."
> — [page-experience FAQ](https://developers.google.com/search/docs/appearance/page-experience)

---

## 5. Mobile-First & Grundlagen

### 5.1 Mobile-First Indexing

Google indexiert die **mobile** Version als Basis. Daraus folgen harte Anforderungen ([mobile-first indexing](https://developers.google.com/search/docs/crawling-indexing/mobile/mobile-sites-mobile-first-indexing)):

- **Gleicher Inhalt** auf Mobile und Desktop.
- **Gleiche Structured Data** auf beiden Versionen; URLs darin müssen korrekt sein.
- **Gleiche Robots-Meta-Tags** auf beiden Versionen – ein abweichendes `noindex` auf Mobile kann die ganze Seite deindexieren.
- `title` und `meta description` müssen auf der mobilen Version vorhanden sein.

Bei **einer responsiven Codebasis** (wie hier, FastAPI + ein Template) ist das strukturell trivial – es gibt nur eine HTML-Version. Das ist ein echter Vorteil gegenüber separaten m.*-Sites.

**Viewport:** `<meta name="viewport" content="width=device-width, initial-scale=1">` ist Voraussetzung für korrekte mobile Darstellung und Lighthouse-Audit "Viewport". (Google dokumentiert das im Rahmen der Mobile-Usability; die Anforderung selbst ist HTML-Standard, nicht SEO-Spezialwissen.)

### 5.2 Semantische Überschriften

Google ist hier überraschend entspannt – und widerspricht der gängigen "genau eine H1"-Regel:

> "Having your headings in semantic order is fantastic for screen readers, but from Google Search perspective, it doesn't matter if you're using them out of order."
> "There's also no magical, ideal amount of headings a given page should have."
> — [SEO Starter Guide](https://developers.google.com/search/docs/fundamentals/seo-starter-guide)

Praktisch relevant ist also nicht die Tag-Hierarchie, sondern:
- **Eine klare inhaltliche Hauptaussage pro Seite** – sie beeinflusst, welche Textpassage als Snippet taugt.
- **Keine Keyword-Stuffing-Überschriften** ([title-link](https://developers.google.com/search/docs/appearance/title-link) nennt das explizit als spam-verdächtig).
- Semantisch korrektes HTML trotzdem verwenden – für Screenreader und Barrierefreiheit, nicht für Google.

### 5.3 `lang`

`<html lang="de">` wird von Google zur Spracherkennung genutzt: *"Google uses … hreflang or the HTML lang attribute to detect the language of a page"* ([localized-versions](https://developers.google.com/search/docs/specialty/international/localized-versions)). Kein Ranking-Signal, aber korrekt gesetzt lassen – insbesondere bei gemischtsprachigen Inhalten (z. B. englische Anbieternamen).

### 5.4 Title & Description

**Es gibt keine Längenbegrenzung.** Google sagt zu beiden explizit, dass gekürzt wird, um es an die Gerätebreite anzupassen:

> "While there's no limit on how long a `<title>` element can be, the title link is truncated in Google Search results as needed, typically to fit the device width."
> — [title-link](https://developers.google.com/search/docs/appearance/title-link)

> "There's no limit on how long a meta description can be, but the snippet is truncated in Google Search results as needed, typically to fit the device width."
> — [snippet](https://developers.google.com/search/docs/appearance/snippet)

Kürzung ist also **pixelbasiert**, nicht zeichenbasiert. Die verbreiteten "60 Zeichen / 155 Zeichen" sind Konventionen, keine Google-Regeln.

**Empirie statt Regel:**
- Google ersetzt Titel häufig. Ahrefs (2021, 953.276 Seiten): **33,4 %** der Titel wurden umgeschrieben ([ahrefs.com](https://ahrefs.com/blog/title-tags-study/)). Eine neuere Untersuchung (Shepard/SE Land, Q1 2025, ~30.000 Keywords) kommt auf **76 %** – andere Methodik, daher nicht direkt vergleichbar ([Search Engine Land](https://searchengineland.com/google-changed-76-of-title-tags-in-q1-2025-heres-what-that-means-454847)).
- Angezeigte Titel sind **kürzer als der Tag**: 10.000 SERP-Titel, Durchschnitt 42–46 Zeichen, unabhängig von der Position ([Search Engine Land](https://searchengineland.com/title-tag-length-388468)).
- Meta-Descriptions werden mehrheitlich ersetzt: **62,78 %** (20.000 Keywords), und die eigene Description erscheint nur in **37,22 %** der Fälle ([Ahrefs](https://ahrefs.com/blog/meta-description-study/)).

**Wichtiger als die Description ist der Seiteninhalt selbst:** Google sagt, der Snippet werde "from the actual content of the page" gezogen – "thus you have complete control over the words that can be used to generate the snippet" ([SEO Starter Guide](https://developers.google.com/search/docs/fundamentals/seo-starter-guide)). Eine gute Description erhöht die Chance auf einen passenden Snippet, ersetzt aber keinen guten sichtbaren Text.

**Praxis:**
- Title: **einzigartig pro Seite**, beschreibend, Marke ans Ende, ~45–55 Zeichen als Ziel (Empirie, nicht Vorschrift). Boilerplate-Titel ("Günstige Reisen – …") sind explizit schlecht ([title-link](https://developers.google.com/search/docs/appearance/title-link)).
- Description: **kein Ranking-Faktor**, aber CTR-relevant, wenn sie verwendet wird. Sie sollte die Seite präzise beschreiben, nicht Keywords stapeln.
- Beide werden von Google **überschrieben**, wenn die Seite es hergibt. Das ist kein Fehler, den man "fixen" muss.

### 5.5 Canonical

Siehe 1.4. Für jede indexierbare Seite: **selbstreferenziell**, absolute URL, identisch mit Sitemap und internen Links.

### 5.6 Open Graph

**Kein Ranking-Effekt – als Indiz, nicht als Google-Statement.** Die Liste der Meta-Tags, die Google dokumentiert unterstützt, enthält `description`, `robots`, `googlebot`, `google-site-verification` etc. – **`og:*` ist nicht dabei** ([special-tags](https://developers.google.com/search/docs/crawling-indexing/special-tags)). Google nennt Open Graph weder als Indexierungs- noch als Bewertungssignal. Dass daraus "kein Ranking-Effekt" folgt, ist ein **Umkehrschluss aus der Doku**, keine explizite Google-Aussage.

Sinnvoll bleibt OG für **Social-Previews** (Slack, WhatsApp, LinkedIn, X) – und indirekt für Traffic. `og:image` ist dabei der wirksamste Teil.

### 5.7 `hreflang`

Nur relevant bei **mehreren Sprach-/Regionsversionen**. Dann gelten ([localized-versions](https://developers.google.com/search/docs/specialty/international/localized-versions)):

- Jede Seite verweist auf **alle** Alternativen inkl. sich selbst ("return links" sind Pflicht: *"If page X links to page Y, page Y must link back to page X"*).
- `x-default` für Sprachwahl-Seiten / nicht zugeordnete Sprachen.
- Canonical muss auf **dieselbe Sprache** zeigen.
- Falsches/inkonsistentes hreflang wird ignoriert – es gibt keine Strafe, aber auch keinen Nutzen.

Für eine rein deutschsprachige Seite: **weglassen**. `lang="de"` genügt.

---

## 6. Rechtliches & Transparenz

### 6.1 Hat "Anzeige"-Kennzeichnung SEO-Auswirkungen?

**Auf Google-Richtlinien: nein.** Es gibt keine Google-Regel, die eine Kennzeichnung wie "Anzeige" verlangt oder belohnt. Die Kennzeichnungspflicht ist **deutsches Wettbewerbsrecht**:

> "Unlauter handelt auch, wer den kommerziellen Zweck einer geschäftlichen Handlung nicht kenntlich macht, sofern sich dieser nicht unmittelbar aus den Umständen ergibt …"
> — [§ 5a Abs. 4 UWG](https://www.gesetze-im-internet.de/uwg_2004/__5a.html)

**Indirekt aber schon relevant:** Im Kontext der *Site-Reputation Policy* bewertet Google, ob "affiliate links are clearly marked" und ob der kommerzielle Charakter erkennbar ist – als Indiz für redaktionelle Verantwortung. Fehlende Kennzeichnung wird dort als Negativbeispiel genannt ([spam-policies § Site reputation](https://developers.google.com/search/docs/essentials/spam-policies#site-reputation)). Das betrifft primär Drittanbieter-Inhalte auf Host-Seiten, ist aber die einzige Stelle, an der Google kommerzielle Kennzeichnung überhaupt erwähnt.

**Fazit:** "Anzeige" ist rechtlich Pflicht (§ 5a UWG), SEO-neutral. Kein Nachteil, kein Vorteil – aber ein Vertrauenssignal für Nutzer.

### 6.2 Bezahlte Links: `rel="sponsored"`

Klar geregelt:

> "Mark links that are advertisements or paid placements (commonly called paid links) with the `sponsored` value. … The nofollow attribute was previously recommended for these types of links and is still an acceptable way to flag them, though `sponsored` is preferred."
> — [Qualify your outbound links](https://developers.google.com/search/docs/crawling-indexing/qualify-outbound-links)

Und in den Spam-Policies:

> "It's not a violation of our policies to have such links as long as they are qualified with a `rel="nofollow"` or `rel="sponsored"` attribute value to the `<a>` tag."
> — [spam-policies § Link spam](https://developers.google.com/search/docs/essentials/spam-policies#link-spam)

**Für Affiliate-Links heißt das:** Jeder Link, für den Geld fließt, bekommt `rel="sponsored"` (oder mindestens `nofollow`). `sponsored` ist die präzisere und von Google bevorzugte Variante. Kombination ist erlaubt: `rel="sponsored nofollow"`.

**Was das *nicht* bedeutet:** Es ist keine Abstrafung der Seite, und es ist kein Ranking-Nachteil für die eigene Seite – es verhindert nur, dass der Link Ranking-Signal an den Partner weitergibt. Affiliate-Links sind damit **kein** SEO-Problem, solange sie qualifiziert sind.

### 6.3 E-E-A-T: kein Ranking-Faktor, aber Qualitätsrahmen

Google sagt es im SEO Starter Guide unmissverständlich:

> "Thinking E-E-A-T is a ranking factor — No, it's not."
> — [SEO Starter Guide](https://developers.google.com/search/docs/fundamentals/seo-starter-guide)

Gleichzeitig fließt Vertrauenswürdigkeit in die Bewertung "hilfreicher Inhalte" ein ([Creating helpful content](https://developers.google.com/search/docs/fundamentals/creating-helpful-content)). Für einen Preisvergleich heißt das konkret und **ohne Ranking-Versprechen**: Quellen nennen, Aktualität datieren, Betreiber/Redaktion erkennbar machen, Preise nachvollziehbar herleiten. Das ist Goodwill beim Nutzer und senkt das Thin-Affiliate-Risiko – es ist kein "E-E-A-T-Signal", das man einbauen könnte.

### 6.4 Der eigentliche rechtliche/SEO-Berührungspunkt: Preisangaben

Nicht Teil der Google-Richtlinien, aber für einen Preisvergleich relevant: Preisangaben gegenüber Verbrauchern unterliegen der **Preisangabenverordnung (PAngV)**. Ich habe die PAngV im Rahmen dieser Recherche **nicht im Detail geprüft** und gebe deshalb keine Aussage zu Endpreis-/Grundpreis-Pflichten. Das ist ein separater Rechts-Check, kein SEO-Thema. (Siehe § 8.)

---

## 7. Prioritätenliste

Bezogen auf: ~10 statische Kategorieseiten, viele kurzlebige `/jobs/<id>`-URLs, SSR ohne nennenswertes JS, deutschsprachig.

### Hoch

| # | Maßnahme | Aufwand | Erwartete Wirkung | Beleg-Basis |
|---|---|---|---|---|
| H1 | **`/jobs/<id>`: `noindex, follow` – und `Disallow: /jobs/` entfernen** (nicht beides gleichzeitig) | S | Verhindert URL-only-Indexeinträge; beseitigt widersprüchliche Signale. Direkt belegter Mechanismus. | [block-indexing](https://developers.google.com/search/docs/crawling-indexing/block-indexing), [robots-meta-tag](https://developers.google.com/search/docs/crawling-indexing/robots-meta-tag#combining) |
| H2 | **`Disallow: /static/` prüfen und entfernen**, falls CSS/JS darüber laufen | S | Verhindert Render-Probleme; Google warnt explizit davor | [robots.txt intro](https://developers.google.com/search/docs/crawling-indexing/robots/intro) |
| H3 | **Stabile Landingpages pro Nachfragecluster** (Route/Kategorie) statt ID-Seiten: eigener Slug, eigener Title/H1, Preisverlauf, Quellenlage | L | Der zentrale Hebel für organischen Traffic – ID-Seiten sind nicht indexierbar und sollen es nicht sein | [Mueller](https://www.seroundtable.com/google-index-search-results-35232.html), [URL-Struktur](https://developers.google.com/search/docs/crawling-indexing/url-structure) |
| H4 | **Sitemap nur mit 200 + indexierbaren + kanonischen URLs**; abgelaufene Routen entfernen | S | Kein direkter Ranking-Effekt; vermeidet Fehlerreports und Crawl-Verschwendung | [build-sitemap](https://developers.google.com/search/docs/crawling-indexing/sitemaps/build-sitemap) |
| H5 | **Selbstreferenzielle Canonicals + eindeutige Titles** auf allen indexierbaren Seiten | S | Konsolidiert Signale; verhindert "Duplicate, Google chose different canonical" | [consolidate-duplicate-urls](https://developers.google.com/search/docs/crawling-indexing/consolidate-duplicate-urls) |

### Mittel

| # | Maßnahme | Aufwand | Erwartete Wirkung | Beleg-Basis |
|---|---|---|---|---|
| M1 | **`Organization` + `BreadcrumbList`** als JSON-LD | S | Knowledge-Panel-/Logo-Signale, Breadcrumb in SERPs. Kein Ranking-Hebel. | [organization](https://developers.google.com/search/docs/appearance/structured-data/organization), [breadcrumb](https://developers.google.com/search/docs/appearance/structured-data/breadcrumb) |
| M2 | **`FAQPage` und `SearchAction` aus dem Markup entfernen** (oder belassen – schadet nicht) | S | Kein Effekt, aber weniger Wartungslast und keine falschen Erwartungen | [Changelog](https://developers.google.com/search/updates), [Sitelinks-Box](https://developers.google.com/search/blog/2024/10/sitelinks-search-box) |
| M3 | **`Product` + `AggregateOffer` nur auf echten Ein-Objekt-Seiten**, Preise sichtbar, `priceValidUntil` korrekt | M | Kann Produkt-Snippet liefern; für Flüge **nicht garantiert** | [product-snippet](https://developers.google.com/search/docs/appearance/structured-data/product-snippet) |
| M4 | **CWV: TTFB + kritisches CSS** | M | LCP mobiler ist der häufigste Failed-Metric; bei SSR meist TTFB/CSS-limitiert | [web.dev/vitals](https://web.dev/articles/vitals), [CrUX](https://developer.chrome.com/docs/crux/release-notes) |
| M5 | **Affiliate-Links auf `rel="sponsored"`** + sichtbare "Anzeige"-Kennzeichnung | S | Policy-Konformität; kein Ranking-Nachteil | [qualify-outbound-links](https://developers.google.com/search/docs/crawling-indexing/qualify-outbound-links), [§ 5a UWG](https://www.gesetze-im-internet.de/uwg_2004/__5a.html) |
| M6 | **Leere Ergebnisse → 404**, abgelaufene Suchen → 404/410 | S | Vermeidet Soft-404-Klassifizierung und Indexmüll | [faceted navigation](https://developers.google.com/search/docs/crawling-indexing/crawling-managing-faceted-navigation) |

### Niedrig

| # | Maßnahme | Aufwand | Erwartete Wirkung | Beleg-Basis |
|---|---|---|---|---|
| N1 | `ItemList` auf Kategorieseiten | S | **Kein** Rich Result (Carousel nur Course/Movie/Recipe/Restaurant); rein semantisch | [carousel](https://developers.google.com/search/docs/appearance/structured-data/carousel) |
| N2 | Open-Graph-Tags ausbauen | S | Kein Ranking-Effekt; nur Social-Previews | [special-tags](https://developers.google.com/search/docs/crawling-indexing/special-tags) |
| N3 | Title/Description auf 60/~155 Zeichen trimmen | S | Keine Google-Regel; Kürzung ist pixelbasiert. Nur als Konsistenz-Hilfe sinnvoll | [title-link](https://developers.google.com/search/docs/appearance/title-link), [snippet](https://developers.google.com/search/docs/appearance/snippet) |
| N4 | `hreflang` | M | Nur bei Mehrsprachigkeit; aktuell nicht relevant | [localized-versions](https://developers.google.com/search/docs/specialty/international/localized-versions) |
| N5 | `changefreq`/`priority` in der Sitemap | S | Wird von Google ignoriert | [build-sitemap](https://developers.google.com/search/docs/crawling-indexing/sitemaps/build-sitemap) |

### Explizit **nicht** verfolgen

| Maßnahme | Grund |
|---|---|
| `AggregateRating` aus OTA-/Airline-Sternen | "Don't aggregate reviews or ratings from other websites" – Manual-Action-Risiko |
| `FAQPage`-Markup als Rich-Result-Strategie | Feature seit 07.05.2026 entfernt |
| `SearchAction` / Sitelinks-Searchbox | Feature seit 21.11.2024 entfernt |
| Tausende `/jobs/<id>`-Seiten indexieren | Doorway-/Scaled-Content-Risiko, kein Content-Mehrwert |
| `Product`-Markup auf Kategorieseiten | Google: nur Ein-Produkt-Seiten |
| CWV-Punkte als Hauptstrategie | Google: andere Page-Experience-Aspekte heben das Ranking nicht direkt |

---

## 8. Was **nicht** belegt ist / offene Punkte

Ich markiere das explizit, damit es nicht als gesichert in Entscheidungen einfließt:

1. **`Product`/`AggregateOffer` für Flugstrecken-Seiten.** Die Markup-Form ist konform (Aggregator-Beispiel existiert), aber Google dokumentiert nur Waren-Produkte. Ob ein Flug als "product" akzeptiert und als Snippet angezeigt wird, ist **nicht belegt**. Die Doku sagt nur, dass Konformität das Feature *ermöglicht*, nicht garantiert.
2. **Auswirkung von `Product`-Markup auf Rankings.** Es gibt kein Google-Dokument, das strukturierten Daten einen Ranking-Effekt zuschreibt. Die Doku beschreibt Rich Results ausschließlich als Darstellungsfeature; ein Ranking-Effekt wird nirgends behauptet ([sd-policies](https://developers.google.com/search/docs/appearance/structured-data/sd-policies)).
3. **Indexierungsquote / "wie viele Seiten sollte ich im Index haben".** Die 16,5-%-Zahl stammt aus einer Berater-Stichprobe (50 Konten), nicht von Google, und ist nicht repräsentativ ([matthewedgar.net](https://www.matthewedgar.net/google-search-console-page-indexing/)).
4. **Titel-Rewrite-Rate 76 % (2025).** Einzelstudie mit eigener Methodik, nicht von Google bestätigt; die ältere Ahrefs-Zahl (33,4 %) widerspricht ihr. Beide sind nur Indikatoren für "Google ersetzt Titel häufig".
5. **Optimale Title-/Description-Länge.** Es gibt keine Google-Vorgabe. Alle Zahlen (45–55, 60, 155) sind empirische Konventionen.
6. **CTR-Effekt von Rich Results für Reise-Preisvergleiche.** Google veröffentlicht dazu keine belastbaren Zahlen für dieses Segment; Case Studies betreffen andere Branchen.
7. **Aggregator Unit – konkrete Erfolgsaussichten.** Die Existenz und die Voraussetzungen sind belegt, die tatsächliche Sichtbarkeit/Zulassungsschwelle nicht.
8. **PAngV-Konformität der Preisangaben.** Nicht geprüft (Rechtsthema, kein SEO). Separat zu klären.
9. **Ob `noindex, follow` bei sehr großem URL-Raum crawl-seitig reicht.** Google dokumentiert die Mechanik, nicht die Mengenschwelle. Bei unbegrenztem URL-Raum ist `robots.txt` die einzige echte Crawl-Bremse – mit dem dokumentierten Index-Restrisiko.

---

## 9. Beobachtungen am vorhandenen Code (nur Recherche, nichts geändert)

Beim Blick in `/home/batnini/mimo-agents/seo/` fallen fünf Punkte auf, die direkt an die oben belegten Regeln anschließen. Ich habe **nichts davon angefasst**:

1. **`sitemap.py` setzt gleichzeitig `Disallow: /jobs/` in der robots.txt und `pages.py`/`meta.py` setzen `noindex` für `/jobs/`.** Das ist genau die in § 1.3 belegte Kombination, bei der `noindex` **nicht** gelesen wird. Ergebnis kann "Indexed, though blocked by robots.txt" sein – die URL erscheint ohne Snippet, statt zu verschwinden.
2. **`Disallow: /static/`** mit dem Kommentar "dürfen geladen werden (Rendering), aber nicht indexiert" widerspricht der Google-Doku: `Disallow` verhindert genau das Laden. Für Assets ist `X-Robots-Tag: noindex` das passende Mittel.
3. **`jsonld.py` baut `WebSite` + `SearchAction`** – das Feature ist seit 21.11.2024 entfernt. Harmlos, aber wirkungslos. Ebenso `faq()` → `FAQPage`: seit 07.05.2026 ohne Rich Result. Der sichtbare FAQ-Text bleibt trotzdem sinnvoll.
4. **`meta.py` dokumentiert "Title ≤ 60 Zeichen (Google schneidet danach ab)" und "Description 80–160".** Das ist als **interne Konsistenzregel** legitim, aber die Begründung ist nicht korrekt: Google nennt keine Zeichenlimits und kürzt pixelbasiert (§ 5.4). Falls die Regel als "Google-Anforderung" in Doku oder Tests weitergetragen wird, wäre das eine falsche Prämisse.
5. **`sitemap.py` übernimmt alle Routen aus `routes_cache.all_routes()`, ohne das Alter zu prüfen.** Die Hilfsfunktion `age_hours()` existiert in `routes_cache.py`, wird aber nirgends aufgerufen. Folge: Eine Route mit sehr alten Preisen bleibt in der Sitemap, und `lastmod` ist dann der alte `generated_at`. Das ist kein technischer Fehler (die Seite liefert 200), aber ein Aktualitätsproblem – und `lastmod` soll laut Google die letzte *inhaltliche* Änderung abbilden, nicht ein beliebig altes Erzeugungsdatum.

Diese Punkte sind **Beobachtungen aus dem Code, keine Empfehlung, ihn zu ändern** – die Entscheidung liegt beim Hauptagenten.

---

## 10. Quellen

### Google Search Central
- Search technical requirements — https://developers.google.com/search/docs/essentials/technical
- Spam policies — https://developers.google.com/search/docs/essentials/spam-policies
- robots.txt intro — https://developers.google.com/search/docs/crawling-indexing/robots/intro
- Robots meta tag / X-Robots-Tag (inkl. Kombinationsregeln) — https://developers.google.com/search/docs/crawling-indexing/robots-meta-tag
- Block Search indexing with noindex — https://developers.google.com/search/docs/crawling-indexing/block-indexing
- Sitemaps: Übersicht — https://developers.google.com/search/docs/crawling-indexing/sitemaps/overview
- Sitemaps: Build and submit — https://developers.google.com/search/docs/crawling-indexing/sitemaps/build-sitemap
- Canonicalization — https://developers.google.com/search/docs/crawling-indexing/canonicalization
- rel="canonical" & andere Methoden — https://developers.google.com/search/docs/crawling-indexing/consolidate-duplicate-urls
- Faceted navigation — https://developers.google.com/search/docs/crawling-indexing/crawling-managing-faceted-navigation
- URL structure — https://developers.google.com/search/docs/crawling-indexing/url-structure
- Ecommerce URL structure — https://developers.google.com/search/docs/specialty/ecommerce/designing-a-url-structure-for-ecommerce-sites
- Ecommerce site structure — https://developers.google.com/search/docs/specialty/ecommerce/help-google-understand-your-ecommerce-site-structure
- Pagination & incremental page loading — https://developers.google.com/search/docs/specialty/ecommerce/pagination-and-incremental-page-loading
- Mobile-first indexing — https://developers.google.com/search/docs/crawling-indexing/mobile/mobile-sites-mobile-first-indexing
- Meta tags Google supports — https://developers.google.com/search/docs/crawling-indexing/special-tags
- Qualify outbound links — https://developers.google.com/search/docs/crawling-indexing/qualify-outbound-links
- hreflang / localized versions — https://developers.google.com/search/docs/specialty/international/localized-versions
- Structured data: general guidelines — https://developers.google.com/search/docs/appearance/structured-data/sd-policies
- Structured data gallery — https://developers.google.com/search/docs/appearance/structured-data/search-gallery
- Product snippets — https://developers.google.com/search/docs/appearance/structured-data/product-snippet
- Product intro — https://developers.google.com/search/docs/appearance/structured-data/product
- Merchant listing — https://developers.google.com/search/docs/appearance/structured-data/merchant-listing
- Review snippet — https://developers.google.com/search/docs/appearance/structured-data/review-snippet
- Breadcrumb — https://developers.google.com/search/docs/appearance/structured-data/breadcrumb
- Carousel (ItemList) — https://developers.google.com/search/docs/appearance/structured-data/carousel
- Organization — https://developers.google.com/search/docs/appearance/structured-data/organization
- Vacation rental — https://developers.google.com/search/docs/appearance/structured-data/vacation-rental
- Aggregator unit — https://developers.google.com/search/docs/appearance/aggregator-unit
- Core Web Vitals — https://developers.google.com/search/docs/appearance/core-web-vitals
- Page experience — https://developers.google.com/search/docs/appearance/page-experience
- Title links — https://developers.google.com/search/docs/appearance/title-link
- Snippets / meta description — https://developers.google.com/search/docs/appearance/snippet
- Reviews system — https://developers.google.com/search/docs/appearance/reviews-system
- Creating helpful content — https://developers.google.com/search/docs/fundamentals/creating-helpful-content
- Search updates / Changelog — https://developers.google.com/search/updates

### Google Blog / Announcements
- FAQ- und HowTo-Änderungen (08.08.2023) — https://developers.google.com/search/blog/2023/08/howto-faq-changes
- Sitelinks Search Box entfernt (21.10.2024) — https://developers.google.com/search/blog/2024/10/sitelinks-search-box

### Search Console Help
- Page indexing report — https://support.google.com/webmasters/answer/7440203?hl=en
- "No page information in search results" — https://support.google.com/webmasters/answer/7489871?hl=en
- Internal site search spam (Community Guide) — https://support.google.com/webmasters/community-guide/297497016/what-to-do-about-internal-site-search-spam?hl=en

### Web Vitals / CrUX
- web.dev Core Web Vitals — https://web.dev/articles/vitals
- CrUX methodology — https://developer.chrome.com/docs/crux/methodology
- CrUX release notes — https://developer.chrome.com/docs/crux/release-notes

### schema.org
- AggregateOffer — https://schema.org/AggregateOffer
- Offer — https://schema.org/Offer
- Product — https://schema.org/Product

### Recht
- § 5a UWG (Irreführung durch Unterlassen) — https://www.gesetze-im-internet.de/uwg_2004/__5a.html

### Sekundärdaten (keine Primärquellen)
- HTTP Archive Web Almanac 2024 – SEO — https://almanac.httparchive.org/en/2024/seo
- HTTP Archive Web Almanac 2024 – Structured Data — https://almanac.httparchive.org/en/2024/structured-data
- HTTP Archive Web Almanac 2025 – Performance — https://almanac.httparchive.org/en/2025/performance
- Ahrefs Title-Tag-Studie (2021) — https://ahrefs.com/blog/title-tags-study/
- Ahrefs Meta-Description-Studie (2020) — https://ahrefs.com/blog/meta-description-study/
- Search Engine Land: Title-Länge (2025) — https://searchengineland.com/title-tag-length-388468
- Search Engine Land: 76 % Title-Änderungen (2025) — https://searchengineland.com/google-changed-76-of-title-tags-in-q1-2025-heres-what-that-means-454847
- SERoundtable: Mueller zu internen Suchergebnisseiten (2023) — https://www.seroundtable.com/google-index-search-results-35232.html
- Matthew Edgar: Page-Indexing-Report-Auswertung (2026) — https://www.matthewedgar.net/google-search-console-page-indexing/
