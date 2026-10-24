# Deployment: travel.hanibal-ai.com (Contabo)

Stand: 24.10.2026 · Server: `176.57.189.201` (Contabo, Ubuntu 24.04)

## Architektur

```
Browser/Agent
   │ HTTPS (Cloudflare, proxied)
   ▼
Cloudflare Edge  ──►  Contabo 176.57.189.201 :443
                         │ Caddy (TLS, HSTS, Security-Header)
                         ▼
                    127.0.0.1:8077  (systemd: reise-agent)
                         │ uvicorn (FastAPI, ui.app:app)
                         ▼
                    /home/batnini/mimo-agents
```

Die App läuft **auf dem Contabo-Server**, nicht mehr per SSH-Tunnel.
Caddy terminiert TLS (Let's Encrypt, HTTP-01 über Cloudflare) und proxyt
auf `127.0.0.1:8077`.

## Dienste

| Was | Wo |
|---|---|
| App | `systemctl status reise-agent` · `journalctl -u reise-agent -f` |
| Caddy | `systemctl status caddy` · `journalctl -u caddy -f` |
| Code | `/home/batnini/mimo-agents` |
| venv | `/home/batnini/mimo-agents/.venv` |
| Secrets | `/etc/reise-agent.env` (0600, root) |
| Caddyfile | `/etc/caddy/Caddyfile` |
| systemd-Unit | `/etc/systemd/system/reise-agent.service` |

## Update deployen

```bash
cd /home/batnini/mimo-agents
./deploy/contabo.sh          # rsync + restart + health
```

Der Rsync löscht entfernte Dateien (`--delete`), aber schützt `.venv`,
`__pycache__`, `attest/artifacts`, Test-Keys und Ledger.

## Firewall

* `22/tcp` – SSH (überall)
* `80/tcp` + `443/tcp` – **nur Cloudflare-IPv4/IPv6-Ranges**
* `8080/tcp` – bestehender `km-hr-agent` (unverändert)

Direktzugriff auf `176.57.189.201:443` ist damit blockiert; der einzige Weg
ist über Cloudflare. Bei Cloudflare-IP-Änderungen: Ranges von
`https://www.cloudflare.com/ips-v4` / `ips-v6` neu eintragen.

## TLS / Cloudflare

* Cloudflare proxied (`A → 176.57.189.201`), SSL-Modus **Full (strict)**.
* Caddy holt ein Let's-Encrypt-Zertifikat per HTTP-01 (TLS-ALPN ist durch
  Cloudflare nicht möglich; im Caddyfile deaktiviert).
* HSTS, `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`,
  `Permissions-Policy` werden von Caddy gesetzt.

## Rechtliches ausfüllen

`ui/legal.yaml` ist eine Vorlage. Solange Pflichtfelder leer sind, bleiben
`/impressum` und `/datenschutz` auf `noindex`. Nach dem Ausfüllen:

```bash
rsync -a ui/legal.yaml contabo:/home/batnini/mimo-agents/ui/legal.yaml
ssh contabo 'chown batnini:batnini /home/batnini/mimo-agents/ui/legal.yaml'
```

Kein Neustart nötig (die Datei wird pro Request gelesen).

Pflichtfelder: `betreiber.name`, `strasse`, `plz_ort`, `land`, `email`,
`umsatzsteuer_id` (oder `"keine"`), `verantwortlich`; `datenschutz.hosting`,
`kontakt_datenschutz`, `aufbewahrung_logs`, `aufsichtsbehoerde`, `stand`.

## Health-Checks

```bash
curl -s https://travel.hanibal-ai.com/health
curl -s https://travel.hanibal-ai.com/llms.txt | head
curl -s https://travel.hanibal-ai.com/.well-known/agent-payments.json
curl -s -o /dev/null -w '%{http_code}\n' https://travel.hanibal-ai.com/
```

## Monatliche Selbstzahlung (30-Tage-Regel)

Dateien: `deploy/travel-monthly-payment.{sh,service,timer}`. Der Timer zahlt
einmal monatlich 0,01 USDC an den eigenen Endpunkt, damit das Listing im
CDP-Bazaar nicht nach 30 Tagen ohne Aktivität entfernt wird.

Installation auf dem Server (als root, einmalig; bei Neuinstallation wiederholen):

```sh
install -m 755 deploy/travel-monthly-payment.sh /usr/local/bin/travel_monthly_payment.sh
install -m 644 deploy/travel-monthly-payment.service deploy/travel-monthly-payment.timer /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now travel-monthly-payment.timer
```

Voraussetzungen: `attest/keys/buyer.key` (Rechte 600, Besitzer batnini) und
`/etc/reise-agent.env` mit `CDP_API_KEY_ID`/`CDP_API_KEY_SECRET`. Der Key
liegt nicht im Git (Deploy-Excludes).

Prüfen: `systemctl list-timers travel-monthly-payment.timer` und
`journalctl -u travel-monthly-payment.service`. Testlauf: `systemctl start travel-monthly-payment.service`
(kostet 0,01 USDC). Ergebnis-Rechnungen stehen in `attest/state/invoices.jsonl`.

## Zahlungs-Watch (E-Mail bei fremden Zahlungen)

Dateien: `deploy/payment_watch.py`, `deploy/payment-watch.{service,timer}`.
Prüft stündlich USDC-Transfers auf Base an die payTo-Adresse und mailt jede
Zahlung einer **fremden** Wallet. Eigene Wallets (Testkäufer, payTo selbst)
werden ignoriert, damit Eigenzahlungen nicht als Umsatz gelten.

Voraussetzung in `/etc/reise-agent.env` (Rechte 600, Besitzer root):

```sh
SMTP_HOST=smtp.mail.yahoo.com
SMTP_PORT=587
SMTP_USER=batniniabdelkader@yahoo.com
SMTP_PASSWORD=<Yahoo-App-Passwort>
ALERT_TO=batniniabdelkader@yahoo.com
```

Installation (als root):

```sh
install -m 644 deploy/payment-watch.service deploy/payment-watch.timer /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now payment-watch.timer
```

Prüfen: `journalctl -u payment-watch.service -n 20`. Testlauf ohne Zahlung:
`python3 deploy/payment_watch.py --dry-run` (zeigt nur, was gemeldet würde).

Bereits gemeldete Transaktionen stehen in `attest/state/payment_watch.json`.
Schlägt der Mailversand fehl, bleibt die Transaktion ungemeldet und wird beim
nächsten Lauf erneut versucht. Quelle ist `BASE_RPC_URL`
(Standard `https://base-rpc.publicnode.com`).

## Auto-Deploy über GitHub Actions

Push auf `main` löst aus:

1. **test** – `scripts/ci.sh` (Compile + alle Suiten)
2. **deploy** – nur wenn `test` grün ist und der Push auf `main` ging

Der Deploy-Job:

* verbindet sich per SSH als `batnini` (dedizierter Deploy-Key),
* rsync nach `/home/batnini/mimo-agents` (Runtime-State, Keys und Venvs sind
  ausgeschlossen),
* installiert `requirements-runtime.txt` im venv,
* startet `reise-agent` neu und prüft `/health` lokal **und** öffentlich.

### GitHub-Secrets

| Secret | Inhalt |
|---|---|
| `CONTABO_SSH_KEY` | privater Ed25519-Deploy-Key (nur für Deploy) |
| `CONTABO_HOST` | `176.57.189.201` |
| `CONTABO_USER` | `batnini` |
| `CONTABO_KNOWN_HOSTS` | `ssh-keyscan -H 176.57.189.201` |

### Server-Seite

* `~batnini/.ssh/authorized_keys`: Deploy-Key mit
  `no-agent-forwarding,no-port-forwarding,no-X11-forwarding,no-pty`.
* `/etc/sudoers.d/reise-deploy`: `batnini` darf **nur**
  `systemctl restart/is-active/status reise-agent` ohne Passwort.

### Deploy-Key rotieren

```bash
ssh-keygen -t ed25519 -f deploy_key -N "" -C "github-actions-deploy"
# Public Key in ~batnini/.ssh/authorized_keys ersetzen
# Private Key als CONTABO_SSH_KEY in GitHub aktualisieren
```

Manuell (Fallback): `./deploy/contabo.sh`
