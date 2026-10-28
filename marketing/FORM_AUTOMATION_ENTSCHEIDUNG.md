# Formular-Automation: Recherche & Entscheidung

> **Nachtrag 2026-10-28:** Diese Doku ist PayAPI-spezifisch. Die allgemeine,
> benchmarkgestützte Analyse für beliebige Formulare steht in
> [`UNIVERSAL_FORM_AUTOMATION.md`](UNIVERSAL_FORM_AUTOMATION.md).

Stand: 2026-10-28 · Auftrag: Wie kann ein KI-Agent das PayAPI-Market-Formular
(oder ähnliche Formulare) vollautomatisch ausfüllen? Kein Bau ohne Freigabe.

**Kurzfassung:** Für PayAPI ist die beste Lösung **keine Browser-Automation**,
sondern der offizielle MCP-Tool `submit_listing` unter
`https://payapi.market/mcp`. Für Formulare ohne Schreib-API ist **Playwright MCP**
die beste allgemeine Wahl; **browser-use** ist die Python-Alternative, wenn ein
LLM den Weg selbst entscheiden soll. Stagehand/Browserbase und Skyvern sind
Optionen für geschützte/komplexe Portale; echte Computer-Use ist nur Fallback.

---

## 1. Anforderungen aus E-Mail und Playbook

Chet Parker (PayAPI) und das Provider-Playbook nennen:

| Anforderung | Bedeutung |
|---|---|
| Stabile HTTPS-URL | Kein Tunnel, keine Sandbox-Domain, kein Login |
| HTTP 402 unbezahlt | Preis, Netz, Wallet im Challenge |
| Bezahlt: HTTP 200 + echte Daten | Kein Stub, kein leeres Demo-JSON |
| Netz `eip155:8453` | Base Mainnet |
| Asset | Kanonisches USDC |
| `payTo` | Exakt die Wallet aus dem Listing-Formular |
| `extra.name` | Exakt `"USD Coin"` (nicht `"USDC"`) |
| Preis | Live-Challenge = Listing-Preis |
| Kein Free-Leak | Unbezahlt keine Produktdaten |
| Ein Produkt = ein Listing | Keine Sub-Pfade als separate Karten |
| Paid Canary | PayAPI zahlt einmal klein (bis 0,10 USDC) und prüft echte Daten |
| Menschliche Freigabe | Badge erst nach Review, nie automatisch |

Formularfelder (Playbook + MCP-Schema): API-Name, Base-URL, Wallet, Preis,
Kategorie, Beschreibung, Kontakt-E-Mail. Die Live-Seite ist eine React/SPA;
`OPTIONS /api/listings` erlaubt nur `GET, OPTIONS` – einen öffentlichen
Create-Endpunkt für das Formular gibt es nicht. Das Formular prüft die URL
vor dem Anlegen (402, `payTo`, Host-Stabilität).

### Status der bestehenden M2-Instanz

Die zweite Instanz `/api/attest-v2` erfüllt die technischen Punkte: 402
unbezahlt, `extra.name="USD Coin"`, 0,01 USDC, Base/USDC, gleiche Wallet,
Discovery `/.well-known/x402`, bezahlt signierte Attestierung. Ein Browser-Request
(`Accept: text/html` + Mozilla-UA) löste zunächst einen 500er in der
x402-Paywall aus; die Ursache (`paywall_config` als dict statt `PaywallConfig`)
ist behoben, beide Instanzen antworten browser-like mit 402 (getestet
2026-10-28).

---

## 2. Zentraler Fund: PayAPI hat einen offiziellen MCP-Schreibpfad

PayAPI veröffentlicht:

- `https://payapi.market/.well-known/mcp.json`
- MCP-Server: `https://payapi.market/mcp` (Streamable HTTP, stateless, **keine Auth**)
- Tools: `search_apis`, `list_apis`, `get_api`, **`submit_listing`**

`submit_listing` ist kein Lese-Tool: Es validiert, preflightet und legt eine
Listung **pending review** an. Es setzt nie `payment_verified` und schaltet nie
live. Rate-Limits: 10 Einreichungen/Stunde pro Wallet und E-Mail, 50/Tag pro IP
und `payTo`. Bei gleicher Wallet + gleicher API kommt die bestehende Listing-ID
zurück.

Pflichtfelder des Tools:

```json
{
  "name": "Reise-Agent Attest v2 (PayAPI)",
  "description": "Ed25519-signed travel price attestations ...",
  "base_url": "https://travel.hanibal-ai.com",
  "paid_route_url": "https://travel.hanibal-ai.com/api/attest-v2",
  "price": 0.01,
  "networks": ["base"],
  "payTo": "0x1cE5379a485a0bd726fce57BbfDfc316b0D35Cc4",
  "contact_email": "batniniabdelkader@yahoo.com",
  "category": "Data",
  "sample_input": "{\"route\":\"BER-FCO\",\"travel_date\":\"2026-11-05\",\"price\":\"129.99\",\"currency\":\"EUR\",\"price_scope\":\"per_person\",\"source\":\"payapi\"}",
  "provider_name": "Reise-Agent"
}
```

**Konsequenz:** Für PayAPI brauchen wir keinen Browser, kein Node.js, keine
CAPTCHA-Lösung und keine Formular-Selektoren. Der MCP-Aufruf ist der vom
Anbieter dokumentierte Maschinenweg. Wir haben nur `tools/list` gelesen und
**nichts eingereicht**.

---

## 3. Recherchierte Techniken

### 3.1 PayAPI MCP `submit_listing` (API-first)

- **Interaktion:** JSON-RPC `tools/call` über HTTP; keine UI.
- **Voraussetzungen:** Python + `httpx` oder ein beliebiger MCP-Client; kein Node.
- **Komplexe Formulare:** entfällt – das Schema ist strikt, `additionalProperties: false`.
- **Autonomie:** vollautomatisch möglich; danach menschliche PayAPI-Review.
- **Grenzen:** Rate-Limits, Pflichtfelder, `category`-Enum, keine garantierte
  Sofort-Listung; Canary/Review bleibt.
- **Erster Schritt:** Payload vorbereiten, `submit_listing` einmal aufrufen,
  Antwort/Listing-ID speichern, mit `get_api` prüfen.

### 3.2 Playwright MCP (Microsoft, offiziell)

- **Interaktion:** Accessibility-Snapshots mit stabilen Refs (`e12`);
  `browser_fill_form` füllt Textboxen, Checkboxen, Radios, Comboboxen und
  Slider in einem Aufruf; `browser_click` submitet; `browser_snapshot` prüft.
- **Voraussetzungen:** Node.js 20+, `npx @playwright/mcp@latest`, Browser;
  jeder MCP-Client. Lokal vorhanden (Node 22), auf Production **nicht**.
- **Komplexe Formulare:** sehr gut bei klaren Labels/Rollen; dynamische
  Validierungen brauchen Re-Snapshot/Retry.
- **Autonomie:** vollautomatisch, aber LLM nötig; Snapshot-Inhalte sind
  untrusted (Prompt-Injection-Risiko).
- **Grenzen:** keine CAPTCHA-Lösung; Anti-Bot kann blocken; Node-Abhängigkeit.
- **Erster Schritt:** Server headless/isolated starten, Formular navigieren,
  Snapshot lesen, `browser_fill_form`, Submit, Erfolgstext verifizieren.

### 3.3 browser-use (Python, LLM-Agent)

- **Interaktion:** LLM liest DOM/Accessibility (optional Vision) und führt
  Aktionen aus; Form-Filling ist ein dokumentierter Standardfall (Text,
  Dropdown, Radio, Checkbox, Upload).
- **Voraussetzungen:** Python 3.11+, `browser-use`, LLM (ChatBrowserUse-Key
  oder eigener Provider), Chromium.
- **Komplexe Formulare:** gut bei unbekannten Formularen, aber weniger
  deterministisch als Playwright MCP; Token-Kosten und Modellvarianz.
- **Autonomie:** vollautomatisch; Retries/`max_failures` möglich.
- **Grenzen:** LLM-Halluzination, Kosten, schwieriger zu testen; Datenschutz
  bei sensiblen Feldern.
- **Erster Schritt:** `pip install browser-use`, Modell konfigurieren,
  Trockenlauf gegen ein Testformular, dann PayAPI-ähnliches Formular.

### 3.4 Stagehand / Browserbase MCP

- **Interaktion:** natürliche Sprache `act`, `observe`, `extract`; Actions
  können nach `observe` gecacht und deterministisch wiederholt werden.
- **Voraussetzungen:** Node/TypeScript (oder Python-SDK), Browserbase-Account
  + API-Key, Modell; hosted MCP unter `https://mcp.browserbase.com/mcp`.
- **Komplexe Formulare:** sehr gut; Cloud-Browser, Session Replay, optional
  Verified/Proxies gegen Bot-Schutz.
- **Autonomie:** vollautomatisch; Infrastruktur/Kosten extern.
- **Grenzen:** Cloud-Abhängigkeit, API-Key, Kosten, Datenresidenz.
- **Erster Schritt:** Browserbase-Key, MCP-Client konfigurieren, `observe`
  gegen das Formular, dann `act`.

### 3.5 Skyvern

- **Interaktion:** Vision-LLM + Playwright; füllt Formulare auf unbekannten
  Seiten, Workflows/SDK/REST/MCP; `fill_form` in neueren Versionen.
- **Voraussetzungen:** Python 3.11+, Self-Hosting (Docker/DB) oder Cloud-Key;
  AGPL-3.0; Anti-Bot nur in der Cloud.
- **Komplexe Formulare:** stark bei unbekannten/visuellen Formularen; höherer
  Betriebsaufwand.
- **Autonomie:** vollautomatisch, aber schwere Infrastruktur.
- **Grenzen:** AGPL, Ressourcen, Overkill für ein bekanntes Formular.
- **Erster Schritt:** Cloud-API-Key oder Docker-Compose, Testlauf mit einer
  URL + Zielbeschreibung.

### 3.6 Chrome DevTools MCP (Google, offiziell)

- **Interaktion:** Accessibility-Snapshot + `fill_form` für Inputs/Selects/
  Checkboxen/Radios; zusätzlich Netzwerk/Performance/Debugging.
- **Voraussetzungen:** Node + Chrome.
- **Komplexe Formulare:** gut, ähnlich Playwright MCP; Fokus eher Debugging.
- **Grenzen:** Chrome/Node, keine eingebaute CAPTCHA-Lösung.
- **Erster Schritt:** `npx chrome-devtools-mcp@latest`, `fill_form` gegen das
  Formular.

### 3.7 Browser MCP / mcpwright / Computer-Use

- **Browser MCP:** nutzt den echten Chrome-Profil/Extension; gut für
  eingeloggte Portale, aber manuelle Freigabe und Desktop-Browser nötig –
  **nicht** für unbeaufsichtigten Serverbetrieb.
- **mcpwright:** dünner Playwright-MCP-Wrapper mit `smart_wait`,
  `react_aware_type`, Retry; kleines Projekt, eher Muster als Produktionsbasis.
- **Computer-Use/Vision:** Screenshots + Koordinaten; robust gegen exotische
  UIs, aber teuer, langsam und fehleranfällig; nur Fallback.

---

## 4. Vergleichsmatrix

Bewertung 1 (schlecht) bis 5 (sehr gut); „Aufwand“ aus Projektsicht.

| Technik | Interaktion | Abhängigkeiten | Aufwand | Komplexe Formulare | Ohne Mensch | PayAPI-Eignung | Kosten/Risiko |
|---|---|---|---|---|---|---|---|
| **PayAPI MCP `submit_listing`** | JSON-RPC-Tool | Python/httpx oder MCP-Client | **1** | **5** (Schema statt UI) | **5** | **5** | Rate-Limits, Review |
| **Playwright MCP** | Accessibility-Refs, `fill_form` | Node 20+, Browser, LLM | 3 | **4** | 4 | 3 (durch MCP ersetzt) | Prompt-Injection, Anti-Bot |
| **browser-use** | LLM + DOM/A11y, optional Vision | Python 3.11+, LLM-Key, Chromium | 3 | 4 | 4 | 3 | Tokenkosten, Varianz |
| **Stagehand/Browserbase** | `act`/`observe`/`extract` | Node/TS, Browserbase-Key, Modell | 4 | **5** | 5 | 3 | Cloud-Kosten, Datenresidenz |
| **Skyvern** | Vision + LLM, Workflows | Python, Docker/DB oder Cloud, AGPL | **5** | **5** | 4 | 2 | schwer, AGPL |
| **Chrome DevTools MCP** | A11y + `fill_form` | Node + Chrome | 3 | 4 | 4 | 3 | wie Playwright |
| **Browser MCP** | echter Chrome + Extension | Chrome, Node, manuelle Freigabe | 3 | 4 | **2** | 2 | nicht unbeaufsichtigt |
| **mcpwright** | Playwright-MCP-Wrapper | Chrome-Profil, kleines Projekt | 3 | 3 | 3 | 1 | Wartungsrisiko |
| **Computer-Use/Vision** | Screenshots + Klicks | multimodales Modell | 4 | 3 | 3 | 1 | teuer, fragil |
| **Direkter HTTP/Supabase-Hack** | interne API | keine offizielle API | 4 | – | 4 | **0** | inoffiziell, RLS/ToS |

---

## 5. Entscheidung

### Für PayAPI: MCP `submit_listing` (primär)

Begründung:

1. **Offizieller, dokumentierter Schreibweg** – kein Reverse Engineering der
   SPA/Supabase-Tabellen.
2. **Keine Browser-Abhängigkeit** – Production hat kein Node; Python/httpx
   reicht.
3. **Keine CAPTCHA-/Anti-Bot-/Selektor-Probleme**; das Formular würde bei
   Änderungen brechen.
4. **Striktes Schema** mit Validierung/Preflight; weniger Fehlbedienung.
5. **Idempotenz-Hinweis** im Tool (gleiche Wallet + API → bestehende ID).

### Für allgemeine Formulare ohne Schreib-API: Playwright MCP

- Beste Balance aus offizieller Pflege, deterministischen Accessibility-Refs,
  `browser_fill_form` für alle Feldtypen und breiter MCP-Client-Unterstützung.
- Nachteil Node; für Production müsste Node installiert werden (oder ein
  separater Browser-Runner-Container).

### Python-only-Alternative: browser-use

- Wenn kein Node gewünscht ist und das Formular unbekannt/wechselnd ist.
- Weniger deterministisch; nur mit Trockenlauf und klaren Feld-Mappings.

### Nicht empfohlen für PayAPI

- **Stagehand/Browserbase** und **Skyvern**: technisch stark, aber für ein
  einziges bekanntes Formular mit offizieller MCP-API Overkill und externe
  Kosten.
- **Browser MCP**: Desktop-Profil und manuelle Freigabe.
- **Computer-Use**: teuer/fragil.
- **Direkter Supabase-Zugriff**: inoffiziell, RLS/ToS-Risiko.

---

## 6. Vorschlag / erste Schritte (kein Bau)

### A. PayAPI per MCP (empfohlen)

1. Werte festlegen: URL, Wallet, Preis 0,01, Kategorie `Data`, Kontakt.
2. **Einmalige Freigabe** für den schreibenden `submit_listing`-Aufruf.
3. JSON-RPC:

```python
import httpx, json

payload = {
    "name": "Reise-Agent Attest v2 (PayAPI)",
    "description": "Ed25519-signed travel price attestations ...",
    "base_url": "https://travel.hanibal-ai.com",
    "paid_route_url": "https://travel.hanibal-ai.com/api/attest-v2",
    "price": 0.01,
    "networks": ["base"],
    "payTo": "0x1cE5379a485a0bd726fce57BbfDfc316b0D35Cc4",
    "contact_email": "batniniabdelkader@yahoo.com",
    "category": "Data",
    "provider_name": "Reise-Agent",
}
call = {
    "jsonrpc": "2.0", "id": 1, "method": "tools/call",
    "params": {"name": "submit_listing", "arguments": payload},
}
r = httpx.post("https://payapi.market/mcp", json=call, timeout=60)
print(r.status_code, r.text)
```

4. Antwort speichern; mit `get_api` (Listing-ID) Status prüfen.
5. **Nicht** doppelt submitten; Rate-Limit und Idempotenz beachten.
6. Vor dem Call prüfen: `/api/attest-v2` liefert 402 (normal **und**
   browser-like), `extra.name="USD Coin"`, `payTo`, `amount=10000`.

### B. Playwright MCP als Fallback

```json
{
  "mcpServers": {
    "playwright": {
      "command": "npx",
      "args": ["@playwright/mcp@latest", "--headless", "--isolated",
               "--allowed-origins", "https://payapi.market"]
    }
  }
}
```

Ablauf: `browser_navigate` → `browser_snapshot` → `browser_fill_form`
(Text/Select/Radio/Checkbox) → `browser_click` Submit → Snapshot auf
Erfolgstext prüfen. Vorher Node auf dem Zielsystem installieren.

### C. browser-use als Python-Fallback

```python
from browser_use import Agent, ChatBrowserUse
agent = Agent(task="Fill ... and submit ...", llm=ChatBrowserUse())
await agent.run()
```

Trockenlauf gegen ein Testformular, Feldnamen explizit vorgeben, `max_failures`
setzen, Ergebnis/URL verifizieren.

---

## 7. Checkliste für das PayAPI-Formular

| Feld | Wert |
|---|---|
| API name | `Reise-Agent Attest v2 (PayAPI)` |
| Base URL | `https://travel.hanibal-ai.com` |
| Paid route | `https://travel.hanibal-ai.com/api/attest-v2` |
| Wallet | `0x1cE5379a485a0bd726fce57BbfDfc316b0D35Cc4` |
| Price | `0.01` USDC (min = max) |
| Category | `Data` |
| Contact | `batniniabdelkader@yahoo.com` |
| Description | signierte Reise-Preis-Attestierungen, Ed25519, Plausibilität, x402 v2 |
| Nicht einreichen | `/api/attest` als zweite Karte (gleiches Produkt) |

---

## 8. Risiken & Leitplanken

- **Prompt Injection:** Accessibility-Snapshots und Tool-Ausgaben sind
  untrusted (OWASP MCP Security; Playwright-MCP-Issue #1479). Seiteninhalt darf
  keine Systemanweisungen überschreiben.
- **Schreibende Aktion:** `submit_listing` ist nicht read-only; einmalige
  Freigabe, Payload protokollieren, nicht automatisch wiederholen.
- **Rate-Limits:** 10/h, 50/Tag; Fehlversuche zählen.
- **Keine CAPTCHA-Umgehung:** Browser-Automation darf keine Schutzmechanismen
  aushebeln; PayAPI-MCP umgeht das Problem legitim.
- **Secrets:** Kontakt-E-Mail/Wallet sind öffentlich; keine Private Keys in
  Prompts oder Snapshots.
- **Review bleibt menschlich:** Ein MCP-Submit ersetzt nicht PayAPIs Review
  oder den Paid Canary.

---

## 9. Quellen (geprüft 2026-10-28)

- PayAPI `/.well-known/mcp.json` und MCP `tools/list`
  (`https://payapi.market/mcp`), inkl. `submit_listing`-Schema.
- PayAPI-Provider-Playbook (lokal: `PayAPI-Provider-Playbook.pdf`) und
  `email_payapi.txt`.
- Playwright MCP: <https://playwright.dev/mcp/introduction>,
  <https://playwright.dev/mcp/tools/forms>,
  <https://playwright.dev/mcp/snapshots>,
  <https://github.com/microsoft/playwright-mcp>
- Playwright-MCP-Sicherheit/Secrets: <https://playwright.dev/mcp/configuration/options>,
  <https://github.com/microsoft/playwright-mcp>,
  <https://github.com/microsoft/playwright-mcp/issues/1479>
- browser-use: <https://docs.browser-use.com/open-source/quickstart>,
  <https://github.com/browser-use/browser-use>,
  <https://browser-use.com/form-filling>
- Stagehand/Browserbase: <https://docs.stagehand.dev/v3/integrations/mcp/introduction>,
  <https://docs.browserbase.com/use-cases/automating-form-submissions>,
  <https://docs.stagehand.dev/v3/basics/observe>
- Skyvern: <https://github.com/Skyvern-AI/skyvern>,
  <https://www.skyvern.com/docs>
- Chrome DevTools MCP: <https://developer.chrome.com/docs/devtools/agents/get-started>,
  <https://github.com/ChromeDevTools/chrome-devtools-mcp>
- Browser MCP: <https://browsermcp.io/>, <https://github.com/BrowserMCP/mcp>
- mcpwright: <https://github.com/raghavsaiassistant-wq/mcpwright>
- OWASP MCP Security Cheat Sheet:
  <https://cheatsheetseries.owasp.org/cheatsheets/MCP_Security_Cheat_Sheet.html>
