# PayAPI „degraded" — Ursache, Fix, Beweis

> **Datum:** 09.11.2026 · **Ziel:** `https://travel.hanibal-ai.com/api/attest-v2` (PayAPI Market listing `travel-agent-price-attestation`)
> **Host:** 176.57.189.201, `/home/batnini/mimo-agents`, `reise-agent.service` (uvicorn 127.0.0.1:8077, Caddy)

## 1. Recherche (offizielle Quellen)

**CDP x402 — Get discovered (Bazaar)** (`https://docs.cdp.coinbase.com/x402/seller/get-discovered`):

- Validierung prüft: erreichbar, **402 Payment Required**, **gültige `extensions.bazaar`**, technische Index-Anforderungen (`POST /platform/v2/x402/validate` mit `{resource, method}`).
- „For any route that accepts query parameters, path parameters, or a request body, we **strongly recommend adding explicit schemas and examples**."
- Curation/Health: „**Health** — Passes the platform health probe. **Sustained consecutive failures auto-delist** the endpoint"; „Endpoints that **stop returning 402** Payment Required are eventually removed from the index entirely."
- „No `bazaar` key means discovery was not submitted."
- „Rejections are usually strict JSON Schema validation: your declared `input` must validate against `schema.properties.input`."

**PayAPI Market — Providers** (`https://payapi.market/providers`) und `/list`:

- „The form calls your paid route **unpaid** before it creates a row, so a URL that does not already answer a Base x402 challenge is refused on the spot."
- „**Offer a free sample or health route that returns real data in the same shape as the paid route. We can check that route without paying.**"
- „If an upstream service returns HTTP 429 or HTTP 5xx, or the call times out, return HTTP 4xx or HTTP 5xx. **Do not return HTTP 200 with an empty body, null, or stub data.**"
- „Listed paid routes should only settle payment **after a successful response** (a 2xx status with real, non-empty data)."
- „Reliability scoring (based on paid verifications, **health history** and payment-address integrity)."
- „`extra.name` must be `USD Coin` on Base USDC or settlement fails." (erfüllt)

## 2. Diagnose (vor dem Fix)

| Prüfung | Befund |
|---|---|
| Unpaid GET / POST / HEAD auf `/api/attest-v2` | **402** + `PAYMENT-REQUIRED` (ok) |
| Header dekodierbar | `x402Version 2`, `accepts[0]` mit `payTo 0x1cE5…`, `amount 10000`, `extra {name:"USD Coin",version:"2"}` (ok) |
| `PAYMENT-REQUIRED` im Body | Body ist `{}`; Challenge steht nur im Header (von CDP akzeptiert) |
| Latenz | 0,07–0,15 s (ok) |
| **Bazaar-Methode** | Alle Routen (POST/GET/HEAD) deklarierten `bazaar.info.input.method = "POST"` → CDP `/validate` mit `method=GET`: **`valid:false`**, `bazaar.info.input.method.matches_request` = FAIL („declared POST but probed with GET") |
| **GET nach Zahlung** | `_observation_from_query` warf `ValueError` → **422** („Parameter fehlen"), also genau der Fall „cold probe mit GET ohne Body" → Fehler nach der Zahlung |
| **Beispiel-Datum** | `sample`/Bazaar-Beispiel: festes `travel_date: 2026-11-05`. Plausibilität lehnt Daten vor `heute-1` ab → seit ~07.11. **reject → 422 nach Zahlung**. PayAPI hat am 28.10. mit genau diesem Beispiel verifiziert (damals gültig) |
| Latenter 500er | `except Exception as exc:` definiert `_unavailable()` mit `str(exc)` → `NameError` nach dem except-Block (am 28.10. real als 500 auf `/api/attest`) |

**Ursache „degraded":** Der Health-/Canary-Pfad der Indexer benutzt das veröffentlichte Beispiel bzw. einen kalten GET. Beides endete nach der Zahlung in **422** (fehlende Parameter bzw. veraltetes Reisedatum), und die Bazaar-Metadaten deklarierten POST, während mit GET geprobt wurde (`valid:false`). Für einen Indexer sieht das wie „API beeinträchtigt" aus — obwohl der 402-Teil korrekt war.

## 3. Fix (live deployed)

| Datei | Änderung |
|---|---|
| `attest/discovery.py` | `bazaar_extension(method)` — methodenspezifisch: GET/HEAD/DELETE → `queryParams`-Schema, POST/PUT/PATCH → `body`-Schema. Beispiel-`travel_date` wird beim Start **dynamisch** auf `heute+30` gesetzt (kein festes Datum mehr). `SAMPLE_OUTPUT` ohne Ellipsis-Platzhalter, vollständige Dokumentform. |
| `attest/x402_gate.py` | `route_config(method)` statt einer Deklaration für alle Methoden — jede Route trägt ihre eigene Bazaar-Methode. |
| `attest/payapi/instance.py` | (a) GET/POST ohne Eingaben liefern das signierte **Referenzbeispiel** statt 422; (b) `_sign()` signiert auch ein `plausibility.status = "reject"` und antwortet **200** (das Verdikt steht im Dokument — kein Fake-„ok", aber auch kein Fehler nach der Zahlung); (c) neue kostenlose Route **`GET /api/attest-v2/sample`** in exakt der bezahlten Form; (d) `NameError`-Bug behoben (`detail` vor der Closure binden). |
| `attest/routes.py` | gleicher `NameError`-Fix für die v1-Instanz. |

**Semantik-Hinweis:** Ein negatives Plausibilitäts-Verdikt ist jetzt ein Produkt (signierte Beobachtung + Prüfergebnis), kein HTTP-Fehler. Damit bestehen Health-Checks auch dann, wenn ein Indexer ein **altes, zwischengespeichertes Beispiel** verwendet. v1 (`/api/attest`) bleibt unverändert (weiter 422 bei reject).

Backups: `*.bak-20261109-1343` und `*.bak2-*` neben den Dateien. Rollback: Datei zurückkopieren, `systemctl restart reise-agent`.

## 4. Beweis (nach dem Fix, 09.11.2026)

**Unbezahlt (curl):**

```text
GET  /api/attest-v2                    -> 402
GET  /api/attest-v2?route=BER-FCO&…    -> 402
POST /api/attest-v2  (leerer Body)     -> 402
HEAD /api/attest-v2                    -> 402
```

`PAYMENT-REQUIRED` (base64) dekodiert:

```json
{"x402Version":2,"error":"Payment required",
 "accepts":[{"scheme":"exact","network":"eip155:8453",
   "asset":"0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
   "amount":"10000","payTo":"0x1cE5379a485a0bd726fce57BbfDfc316b0D35Cc4",
   "maxTimeoutSeconds":120,"extra":{"name":"USD Coin","version":"2"}}],
 "extensions":{"bazaar":{"info":{"input":{"method":"GET", …}}}}
```

**CDP `/validate`:**

| Methode | valid | simulation | Preflight-Fails | Bazaar-Methode | Beispiel-Datum |
|---|---|---|---|---|---|
| GET | **true** | accepted | **0** | GET | — (queryParams) |
| POST | **true** | accepted | **0** | POST | 2026-12-09 |

**Bezahlte Calls (echtes Geld, Base Mainnet, 0,01 USDC je Call):**

| Call | Ergebnis | Settlement-Tx | Rechnung |
|---|---|---|---|
| `--method GET` (Beispiel mit altem Datum 2026-11-05) | **HTTP 200**, Signatur `valid:true`, `plausibility.status="reject"` (travel_date) | `0x2d848df62b995a84eefb307988f89fe0dff3a795e2644cc37c6b689182c7a64f` | `RE-2026-V2-000002` |
| `--method POST` | **HTTP 200**, Signatur `valid:true` | `0x35e0a26b9ecc34ad85daeafacaa5dd74d72ecf97863f72ee71f2318918801263` | `RE-2026-V2-000003` |

On-Chain geprüft (`mainnet.base.org`, `eth_getTransactionReceipt`): Status `1`, ERC-20-`Transfer` 10000 (0,01 USDC) von `0xbD93…9d59` an `0x1cE5…5Cc4`, USDC `0x8335…2913`.

**Kostenlose Health-Route:**

```text
GET /api/attest-v2/sample -> 200, signiert (key_id iVp3Mfq7AxKi6Hjq),
                             subject.travel_date = heute+7, plausibility "ok"
POST /api/attest-v2/verify {"document": …} -> {"valid":true,"reason":"ok"}
```

**Regression v1:** `GET/POST /api/attest` → 402; CDP `/validate` (POST) → `valid:true`, 0 Fails.

## 5. Ehrlich: offene Punkte

1. **„degraded" ist ein PayAPI-internes Scoring.** Öffentlich sichtbar sind nur `status: live`, `payment_verified: true`, `verification_paused: false`, `reliability: unscored`. Ohne Dashboard-Zugang lässt sich der genaue Badge-Wert nicht ablesen; der Fix beseitigt die reproduzierbaren Ursachen, die Health-/Canary-Prüfungen scheitern lassen. Die Neubewertung erfolgt mit den nächsten Probes.
2. ~~**Canary-Zahlung vom 28.10. fehlt im Ledger**~~ **Nachgetragen am 09.11.2026** als `RE-2026-V2-000001` mit Quellenangabe (`source=payapi-market-verification`, PayAPI-Listing + Base-Receipt Block 53214782). Die damalige v2-Route schrieb noch keine Rechnung; der Eintrag ist als manuell nachgetragen markiert, nicht als automatisch erzeugt.
3. ~~**DIDs nicht auflösbar**~~ **Behoben am 09.11.2026:** v1 nutzt jetzt `did:web:travel.hanibal-ai.com` (Root-Dokument `/.well-known/did.json` mit v1-Key); v2 nutzt `did:web:travel.hanibal-ai.com:payapi` (`/payapi/did.json`, HTTP 200).
4. **Kein Testlauf auf dem Host:** `pytest` fehlt im Deployed-Venv (`x402` ist vorhanden). Verifiziert wurde per echtem HTTP/CDP/On-Chain, nicht per Unit-Suite.
5. **Host ist kein Git-Repo**; die lokale Kopie `/home/opc/travel` wich vor dem Fix in 16 Dateien ab. Die Änderungen sind zusätzlich in die lokale Kopie gespiegelt (siehe Commit-Hinweis unten), damit der nächste Deploy sie nicht überschreibt.
