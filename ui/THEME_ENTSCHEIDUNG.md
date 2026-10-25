# Theme-Entscheidung: Dark/Light-Mode

Stand: 2026-10-25 · Geltungsbereich: gesamte System-UI (`ui/`)

## 1. Ausgangslage

Die UI war rein dunkel: zehn Farb-Tokens in `:root`, aber

- keine Light-Variante,
- kein Umschalter, keine Persistenz,
- kein `prefers-color-scheme`, kein `color-scheme`, kein `data-theme`,
- harte Farben außerhalb der Tokens (SVG-Graph, Status-Badges, Tints, `theme-color`),
- `legal.html` als eigene HTML-Hülle ohne `base.html`.

## 2. Recherche (Kurzfassung)

Ausgewertet wurden MDN, web.dev, CSS-Tricks, WCAG 2.2 sowie Referenzprojekte
(Nokturne, `theme-change`, GoogleChromeLabs `dark-mode-toggle`, Josh Comeau).

Konsens:

1. **Farb-Tokens** in `:root`, Theme über `[data-theme]` auf `<html>` überschreiben –
   ein Stylesheet, keine doppelten CSS-Dateien.
2. **Inline-Blocking-Script im `<head>` vor dem CSS** liest die Wahl und setzt
   `data-theme` + `style.colorScheme` → kein Flash of wrong theme (FOUC).
3. **`color-scheme` pro Theme** setzen, damit native Controls (Date-Picker, Select,
   Checkbox, Scrollbars) mitwechseln.
4. **`localStorage`** ist für ein No-Build-Setup ohne SSR-Theme der richtige Speicher:
   kein Request-Overhead, kein `Vary: Cookie`, keine Cache-Invalidierung. Cookie nur,
   wenn serverseitig das Theme gebraucht wird (haben wir nicht).
5. **Systempräferenz** über `matchMedia('(prefers-color-scheme: dark)')`, inkl.
   Laufzeit-Listener; eine explizite Wahl überschreibt sie.
6. **`theme-color`** folgt per `media` nur dem OS → bei manueller Wahl per JS setzen.
7. **SVG** über `currentColor` bzw. CSS-Variablen; keine festen Hex-Werte in JS.

Quellen:

- https://developer.mozilla.org/en-US/docs/Web/CSS/color-scheme
- https://web.dev/articles/color-scheme
- https://web.dev/articles/prefers-color-scheme
- https://css-tricks.com/a-complete-guide-to-dark-mode-on-the-web/
- https://kilianvalkhof.com/2020/design/your-dark-mode-toggle-is-broken/
- https://www.joshwcomeau.com/react/dark-mode/
- https://github.com/ErwanHeschung/Nokturne
- https://github.com/GoogleChromeLabs/dark-mode-toggle
- https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html

## 3. Entscheidung

| Frage | Entscheidung | Begründung |
|---|---|---|
| Technik | CSS Custom Properties + `html[data-theme]` | ein File, kein Build, sofort umschaltbar |
| Speicher | `localStorage["theme"] = "light" \| "dark"` | kein Serverzustand nötig; HTML bleibt cachebar |
| Default | System (`prefers-color-scheme`) | respektiert OS-Einstellung ohne Zutun |
| FOUC | Inline-Script im `<head>` **vor** dem CSS-Link | setzt `data-theme` vor dem ersten Paint |
| Native Controls | `color-scheme: dark/light` pro Theme + `style.colorScheme` | sonst weiße Selects/Date-Picker im Dark |
| Browser-Chrome | `<meta name="theme-color">` mit JS-Update | `media` würde nur dem OS folgen, nicht der manuellen Wahl |
| Toggle | ein Button mit Sonne/Mond, `aria-pressed`, i18n-Label | platzsparend, tastatur- und screenreader-tauglich |
| Rechtsseiten | gleiches Head-Script + `theme.js` in `legal.html` | die Seite erbt nicht von `base.html` |
| SVG | Fills/Strokes über `var(--…)`, Gradient-Stops per `style="stop-color:var(--accent)"` | Theme-Wechsel ohne Neurendern |

**Bewusste Einschränkung (v1):** Der Button schaltet zwischen Hell und Dunkel.
„System“ ist der Default, solange nichts gespeichert ist; ein sichtbarer
„Zurück zu System“-Eintrag fehlt. `window.resetTheme()` setzt die Wahl zurück
(und damit wieder System). Ein Drei-Zustands-Menü (System/Hell/Dunkel) ist die
naheliegende Erweiterung, wurde für die Header-Breite aber nicht eingebaut.

## 4. FOUC-frei: so funktioniert es

`base.html` und `legal.html` laden im `<head>`, **vor** `app.css`:

```html
<meta name="theme-color" content="#0f1420"
      data-theme-dark="#0f1420" data-theme-light="#f4f7fb">
<script>
(function () {
  try {
    var p = localStorage.getItem('theme');
    var d = matchMedia('(prefers-color-scheme: dark)').matches;
    var t = (p === 'light' || p === 'dark') ? p : (d ? 'dark' : 'light');
    document.documentElement.dataset.theme = t;
    document.documentElement.style.colorScheme = t;
  } catch (e) {}
})();
</script>
```

Danach übernimmt `ui/static/theme.js` (defer):

- setzt `theme-color`, `aria-label`/`title` und `aria-pressed` des Buttons,
- Klick → Gegenteil der aktuell aufgelösten Farbe, speichert in `localStorage`,
- `matchMedia`-Listener greift **nur**, wenn keine eigene Wahl gespeichert ist,
- `storage`-Event synchronisiert andere Tabs,
- `document.dispatchEvent(new CustomEvent('themechange'))` für künftige Canvas/Chart-Renderer.

## 5. Abgedeckte Flächen

| Fläche | Umsetzung |
|---|---|
| Header/Navigation/Sprachwechsel | `--panel`, `--line`, `--muted`, `--text`; Toggle in `.topbar-tools` |
| Formulare (Inputs, Selects, Checkboxen, Datum) | Tokens + `color-scheme`; Fokus `outline: 2px var(--accent)` |
| Buttons | `--accent` + `--on-accent` (Kontrast in beiden Modi) |
| Tabellen (Ergebnisse, KV, Live-Quellen) | `--line`, `--line-soft`, `--accent-soft` für Gewinnerzeile |
| Statusmeldungen | `.alert.error/.warn` über `--err-*`/`--warn-*` |
| Tags/Dots | `--ok-text`, `--warn-text`, `--err-text`, `--off` |
| Startseiten-Schaubild | Knoten/Kanten/Loop/Phasen/Core über Tokens; Gradient-Stops `var(--accent)` |
| Ergebnis-Graph | dito; Kanten `--edge`, Pakete `--packet`, Halo `--accent` |
| Live-Quellenstatus-Tabelle | `.st.ok/.warn/.err`, `.dot.*` über Tokens |
| Detailansicht/Affiliate | `--accent-soft`, `--accent-line`, `--warn-*` |
| Preisalarme | Standard-Tokens/Tabellen |
| Rechtsseiten | eigenes Head-Script + Toggle; `theme-color` ergänzt |
| Fehlerseiten | erben von `base.html` |
| RTL (Arabisch) | logische Margins; Toggle-/Sprachreihenfolge gespiegelt |

## 6. Farben & Kontrast

Die Light-Palette ist **nicht** invertiert, sondern eigenständig:

| Rolle | Dark | Light |
|---|---|---|
| `--bg` | `#0f1420` | `#f4f7fb` |
| `--panel` | `#171d2b` | `#ffffff` |
| `--text` | `#e8edf6` | `#16202f` |
| `--muted` | `#93a0b8` | `#55637a` |
| `--accent` | `#4c8dff` | `#1a5fd0` |
| `--ok` / `--ok-text` | `#2fbf71` / `#9ff0c4` | `#15803d` / `#166534` |
| `--warn` / `--warn-text` | `#f0a23c` / `#ffd9a6` | `#b45309` / `#92400e` |
| `--err` / `--err-text` | `#ef5f5f` / `#ffb3b3` | `#b91c1c` / `#991b1b` |

Geprüft im Test (`test_theme.py`): Text/Hintergrund und Button-Text/Button-Fläche
erreichen in beiden Modi mindestens 4,5:1 (WCAG AA). `--on-accent` ist im Dark
dunkel (`#08111f`), weil Weiß auf `#4c8dff` nur ~3,3:1 hätte; im Light ist es Weiß
auf `#1a5fd0`.

## 7. Tests

`python3 ui/tests/test_theme.py` (Chrome DevTools Protocol, ohne Playwright-Abhängigkeit):

- Toggle existiert auf Startseite, Kategorieseite, Preisvergleich, Ergebnis,
  Detail, Alarme, Impressum und Datenschutz.
- Klick wechselt `data-theme`, `localStorage` und `aria-label`; Reload bleibt.
- Ohne gespeicherte Wahl folgt die Seite `prefers-color-scheme` (CDP-Emulation hell/dunkel).
- Explizite Wahl überschreibt die Systemeinstellung (auch nach Medienwechsel).
- FOUC-Guard: Inline-Script steht im HTML **vor** dem CSS-Link.
- Kontrastwerte ≥ 4,5:1 in beiden Modi.
- SVG-Gradient-Stops liefern in Dark/Light unterschiedliche `stop-color`-Werte.
- Live-Quellen-Tabelle und Graph haben in beiden Modi sichtbare, unterschiedliche Farben.
- Suche funktioniert in beiden Modi (Formular-Submit → `/jobs/...`).
- Screenshots: `ui/screenshots/theme_{dark,light}_{home,fluege,preisvergleich,results,detail,alarms,impressum}.png`.

Regression: `test_i18n`, `test_i18n_scan`, `test_category_pages`, `test_home_graph`,
`test_agent_graph`, `e2e_test`, `seo`, `affiliate`, `legal`, `discovery`.

## 8. Neue Sprache / neues Theme

Neue Sprache: `ui/locales/<code>.theme.json` anlegen (drei Keys) und in
`ui/i18n_core.py` registrieren – wie bei allen anderen Locale-Dateien.

Neues Theme (z. B. „sepia“):

1. Block `[data-theme="sepia"] { … }` mit allen Tokens ergänzen.
2. In `theme.js` die Allowlist (`light|dark`) und den Toggle-Zyklus erweitern.
3. `data-theme-dark`/`data-theme-light` der `theme-color`-Meta ergänzen.
4. Testmatrix in `test_theme.py` um das Theme erweitern.

## 9. Bekannte Grenzen

- **Favicon/OG-Bild** bleiben dunkel gestaltet (`static/favicon.svg`, `static/og.png`);
  sie sind Marken-Assets, keine UI-Flächen. Light-Varianten wären manuell zu erzeugen.
- **Ohne JavaScript** bleibt es beim dunklen Default (das Head-Script entfällt).
  Der Fallback ist bewusst die bisherige, lesbare Darstellung.
- **Autofill** von Chrome kann je nach Version eigene Hintergründe setzen;
  `color-scheme` deckt die nativen Controls ab, ein `:autofill`-Override ist nicht eingebaut.
- **`forced-colors`** (Windows-Kontrastmodus) wird nicht durch ein zweites Theme
  überschrieben; Ränder/Outlines bleiben sichtbar.
- Der **`theme-color`** wird erst nach dem Inline-Script aktualisiert; bei deaktiviertem
  JS zeigt die Browserleiste den dunklen Wert.
