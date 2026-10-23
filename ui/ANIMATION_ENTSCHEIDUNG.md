# Animation des Suchfortschritts: Recherche und Entscheidung

Stand: 23.10.2026 · Umsetzung: `ui/templates/results.html`, `ui/static/app.js`, `ui/static/app.css`

## 1. Anforderung

Statt eines Fortschrittsbalkens: ein **Agenten-Netzwerk** – zentraler Knoten (der Agent), außen die
Quellen, dazwischen Verbindungen. Der Fortschritt muss durch **fließende** Linien/Punkte sichtbar
sein, live aktualisiert, ohne neue Bibliothek.

## 2. Recherche: wie machen es andere?

| Quelle | Technik | Beleg |
|---|---|---|
| MDN – `stroke-dashoffset` | Gestrichelte Linie, Offset animiert → Muster „fließt" | developer.mozilla.org/…/stroke-dashoffset |
| CSS-Tricks – „How SVG Line Animation Works" | `stroke-dasharray` + `stroke-dashoffset`-Keyframes; für „Zeichnen" `pathLength` | css-tricks.com/svg-line-animation-works |
| O'Reilly „Drawing with Dashes" | Warnt vor Browser-Unterschieden bei `pathLength` → besser echte Längen oder `dasharray` in px | oreillymedia.github.io/Using_SVG/extras/ch13-drawing.html |
| **flow-engine-hr** (GitHub) | „Custom SVG edges using `animateMotion` – cyan data stream at rest, switches to emerald and accelerates when active" | github.com/NishanthKamalakkannan/flow-engine-hr |
| **agentFlow** (Naurolabs) | React Flow mit **animated edges** + per-flow filtering | github.com/samoletovs/agentFlow |
| **agent-canvas** | „a dot travels along each edge as data flows downstream, nodes settle green as they complete" | github.com/TheSaiEaranti/agent-canvas |
| **AgentCine** | Custom Edge mit 6 Status-Zuständen, „flow animation … using CSS keyframes" | github.com/pengchengneo/AgentCine (Commit 2bb30b6) |
| **GodUI Agent Flow** | „data packets that flow along the edges"; Status idle/running/done/error | godui.design/docs/lab/ai/agent-flow |

**Gemeinsames Muster:** Knoten mit Status (`idle/running/done/error`), Kanten mit `animated`-Flag,
Bewegung über CSS-Keyframes oder `animateMotion`; Farbe kodiert den Status.

## 3. Vergleichsmatrix

| Technik | Aufwand | Abhängigkeiten | Visuelle Qualität | Performance | Urteil |
|---|---|---|---|---|---|
| **CSS `stroke-dashoffset`** auf SVG-Pfaden | **S** | keine (SVG+CSS) | gut: fließende Striche, klar lesbar | sehr gut (Compositor) | **gewählt** |
| CSS `offset-path` (Punkt auf Pfad) | S–M | keine | sehr gut („Datenpakete") | gut | **gewählt, zusätzlich** (mit `@supports`-Fallback) |
| SMIL `<animateMotion>` | S | keine | sehr gut | gut | verworfen: SMIL ist nicht auf dem Standardpfad, Tooling/Testbarkeit schlechter |
| React Flow / @xyflow/react | L | **neue npm-Kette** (React, Build) | sehr gut | mittel | verworfen: passt nicht zu FastAPI+Jinja2 ohne Build |
| D3 / Three.js | L | große Bibliotheken | sehr gut | schwer | verworfen (unnötig) |
| Canvas 2D + rAF | M | keine | gut | gut, aber Neuzeichnen bei Resize | verworfen: SVG ist hier einfacher und zugänglich |

## 4. Entscheidung und Begründung

**Vanilla SVG + CSS-Animation, clientseitig aufgebaut.**

* **Keine neuen Abhängigkeiten** – passt zur bestehenden Architektur (FastAPI + Jinja2 + Vanilla JS,
  kein Build-Schritt). Die Projekte aus der Recherche brauchen React Flow; das wäre ein Bruch.
* **`stroke-dashoffset`** ist der robusteste Weg für „fließende" Linien (MDN/CSS-Tricks) und läuft
  auf dem Compositor – bei 9–12 Kanten vernachlässigbare Last.
* **`offset-path`** ergänzt einen kleinen Punkt, der entlang der Verbindung wandert („Datenpaket"),
  wie bei den Agenten-Visualisierungen. Ältere Browser zeigen dann nur die fließende Linie –
  `@supports (offset-path: path("M0 0 L1 1"))` schaltet den Punkt nur frei, wenn er funktioniert.
* **Statussprache wie in der Recherche:** wartend = gestrichelt/grau (langsam fließend), aktiv =
  blau, schnell fließend; ok = durchgezogen grün; übersprungen = gelb; Fehler = rot.
* **Kein Layout-Springen:** Der Graph hat eine **feste Höhe** (300 px), die SVG skaliert per
  `viewBox`. Das behebt gleichzeitig die frühere Ursache des „Wackelns".
* **Barrierefreiheit:** `prefers-reduced-motion` schaltet alle Animationen ab; die SVG trägt
  `role="img"` und eine Beschreibung, der Status steht zusätzlich als Text in der Tabelle.

## 5. Aufbau der Animation

```
        ┌───────────────┐
        │   alice-flights │──╲
        └───────────────┘   ╲
                  ╭───────────╮
   easygroupflights ───│           │─── fli_flights
                  │   AGENT   │
      flights-gf ────│   6/9     │──── googleflights-local
                  ╰───────────╯
        ┌───────────────┐   ╱
        │ maqami-travel │──╱
        └───────────────┘
```

* **Zentrum:** Kreis mit Verlauf, Ring pulsiert solange die Suche läuft (CSS `@keyframes`),
  Text „Agent" + Zähler „6/9".
* **Knoten:** Rechtecke auf einer Ellipse (rx 330, ry 150 im 900×420-ViewBox), Beschriftung =
  Quellen-ID, kleiner Statuspunkt in der Knotenfarbe.
* **Kanten:** quadratische Bézierkurven vom Zentrum zum Knoten. Je Status:
  * `waiting`: `stroke-dasharray: 5 7`, Animation `flow 1.2s linear infinite` (Offset −24) +
    wandernder Punkt (`offset-path`).
  * `ok`: durchgezogen, grün, kein Fluss.
  * `error`/`corrupt`: rot; `skipped`: gelb.
  * Frisch beantwortete Quelle: 1,2 s „pulse"-Klasse (hellblau, schneller Fluss) als Feedback.
* **Live:** Derselbe Polling-Tick, der die Tabelle aktualisiert, aktualisiert Knoten/Kanten
  (Klassenwechsel, kein Neuaufbau).

## 6. Test

* `ui/tests/test_agent_graph.py` (Chrome/CDP): SVG vorhanden, Knotenzahl = Quellenzahl, Kanten
  vorhanden, Status-Klassen wechseln (waiting → ok/error), Zentrum zeigt „x/y", Animation aktiv
  (`animation-name` gesetzt), Höhe konstant (kein Springen), nach Abschluss alle Kanten final.
* Screenshots: `ui/screenshots/ui_graph_running.png`, `ui/screenshots/ui_graph_done.png`.
