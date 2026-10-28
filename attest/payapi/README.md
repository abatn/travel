# PayAPI-Instanz (M2b)

> **PayAPI Market:** gelistet unter <https://payapi.market> (Suche nach
> **„Travel-Agent Price Attestation"**), verifiziert am **2026-10-28**.
> Agenten finden die Route über den MCP-Server `https://payapi.market/mcp`.
>
> Die 402-Antwort enthält `extensions.bazaar` mit Input-/Output-Beispiel und
> JSON-Schema, damit die Route im Coinbase x402 Bazaar indexiert werden kann.

Zweite, unabhängige Instanz der Preis-Attestierung – ausschließlich für die
Listung auf **PayAPI Market**. Die bestehende Instanz `/api/attest` bleibt
unverändert.

## Was ist unabhängig?

| Bereich | Hauptinstanz | PayAPI-Instanz |
|---|---|---|
| URL | `/api/attest` | `/api/attest-v2` |
| Config | `attest/config.yaml` | `attest/payapi/config.yaml` |
| Schlüssel | `attest/keys/issuer.ed25519` | `attest/payapi/keys/issuer.ed25519` |
| Ledger | `attest/state/invoices.jsonl` | `attest/payapi/state/invoices.jsonl` |
| Discovery | `/.well-known/agent-payments.json` | `/.well-known/x402` |
| Preis | 0,01 USDC | 0,01 USDC |
| Netz/Asset | Base / USDC | Base / USDC |
| `extra.name` | `USD Coin` | **`USD Coin`** (explizit) |

Die Zahlungs-Wallet (`payTo`) ist bewusst dieselbe verifizierte Base-Wallet:
`0x1cE5379a485a0bd726fce57BbfDfc316b0D35Cc4`.

## PayAPI-Anforderungen (Playbook)

- Öffentliche, stabile HTTPS-URL ohne Login → `https://travel.hanibal-ai.com/api/attest-v2`
- Unbezahlt: GET/HEAD/POST → **HTTP 402**, keine Produktdaten
- Netz: **Base Mainnet** (`eip155:8453`)
- Asset: kanonisches USDC (`0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913`)
- `payTo` = Listing-Wallet
- `extra.name` = **`"USD Coin"`** (nicht „USDC“)
- Preis = Listing-Preis: **0,01 USDC** (`10000` atomic)
- Bezahlt: **HTTP 200 + echte signierte Attestierung**
- Ein Produkt = eine Listung (nicht zusätzlich `/api/attest` einreichen)
- Discovery: `/.well-known/x402` (Saylor/Agent-Bazaar-Format)

## Endpunkte

| Methode | Pfad | Zweck |
|---|---|---|
| GET/HEAD/POST | `/api/attest-v2` | bezahlt; GET ohne Parameter liefert ein signiertes Referenzbeispiel, POST signiert die Beobachtung |
| GET | `/api/attest-v2/key` | öffentlicher Ed25519-Schlüssel |
| POST | `/api/attest-v2/validate` | kostenlose Vorprüfung |
| POST | `/api/attest-v2/verify` | Signatur prüfen |
| GET | `/api/attest-v2/openapi.json` | minimale OpenAPI-Beschreibung |
| GET | `/.well-known/x402` | x402-Manifest |

## Beispiel

```bash
# unbezahlt -> 402
curl -i https://travel.hanibal-ai.com/api/attest-v2

# Discovery
curl -s https://travel.hanibal-ai.com/.well-known/x402 | jq .

# bezahlt (eigener Test-Schlüssel, Base Mainnet)
.venv-x402/bin/python -m attest.client \
  --base https://travel.hanibal-ai.com \
  --path /api/attest-v2 \
  --method POST \
  --network eip155:8453 \
  --key-file attest/keys/buyer.key
```

## Test

```bash
.venv-x402/bin/python attest/payapi/tests/test_payapi.py
```

Der Test startet einen Mock-Facilitator und die App, prüft unbezahlte
402-Antworten ohne Datenleck, die exakten Challenge-Felder, bezahlte GET/POST-
Aufrufe, Signaturprüfung, eigenen Schlüssel und eigenen Ledger.

## Betrieb

- Benötigt `CDP_API_KEY_ID` / `CDP_API_KEY_SECRET` (wie die Hauptinstanz).
- `PAYAPI_ENABLED=false` deaktiviert nur diese Instanz.
- Überschreibbar per Env: `PAYAPI_CONFIG`, `PAYAPI_PRICE`, `PAYAPI_PAY_TO`,
  `PAYAPI_NETWORK`, `PAYAPI_PUBLIC_BASE_URL`, `PAYAPI_LEDGER`, `PAYAPI_KEY_FILE`,
  `PAYAPI_FACILITATOR_URL`.
- `attest/payapi/keys/` und `attest/payapi/state/` sind vom Deploy ausgeschlossen
  und überleben ein Redeploy.

## PayAPI-Formular (Checkliste)

| Feld | Eintrag |
|---|---|
| API name | `Reise-Agent Attest v2 (PayAPI)` |
| Base URL | `https://travel.hanibal-ai.com/api/attest-v2` |
| Wallet | `0x1cE5379a485a0bd726fce57BbfDfc316b0D35Cc4` |
| Price range | `0.01` – `0.01` USDC per call |
| Category | `Data` (alternativ `Tools`/`Travel`) |
| Description | „Ed25519-signed travel price attestations (flights, hotels, ferries, cruises) with plausibility checks; 0.01 USDC per call via x402 v2 on Base.“ |

**Wichtig:** Die URL im Formular muss exakt der Live-Challenge entsprechen
(`/api/attest-v2`), die Wallet exakt `payTo`, und der Preis exakt `10000`
atomic USDC (0,01 USDC). Keine Tunnels, kein Login, kein zweiter Pfad als
separate Listung.
