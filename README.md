# Reise-Agent (travel)

Unabhängiger Reise-Preisvergleich für Flüge, Hotels, Fähren und Kreuzfahrten –
mit **x402-bezahlten, signierten Preis-Attestierungen** für autonome Agenten.

Keine Buchung, keine Zahlung für Reisen: Die Anwendung vergleicht Preise aus
mehreren Quellen, prüft sie auf Plausibilität und leitet zum Anbieter weiter.

## PayAPI Market

Die Route **`/api/attest-v2`** ist bei [PayAPI Market](https://payapi.market) gelistet –
suche dort nach **„Travel-Agent Price Attestation"**. PayAPI Market hat die Listung am
**2026-10-28** verifiziert. Agenten finden die Route über den PayAPI-MCP-Server
`https://payapi.market/mcp`. Zusätzlich ist sie im **Coinbase x402 Bazaar** indexiert
(402-Antwort enthält `extensions.bazaar`).

## Architektur

```
Browser/Agent
   │ HTTPS
   ▼
Caddy (TLS, Reverse Proxy) ──► 127.0.0.1:8077
                                  │ FastAPI/uvicorn
                                  ├─ ui/          Web-UI + API
                                  ├─ providers/   Multi-Quellen-Abfrage
                                  ├─ resolver/    Orte → IATA/Hafen
                                  ├─ bundling/    Bündelung
                                  ├─ alerts/      Preiswächter
                                  ├─ seo/         Kategorien/Routen/JSON-LD
                                  └─ attest/      x402-Preis-Attestierungen
```

## Schnellstart (lokal)

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-runtime.txt
.venv/bin/python -m uvicorn ui.app:app --host 127.0.0.1 --port 8077
```

Danach: <http://127.0.0.1:8077>

## CI

* GitHub Actions: [`.github/workflows/ci.yml`](.github/workflows/ci.yml)
* Lokal (gleiche Prüfungen): `./scripts/ci.sh`

> GitHub-hosted Runner benötigen ein aktives Actions-Guthaben. Meldet GitHub
> „recent account payments have failed …", ist das ein Billing-Thema im
> Account (Settings → Billing & plans), kein Fehler im Workflow. Der Workflow
> ist mit `./scripts/ci.sh` lokal reproduzierbar.

## Tests

```bash
python -m unittest attest.tests.test_attest_unit attest.tests.test_billing
python attest/tests/test_x402_flow.py     # 402 → Zahlung → Signatur (Mock-Facilitator)
python attest/tests/test_legal.py         # legal.yaml: noindex/index
python attest/tests/test_discovery.py     # llms.txt + agent-payments.json
python resolver/tests/test_resolver.py
python affiliate/tests/test_affiliate.py
python seo/tests/test_seo.py
```

## x402-Attestierungen

* `POST /api/attest` – kostenpflichtig (USDC, x402 v2)
* `POST /api/attest/validate` – kostenlose Vorprüfung
* `POST /api/attest/verify` – Signaturprüfung
* `GET /.well-known/agent-payments.json` – Discovery
* `GET /llms.txt` – Agenten-Dokumentation

Konfiguration: `attest/config.yaml` (Netz, Preis, Facilitator, Auth).
Testnet → Mainnet ist reine Konfiguration, kein Code.

## Deployment

Siehe [`docs/DEPLOY_CONTABO.md`](docs/DEPLOY_CONTABO.md).

```bash
./deploy/contabo.sh
```

Push auf `main` deployt automatisch: GitHub Actions führt erst die Tests aus
und ruft danach den Deploy-Job auf (SSH/rsync + `systemctl restart`).

Zusätzlich läuft auf dem Server ein **2-Minuten-Auto-Deploy-Timer**
(`travel-deploy.timer`): er zieht `main` aus GitHub und deployt auch dann, wenn
GitHub-hosted Actions wegen Account-Billing nicht starten.

## Recht & Steuern

* Impressum/Datenschutz: `ui/legal.yaml` (Vorlage; Pflichtfelder ausfüllen).
* Rechnungsledger: `attest/billing.py` (`attest/state/invoices.jsonl`).
* Steuerhinweise: `attest/README.md`, Abschnitt 9.

## Lizenz / Status

Privates Projekt. Keine Buchungs- oder Zahlungsfunktion für Reisen.
