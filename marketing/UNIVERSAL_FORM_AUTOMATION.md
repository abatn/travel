# Universelle Formular-Automation: Recherche & Entscheidung

> **Weiterentwicklung 2026-10-28:** Der Entwurf einer nicht-RPA-basierten
> Architektur (Form Genome, Skill Lattice, Self-Play) steht in
> [`INNOVATIVE_FORM_ARCHITEKTUR.md`](INNOVATIVE_FORM_ARCHITEKTUR.md).

Stand: 2026-10-28 · Auftrag: Wie kann ein KI-Agent **beliebige** Webformulare
autonom, zuverlässig und ohne menschliches Eingreifen ausfüllen?
Kein Bau ohne Freigabe – dies ist Recherche, Bewertung und Vorschlag.

**Kernaussage:** Es gibt keinen einzelnen MCP-Server und keine Bibliothek, die
„jedes Formular“ zuverlässig löst. Der beste Ansatz ist eine **eigene,
Python-native Hybrid-Architektur**: semantisches Formular-Modell +
deterministisches Field-Matching + Playwright-Ausführung + lokaler LLM-Fallback +
selbstheilende Trace-Wiedergabe + Vision-Fallback. PayAPI ist dafür nur ein
Spezialfall (und hat glücklicherweise einen MCP-Schreibpfad, der Browser
überflüssig macht).

---

## 1. Kritische Selbstanalyse der bisherigen Doku

Die alte `FORM_AUTOMATION_ENTSCHEIDUNG.md` war **zu eng**:

1. **PayAPI dominiert.** Analyse, Anforderungen, Entscheidung und Checkliste
   drehen sich fast vollständig um PayAPI. Der allgemeine Fall „beliebiges
   Formular“ kommt nur als Anhang vor.
2. **Werkzeug statt Architektur.** „Playwright MCP“ ist eine Interaktionsschicht,
   aber keine Lösung für Feldverständnis, Validierung, Fehlerbehandlung,
   Erfolgsprüfung, Lernen oder Wiederholung.
3. **Benchmarks fehlten.** WebArena, Mind2Web, WebVoyager, Online-Mind2Web,
   WorkArena und BrowserGym wurden nicht betrachtet. Dadurch fehlte die
   realistische Erwartung: Auch die besten Agenten scheitern an einem
   erheblichen Teil unbekannter Aufgaben.
4. **Python-only/No-Node/No-API-Key nicht untersucht.** Playwright Python,
   lokale Modelle (Ollama/vLLM), OmniParser + lokale VLM und selbstheilende
   Replay-Systeme kamen nicht vor.
5. **Die harten Teile fehlten:** Labels/Semantik, dynamische Comboboxen,
   Datums-Picker, iframes/shadow DOM, mehrstufige Wizards, Pflichtfeld- und
   Formatvalidierung, Fehlermeldungen, Erfolgsnachweis, Idempotenz, CAPTCHAs,
   Anti-Bot und Datenschutz.
6. **Keine Evaluation.** Es gab keinen Plan, wie man „funktioniert universell“
   messen würde (Erfolgsquote, Schritte, Kosten, Latenz, Eingriffe).

Die neue Frage ist daher nicht „Welches Tool klickt?“, sondern:
**Wie nimmt der Agent ein unbekanntes Formular wahr, versteht es, füllt es
korrekt aus, prüft das Ergebnis und lernt aus dem Lauf?**

---

## 2. Was universelle Formular-Automation wirklich braucht

| Schicht | Aufgabe | Ohne sie passiert |
|---|---|---|
| **1. Perception** | DOM + Accessibility Tree; Screenshot nur als Fallback; iframes/shadow DOM; Scrollen | Felder werden übersehen oder falsch zugeordnet |
| **2. Formular-Modell** | Formulargrenzen, Felder, Labels, Typen, Optionen, Pflicht, Constraints, Schritte | Agent füllt falsche Felder oder übersieht Validierung |
| **3. Semantisches Matching** | Task-Daten → Feld: exakt, synonym, embedding, LLM-Fallback; Confidence | „E-Mail“ vs. „Kontakt“, „PLZ“ vs. „Postal Code“ scheitern |
| **4. Ausführung** | echte Events, Fokus/Blur, Select/Combobox/Radio/Checkbox/Date/File, ContentEditable | React/Vue-Formulare bleiben leer oder Submit disabled |
| **5. Verifikation** | Erfolgstext, URL, DOM/Netzwerk, Bestätigungsnummer; Fehler auslesen | Agent meldet Erfolg, obwohl nichts abgeschickt wurde |
| **6. Reparatur/Lernen** | Retry, Field-Repair, Re-Plan, Trace-Cache, Self-Healing | jede Layout-Änderung bricht den Agenten |
| **7. Sicherheit** | Domain-Allowlist, Dry-Run, Secrets, Rate-Limit, Audit, keine CAPTCHA-Umgehung | Datenleck, Doppel-Submit, rechtliche Risiken |

Der entscheidende Punkt: **Ein Formular ist kein Klickproblem, sondern ein
Verständnis- und Verifikationsproblem.**

---

## 3. Benchmark-Lage (was wirklich messbar ist)

| Benchmark | Was er misst | Stand/Grenze |
|---|---|---|
| **WebArena** (2023) | 812 lange Aufgaben auf selbst gehosteten Shop/Forum/GitLab/CMS-Seiten | Sandbox; Spitzenwerte berichtet um **56–62 %** Task-Erfolg (harnessabhängig) |
| **WorkArena / WorkArena++** (2024) | ServiceNow: Listen, Formulare (1–26 Felder), Kataloge, Dashboards; 19.912 Instanzen | Enterprise-Formulare; ausdrücklich **nicht gelöst**; Formulare mit Tabs/Autocomplete |
| **Mind2Web** (2023) | 2.350 Offline-Aufgaben auf 137 Seiten; nächster Schritt | Element-Accuracy berichtet um **68–70 %**, Gesamt-Erfolg um **58,7 %**; kein End-to-End-Submit |
| **Online-Mind2Web** (2025) | 300 Live-Aufgaben auf 136 Seiten | Berichtet **78–90 %**, harte Aufgaben **59–82 %**; Live-Drift, Judge-Varianz |
| **WebVoyager** (2024) | 643 Live-Aufgaben auf 15 Seiten | Berichtet **86–94 %**; selbst gemeldet, Judge/ Harness unterschiedlich |
| **BrowserGym** (2024) | Vereinheitlichung von MiniWoB/WebArena/WorkArena/VisualWebArena/WebLINX | Framework, kein einzelner Score; hilft gegen Fragmentierung |
| **WebBench / AssistantBench** | Live-Aufgaben inkl. Create/Update/Delete, Recherche | Hohe Varianz; keine reine Formular-Metrik |

**Wichtig:** Diese Zahlen sind **keine Formular-Erfolgsquote**. Formulare sind
nur ein Teil; WorkArena zeigt, dass Formulare mit 1–26 Feldern, Tabs und
Autocomplete weiterhin schwer sind. Es gibt **keinen modernen universellen
Formular-Benchmark**; für unsere Zwecke brauchen wir einen eigenen Korpus
(z. B. 20–50 Formulare: Bewerbung, Behörde, Buchung, Newsletter, Checkout).

### Forschungslinien, die die Lücke adressieren

- **AgentOccam** (Amazon, ICLR 2025): Vereinfachung von Observation/Action-
  Space (Elemente zusammenfassen, Tabellen zu Markdown, Dropdown in einem
  Klick) steigert WebArena um **+161 %** gegenüber naiven Agenten. Lehre:
  Darstellung und Aktionsraum sind wichtiger als ein größeres Modell.
- **SeeAct** (OSU, ICML 2024): LMM plant, aber **Grounding** (Textplan →
  exaktes HTML-Element) ist der Engpass; Set-of-Mark allein hilft bei Webseiten
  kaum, HTML+Visuals zusammen am besten. Live-Erfolg 51,1 % **mit manuellem
  Grounding** – ohne Grounding deutlich schlechter.
- **OmniParser** (Microsoft, arXiv 2408.00203): Screenshot → strukturierte
  interagierbare Elemente + Iconsemantik; **screenshot-only** kann auf
  Mind2Web/AITW textbasierte GPT-4V-Baselines übertreffen. MIT-lizenzierte
  v2-Detektor-Gewichte; lokal, aber GPU/Modell nötig.
- **mForms** (arXiv 2011.12340): Formularfelder als natürliche Fragen
  formulieren und mit extraktivem QA beantworten; zero-shot, ohne
  formularspezifisches Training. Gute Idee für das Field-Matching.
- **WebXSkill** (arXiv 2604.13318): Agent lernt wiederverwendbare Skills aus
  Exploration und überträgt sie auf neue Seiten; **86,1 %** WebVoyager im
  „grounded“-Modus. Lehre: einmal lernen, wiederverwenden.
- **Selbstheilende Replay-Systeme** (Workflow Use, Fantoma, Healix, AutoHeal,
  form-filler-agent, Navia, Browsewright): einmal per LLM entdecken, Trace
  cachen, deterministisch abspielen, bei Abweichung reparieren. Viele sind
  jung/klein und nicht benchmarkgestützt – die **Muster** sind aber genau
  richtig: Record → Replay → Self-Heal.

---

## 4. Fünf innovative Ansätze

### A. Hybrid Semantic Form Engine + Self-Healing Replay (Empfehlung)

**Kernidee:** Ein Python-Modul (Playwright Python, kein Node) extrahiert aus
DOM/Accessibility ein typisiertes Formularmodell, matcht Task-Daten
deterministisch (Labels, ARIA, Namen, Placeholder, Nachbartext, Optionen) und
nutzt einen lokalen LLM nur für mehrdeutige Felder. Nach Erfolg wird der Trace
mit einem **Form-Fingerprint** (Domain + Form-Action + Feld Signatur) gespeichert
und beim nächsten Mal **ohne LLM** abgespielt; bei Abweichung repariert der
Agent feldweise.

**Warum innovativ:** Es verbindet die Stärken von deterministischer RPA
(zuverlässig, billig) und LLM-Agenten (generalisiert) und lernt aus jedem Lauf.
Es ist keine weitere Browser-Hülle, sondern eine **Formular-Engine**.

**Bausteine:**
1. `perceive()`: DOM + AXTree + Bounding Boxes; iframes/shadow DOM; bei
   Canvas/Custom-Widgets optional Screenshot.
2. `build_schema()`: Felder, Typen, Labels, Optionen, `required`, Pattern,
   Fehlermeldungen, Schritte.
3. `match()`: Score aus Label/ARIA/Name/Placeholder/Nähe; Embedding/Fuzzy;
   LLM-Fallback mit JSON-Schema; Confidence + optional Review.
4. `act()`: Playwright Python; echte Tastatur/Maus; Select/Combobox/Radio/
   Checkbox/Date/File; warten auf Stabilität.
5. `verify()`: Erfolgstext/URL/DOM/Netzwerk/Bestätigungsnummer; Fehler auslesen.
6. `repair()`: Field-Repair, Re-Snapshot, Re-Plan; max. Schritte/Zeit.
7. `remember()`: Trace-Cache pro Form-Fingerprint; Zero-LLM-Replay.
8. `guard()`: Allowlist, Dry-Run, Secrets, Rate-Limit, Audit.

**Vorteile:** Python/FastAPI-native, kein Node, ohne API-Key nutzbar (lokales
Modell optional), schnell und günstig nach dem ersten Lauf, erklärbar,
testbar, schrittweise ausbaubar.
**Grenzen:** CAPTCHAs/Anti-Bot, stark visuelle Canvas-Formulare, rechtliche
Zulässigkeit; initialer Entwicklungsaufwand.

---

### B. Vision-first: OmniParser + lokales VLM + Playwright

**Kernidee:** Screenshot → OmniParser erkennt interagierbare Regionen und
Iconsemantik → lokales Vision-Language-Modell entscheidet die nächste Aktion →
Playwright klickt/tippt an den Koordinaten. Kein DOM nötig.

**Warum innovativ:** Funktioniert auch bei Canvas, Shadow DOM, custom
Webcomponents und exotischen UIs, wo DOM-Selektoren versagen. OmniParser ist
MIT-lizenziert (v2-Detektor) und lokal betreibbar.

**Voraussetzungen:** Python, Torch/GPU (empfohlen), lokale VLM-Gewichte
(z. B. Qwen-VL), Playwright; keine Cloud/API-Keys.
**Grenzen:** Langsam, teuer pro Schritt, OCR/Icon-Fehler, keine semantische
Formularstruktur; am besten als **Fallback** für Schicht 1.

---

### C. Lokaler LLM-Browser-Agent (browser-use + Ollama)

**Kernidee:** Ein Python-Agent (browser-use) bekommt eine natürliche Aufgabe
und entscheidet selbst über DOM/Accessibility-Aktionen; mit `ChatOllama` läuft
das komplett lokal ohne externen API-Key.

**Warum innovativ:** Sehr niedrige Einstiegshürde, Python, echte
Generalisierung, lokale Modelle möglich; Form-Filling ist ein dokumentierter
Standardfall.
**Voraussetzungen:** Python 3.11+, Chromium, Ollama + Modell (z. B.
Qwen2.5/32B), ausreichend RAM/GPU.
**Grenzen:** Lokale Modelle sind bei komplexen Formularen deutlich schwächer
als Cloud-Modelle; nicht deterministisch; Token-/Zeitkosten; schwierig zu
debuggen. Guter Prototyp, aber keine belastbare Produktions-Engine.

---

### D. MCP-Browser-Agent (Playwright MCP / Chrome DevTools MCP)

**Kernidee:** Ein MCP-Server stellt dem LLM Accessibility-Snapshots und
Aktionen (`browser_fill_form`, `click`, `select`) bereit; der Agent entscheidet
Schritt für Schritt.

**Warum innovativ:** Standardisierte Tool-Schnittstelle, breite
Client-Unterstützung, sehr gute Accessibility-Interaktion, `fill_form` für
alle Feldtypen.
**Voraussetzungen:** Node 20+, Browser, MCP-Client, LLM.
**Grenzen:** Node-Abhängigkeit (Production hat kein Node), keine
Formularsemantik/Verifikation/Replay; Prompt-Injection über Snapshots;
Anti-Bot/CAPTCHA ungelöst. Als **Aktionsschicht** gut, als Universallösung
unvollständig.

---

### E. Cloud-/Vision-Agent (Stagehand/Browserbase, Skyvern)

**Kernidee:** Natürlichsprachliche Aktionen (`act`, `observe`, `extract`) auf
Cloud-Browsern mit Proxies, Session Replay, Bot-Schutz; oder Skyvern mit
Vision-LLM und Workflows.

**Warum innovativ:** Höchste Chance bei geschützten, dynamischen Seiten und
bei Skalierung; Browserbase/Stagehand liefern Infrastruktur, Skyvern
automatisiert unbekannte Seiten visuell.
**Voraussetzungen:** Cloud-Account/API-Key, Modell, Node/TypeScript oder
Python-SDK; Kosten.
**Grenzen:** Externe Abhängigkeit, Datenresidenz, laufende Kosten, weniger
Kontrolle; für eine eigene Python/FastAPI-Architektur nur bei Bedarf.

---

## 5. Vergleichsmatrix

Bewertung 1–5; „Unabhängig“ = ohne Node und ohne externen API-Key.

| Ansatz | Allgemeinheit | Autonomie | Python/FastAPI | Zuverlässigkeit | Unabhängig | Aufwand | Reife |
|---|---|---|---|---|---|---|---|
| **A. Hybrid Semantic Engine + Replay** | **5** | **4,5** | **5** | **4** | **5** (lokales LLM optional) | 4 | 3 |
| B. OmniParser + lokales VLM | **5** | 4 | 4 | 3,5 | 4 (Gewichte/GPU) | 5 | 3 |
| C. browser-use + Ollama | 4,5 | 4 | **5** | 3,5 | 4 (lokales Modell) | 3 | 4 |
| D. Playwright/Chrome MCP | 4,5 | 4 | 3 (Node) | 4 | **1** | 2 | **5** |
| E. Stagehand/Browserbase/Skyvern | **5** | **5** | 4 | **4,5** | **1** | 2 | 4,5 |
| F. Klassische RPA + Selector-Healing | 2,5 | 2,5 | 5 | 4,5 (stabile Formulare) | 5 | 2 | 4 |

**Lesart:** A gewinnt, weil es die Generalisierung eines LLM-Agenten mit der
Determinismus/Robustheit einer RPA kombiniert und dabei Python-native bleibt.
B ist der beste Fallback für visuelle/CANVAS-UIs. C ist der schnellste
Prototyp. D/E sind starke Aktions-/Infrastrukturschichten, aber keine
vollständige universelle Lösung.

---

## 6. Entscheidung

**Gewählt: A – Hybrid Semantic Form Engine + Self-Healing Replay, mit B als
Vision-Fallback und C als Prototyp-/Notfallmodus.**

Begründung:

1. **Allgemeinheit:** DOM/Accessibility deckt die große Mehrheit der Formulare
   ab; Vision fängt den Rest.
2. **Autonomie:** deterministische Füllung + Verifikation + Reparatur; lokaler
   LLM nur bei Mehrdeutigkeit.
3. **Python/FastAPI:** Playwright Python, httpx, Pydantic; kein Node.
4. **Unabhängigkeit:** ohne externen API-Key nutzbar; lokales Ollama/VLM
   optional.
5. **Zuverlässigkeit:** Erfolgsprüfung, Validierungsfehler, Self-Healing und
   Trace-Cache statt „blind klicken“.
6. **Kosten/Latenz:** Zero-LLM-Replay nach dem ersten erfolgreichen Lauf.
7. **Erweiterbarkeit:** MCP-/Cloud-Adapter können später andocken, ohne die
   Kern-Engine zu ersetzen.

**Nicht gewählt als Kern:** Playwright MCP (Node, keine Formularsemantik),
browser-use allein (zu variabel), Cloud allein (Kosten/Abhängigkeit),
Klassik-RPA allein (bricht bei Layoutänderungen).

---

## 7. Zielarchitektur (Vorschlag, kein Bau)

```
FastAPI / Agent
   │
   ├─ FormPerceiver (Playwright Python)
   │    DOM + AXTree + iframes/shadow DOM + optional Screenshot
   ├─ FormSchema (Pydantic)
   │    Felder, Labels, Typen, Optionen, required, Pattern, Schritte
   ├─ FieldMatcher
   │    exakt → fuzzy/embedding → lokaler LLM-Fallback (JSON)
   ├─ ActionExecutor
   │    fill/select/check/upload/date/combobox; echte Events; waits
   ├─ Verifier
   │    Erfolg/Fehler/URL/DOM/Netzwerk/Bestätigung
   ├─ RepairEngine
   │    Field-Repair, Re-Snapshot, Re-Plan, Max-Steps
   ├─ TraceStore
   │    Form-Fingerprint → Aktionen; Zero-LLM-Replay
   └─ Guard
        Allowlist, Dry-Run, Secrets, Rate-Limit, Audit
```

**Form-Fingerprint:** `sha256(domain + form.action + sort(role,label,name,type))`.
**Confidence:** pro Feld; unter Schwellwert → LLM-Fallback oder kontrollierte
Übergabe (optional, nicht Standard).
**Erfolg:** nie aus „Submit geklickt“ ableiten; immer DOM/URL/Confirmation.

---

## 8. Erste Schritte / Evaluationsplan

1. **Korpus bauen:** 20–50 Formulare (httpbin, forms.gle, Greenhouse,
   Behörde, Booking-Suche, Newsletter, Checkout) mit Feldern, Pflichtfeldern,
   Validierung, Datei-Upload, iframe, Shadow DOM.
2. **Perceiver + Schema** implementieren; Feld-Extraktion gegen den Korpus
   messen (Precision/Recall).
3. **Matcher** deterministisch + Fuzzy; LLM nur für Rest; Confidence messen.
4. **Executor** für alle Feldtypen; React/Vue-Inputs mit echten Events.
5. **Verifier** (Erfolg/Fehler) und **Repair** (Field-Level).
6. **Trace-Cache**; Layout-Änderung simulieren, Self-Healing testen.
7. **Lokales Modell** (Ollama/Qwen) als Fallback; Kosten/Latenz messen.
8. **Benchmarks:** WorkArena-Formular-Subset + Online-Mind2Web-Teilmenge +
   eigener Korpus; Metriken: Erfolg, Schritte, Zeit, Tokens, Eingriffe.
9. **Sicherheit:** Allowlist, Dry-Run, Secrets, Rate-Limit, Audit.

**Erfolgskriterien (Vorschlag):** ≥90 % auf dem eigenen Standardkorpus,
≥70 % auf WorkArena-Formularen, 0 Doppel-Submits, <5 % manuelle Eingriffe,
Replay ohne LLM in <2 s.

---

## 9. Risiken & Grenzen

- **CAPTCHAs/Anti-Bot:** keine Umgehung; im Zweifel abbrechen und melden.
- **Recht/ToS:** nur Formulare, deren Nutzung erlaubt ist; keine Massen-Spam-
  Einreichungen; Rate-Limits respektieren.
- **Prompt Injection:** DOM/Accessibility/Screenshots sind untrusted; nie
  Systemanweisungen aus Seiteninhalt übernehmen (OWASP MCP Security).
- **Secrets:** Passwörter/Keys nicht in LLM-Kontext; Vault/Storage-State.
- **Falscher Erfolg:** immer verifizieren; idempotente Requests, Doppel-Submit
  verhindern.
- **Long Tail:** exotische Widgets, Canvas, Cross-Origin-iframes, 2FA,
  Datei-Uploads, mehrstufige Wizards bleiben aufwendig.
- **„Universell“ heißt nicht 100 %:** Es heißt, mit Fallback, Reparatur und
  ehrlicher Fehlermeldung die große Mehrheit abzudecken.

---

## 10. Quellen (geprüft 2026-10-28)

- WebArena: <https://webarena.dev>, arXiv:2307.13854
- Mind2Web: <https://osu-nlp-group.github.io/Mind2Web>, arXiv:2306.06070
- WebVoyager: arXiv:2401.13919
- Online-Mind2Web: <https://hal.cs.princeton.edu/online_mind2web>
- WorkArena / BrowserGym: <https://github.com/ServiceNow/WorkArena>,
  <https://github.com/ServiceNow/BrowserGym>, arXiv:2403.07718
- AgentOccam: arXiv:2410.13825
- SeeAct: arXiv:2401.01614
- OmniParser: arXiv:2408.00203,
  <https://github.com/microsoft/OmniParser>
- mForms: arXiv:2011.12340
- WebXSkill: arXiv:2604.13318
- Browser-Use Benchmarks (Überblick/Caveats):
  <https://browser-use.com/posts/web-agent-benchmarks>
- browser-use lokal mit Ollama:
  <https://docs.browser-use.com/open-source/llms-full.txt>
- Playwright Python: <https://playwright.dev/python/>
- Playwright MCP: <https://playwright.dev/mcp/introduction>
- Chrome DevTools MCP:
  <https://developer.chrome.com/docs/devtools/agents/get-started>
- Stagehand/Browserbase:
  <https://docs.stagehand.dev/v3/integrations/mcp/introduction>
- Skyvern: <https://github.com/Skyvern-AI/skyvern>
- Selbstheilende Muster:
  <https://github.com/EPIATBIG/workflow-use>,
  <https://github.com/Huzy85/fantoma>,
  <https://github.com/kunaal-ai/healix>,
  <https://github.com/Shubhambawner/form-filler-agent>,
  <https://github.com/azulls1/navia>,
  <https://github.com/krishnashakula/browsewright>
- OWASP MCP Security:
  <https://cheatsheetseries.owasp.org/cheatsheets/MCP_Security_Cheat_Sheet.html>
