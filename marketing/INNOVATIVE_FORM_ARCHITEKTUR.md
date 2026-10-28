# FORGE: Form Genome & Repair Engine

**Eine Architektur für einen universellen, selbstverbessernden Formular-Agenten**

Stand: 2026-10-28 · Kein Bau ohne Freigabe · Dokumentation des Entwurfs

> **These:** Ein Formular ist kein HTML-Dokument und kein Klickpfad, sondern ein
> **latentes Programm**: Felder, Semantik, Constraints, Zustandsübergänge und
> Erfolgsbedingungen. Wer dieses Programm induziert, kann es ausführen,
> verifizieren, reparieren und als **wiederverwendbaren Skill** auf neue
> Formulare übertragen. Genau das ist FORGE.

---

## 1. Schonungslose Selbstkritik

Die bisherige „Hybrid Engine“ war handwerklich solide, aber konzeptionell eine
**klassische RPA mit LLM-Fallback**. Die Paper wurden zitiert, aber nicht in die
Architektur übersetzt:

| Paper/Idee | Was ich zitiert habe | Was ich **nicht** integriert habe |
|---|---|---|
| **SeeAct** | „Grounding ist der Engpass“ | Kein echtes Cross-Modal-Grounding: keine Zuordnung Textplan → HTML-Element → visuelle Bounding Box, kein Grounding-Score, keine Fusion aus DOM + Screenshot |
| **AgentOccam** | „Observation/Action-Space vereinfachen“ | Kein Observation-Compiler: rohe DOM/AXTree, keine Element-Merges, keine Tabellen→Markdown-Reduktion, keine abstrahierten Aktionen |
| **WebXSkill** | „Skills lernen und übertragen“ | Kein Skill-Begriff: nur Trace-Cache pro URL, keine Abstraktion, keine Komposition, kein Transfer auf neue Domains |
| **OmniParser** | „Vision-Fallback“ | Keine Cross-Modal-Korrespondenz, kein Set-of-Mark für Formularfelder, keine visuelle Unsicherheitskalibrierung |
| **mForms** | „Felder als Fragen“ | Kein QA-basiertes Field-Matching; nur Label/Fuzzy-Heuristiken |
| **Self-Healing** | „Repair“ | Kein Repair-Kalkül: nur Retry/Neustart, keine minimalen kausalen Reparaturen, keine Lerndaten aus Fehlern |

### Warum die alte Engine im Kern RPA ist

1. **Regeln zuerst, LLM nur bei Fehlern.** Das ist eine Fallback-Hierarchie, keine
   lernende Repräsentation.
2. **Selectors/URLs sind die Identität.** Ein Trace wird pro Formular/URL
   gespeichert; eine neue Domain beginnt bei null.
3. **Keine Abstraktion.** Der Agent lernt „klicke #email“, nicht „Feld mit
   semantischer Rolle *email*“.
4. **Kein Weltmodell.** Er weiß nicht, dass „Land = USA“ ein Bundesland-Feld
   einblendet oder dass eine Checkbox den Submit-Button aktiviert.
5. **Keine aktive Wahrnehmung.** Er wartet auf Labels; er provoziert sie nicht
   durch Hover, Fokus, Dropdown-Öffnen oder Scrollen.
6. **Keine Selbstverbesserung.** Nach einem erfolgreichen Lauf wird nichts
   generalisiert; nach einem Fehler wird nichts Kausales gelernt.
7. **Evaluation nur Erfolgsquote.** Keine Transfer-, Lern-, Kalibrierungs- oder
   Autonomiemessung.

Kurz: Die alte Engine **wiederholt** Formulare. FORGE soll **Formulare
verstehen und Wissen übertragen**.

---

## 2. Das 2028-Szenario

Ein Agent bekommt eine neue, unbekannte Behörden- oder Bewerbungsseite. Innerhalb
von ein bis zwei Versuchen:

1. **induziert** er ein Form-Genom (Felder, Semantik, Constraints, Schritte),
2. **ruft** aus einer Skill-Bibliothek passende „Address Block“, „Identity“,
   „Consent“- und „File Upload“-Skills ab,
3. **probt** aktiv verborgene Felder (Hover, Fokus, Dropdown, Tab-Wechsel),
4. **plant** mit einem gelernten Form-Weltmodell mehrere Schritte voraus,
5. **füllt** mit echten Events, löst Cross-Field-Constraints mit einem Solver,
6. **verifiziert** den Erfolg und erzeugt ein Prüfzertifikat,
7. **extrahiert** aus dem Lauf einen neuen, generalisierten Skill und
8. **publiziert** ihn signiert in einer Skill-Commons, aus der andere Agenten
   lernen – ohne PII, mit Provenienz und Safety-Rating.

Der Mensch setzt nur noch **Policy** (erlaubte Domains, sensible Aktionen,
Freigabeschwellen). Der Agent wird mit jedem Formular **auf neuen Formularen**
besser, nicht nur auf dem bereits gesehenen.

---

## 3. Kerninnovation: Form Genome + Skill Lattice + Self-Play

FORGE ist **keine** weitere Kombination aus „DOM + LLM + Playwright“. Der Kern
besteht aus vier neuen Abstraktionen:

### 3.1 Form Genome (FG)

Eine domainen-agnostische, typisierte Repräsentation eines Formulars:

```json
{
  "genome_id": "sha256:...",
  "domain_family": "government/benefits",
  "locale": "de-DE",
  "steps": [
    {"id": "s1", "fields": ["f1", "f2"], "next": "s2",
     "transition": "submit|validate|reveal"}
  ],
  "fields": [
    {
      "id": "f1",
      "slot": "person.email",
      "role": "email",
      "label": "E-Mail-Adresse",
      "aliases": ["E-Mail", "Email", "Kontakt"],
      "widget": "textbox",
      "required": true,
      "constraints": [{"type": "format", "value": "email"}],
      "group": "contact",
      "visibility": "always",
      "confidence": 0.98,
      "evidence": ["label:for", "aria-label", "dom:nearby-text"]
    }
  ],
  "cross_constraints": [
    {"if": "person.country == 'US'", "require": ["person.state"], "reveal": "f7"}
  ],
  "success_predicates": [
    {"type": "text", "value": "Antrag eingegangen"},
    {"type": "url", "pattern": "/confirmation/.*"}
  ],
  "visual_refs": [{"field": "f1", "bbox": [120, 340, 300, 28]}]
}
```

Das Genom ist **nicht** an Selektoren oder eine URL gebunden. Es beschreibt
Bedeutung, Constraints und Dynamik. Zwei Formulare mit unterschiedlichem HTML,
aber gleicher Semantik, erhalten ein ähnliches Genom.

### 3.2 Form Skill (FS)

Ein Skill ist ein **typisiertes Programm** über einem Genom:

```json
{
  "skill_id": "skill.address-block.v3",
  "signature": "genome:address-block",
  "preconditions": ["fields:street,city,postal,country"],
  "program": [
    {"op": "fill_slot", "slot": "address.street", "source": "profile.address.street"},
    {"op": "fill_slot", "slot": "address.city", "source": "profile.address.city"},
    {"op": "select_slot", "slot": "address.country", "source": "profile.address.country"},
    {"op": "await_reveal", "field": "address.state"},
    {"op": "fill_slot", "slot": "address.state", "source": "profile.address.state"}
  ],
  "verifier": ["all_required_filled", "no_validation_errors"],
  "repair_ops": ["relabel", "reselect", "reorder", "wait", "switch_widget"],
  "stats": {"uses": 41, "success": 0.95, "domains": 7},
  "provenance": {"learned_from": ["gov-form-17", "job-app-4"], "signed": "..."}
}
```

Skills sind **komponierbar**: Field-Skills (ein Slot), Block-Skills (Adresse,
Zahlung, Consent), Form-Skills (gesamter Ablauf). Die **Skill Lattice** ordnet
sie nach Generalisierung/Spezialisierung: `address-block` → `us-address-block` →
`us-address-block-with-county`.

### 3.3 Form World Model (FWM)

Ein gelerntes Übergangsmodell:

```text
state + action -> predicted next state + validation effects
```

Beispiele: „Land = US“ blendet Bundesland ein; „Newsletter = false“ deaktiviert
E-Mail-Pflicht; „Kreditkarte“ zeigt Rechnungsadresse. Das Modell wird aus Traces
gelernt und für **Model Predictive Control** (mehrere Schritte vorausplanen)
genutzt. Es ist die Grundlage für echte Autonomie auf mehrstufigen Formularen.

### 3.4 Self-Play-Curriculum

Ein **Form Designer** generiert systematisch neue Formularvarianten:
Feldreihenfolge, Labels/Synonyme, Pflichtfelder, Cross-Field-Constraints,
mehrstufige Wizards, iframes, Shadow DOM, Custom-Comboboxen, Fehlermeldungen.
Der **Filler** versucht sie; Erfolge und Reparaturen werden zu Skills. Ein
Difficulty-Estimator sampelt gezielt an der Grenze des Könnens (active learning).
So entsteht **Selbstverbesserung ohne menschliche Labels**.

Das ist der entscheidende Unterschied zu „Trace-Cache“: Der Agent trainiert
sich an **selbst erzeugten, unbekannten** Formularen und lernt transferierbare
Programme, nicht nur einen Ablauf.

---

## 4. Architektur

```
┌─────────────────────────────────────────────────────────────────────┐
│                        FORGE Agent (Python/FastAPI)                 │
│                                                                     │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────────────────┐  │
│  │ Perception   │──▶│ Form Compiler│──▶│ Genome / Constraint Graph│  │
│  │ DOM+AX+Vision│   │ (Schema/IR)  │   │ (typed slots, transitions)│  │
│  └──────────────┘   └──────────────┘   └────────────┬─────────────┘  │
│         ▲                                           │                │
│         │                                           ▼                │
│  ┌──────┴───────┐   ┌──────────────┐   ┌──────────────────────────┐  │
│  │ Active Probe │   │ Skill Lattice│◀─▶│ Planner (MPC + retrieval)│  │
│  │ hover/focus/ │   │ retrieve/    │   │ program adaptation        │  │
│  │ open/scroll  │   │ compose/rank │   └────────────┬─────────────┘  │
│  └──────────────┘   └──────────────┘                │                │
│         ▲                                           ▼                │
│         │              ┌──────────────────────────────────────────┐  │
│         └──────────────│ Executor (Playwright Python, real events)│  │
│                        └──────────────────┬───────────────────────┘  │
│                                           ▼                          │
│                        ┌──────────────────────────────────────────┐  │
│                        │ Verifier + Proof-Carrying Submission     │  │
│                        │ success predicates, constraints, receipt │  │
│                        └──────────────────┬───────────────────────┘  │
│                                           ▼                          │
│                        ┌──────────────────────────────────────────┐  │
│                        │ Self-Improvement Loop                    │  │
│                        │ trace→program → skill → repair → curriculum│ │
│                        └──────────────────────────────────────────┘  │
│                                                                     │
│  Guard: allowlist · secrets · rate-limit · audit · consent          │
└─────────────────────────────────────────────────────────────────────┘
```

### 4.1 Wahrnehmen: Perception + Active Probing

- **DOM/Accessibility Tree**: Rollen, Labels, `aria-*`, `name`, `id`,
  Placeholder, Nachbartext, `<label for>`, Optionen, `required`, Pattern.
- **Visuell**: Screenshot nur bei Canvas/Shadow DOM/Custom Widgets; OmniParser
  erzeugt Bounding Boxes + Iconsemantik.
- **Cross-Modal Grounding (SeeAct)**: Jedes Feld erhält eine Konfidenz aus
  Text-, DOM- und visueller Evidenz; bei niedriger Konfidenz wird aktiv geprobt.
- **Active Probing**: Hover auf Label, Fokus, Dropdown öffnen, Tab wechseln,
  scrollen, Fehlermeldung provozieren (nur lesend/validierend). Der Agent lernt,
  welche Probe welche Information liefert.

### 4.2 Verstehen: Form Compiler

- Segmentiert Formulargrenzen und Schritte.
- Extrahiert ein **typisiertes Genom** (Slots, Constraints, Visibility,
  Transitions).
- Formuliert Feldlabels als **Fragen** (mForms): „Wie lautet die E-Mail?“
- Erkennt Cross-Field-Abhängigkeiten und Validierungsregeln.
- Markiert Mehrdeutigkeiten mit Konfidenz und Evidenz.

### 4.3 Lernen: Skill Induction

Aus jedem Lauf (Erfolg oder Fehler):

1. **Trace normalisieren**: Selektoren entfernen, Aktionen auf semantische
   Operatoren abbilden (`fill_slot`, `select_option`, `reveal`, `submit`).
2. **Programm abstrahieren**: Welche Felder/Gruppen wurden in welcher Ordnung
   bearbeitet? Welche Bedingungen/Verifier waren nötig?
3. **Skill bilden**: Preconditions, Programm, Verifier, Repair-Operatoren,
   Statistik, Provenienz.
4. **Lattice einordnen**: generalisieren (z. B. „address“) oder spezialisieren
   („US address with county“).
5. **Promote/Prune**: Nur Skills mit reproduzierbarem Erfolg und ohne
   Safety-Verstoß werden dauerhaft behalten.

### 4.4 Übertragen: Genome Alignment + Skill Composition

- **Strukturelles Alignment**: Slots, Gruppen, Constraints und Transitions
  werden zwischen neuem Genom und Skill-Signaturen verglichen (Graph Matching +
  Embeddings + LLM nur für Mehrdeutigkeit).
- **Analogie**: „Dieses Formular hat einen Adressblock wie jenes; übernimm die
  Block-Skill und passe nur die Feldnamen an.“
- **Komposition**: Field-Skill + Block-Skill + Form-Skill; fehlende Teile werden
  neu gelernt.
- **Negativtransfer vermeiden**: Preconditions und Domain-Family-Checks; bei
  Unsicherheit lieber neu induzieren.

### 4.5 Reparieren: Counterfactual Repair Algebra

Bei einem Fehler wird **nicht** blind neu gestartet, sondern die minimale
Ursache gesucht:

1. **Hypothesen**: falsches Label, falscher Selektor, Widget-Typ, Reihenfolge,
   Sichtbarkeit, Validierung, Frame/Shadow DOM, Timing.
2. **Counterfactual Replay**: DOM-Snapshot + Aktion mutieren (z. B. Label
   ändern, Feld tauschen) und im Sandbox-Replay prüfen, welche Mutation den
   Fehler behebt.
3. **Repair-Operator** wählen: `relabel`, `reselect`, `reorder`, `wait`,
   `switch_widget`, `reveal`, `switch_frame`, `split_field`.
4. **Skill aktualisieren**: Repair als Präzedenzfall speichern; bei häufiger
   Wiederholung generalisieren.

### 4.6 Verifizieren: Proof-Carrying Submission

Vor dem Submit wird ein **Prüfzertifikat** erzeugt:

- alle Pflichtfelder sichtbar/gefüllt,
- Cross-Field-Constraints erfüllt,
- keine Validierungsfehler,
- Erfolgsprädikat definiert (Text/URL/DOM/Netzwerk/Bestätigungsnummer).

Nach dem Submit wird das Prädikat geprüft; das Zertifikat wird signiert und
protokolliert. „Submit geklickt“ ist **kein** Erfolg.

### 4.7 Selbstverbessern: Curriculum + Self-Play

- **Form Designer** generiert Varianten aus einem Formular-Grammatikmodell.
- **Difficulty Estimator** wählt Aufgaben an der Kompetenzgrenze.
- **Filler** versucht sie; Erfolge/Repairs werden zu Skills.
- **Evaluator** misst Transfer, nicht nur Wiederholung.
- **Skill Commons** (optional): signierte Skills teilen, ohne PII; andere Agenten
  können sie übernehmen.

---

## 5. Der Lernzyklus in Pseudocode

```python
def solve(form):
    genome = perceive_and_compile(form)          # DOM + AX + Vision + Probes
    candidates = skill_lattice.retrieve(genome)  # structural + semantic match
    plan = planner.adapt(candidates, genome)     # compose + fill gaps + MPC
    result = executor.run(plan)                  # Playwright Python, real events
    if verifier.success(result):
        skill = induce_skill(genome, plan, result)
        skill_lattice.add_or_update(skill)
        return result
    diagnosis = repair.counterfactual(genome, plan, result)
    repaired = planner.repair(plan, diagnosis)
    result = executor.run(repaired)
    skill_lattice.record_repair(diagnosis, repaired)
    return result

def self_play(rounds):
    for task in curriculum.sample():
        outcome = solve(task.form)
        curriculum.update(task.difficulty, outcome)
        if outcome.success:
            skill_lattice.promote(outcome.skill)
        else:
            skill_lattice.add_negative_case(outcome.diagnosis)
```

---

## 6. Neue Metriken (Innovation messbar machen)

| Metrik | Definition | Warum neu |
|---|---|---|
| **Zero-Shot Form Success (ZFS)** | Erfolg auf nie gesehenen Domains ohne Anpassung | misst echte Generalisierung |
| **k-Shot Adaptation** | Erfolg nach k Versuchen auf neuer Domain | misst Lernkurve |
| **Transfer Slope** | Δ Erfolg / Δ k | wie schnell der Agent lernt |
| **Skill Reuse Rate** | % Felder/Aktionen durch vorhandene Skills gelöst | misst Wissensreuse |
| **Repair Efficiency** | Schritte/Tokens bis zur Reparatur; Reparaturerfolg | misst Selbstheilung |
| **Autonomy Ratio** | Anteil Aktionen ohne menschliche Hilfe | misst Autonomie |
| **Calibration (ECE)** | Konfidenz vs. tatsächlicher Erfolg | misst Selbsteinschätzung |
| **Cost per Success** | Tokens + Zeit + Browser-Schritte | wirtschaftlich |
| **Safety Violation Rate** | Doppel-Submits, unerlaubte Domains, PII-Leaks | Risiko |
| **Proof Validity** | % Submits mit verifiziertem Erfolgszertifikat | Vertrauen |
| **Curriculum Gain** | Verbesserung durch Self-Play vs. ohne | misst Selbstverbesserung |
| **Generalization Gap** | In-Domain- vs. Out-of-Domain-Erfolg | misst Overfitting |
| **Time to First Success** | Zeit bis zum ersten Erfolg auf neuem Formular | Praxistauglichkeit |

### FormBench (Vorschlag)

- 200–500 Formulare aus 20 Domänen (Behörde, Bewerbung, Checkout, Buchung,
  Newsletter, Versicherung, Gesundheitswesen, Bildung).
- **Domain-Split**: Train/Dev/Test nach Domänen, nicht nach URLs – sonst misst
  man Auswendiglernen.
- **Varianten**: Labels, Reihenfolge, Pflichtfelder, Cross-Field, Wizard,
  iframe, Shadow DOM, Custom Widgets, Fehlermeldungen, Datei-Upload.
- **Synthetic**: Form Designer erzeugt Varianten; Test hält Formularfamilien
  zurück.
- **Metriken**: ZFS, k-Shot, Transfer Slope, Reuse, Repair, Autonomie, Kosten,
  Safety, Proof Validity.
- **Externe Anker**: WorkArena-Formular-Subset, Online-Mind2Web-Teilmenge,
  WebArena – aber getrennt ausgewiesen.

---

## 7. Was ist wirklich neu – und was nicht?

### Wirklich neu (der Kern)

1. **Form Genome als explizite Zwischenrepräsentation** für Formular-Agenten
   (nicht DOM, nicht Trace, nicht URL).
2. **Skill Lattice**: transferierbare, komponierbare Formular-Programme mit
   Generalisierungs-/Spezialisierungsrelationen.
3. **Counterfactual Repair Algebra**: minimale kausale Reparatur statt Retry.
4. **Form Designer/Filler Self-Play**: Selbstverbesserung durch selbst erzeugte
   Formularvarianten, ohne Human-Labels.
5. **Proof-Carrying Submission**: verifizierter Erfolg statt „Button geklickt“.
6. **Transfer-Metriken** (ZFS, k-Shot, Transfer Slope, Reuse) statt nur
   Erfolgsquote.

### Nur Kombination bekannter Techniken

- Playwright/DOM/AXTree, LLM, Vision, Constraint-Solver, Trace-Cache,
  Self-Healing, Embeddings. Diese sind Bausteine, nicht die Innovation.
- Die Innovation liegt in **Repräsentation + Transfer + Selbstverbesserung**,
  nicht in einem neuen Browser-Treiber.

### Abgrenzung zu WebXSkill/AgentOccam/SeeAct

- **WebXSkill** lernt Skills, aber primär für Navigation/Aktionen; FORGE
  überträgt **Formular-Programme** über Genome-Alignment und komponiert
  Feld-/Block-/Form-Skills.
- **AgentOccam** optimiert Beobachtung/Aktion; FORGE nutzt das als
  Observation-Compiler, geht aber darüber hinaus durch Genom, Weltmodell und
  Skill-Lattice.
- **SeeAct** grounded Pläne; FORGE nutzt Cross-Modal-Grounding als **eine
  Evidenzquelle** im Genom und kalibriert Feldkonfidenz.
- **OmniParser** parst Screenshots; FORGE nutzt es nur für Felder, die DOM/AX
  nicht erklären, und aligniert visuelle Boxen mit Genom-Slots.

---

## 8. Risiken und harte Grenzen

1. **Synthetic-to-Real-Gap:** Der Form Designer erzeugt vielleicht Formulare,
   die leichter sind als die Realität. Gegenmaßnahme: echte Hold-out-Formulare,
   Domain-Split, externe Benchmarks.
2. **Skill Poisoning:** Ein falscher Erfolg erzeugt einen schlechten Skill.
   Gegenmaßnahme: Proof-Carrying Submission, Statistik, Review, Rollback,
   signierte Provenienz.
3. **PII/Privacy:** Genome und Skills dürfen keine personenbezogenen Werte
   speichern – nur Slots/Semantik; Werte bleiben im Vault.
4. **Prompt Injection:** DOM/AX/Screenshots sind untrusted; Systempolicy bleibt
   außerhalb des Seiteninhalts (OWASP MCP Security).
5. **CAPTCHAs/Anti-Bot:** keine Umgehung; Abbruch und Meldung.
6. **Recht/ToS:** nur erlaubte Formulare; Rate-Limits; keine Massen-Spam.
7. **Komplexität:** Die Architektur ist aufwendig; deshalb zuerst Genome +
   FormBench, nicht der volle Agent.
8. **Benchmark-Contamination:** Keine Testformulare im Curriculum; Domain-Split.

---

## 9. Erster Schritt (ohne vollen Agenten)

**Nicht** mit dem Browser-Agenten beginnen. Zuerst die riskanteste Annahme
testen: **Ist ein Form Genome extrahierbar und zwischen Domains übertragbar?**

1. **Form Genome Extractor** (Playwright Python): 30 reale Formulare aus 5
   Domänen; DOM/AX + optionale Vision; manuell verifiziertes Genom.
2. **FormBench v0**: dieselben 30 + 30 Varianten; Domain-Split.
3. **Genome-Alignment**: Ähnlichkeit zwischen Formularen messen; prüfen, ob
   „Adressblock“-Genome über Domänen matchen.
4. **Skill Induction v0**: 5 wiederkehrende Formulare; Trace → Skill; Transfer
   auf 5 Varianten.
5. **Metriken**: Feld-Extraktions-F1, ZFS, k-Shot, Reuse, Repair-Erfolg.
6. Erst danach: Executor/Verifier/Self-Play ausbauen.

**Erfolgskriterium für den ersten Schritt:** Ein neues Formular aus einer
**unbekannten Domäne** wird nach höchstens 2 Versuchen zu ≥80 % korrekt gefüllt,
und der Agent kann erklären, welche Skills wiederverwendet wurden.

---

## 10. Quellen

- WebArena: <https://webarena.dev>, arXiv:2307.13854
- Mind2Web: <https://osu-nlp-group.github.io/Mind2Web>, arXiv:2306.06070
- WebVoyager: arXiv:2401.13919
- Online-Mind2Web: <https://hal.cs.princeton.edu/online_mind2web>
- WorkArena/BrowserGym: <https://github.com/ServiceNow/WorkArena>,
  <https://github.com/ServiceNow/BrowserGym>, arXiv:2403.07718
- AgentOccam: arXiv:2410.13825
- SeeAct: arXiv:2401.01614
- OmniParser: arXiv:2408.00203,
  <https://github.com/microsoft/OmniParser>
- mForms: arXiv:2011.12340
- WebXSkill: arXiv:2604.13318
- Browser-Use Benchmarks:
  <https://browser-use.com/posts/web-agent-benchmarks>
- Selbstheilende Muster:
  <https://github.com/EPIATBIG/workflow-use>,
  <https://github.com/Huzy85/fantoma>,
  <https://github.com/kunaal-ai/healix>,
  <https://github.com/Shubhambawner/form-filler-agent>
- OWASP MCP Security:
  <https://cheatsheetseries.owasp.org/cheatsheets/MCP_Security_Cheat_Sheet.html>
