# x402scan-Registrierung (`/api/attest-v2`)

**Status:** Daten vorbereitet – **manuelle Eintragung durch den Betreiber** nötig.
Stand: 2026-10-28.

## Was x402scan benötigt

Die Registrierungsseite <https://www.x402scan.com/resources/register> fragt im
Formular **nur eine öffentliche HTTPS-URL** ab. Preis, Wallet, Netzwerk und
Beschreibung liest x402scan aus der **402-Antwort** (`PAYMENT-REQUIRED`) und der
Discovery. Deshalb müssen dort die korrekten Werte stehen.

| Feld | Wert |
|---|---|
| Resource-URL | `https://travel.hanibal-ai.com/api/attest-v2` |
| Methode | `POST` (GET/HEAD werden ebenfalls unterstützt) |
| Netzwerk | `eip155:8453` (Base Mainnet) |
| Asset | `0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913` (USDC) |
| `payTo` | `0x1cE5379a485a0bd726fce57BbfDfc316b0D35Cc4` |
| Preis | `$0.01` = `10000` atomic USDC |
| Service-Name | `Reise-Agent Attest v2 (PayAPI)` |
| Beschreibung | Ed25519-signierte Preis-Attestierung für Flüge, Hotels, Fähren und Kreuzfahrten mit Plausibilitätsprüfung; Beobachtung liefert der Käufer. |
| Tags | `travel`, `price`, `attestation`, `payapi` |
| Kontakt | `batniniabdelkader@yahoo.com` |
| Discovery | `https://travel.hanibal-ai.com/.well-known/x402` |

## Beispielanfrage (bezahlt)

```http
POST https://travel.hanibal-ai.com/api/attest-v2
Content-Type: application/json

{
  "route": "BER-FCO",
  "travel_date": "2026-11-05",
  "price": "129.99",
  "currency": "EUR",
  "price_scope": "per_person",
  "source": "googleflights-local",
  "source_url": "https://www.google.com/travel/flights",
  "passengers": 1
}
```

Unbezahlt: **HTTP 402** + `PAYMENT-REQUIRED`-Header. Bezahlt: **HTTP 200** +
signiertes JSON-Dokument (`subject`, `plausibility`, `signature`).

## Manuelle Schritte

1. <https://www.x402scan.com/resources/register> öffnen.
2. URL `https://travel.hanibal-ai.com/api/attest-v2` eintragen und absenden.
3. Prüfen, ob x402scan Netzwerk **Base**, Asset **USDC**, Preis **0.01**,
   `payTo` `0x1cE5…Cc4` und den Service-Namen korrekt erkannt hat.
4. Falls eine Wallet-Signatur verlangt wird: mit der Wallet
   `0x1cE5379a485a0bd726fce57BbfDfc316b0D35Cc4` signieren (Schlüssel liegt nicht im Repo).
5. Nach Freischaltung Eintrag prüfen und Status hier dokumentieren.

## Hinweise

- **Nur v2 registrieren** (ein Produkt = eine Listung); `/api/attest` nicht zusätzlich eintragen.
- x402scan ist ein Drittanbieter-Katalog; Aufnahme und Ranking liegen nicht bei uns.
- Die 402-Antwort enthält `extensions.bazaar` (Coinbase-x402-Bazaar), damit die
  Route auch dort indexierbar ist.
