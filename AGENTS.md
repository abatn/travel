# AGENTS.md

German travel price comparison (flights, hotels, ferries, cruises) plus x402-paid, Ed25519-signed price attestations. FastAPI + Jinja2, pure Python, no build step, no JS bundler. Docs, comments and commit messages are German; code identifiers are English.

## Commands

- Setup: `python3 -m venv .venv && .venv/bin/pip install -r requirements-runtime.txt` (pulls `x402[evm]`; system `python3` lacks it). A local `.venv-x402` also exists and is what the commands below use.
- Run UI: `.venv-x402/bin/python -m uvicorn ui.app:app --host 127.0.0.1 --port 8077`. `ui/start.sh` execs bare `python3` from PATH, so activate a venv first.
- Full local CI (same checks as GitHub Actions): `PYTHON=.venv-x402/bin/python bash scripts/ci.sh`
- Single unittest module: `.venv-x402/bin/python -m unittest attest.tests.test_attest_unit -v`
- Single script test: `.venv-x402/bin/python attest/tests/test_x402_flow.py`
- Provider CLI: `.venv-x402/bin/python providers/runner.py --category flights --origin BER --destination FCO --depart-date 2026-10-31 --return-date 2026-11-02 --adults 2 --currency EUR`
- Run everything from the repo root. Several modules add their own directory to `sys.path` and import flat names (`from score import ...`). Do not convert them to package imports.

## Tests

- CI (`scripts/ci.sh`) covers: compileall, attest unit/billing, x402 mock flow, legal, discovery, payapi, resolver, affiliate, seo.
- Not in CI; run manually when touched: `ui/tests/*`, `providers/tests/*`, `attest/tests/test_capabilities.py`, `deploy/tests/test_revenue_report.py`.
- Tests are plain scripts plus stdlib `unittest`. There is no pytest config. Do not add a test framework.
- Fixed ports: x402/payapi tests use 8078 and 8097–8099. Chrome/CDP UI tests need a server on 127.0.0.1:8077 and use 92xx ports. `ui/tests/test_theme.py` starts its own server on 8099. Do not run suites in parallel.
- Tests use mocks and fault stubs. Live sources are never hit in tests.

## Architecture

- Request flow: `ui/app.py` (routes) → `ui/service.py` (the only adapter) → `providers/runner.py`, `bundling/compare.py`, `alerts/watcher.py` (subprocess `--once`).
- Searches run in a background thread (can take minutes). Result pages poll `/api/jobs/<id>`. `/health` is liveness; `/ready` is the readiness probe (registry, state, payment paths) and deploy waits on it.
- `providers/registry.yaml` is the single source of truth for 22 sources (20 enabled). A new source is a YAML entry (`transport`, `params`, `extract`, `price_scope`), never Python.
- Keep `ui/` a thin layer. Ranking and scoring belong in `providers/score.py` and the registry.
- `resolver/` is offline (airports, ports, aliases); no network on the search path. `seo/` derives JSON-LD and sitemap from the visible offers.
- `attest/` handles x402 and signing. `attest/payapi/` is a second, independent instance (`/api/attest-v2`) with its own config, keys and state.
- Live searches depend on machine-local CLIs and absolute paths (`~/.local/bin/trvl`, `fli-mcp`, `stays`, `rome-2star/worker_c` MCP) plus external networks.

## Deploy and packaging

- Pushing to `main` deploys production. GitHub Actions runs tests, then rsyncs and runs `systemctl restart reise-agent`. A 2-minute server timer (`travel-deploy.timer`, unit lives on the server, script is `deploy/server-auto-deploy.sh`, documented in `README.md`) also pulls `main`, including when Actions is blocked. There is no staging.
- `.gitignore` is a whitelist (`/*` plus `!dir`). Only listed top-level dirs are versioned. `tools/`, `harness/`, `benchmark/`, `research/`, `promptfoo/`, `ace/`, `inspect_ai/`, `demo.sh` and `.mcp.json` are local scratch: invisible to git and to deploy.
- A new top-level package needs all of: a `.gitignore` whitelist entry, the compileall list in `scripts/ci.sh`, and both rsync lists (`.github/workflows/ci.yml` and `deploy/server-auto-deploy.sh`). The two rsync lists differ. `i18n/` (imported by `attest/routes.py`) must be in the compileall list of `scripts/ci.sh`, the CI rsync list, and the `deploy/contabo.sh` rsync list; the server script already has it.

## Data and secrets

- Runtime state is gitignored and excluded from deploy: `ui/state*/`, `*/state/`, `attest/keys/`, `attest/payapi/keys/`, `attest/state*/` (invoices in `attest/state/*.jsonl`), `attest/artifacts/`. Never commit keys or state. Deleting local state is safe.
- `attest/config.yaml` targets Base mainnet with Coinbase CDP. Testnet/mainnet switching is config or env only (`ATTEST_*`, `CDP_API_KEY_*`). Never commit real keys.
- Env overrides: `SITE_URL` (canonical URLs and sitemap; falls back to request host), `LEGAL_CONFIG`, `ATTEST_LEDGER`, `ATTEST_TAX_ID`.

## Product rules

- No fabricated prices, ratings or availability. Do not emit `AggregateRating`.
- Implausible or corrupt source data must yield "no price", never a fallback estimate.
- No booking or payment for travel. The app only compares and links out.

## Conventions

- German is the source language. Locales live in `ui/locales/<lang>.<namespace>.json`, merged by `ui/i18n_core.py` (base plus extras, German fallback, `ar` is RTL). Add new keys to every language.
- Docs drift: `docs/ANLEITUNG.md` and `i18n/ENTSCHEIDUNG.md` are stale (source counts, locale paths). Trust `providers/registry.yaml`, `ui/i18n_core.py` and `docs/ARCHITECTUR.md`.
- Further reading: `docs/ARCHITECTUR.md`, `ui/README.md`, `docs/DEPLOY_CONTABO.md`, `attest/README.md`.
