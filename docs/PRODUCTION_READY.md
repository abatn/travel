# Production-Ready: x402, Ed25519, Tests, Buchhaltung, DID

> **Datum:** 09.11.2026 · **Host:** `176.57.189.201` (`vmi3680465`), `/home/batnini/mimo-agents`
> **Dienst:** `reise-agent.service` (uvicorn `127.0.0.1:8077`, Caddy/Cloudflare)
> **Öffentlich:** `https://travel.hanibal-ai.com` · v1 `/api/attest` · v2 `/api/attest-v2`

## 0. Master-Entscheidung und Commit-Status

Der **Live-Host war der Master** für die Laufzeitlogik: Er enthielt die striktere
`/verify`-Prüfung (`verify_attestation` mit Signatur, Issuer, Key-ID und Ablauf)
sowie `/ready`. Die lokale Kopie `/home/opc/travel` war an diesen Stellen älter.

Vorgehen:

1. Host-Code (`attest/`, `ui/`, `scripts/`) in die lokale Kopie gespiegelt.
2. Dort die neuen Änderungen (Tests, Buchhaltung, DID, Verify-Trennung) ergänzt.
3. Den zusammengeführten Stand zurück auf den Host deployed und Dienst neu gestartet.
4. **Freigabe erteilt:** Änderungen auf `main` committet und nach
   `origin/main` gepusht. Der Commit liegt auf dem aktuellen Remote-Stand
   (`d2dea69` + dieser Commit); die genaue Hash-ID steht in `git log -1`.
5. Der Host wird nach dem Push auf `origin/main` gesetzt; Working Tree und
   `git status` sind danach sauber.

Die frühere Host-Historie (`4435ada`) wird vor dem Reset als Git-Bundle unter
`/home/batnini/` gesichert, damit nichts verloren geht.

---

## 1. P0 – Code-Sync (erledigt, mit Commit)

**Zusammengeführter Stand:**

| Datei | Änderung |
|---|---|
| `attest/signing.py` | `verify_attestation_details()`; `verify_attestation()` bleibt als strikte Gesamtprüfung |
| `attest/routes.py` | v1-`/verify` nutzt Details; bezahlter v1-GET liefert signiertes Referenzbeispiel und wird fakturiert; neues `GET /api/attest/sample` |
| `attest/payapi/instance.py` | v2-`/verify` nutzt Details; DID-Routen; `series="V2"` |
| `attest/x402_gate.py` | Host-Version mit `facilitator_supports(..., timeout=...)` für `/ready` |
| `ui/app.py` | Host-Version mit `/ready` (Registry, State, Attest, PayAPI) |
| `ui/tests/test_ready.py` | vom Host übernommen |
| `scripts/ci.sh` | erkennt `.venv/bin/python` automatisch; Host-CI und GitHub-CI nutzen denselben Ablauf |
| `pytest.ini` | schließt den Fremd-Symlink `km-hr-agent` aus; `pytest -q` bleibt auf dem Host grün |

**Deploy-Beweis:**

```text
systemctl restart reise-agent
GET http://127.0.0.1:8077/ready

{"ok":true,"service":"reise-agent-ui","checks":{
  "registry":{"status":"ok"},"state":{"status":"ok"},
  "attest":{"status":"ok","detail":null},"payapi":{"status":"ok","detail":null}}}
```

**Git-Stand:**

```text
Basis:   origin/main d2dea69
Commit:  Production-ready: echte v1-DID, Tests, globale Rechnungsnummern,
         Verify-Trennung (exakte Hash-ID: git log -1)
Host:    nach Reset auf origin/main; git status clean
Sicherung: Host-Historie 4435ada als Git-Bundle unter /home/batnini/
```

---

## 2. P1 – Tests repariert (grün)

**Angepasst:**

- `attest/payapi/tests/test_payapi.py`: leere POST-/GET-Aufrufe erwarten jetzt
  `200` + signiertes Referenzbeispiel (statt `422`), prüfen `source=payapi-reference`,
  `V2`-Rechnungsnummern, vier bezahlte Calls und eindeutige Nummern.
- `attest/tests/test_x402_flow.py`: dynamisches Reisedatum (`heute+7`) statt
  `2026-11-05`; zusätzlicher bezahlter v1-GET mit Signatur- und Rechnungsprüfung.
- `attest/tests/test_attest_unit.py`: prüft die getrennten Felder
  `signature_valid` / `expired` bei abgelaufenem und fehlendem `expires_at`.
- `attest/tests/test_billing.py`: erwartet `RE-2026-V1-…`; prüft zusätzlich, dass
  die V2-Serie nicht mit V1 kollidiert.
- `attest/tests/test_discovery.py`: prüft `GET /api/attest/sample` und den
  verlinkten Sample-Endpunkt.
- `attest/client.py`: dynamisches `travel_date` statt festem `2026-11-05`.

**Beweise auf dem Host:**

```text
$ .venv/bin/python -m pytest -q
68 passed, 1 warning in 4.25s   (finaler Lauf)

$ .venv/bin/python attest/payapi/tests/test_payapi.py
Ergebnis: 64/64 Prüfungen bestanden   (EXIT=0)

$ bash scripts/ci.sh
...
OK
CI OK                                  (EXIT=0)
```

Hinweis: `test_payapi.py` ist weiterhin ein eigenständiges Prüfskript, kein
Pytest-Test (keine `test_*`-Funktionen). `scripts/ci.sh` ruft es direkt auf;
`pytest -q` sammelt es daher nicht ein. Das ist jetzt dokumentiert und die CI
führt beide Wege aus.

---

## 3. P1 – Buchhaltung bereinigt

**Neue globale Nummern:**

```text
v1: RE-<Jahr>-V1-000001 …
v2: RE-<Jahr>-V2-000001 …
```

`attest/billing.py` hat `series` (Default `V1`) und schreibt `invoice_series`.
v1 ruft `series="V1"`, v2 `series="V2"`. Zusätzlich werden `source` und `note`
aus der Beobachtung ins Ledger übernommen; dadurch sind Referenz-Calls
(`attest-reference` / `payapi-reference`) von echten Beobachtungen unterscheidbar.

**Migration:** `scripts/migrate_invoice_numbers.py` (idempotent, mit Backups):

- v1: 10 Rechnungen → `RE-2026-V1-000001` … `RE-2026-V1-000010`
- v2: 3 Rechnungen + Canary → `RE-2026-V2-000001` … `RE-2026-V2-000004`
- Nach den zwei Live-GET-Calls (Abschnitt 6): v1 `…-000011`, v2 `…-000005`.
- Canary `0x799e7c01…` ist **`RE-2026-V2-000001`** mit
  `source=payapi-market-verification` und Quellenangabe im `note`-Feld
  (PayAPI-Listing `verified_at 2026-10-28T20:22:10Z`, Base-Receipt Block
  `53214782`, 10000 USDC-Units an `0x1cE5…5Cc4`).

**Beweis:**

```text
rows 16  unique 16  dups []
series ['V1', 'V2']
v1: RE-2026-V1-000001 … RE-2026-V1-000011
v2: RE-2026-V2-000001 … RE-2026-V2-000005
canary: RE-2026-V2-000001 (source=payapi-market-verification)
neu: RE-2026-V1-000011 (source=attest-reference),
     RE-2026-V2-000005 (source=payapi-reference)
```

Backups: `attest/state/invoices.jsonl.bak-20261109-162148`,
`attest/payapi/state/invoices.jsonl.bak-20261109-162148`.

---

## 4. P2 – DID und Verify

### 4.1 DID aufgelöst

Implementiert:

| Route | DID | Zweck |
|---|---|---|
| `GET /payapi/did.json` | `did:web:travel.hanibal-ai.com:payapi` | korrekte did:web-Pfadauflösung |
| `GET /.well-known/did.json` | `did:web:travel.hanibal-ai.com` | Root-DID des Hosts |
| `GET /api/attest-v2/did.json` | `did:web:travel.hanibal-ai.com:payapi` | Alias für Werkzeuge |

Dokument enthält `verificationMethod` mit `JsonWebKey2020`, OKP/Ed25519,
`publicKeyJwk.x` = Base64url des Public Key, sowie `authentication` und
`assertionMethod`.

**Live-Beweis:**

```text
/payapi/did.json          id=did:web:travel.hanibal-ai.com:payapi
                         method=…#iVp3Mfq7AxKi6Hjq  crv=Ed25519
/.well-known/did.json     id=did:web:travel.hanibal-ai.com
/api/attest-v2/did.json   id=did:web:travel.hanibal-ai.com:payapi
```

**v1-DID jetzt echt und auflösbar:** `attest/config.yaml` nutzt jetzt
`did:web:travel.hanibal-ai.com`. Das Root-Dokument unter
`https://travel.hanibal-ai.com/.well-known/did.json` enthält den v1-Key
(`4EATUjoV9o_YvC8z`); der v2-Key (`iVp3Mfq7AxKi6Hjq`) liegt unter der eigenen
Pfad-DID `/payapi/did.json`. `/api/attest/key` und neue v1-Attestierungen
tragen damit die echte Domain.

**Beweis (live):**

```text
GET /api/attest/key
{"did":"did:web:travel.hanibal-ai.com","key_id":"4EATUjoV9o_YvC8z", …}

GET /.well-known/did.json
id = did:web:travel.hanibal-ai.com
verificationMethod = [did:web:travel.hanibal-ai.com#4EATUjoV9o_YvC8z]

GET /payapi/did.json
id = did:web:travel.hanibal-ai.com:payapi
verificationMethod = [did:web:travel.hanibal-ai.com:payapi#iVp3Mfq7AxKi6Hjq]

GET /api/attest/sample
issuer.did = did:web:travel.hanibal-ai.com
issuer.public_key = QQSoDgz6nikKXVSaJAeZHG1D124VqN0-xgLC0_N8JcI
→ im Root-DID-Dokument als verificationMethod enthalten
→ POST /api/attest/verify: valid:true
```

**Hinweis zu alten Dokumenten:** v1-Attestierungen, die noch mit
`did:web:reise.example` signiert wurden, sind nach 300 s ohnehin abgelaufen und
werden von `/verify` jetzt zusätzlich als Issuer-Mismatch abgelehnt. Neue
Dokumente nutzen ausschließlich die echte Domain.

### 4.2 Verify trennt Signatur und Frische

`verify_attestation_details()` liefert:

```json
{
  "valid": true,
  "signature_valid": true,
  "key_id_valid": true,
  "issuer_valid": true,
  "expires_valid": true,
  "expired": true,
  "fresh": false,
  "reason": "Attestierung ist abgelaufen"
}
```

`valid` bedeutet jetzt „Signatur + Issuer + Key-ID gültig“; `expired` und
`fresh` stehen separat. Die strenge Gesamtprüfung bleibt als
`verify_attestation()` erhalten (Signatur + Issuer + Key-ID + Ablauf), damit
interne Aufrufer sich nicht ändern.

**Verhaltensänderung für Clients:** Ein abgelaufenes, aber korrekt signiertes
Dokument liefert jetzt `valid:true` + `expired:true` + `fresh:false`. Wer
Frische erzwingen will, muss `expired`/`fresh` prüfen. Das ist die bewusst
getrennte Semantik; sie ist in dieser Datei und in `attest/README.md` dokumentiert.

**Live-Beweis mit einem absichtlich abgelaufenen Dokument (TTL 300 s):**

```text
POST /api/attest/verify
{"valid":true,"signature_valid":true,"key_id_valid":true,"issuer_valid":true,
 "expires_valid":true,"expired":true,"fresh":false,
 "reason":"Attestierung ist abgelaufen", …}

POST /api/attest-v2/verify
{"valid":true,"signature_valid":true,"key_id_valid":true,"issuer_valid":true,
 "expires_valid":true,"expired":true,"fresh":false,
 "reason":"Attestierung ist abgelaufen", …}
```

Frische Dokumente liefern weiterhin `expired:false`, `reason:"ok"`.

---

## 5. Zusätzlich behoben

1. **v1-GET war un-signiert und wurde nicht fakturiert.** `GET /api/attest`
   liefert jetzt – wie v2 – ein signiertes Referenzbeispiel mit
   `source=attest-reference`; die Billing-Middleware schreibt eine Rechnung.
   Das behebt gleichzeitig den Widerspruch zur Bazaar-GET-Deklaration
   (`queryParams` + Attestierungs-Output).
2. **v1 hat jetzt `GET /api/attest/sample`** (kostenlos, signiert) und ist in
   `/.well-known/agent-payments.json` verlinkt.
3. **Dokumentierter Testclient** sendet kein festes Reisedatum mehr.
4. **Referenz-Rechnungen sind markiert** (`source`, `note`) und nicht mehr von
   echten Beobachtungen ununterscheidbar.
5. **CI nutzt automatisch die Projekt-Venv**, wenn vorhanden; GitHub-CI bleibt
   beim System-Python.

---

## 6. Live-Status nach dem Deploy

```text
GET /api/attest        -> 402, GET-Bazaar-Methode GET, payTo 0x1cE5…5Cc4, amount 10000
GET /api/attest-v2     -> 402, GET-Bazaar-Methode GET, payTo 0x1cE5…5Cc4, amount 10000
GET /api/attest/sample -> 200, signiert, source=attest-reference
GET /api/attest-v2/sample -> 200, signiert, source=payapi-reference
GET /ready             -> 200, attest/payapi ok
```

**Zwei zusätzliche echte Live-GET-Calls nach dem Deploy (je 0,01 USDC):**

| Instanz | Ergebnis | Referenz | Settlement-Tx | Block | Rechnung |
|---|---|---|---|---|---|
| v1 `GET /api/attest` | 200, signiert | `attest-reference` | `0xea97e7e0784b519ce177f83aac596ff9147d6fddcadce378a167e3fe4c0b9d4a` | 55257077 | `RE-2026-V1-000011` |
| v2 `GET /api/attest-v2` | 200, signiert | `payapi-reference` | `0xc2928cd0bdfdec0379a81d69c4b221b1219de9fb105dd4165b10227aed3e1655` | 55257117 | `RE-2026-V2-000005` |

Beide Transfers: status `1`, 10000 USDC-Units von `0xbD93…9d59` an
`0x1cE5…5Cc4`. Beide `/verify`-Antworten unmittelbar danach:
`valid:true, signature_valid:true, expired:false, fresh:true`.

Damit sind die neuen v1-GET- und Buchhaltungswege **live** belegt, nicht nur im
Mock. Insgesamt wurden für diese Prüfung **0,04 USDC** (vier Calls à 0,01 USDC)
aus der Betreiber-Testwallet ausgegeben; alle vier Settlement-Txs sind
on-chain bestätigt.

---

## 7. Ehrliche Restliste

1. **Commit/Push erledigt.** Der Host wird auf `origin/main` gesetzt; die alte
   Host-Historie `4435ada` liegt als Git-Bundle unter `/home/batnini/`.
2. **Host-Historie ist nicht identisch mit der Remote-Historie.** `4435ada`
   bleibt nur im Bundle erhalten; der Server läuft auf dem Remote-Commit.
   Das ist für den Betrieb sauber, aber historisch ein Bruch.
3. **Alte v1-Dokumente mit `did:web:reise.example`** werden nach der
   DID-Umstellung von `/verify` als Issuer-Mismatch abgelehnt; sie sind wegen
   der 300-s-TTL ohnehin abgelaufen. Neue v1-Dokumente nutzen
   `did:web:travel.hanibal-ai.com` und sind auflösbar.
4. **Wallet-Trennung ist bewusst nicht umgesetzt.** Beide Instanzen nutzen
   `0x1cE5…5Cc4`; auch die CDP-API-Credentials sind gemeinsam. Das ist laut
   Betreiber-Entscheidung so gewollt, bleibt aber ein Single Point of Failure.
5. **v1-POST behält 422 bei `plausibility=reject`.** v2 signiert Reject mit 200.
   Das ist weiterhin eine Semantik-Differenz; v1 wurde nicht umgestellt.
6. **`HEAD` wird von CDP `/validate` mit HTTP 400 beantwortet**, obwohl die
   Route HEAD mit 402 bedient. GET/POST sind 25/25 valide. Kein Ausfall, aber
   eine Discovery-Eigenheit.
7. **Cloudflare blockt `Python-urllib`-User-Agent mit 403.** `curl`, `requests`
   und `httpx` erhalten 402. x402-Clients nutzen üblicherweise httpx; exotische
   Clients können scheitern.
8. **PayAPI-`reliability` ist öffentlich `unscored`.** Ein interner
   „degraded“-Score ist ohne Dashboard nicht verifizierbar.
9. **Canary-Eintrag ist manuell.** Er ist als solcher markiert (`note`,
   `source`) und nicht nachträglich als automatisch erzeugt ausgegeben.
10. **Lokale `.venv` ist unvollständig** (kein `x402`, kein `pytest`); alle
    Testbeweise wurden auf dem Host mit `.venv/bin/python` erzeugt.
