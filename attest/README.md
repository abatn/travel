# M2: Verifizierte Preis-Attestierungen (x402)

> **Aktueller Stand:** `config.yaml` läuft auf **Base Mainnet** mit dem
> **Coinbase CDP Facilitator** (Preis 0,01 USDC). Testnet-Werte und der
> kostenlose Einstieg stehen in Abschnitt 1/2.

Ein Agent zahlt **pro Attestierung** in USDC (x402, HTTP 402) und erhält ein
signiertes JSON-Dokument mit Route, Preis, Quelle, Zeitstempel und
Plausibilitätsprüfung. Kein Konto, kein API-Key, keine Buchung.

```
POST /api/attest            → 402 + PAYMENT-REQUIRED (x402 v2)
                            → mit PAYMENT-SIGNATURE: 200 + signiertes Dokument
POST /api/attest/validate   → kostenlose Vorprüfung
POST /api/attest/verify     → Signatur prüfen
GET  /api/attest/key        → öffentlicher Ed25519-Schlüssel
GET  /.well-known/agent-payments.json → Discovery (Preis, Netz, payTo, Facilitator)
```

## 1. Facilitator: OpenFacilitator vs. CDP – nur Konfiguration

Der Code baut immer denselben `HTTPFacilitatorClient`; unterschiedlich sind nur
`url` und `auth`. Umgestellt wird in `attest/config.yaml` oder per Env – **keine
Code-Änderung**.

| | Testnet (Default) | Mainnet |
|---|---|---|
| Netz | `eip155:84532` (Base Sepolia) | `eip155:8453` (Base) |
| Asset | USDC `0x036C…CF7e` | USDC `0x8335…2913` |
| Facilitator | `https://pay.openfacilitator.io` oder `https://x402.org/facilitator` | `https://api.cdp.coinbase.com/platform/v2/x402` |
| Auth | `none` | `cdp_jwt` (`CDP_API_KEY_ID`, `CDP_API_KEY_SECRET`) |

Mainnet-Umschaltung (nur diese Zeilen):

```yaml
payment:
  network: "eip155:8453"
  asset: "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
  facilitator:
    url: "https://api.cdp.coinbase.com/platform/v2/x402"
    auth:
      mode: "cdp_jwt"
      key_id_env: "CDP_API_KEY_ID"
      key_secret_env: "CDP_API_KEY_SECRET"
      alg: "auto"          # ES256 oder EdDSA
```

Oder ohne Dateiänderung:

```bash
export ATTEST_NETWORK=eip155:8453
export ATTEST_FACILITATOR_URL=https://api.cdp.coinbase.com/platform/v2/x402
export ATTEST_FACILITATOR_AUTH=cdp_jwt
export CDP_API_KEY_ID=...
export CDP_API_KEY_SECRET=...
```

## 2. Live-Befund vom 23.10.2026 (Base Sepolia)

**OpenFacilitator** (`https://pay.openfacilitator.io`):

* `/supported` enthält `eip155:84532` → **protokollseitig ausreichend**.
* 402-Challenge, Preis (2000 Atomic = 0,002 USDC), Asset, `payTo` und
  Discovery funktionieren.
* **Settlement schlägt derzeit fehl:**
  `{"success": false, "errorReason": "Facilitator has insufficient ETH for gas"}`
  → Das Gas-Wallet des öffentlichen Facilitators ist leer. Das ist kein Fehler
  unserer Integration; derselbe Request funktioniert mit einem anderen Facilitator.

**x402.org** (`https://x402.org/facilitator`, testnet-only):

* `/supported` enthält `eip155:84532`; Settlement-Pfad ist gesund.
* Fehler mit ungedfundeter Test-Wallet:
  `invalid_exact_evm_insufficient_balance` → erwartet, der Payer hat 0 USDC.
* Ein Zeilenwechsel genügt:
  `ATTEST_FACILITATOR_URL=https://x402.org/facilitator`.

**Fazit:** OpenFacilitator ist als kostenloser Einstieg richtig, aber für einen
zuverlässigen Live-Test heute nicht ausreichend (Gas). x402.org ist der
funktionierende Testnet-Fallback; CDP ist der Weg für Mainnet.

## 3. Vollständiger Test ohne Chain-Guthaben

`attest/tests/test_x402_flow.py` startet einen wire-kompatiblen
Test-Facilitator (`/supported`, `/verify`, `/settle`) und prüft den kompletten
Ablauf inklusive Signatur:

```bash
.venv-x402/bin/python -m pytest attest/tests/test_x402_flow.py -s
# oder direkt:
.venv-x402/bin/python attest/tests/test_x402_flow.py
```

Getestet wird: 402 → Payment-Signatur → Verify → Settle → 200 → Ed25519-Signatur
→ `/api/attest/verify` = `true`. Der Facilitator ist dabei nur eine URL.

## 4. Live-Test (sobald die Payer-Wallet USDC hat)

```bash
# 1. Wallet erzeugen (einmalig)
.venv-x402/bin/python -m attest.client --generate-key

# 2. Adresse mit Base-Sepolia-USDC füllen (0,01 USDC genügen; 0,002 pro Call)
#    Circle-Faucet: https://faucet.circle.com (Base Sepolia, 20 USDC/2h)

# 3. Server + Client
.venv-x402/bin/python -m uvicorn ui.app:app --port 8077
.venv-x402/bin/python -m attest.client --key-file attest/keys/buyer.key
```

Der Client zeigt `HTTP 200`, die Attestierung, die Signaturprüfung und die
Settlement-Transaktion.

## 5. Sicherheit / Betrieb

* `attest/keys/issuer.ed25519` wird beim ersten Start erzeugt (0600). Es ist der
  Vertrauensanker aller Attestierungen – nicht ins Repo.
* Käufer-Keys (`attest/keys/buyer.key`) sind Testgeld, trotzdem 0600.
* Der Dienst signiert **Beobachtungen**, keine Buchungsgarantien. Das steht als
  `terms.meaning` im Dokument.
* Preise werden als String ausgegeben (keine Float-Rundung).
* `ATTEST_ENABLED=0` deaktiviert die Routen vollständig.
* Fehlt das `x402`-Paket (System-Python), startet die UI normal weiter; die
  Attestierungs-Routen sind dann nicht vorhanden.

## 6. Dateien

| Datei | Zweck |
|---|---|
| `config.yaml` | Netz, Preis, payTo, Facilitator, Auth |
| `routes.py` | `/api/attest`, Discovery, Verify, Key |
| `x402_gate.py` | Middleware + Facilitator-Auswahl |
| `auth.py` | `none` / `bearer` / `cdp_jwt` (ES256/EdDSA) |
| `signing.py` | Ed25519, kanonisches JSON |
| `plausibility.py` | Bereich, Datum, Frische, Quelle, Preisbasis |
| `client.py` | Test-Client (402-Probe, zahlen, verifizieren) |
| `tests/mock_facilitator.py` | wire-kompatibler Facilitator für Tests |

## 7. Live-Nachweis (23.10.2026, Base Sepolia)

**Facilitator:** OpenFacilitator weiterhin ohne Gas
(`{"success":false,"errorReason":"Facilitator has insufficient ETH for gas"}`).
Deshalb für diesen Test per Env auf `https://x402.org/facilitator` gewechselt –
keine Code-Änderung.

| | Wert |
|---|---|
| Payer | `0xbD9345754b1b712b4db7aa43dB9189A339599d59` |
| payTo | `0x1cE5379a485a0bd726fce57BbfDfc316b0D35Cc4` |
| Betrag | 0,002 USDC (2000 atomic) |
| Tx 1 | `0xd2edffc6efeb9fc9e4361f31d5c2ca08c136f86b905fc8c98bed8b021311bcd4` |
| Tx 2 | `0x934985b8ae7e5bf2495a0718e529812319f2336551c9a2ca2729d8d6bd8b376c` |
| Block | 49.284.278 (Tx 2), Status `1`, 85.720 Gas |
| Transfer | `0xbD93…9d59 → 0x1cE5…5Cc4`, 0.002 USDC |
| Attestierung | `att_91a8d6b58c2b4b71b01424994bb0dacf` (`artifacts/attestation_live2.json`) |
| Signaturprüfung | `{"valid": true, "key_id": "4EATUjoV9o_YvC8z"}` |
| Tamper-Test | Preis manipuliert → `{"valid": false}` |
| Guthaben | Payer 20,000 → 19,996 · payTo 20,000 → 20,004 USDC |

Explorer:
`https://sepolia.basescan.org/tx/0x934985b8ae7e5bf2495a0718e529812319f2336551c9a2ca2729d8d6bd8b376c`


## 8. Mainnet-Status (23.10.2026)

`config.yaml` ist auf Base Mainnet + CDP umgestellt (ohne Code-Änderung):

* Netz `eip155:8453`, Asset `0x8335…2913` (USDC), Preis `$0.01`.
* `GET https://api.cdp.coinbase.com/platform/v2/x402/supported` → **HTTP 200**,
  29 Payment-Kinds, darunter `eip155:8453` / `exact` (JWT-Auth funktioniert).
* 402-Challenge mainnet: `10000` atomic (0,01 USDC), korrektes Asset und payTo.
* **Settlement noch offen:** Payer `0xbD93…9d59` hat auf Base Mainnet 0 USDC
  (Base-Block 52.996.663). CDP `/verify` revertiert daher mit `invalid_payload`
  (kein On-Chain-Transfer, kein Tx-Hash).

Sobald 0,01 USDC (Base Mainnet, Contract `0x8335…2913`) auf der Payer-Wallet
liegen, genügt:

```bash
.venv-x402/bin/python -m attest.client --key-file attest/keys/buyer.key --network eip155:8453
```

## 9. Steuern & Rechnungen (keine Steuerberatung)

**Rechnungsledger:** `attest/billing.py` schreibt pro erfolgreicher Attestierung
eine Zeile nach `attest/state/invoices.jsonl` (Betrag, Datum, Tx-Hash, Payer,
payTo, Leistung, Netz, Attestierungs-ID) und kann als CSV exportiert werden:

```bash
.venv-x402/bin/python -m attest.billing --json
.venv-x402/bin/python -m attest.billing --csv attest/artifacts/invoices.csv
```

Jeder Rechnungsdatensatz enthält `supplier_tax_id` – die Steuernummer des
Leistenden (hier die tunesische MwSt-IdNr. aus `ui/legal.yaml -> betreiber.
umsatzsteuer_id`, überschreibbar über `ATTEST_TAX_ID`). Ohne echte Nummer bleibt
das Feld leer; erfundene Werte entstehen nie.

**Pflichten, die vor dem ersten Euro zu klären sind:**

* **USt-IdNr. / BZSt:** USt-IdNr. beim Bundeszentralamt für Steuern beantragen.
  Für EU-B2C-e-Dienstleistungen über 10.000 € gilt das Bestimmungslandprinzip;
  die Registrierung für den **One-Stop-Shop (OSS)** erfolgt beim BZSt, die
  Erklärungen werden vierteljährlich über das BZSt-Portal abgegeben.
* **KStTG (Kryptowerte-Steuertransparenz-Gesetz, seit 24.12.2025):** Meldepflichten
  gelten erstmals für 2026; Registrierung von Kryptowerte-Betreibern nach § 17
  KStTG, Meldungen bis 31.07. des Folgejahres an das BZSt. **Prüfen lassen**, ob
  die reine Annahme von USDC als Zahlung für eigene Dienstleistungen als
  Kryptowerte-Dienstleistung gilt (nach hiesiger Einschätzung eher nein – das ist
  keine Rechtsberatung).
* **Rechnung nach § 14 UStG:** vollständiger Name/Anschrift von Leistendem und
  Empfänger, Steuernummer/USt-IdNr., Ausstellungsdatum, fortlaufende
  Rechnungsnummer, Leistungsbeschreibung, Entgelt, Steuersatz und Steuerbetrag.
  Bei Kleinbeträgen (§ 33 UStDV) gelten Erleichterungen.
* **Krypto-Buchhaltung:** USDC-Zugang mit EUR-Wert am Zugangstag (EZB-Kurs)
  bewerten, Tx-Hash und Wallet dokumentieren, spätere Veräußerung getrennt
  erfassen. Aufbewahrung nach § 147 AO (in der Regel 8–10 Jahre).
* **MiCA / KYC:** Der Facilitator (CDP) führt KYT/Sanktionsprüfungen durch.
  Eigene Pflichten (Geldwäsche, Sanktionen) mit Steuerberater/Rechtsanwalt klären.
* **Kein Chargeback:** USDC-Settlements sind irreversibel; Rückerstattung nur als
  neue Transaktion. Preis/AGB entsprechend gestalten.

## 10. Discovery & Registrierung

* `GET /llms.txt` – Kurzbeschreibung, Preis, Ablauf, Grenzen (aus `llms.txt` im
  Root, `{{BASE_URL}}` wird dynamisch ersetzt).
* `GET /.well-known/agent-payments.json` – vollständige Discovery inkl.
  `resources`, `accepts`, `provider`, `contact` und `extensions.bazaar`.
* `GET /.well-known/x402.json` – x402-Manifest (x402Version 2, Ressource,
  `accepts`, `outputSchema`) für Saylor Agent Bazaar und andere Manifest-Indexer.
* Der 402-Response (Header `payment-required`) enthält `resource`, `accepts` und
  dieselbe Bazaar-Erweiterung `extensions.bazaar` wie die Discovery-Datei.

**Automatische Aufnahme (kein Formular, offizielle Quellen):**

* **CDP-Bazaar:** „There is no separate registration step." Der Facilitator
  katalogisiert die Ressource nach dem **ersten erfolgreichen Settlement**
  (dafür muss das Zahlungs-Payload `paymentPayload.resource` enthalten – die
  offizielle x402-Python-SDK setzt es). Quelle:
  <https://docs.cdp.coinbase.com/x402/bazaar>.
* **Statusprüfung:** `POST https://api.cdp.coinbase.com/platform/v2/x402/validate`
  mit `{"resource": "…/api/attest"}` – alle Preflight-Checks, insbesondere
  `returns_402`, müssen `passed: true` sein. Suchindex:
  `GET …/discovery/search?query=…` (Stand 24.10.2026: `query=hanibal` → 1 Treffer).
* **GET/HEAD müssen 402 antworten:** Indexer und Verzeichnisse prüfen per
  HEAD/GET; eine 405 führt zu `returns_402: false` und die Ressource wird nicht
  bzw. nicht dauerhaft geführt. Deshalb antworten auch `GET`/`HEAD` auf
  `/api/attest` mit der Zahlungsaufforderung (unbezahlt 402, bezahlt ein Hinweis
  auf POST) – so auch bei PayAI/„read-only probe" („GET paths answering 405 …
  are refused").
* **30-Tage-Regel:** Der CDP-Index blendet Ressourcen ohne Aktivität nach
  30 Tagen aus → mindestens **ein bezahlter Call pro Monat**.
* **Spiegel-Verzeichnisse (ziehen CDP automatisch):** x402.new, x402scan.com,
  agentic.market, Onyx Bazaar.

**Manuelle Einträge (PR / Issue / Formular):**

| Kanal | Einreichung |
|---|---|
| <https://github.com/xpaysh/awesome-x402> | PR in die Servicetabelle |
| <https://github.com/rawgroundbeef/x402.eco> | PR mit JSON in `data/ecosystem/services-endpoints/` |
| <https://github.com/Haustorium12/gold-402> | Einreichung, lebende 402 auf GET zwingend |
| <https://agent-tools.cloud/submit?type=x402> | Formular/API `/api/v1/submit` inkl. Kontakt-E-Mail |
| <https://github.com/x402-index/x402-discovery-index> | GitHub-Issue: URL, payTo, Beschreibung |
| <https://bazaar.saylorinnovations.com/submit> | `POST` mit `{"manifestUrl": "https://…/.well-known/x402.json"}` |

* Hinweis: `Rug-Munch-Media-LLC/awesome-x402` existiert nicht mehr (geprüft 25.10.2026).
* **Stand 25.10.2026:** CDP Bazaar aktiv (letzter Crawl 09:43 UTC), Saylor Agent Bazaar
  aufgenommen, agent-tools.cloud gelistet (Slug `travel-hanibal-ai-com-sub2070`);
  xpaysh, gold-402, x402.eco und x402-index sind eingereicht und offen.
* `POST /api/register` – **simuliert** die Registrierung: schreibt
  `attest/state/registration_request.json` und liefert Payload, Ziele (CDP-Bazaar,
  Spiegel, manuelle Verzeichnisse) und die manuellen Schritte. Es wird kein
  externer Dienst aufgerufen.
