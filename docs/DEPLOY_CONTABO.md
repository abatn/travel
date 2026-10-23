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
