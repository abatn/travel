# Entscheidung: Internationalisierung (i18n) der Reise-Agent-UI

**Status:** entschieden (Umsetzung offen) · **Datum:** 2026-10-24  
**Scope:** `ui/` (FastAPI + Jinja2 + Vanilla JS) · Sprachen `de` (Quelle), `en`, `fr`, `es`, `ar` (RTL)  
**Nicht im Scope:** Anbieterdaten, Rechtstexte, E-Mails, lokalisierte URL-Slugs.

## 1. Kontext und Ist-Zustand

9 Jinja-Templates (907 Zeilen), dazu `ui/app.py` (651), `app.css` (328) und `app.js` (559), gerendert über `ui/app.py`; zentrale Renderstelle ist `_render()` (`ui/app.py:93`). `legal.html` umgeht sie an `ui/app.py:388` und hat eine
eigene Dokumentwurzel. `i18n/locales/de.json` existiert mit **111 Schlüsseln** (flaches JSON, Platzhalter wie `{count}`), ist aber über `/*` in `.gitignore` ignoriert und muss bewusst getrackt werden.

Vorgaben: kein Build-Schritt, keine neuen Laufzeit-Abhängigkeiten, Umschalten per `?lang=` und Cookie ohne Neustart. Vorhanden: `httpx`, `requests`, `PyYAML`, Jinja2. Betroffene Stellen: `seo/meta.py`
setzt `LOCALE = "de_DE"` und `lang: "de"` statisch; `_fmt()` formatiert Zahlen fest deutsch; HTML läuft mit `Cache-Control: public, max-age=60`; `app.js` (559 Zeilen) enthält deutsche Strings und
SVG-Labels; Templates enthalten Textpfeile (`←`, `→`) und `✈`.

## 2. Recherche: Ansätze für FastAPI + Jinja2

**Babel/gettext.** Strings als `_("…")`/`{% trans %}`; `pybabel extract` → `.pot`, `init/update` → `.po`, `compile` → binäre `.mo` (Pflichtschritt). Jinja2 hat dafür eine i18n-Extension (`trans`,
`install_gettext_translations()`). Stärken: Pluralregeln (`ngettext`), etablierte Werkzeuge. Nachteilig hier: Compile-Schritt, `Babel` als neue Abhängigkeit, und der Extraktor findet keine JSON-Keys.
FastAPI liefert selbst keine i18n und lässt das Format offen (JSON, `.po`, DB).

**starlette-babel / fastapi-babel.** `starlette_babel` bringt Locale-Middleware, Selektoren, Jinja-Globals (`_`, `_p`) und Datums-/Zahlen-/Währungsfilter; eingebaute Reihenfolge `?locale=` → Cookie
`language` → User → `Accept-Language` → Default, für `?lang=`/`lang` wären eigene Selektoren nötig. `fastapi_babel` bietet FastAPI-Middleware mit `locale_selector` und Jinja, basiert aber ebenfalls
auf Babel/`.po`/Compile. Beide sind sauber, kaufen aber die ausgeschlossene Abhängigkeit und den Build-Schritt ein.

**flask-babel.** Funktional die Referenz (Locale-Selector, `gettext`/`ngettext`, Jinja, `force_locale`), aber **Flask-only**; auf FastAPI wäre es eine Eigenimplementierung. Taugt als Vorbild für
Selektor-Logik und Fallbacks, nicht als Dependency.

**JSON + `t()`.** Ein JSON-Objekt pro Sprache, `t(key, **kwargs)` liest daraus, Fallback auf Deutsch. Kein Compile, keine Dependency (stdlib `json`). Dieses Muster nutzen FastAPI-Beispiele und die
offizielle FastAPI-Antwort. Preis: keine Pluralregeln, keine Datums-/Zahlenformate, keine Extraktor-Toolchain.

## 3. Wie große Projekte die Sprache auflösen

- **Django** (`LocaleMiddleware`): Pfad-Präfix → Session → Cookie → `Accept-Language` → `LANGUAGE_CODE`; Cookies gelten nur für unterstützte Sprachen, dazu `Content-Language` und `Vary: Accept-Language`.
- **Next.js / next-intl:** Sub-Path (`/fr/...`) oder Domain (`fr.example.com`); Priorität URL → Cookie → `Accept-Language` → Default. Der Header wählt nur am Root, danach entscheidet die URL.
- **Google Search** empfiehlt unterschiedliche URLs je Sprache statt Cookie/Browser-Setting, warnt vor Auto-Redirects anhand vermuteter Sprache und rät von Sprach-/Länder-Parametern in der URL ab.
  Googlebot sendet kein `Accept-Language`; cookie-/header-abhängige Varianten werden ggf. nicht vollständig gecrawlt.
- **Fazit:** Query-Parameter + Cookie ist ein legitimer UI-Schalter, aber **keine** SEO-Lösung; für indexierbare Seiten ist ein Pfad-Präfix die belastbare Variante.

## 4. RTL-Unterstützung (Arabisch)

`dir="rtl"` gehört auf `<html>`, weil es die Basisrichtung für den Unicode-Bidi-Algorithmus setzt; `lang` allein impliziert **keine** Richtung. Beide Dokumentwurzeln (`base.html:2`, `legal.html:2`)
müssen es tragen.

**Logische CSS-Eigenschaften** statt physischer: `margin-inline-start`, `padding-inline`, `inset-inline-start`, `border-inline-start`, `text-align: start`. In `app.css` sind physische Werte u. a. an
`.topbar nav a` (`margin-left`), `.cat` (`margin-right`), `.hint`, `.tag`, `.dot`, `.table th/td` (`text-align: left`), `.notes`/`.steps` (`padding-left`), `.card`/`.card.legal` (`border-left`) und
`.skip` (`left: -9999px`) zu ersetzen. `flex-direction: row` und `gap` spiegeln sich durch `direction: rtl` automatisch.

**SVG:** Der Browser spiegelt keine Grafiken. Pauschales `[dir="rtl"] svg { transform: scaleX(-1) }` ist falsch: Es dreht Logo, Uhr, Häkchen, Lupe und jeden SVG-Text mit. Nur richtungsweisende Icons
(Pfeile, Chevrons, Zurück) opt-in per Klasse spiegeln. Das Agenten-Schaubild in `app.js` ist ein Diagramm, kein Lesefluss – **nicht** spiegeln, nur Beschriftungen übersetzen; falls doch, `<text>`
gegenläufig transformieren (`transform-box: fill-box; transform-origin: center`).

**Zahlen und Bidi:** Ziffern laufen in RTL-Text von links nach rechts, sind aber „schwach“ gerichtet; Preis-/Datumsfolgen können zwischen Textläufen verrutschen. Preise, Codes, Telefonnummern und
Zeitstempel isolieren: `<bdi dir="ltr">` oder `unicode-bidi: isolate`, Zahlenspalten mit `dir="ltr"`. `Intl.NumberFormat('ar')` liefert standardmäßig arabisch-indische Ziffern, `ar-u-nu-latn` erzwingt
lateinische. Textpfeile (`←`, `→`) werden **nicht** automatisch gespiegelt und sind in RTL semantisch falsch; die Richtung gehört als Schlüssel ins JSON (`route.arrow`: `→` für de/en/fr/es, `←` für ar).

## 5. Extraktion der deutschen Strings und Fallbacks

Die 111 Keys sind der Ausgangspunkt. Realistisch ist **manuelles, templateweises Umstellen**: Text durch `{{ t('key') }}` ersetzen, Key in `de.json` belassen. Ein Extraktor hilft wenig: `pybabel extract` findet `_()`/`{% trans %}`, aber keine `t('key')`-Aufrufe; `keywords = t` fände nur Python-Aufrufe und pflegte trotzdem keine JSON-Datei. `babel-lsp` prüft `.po`-Kataloge – für JSON gibt es kein vergleichbares Python-Werkzeug (nicht belegt).

Stattdessen ein **stdlib-Prüfskript** in CI/Testphase: (1) Key-Mengen aller Locales identisch zu `de.json`; (2) keine leeren Werte, keine Keys nur in einer Sprache; (3) Platzhalter-Parität per
`re.findall(r"\{(\w+)\}", value)`; (4) verwendete Keys (Grep über `t('…')`) ⊆ `de.json`, unbenutzte Keys melden.

**Fallback:** `locale[key]` → `de[key]` → `key`. Nie leer rendern, nie eine Exception im Request; fehlende Keys einmalig loggen (`logging.warning`). Rechtstexte: deutsche Fassung ist verbindlich,
`legal.notice` bleibt in jeder Sprache sichtbar.

## 6. Teststrategie

**HTTP-Tests je Sprache** (ohne neue Dependency, mit `requests` wie in `ui/tests/`, alternativ `httpx`): `GET /?lang=en` → 200, `<html lang="en" dir="ltr">`, `Content-Language: en`, `Set-Cookie: lang=en`,
`og:locale=en_US`; `?lang=ar` → `dir="rtl"`; `?lang=xx` → deutsches Fallback ohne 400; Folgerequest mit Cookie `lang=fr` → französisch; fehlender Key → deutscher Text. Dazu Key-/Platzhalter-Parität (§5).

**Screenshot-Tests:** Playwright `expect(page).toHaveScreenshot()` mit festem Viewport, `maxDiffPixelRatio` und Maskierung dynamischer Werte (Preise, Uhrzeiten, Job-IDs). Rendering unterscheidet sich
nach OS/Browser – Baselines im selben Container erzeugen. Je Sprache ein Snapshot, für `ar` zusätzlich RTL. Das findet, was HTTP-Tests nicht sehen: abgeschnittene Buttons, überlaufende Tabellen,
falsch gespiegelte Icons.

**SEO:** `og:locale` **pro Antwort** setzen (`de_DE`, `en_US`, `fr_FR`, `es_ES`, `ar_AR` – Facebook-Umbrella-Locale), plus `og:locale:alternate`; heute konstant in `seo/meta.py`. `hreflang` ist nur
mit eindeutigen, absoluten URLs korrekt (self-referencing, reziprok). Mit `?lang=` nicht sauber abbildbar; dann lieber **kein** `hreflang` als ein falsches. Canonical bleibt pfadbasiert.

## 7. Vergleichsmatrix

| Ansatz | Abhängigkeiten | Aufwand | Eignung für dieses Projekt | Urteil |
|---|---|---|---|---|
| Babel/gettext + Jinja-i18n | `Babel`, `pybabel`, `.po`/`.mo`, Compile | mittel–hoch | Plurale/Datum stark, aber Build-Schritt, keine JSON-Keys | verworfen |
| flask-babel | Flask + Babel | – | Flask-only, nicht auf FastAPI übertragbar | verworfen |
| fastapi-babel | `fastapi-babel` + Babel | mittel | Middleware/Jinja ja, aber `.po`-Compile und Overhead | verworfen |
| starlette-babel | `starlette-babel` + Babel | mittel | gute Selektoren/Formatter/RTL, aber neue Dependency + `.po` | zurückgestellt (beste Alternative) |
| **JSON + `t()` + Cookie/Query** | **keine (stdlib)** | **niedrig** | **passt exakt; 111 Keys liegen vor** | **gewählt** |
| nur Client-JS | keine | niedrig | FOUC, SEO, doppelte Strings, `app.js` bliebe unübersetzt | verworfen |
| Pfad-Präfix `/en/…` | keine | mittel | SEO-beste, aber Routen/Slugs/Umbau nötig | später prüfen |

## 8. Entscheidung

**JSON-Dateien + Jinja-Global `t()` + Cookie/Query-Auflösung, Fallback Deutsch, `dir="rtl"` für Arabisch, keine Bibliothek.**

Begründung: erfüllt alle Vorgaben (kein Build, keine Dependency), nutzt die vorhandene `de.json`, ist in einem Nachmittag umstellbar und bleibt debugbar (Klartext-Keys). `starlette-babel` wäre
technisch stärker (Plurale, Datumsformate, RTL), verletzt aber die Vorgaben.

**Auflösungsreihenfolge:** (1) `?lang=xx`, nur wenn `xx ∈ SUPPORTED` (gewinnt auch gegen Cookie); (2) Cookie `lang=xx`, nur wenn unterstützt; (3) optional `Accept-Language` (best match); (4) Default
`de`. Bei gültigem `?lang=` direkt in dieser Sprache rendern und Cookie setzen (`Path=/; Max-Age=31536000; SameSite=Lax; Secure` bei HTTPS); kein Redirect nötig. Ungültige Werte ignorieren (kein 400),
damit geteilte Links nicht brechen. Cookie = Präferenz, kein Login-Datum. `?lang=` nicht in den Canonical aufnehmen.

```python
CATALOGS = {code: json.load(...) for code in SUPPORTED}   # beim Start

def translator(lang: str):
    def t(key: str, **kw) -> str:
        raw = CATALOGS.get(lang, {}).get(key) or CATALOGS["de"].get(key) or key
        try:
            return str(raw).format(**kw)
        except (KeyError, IndexError):
            return str(raw)          # kaputter Platzhalter killt die Seite nicht
    return t
```

`t`, `lang` und `dir` werden **pro Request über den Render-Kontext** übergeben (`_render()`), nicht über `templates.env.globals`: Globals sind prozessweit, ein per-Request gesetztes `t` ist unter
parallelen Requests ein Race (die verbreitete Middleware-Variante mit `env.globals['_'] = _` hat genau dieses Problem). Falls Global gewünscht: `contextvars.ContextVar`. `legal.html` erhält denselben
Kontext explizit, da es `_render()` umgeht.

```jinja
<html lang="{{ lang }}" dir="{{ dir }}">
<a href="?lang=en" hreflang="en" lang="en">{{ t('lang.name.en') }}</a>
```

Jinja-Autoescape bleibt an; übersetzte Strings nie mit `|safe` ausgeben, kein HTML in Übersetzungen (Keys splitten) – sonst entstehen XSS-Flächen.

**Caching:** Weil die Sprache aus dem Cookie kommt, ist `Cache-Control: public` für HTML falsch. Entweder `private, max-age=60` oder `Vary: Cookie`; MDN empfiehlt für cookie-personalisierte Inhalte
ausdrücklich `private` statt `Vary: Cookie`. Das kostet CDN-Trefferquote – der bewusste Preis der Cookie-Umschaltung.

**RTL:** `dir = "rtl" if lang == "ar" else "ltr"` zentral aus der Locale-Tabelle. CSS auf logische Eigenschaften umstellen (§4), `[dir="rtl"]` nur für markierte Richtungs-Icons. Preise/Daten in `<bdi dir="ltr">`; Nutzereingaben (`origin`, `destination`, Alarmname) mit `dir="auto"`. `✈` im Brand bleibt ungespiegelt (Logo), Textpfeile werden übersetzt.

## 9. Neue Sprache in 3 Schritten

1. **Datei:** `cp i18n/locales/de.json i18n/locales/xx.json`, nur Werte übersetzen, Keys und `{platzhalter}` unverändert lassen. Keine neuen Keys erfinden.
2. **Registrieren:** `xx` in `SUPPORTED` aufnehmen und in der Locale-Tabelle `{"name": "…", "dir": "ltr|rtl", "og_locale": "xx_YY"}` ergänzen. Der Sprachumschalter iteriert über diese Tabelle; sonst ist
   nichts zu ändern.
3. **Prüfen:** Paritäts-/Platzhalter-Test, HTTP-Test `?lang=xx`, bei RTL ein Screenshot-Snapshot; danach Review durch Muttersprachler (besonders Rechtstexte).

## 10. Grenzen der Lösung

- **Keine Pluralregeln:** `{count} Person(en)` ist in allen Sprachen falsch; Arabisch hat sechs CLDR-Kategorien (zero/one/two/few/many/other). Sauber erst mit ICU/gettext.
- **Keine Datums-/Zahlen-/Währungsformatierung:** `_fmt()` und `isoformat()` bleiben deutsch; deutsches Format in `en`/`ar` wirkt falsch. Dafür wäre Babel/`Intl` nötig.
- **JS nicht abgedeckt:** `app.js` enthält deutsche Strings und SVG-Labels. Entweder `window.__I18N__ = {{ bundle|tojson }}` injizieren oder `data-i18n`-Attribute nachrüsten – sonst bleibt die
  Startseite teilübersetzt.
- **Zwei Dokumentwurzeln:** `legal.html` hat eigenes `<html lang="de">` und umgeht `_render()`.
- **SEO:** `?lang=`/Cookie ist keine indexierbare Sprachversion; kein korrektes `hreflang`, Googlebot ohne `Accept-Language` sieht Deutsch. Für Ranking später Pfad-Präfix (`/en/…`) + `hreflang`.
- **Cache:** HTML muss privat werden (s. o.), sonst liefert der CDN die falsche Sprache.
- **Kein TMS/Review-Workflow:** JSON handgepflegt, keine Übersetzerversionierung, kein Fuzzy-Matching; neue Keys fehlen still.
- **Kein Hot-Reload:** JSON wird beim Start geladen; Übersetzungsänderungen brauchen einen Neustart. Das Umschalten der Sprache selbst braucht **keinen** Neustart.
- **Kein `lang` je Fragment:** Gemischte Inhalte (Anbieternamen, Zitate) werden nicht ausgezeichnet; `dir="auto"` nur an Nutzereingaben.

## 11. Quellen

**FastAPI / Jinja2 / Babel**
- FastAPI #513: https://github.com/tiangolo/fastapi/issues/513 · Phrase: https://phrase.com/blog/posts/fastapi-i18n/
- TheSusian: https://thesusian.com/post/fastapi-translation/ · Jinja-i18n: https://jinja.palletsprojects.com/en/stable/extensions/#i18n-extension
- Jinja/Babel: https://jinja.palletsprojects.com/en/stable/integration/#babel-integration · Babel: https://babel.readthedocs.io/en/latest/messages.html
- Flask-Babel: https://python-babel.github.io/flask-babel/ · fastapi-babel: https://github.com/Anbarryprojects/fastapi-babel
- starlette-babel: https://github.com/alex-oleshkevich/starlette_babel · babel-lsp: https://github.com/alex-oleshkevich/babel-lsp

**Sprachauflösung / SEO**
- Django-Middleware: https://docs.djangoproject.com/en/6.1/ref/middleware/#locale-middleware
- Django-Quelle: https://github.com/django/django/blob/main/django/utils/translation/trans_real.py
- Next.js: https://nextjs.org/docs/pages/guides/internationalization · next-intl: https://next-intl.dev/docs/routing/middleware
- Google mehrsprachig: https://developers.google.cn/search/docs/specialty/international/managing-multi-regional-sites?hl=de
- Google hreflang: https://developers.google.cn/search/docs/specialty/international/localized-versions
- Google-Video (keine Sprach-Parameter): https://www.youtube.com/watch?v=8ce9jv91beQ

**RTL / CSS / SVG / Zahlen**
- MDN `dir`: https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Global_attributes/dir
- MDN logische Eigenschaften: https://developer.mozilla.org/en-US/docs/Web/CSS/Guides/Logical_properties_and_values/Margins_borders_padding
- web.dev: https://web.dev/learn/design/internationalization · W3C SVG/Bidi: https://www.w3.org/International/tutorials/svg-tiny-bidi/Overview.en
- RTL-Icons: https://www.i18n-l10n.com/core-i18n-architecture-locale-negotiation/rtl-bidirectional-layout-engineering/fixing-mirrored-icons-and-logical-css-properties/

**Plurale / Tests / Metadaten**
- ICU: https://unicode-org.github.io/icu/userguide/format_parse/messages/ · CLDR/JSON: https://github.com/ChauCM/dialect/blob/main/dialect/spec/icu-json.md
- Playwright: https://playwright.dev/docs/test-snapshots · Open Graph: https://ogp.me/#optional · `ar_AR`: https://stackoverflow.com/questions/33141402/opengraph-locale-for-argentina
- MDN `Vary`: https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Vary
