# Infrastruktur-Fix: Git + pytest auf dem Server

> **Datum:** 09.11.2026 · **Host:** 176.57.189.201 · **Projekt:** `/home/batnini/mimo-agents` (user `batnini`)
> **Ausgangslage:** kein Git-Repository, kein `pytest` im Deployed-Venv, Projektordner enthält einen Fremd-Symlink (`km-hr-agent -> /opt/km-hr-agent`).

## 1. Git-Repository

**Prüfung:** `git` war vorhanden (`git version 2.43.0`), `apt install` nicht nötig.

**Angewendet (als `batnini`, damit `.git` nicht root gehört):**

```bash
git config --global user.name  "Agent"
git config --global user.email "agent@example.com"
cd /home/batnini/mimo-agents
git init -b main
git add .
git commit -m "Initial commit with M0-M7 and PayAPI fixes"
```

**`.gitignore` (neu, 34 Zeilen)** — ausschlaggebend:

```text
.env  .env.*  *.env  *.key  *.pem
attest/keys/  attest/payapi/keys/
attest/state/  attest/payapi/state/  */state/  state/  logs/  *.log
__pycache__/  *.py[cod]  .pytest_cache/  .venv/  .venv-*/
ui/screenshots/  attest/artifacts/  rome-2star/worker_*/  rome-2star/work/
rome-2star/*.json  resolver/data/*_raw.*  *.db  *.sqlite3
km-hr-agent          # root-owned Symlink nach /opt/km-hr-agent
```

**Beweis, dass die Ausschlüsse greifen** (`git check-ignore -v`):

```text
.gitignore:7:attest/keys/                      attest/keys/issuer.ed25519
.gitignore:8:attest/payapi/keys/               attest/payapi/keys/issuer.ed25519
.gitignore:14:state/                           attest/state/invoices.jsonl
.gitignore:14:state/                           attest/payapi/state/invoices.jsonl
.gitignore:25:.venv/                           .venv/bin/python
.gitignore:29:ui/screenshots/                  ui/screenshots/theme_dark_home.png
```

Vor dem Commit geprüft: **276 Dateien gestaged, 0 Treffer** für `.venv`, `/keys/`, `*.key`, `.env`, `/state/`, `screenshots/`.

**Ergebnis:**

```text
$ git log --oneline
c1e092b Infra: pytest-Setup (norecursedirs) und CI-Workflow mit /ready versioniert
f607add Initial commit with M0-M7 and PayAPI fixes

$ git status --short        # leer → Working Tree sauber
$ git ls-files | wc -l
278
```

Der erste Commit enthält Code, Tests, Docs und Deploy-Skripte; **keine** Keys, Ledger, `.env`-Dateien, `.venv` oder Screenshots.

## 2. pytest im Deployed-Venv

**Installation:**

```bash
cd /home/batnini/mimo-agents
.venv/bin/pip install -U pytest websocket-client
```

```text
Successfully installed iniconfig-2.3.1 packaging-26.3 pluggy-1.7.0 pygments-2.21.0 pytest-9.2.0
$ .venv/bin/python -m pytest --version
pytest 9.2.0
```

**Zwei Stolpersteine, die dabei behoben wurden:**

1. **Fremd-Symlink** `km-hr-agent -> /opt/km-hr-agent`: pytest sammelte dessen `conftest.py` und brach ab mit
   `ERROR km-hr-agent - Failed: Defining 'pytest_plugins' in a non-top-level conftest`.
   → neue `pytest.ini`:
   ```ini
   [pytest]
   norecursedirs = .* .venv* km-hr-agent rome-2star work node_modules
   ```
2. **Fehlendes Modul** `websocket` in sechs UI-Tests → `websocket-client` installiert.

**Zusätzlich:** `.github/workflows/ci.yml` war auf dem Server nicht vorhanden (der Deploy-Test
`deploy/tests/test_deploy_excludes.py` verlangt sie und prüft `/ready`). Die CI-Datei wurde aus dem
Quell-Repo übernommen und ihr Health-Check von `/health` auf **`/ready`** umgestellt (der `/ready`-Endpunkt
liefert zusätzlich `registry/state/attest/payapi`-Checks; live: HTTP 200).

**Testergebnis (vollständige Suite, aus dem Projektverzeichnis):**

```text
$ python -m pytest -q
....................................................................     [100%]
68 passed, 1 warning in 4.24s
```

**Kern-Suite separat:**

```text
$ python -m pytest attest -q
24 passed in 2.29s
```

Einzige Warnung: `StarletteDeprecationWarning: Using 'httpx' with 'starlette.testclient' is deprecated`
(nicht blockierend, keine Testfehler).

## 3. Commits auf dem Server

| Commit | Inhalt |
|---|---|
| `f607add` | Initial commit (278 Dateien; Code, Tests, Docs, Deploy; ohne Secrets/State) |
| `c1e092b` | `pytest.ini` (norecursedirs) + `.github/workflows/ci.yml` mit `/ready` |

## 4. Ehrliche Hinweise / Empfehlungen

1. **pytest liegt jetzt im Produktions-Venv**, ist aber nicht in `requirements-runtime.txt` gepinnt.
   Empfehlung: `requirements-dev.txt` (`pytest==9.2.0`, `websocket-client==…`) anlegen und nur in
   CI/Testumgebungen installieren; im Prod-Venv schadet es nicht, vergrößert es aber.
2. **Kein Remote:** Das Repo ist rein lokal (`git remote -v` leer). Für Backup/Deploy-Traceability
   empfiehlt sich ein privates Remote (z. B. GitHub) und `git push -u origin main`.
3. **Bulk-Daten bewusst nicht versioniert:** `resolver/data/*_raw.*` (~24 MB), `ui/screenshots/` (~11 MB),
   `rome-2star/worker_*/` + `work/` (~29 MB). Sie bleiben auf dem Server, sind aber nicht im Repo.
   Bei Bedarf über Git LFS oder ein separates Daten-Repo versionieren.
4. **Lokale Kopie `/home/opc/travel`** hat weiterhin uncommittete Änderungen (PayAPI-Fix + diese Doku);
   der Server ist die laufende Instanz. `pytest.ini` und die CI-Anpassung sind dort ebenfalls gespiegelt.
5. **Testlauf ist umgebungsabhängig:** Die Suite läuft hier in 4 s; netzwerk-/browserlastige Tests
   (z. B. `providers/ferry_evidence`) werden nicht übersprungen, sondern liefen mit — alle grün.
