#!/bin/bash
# Lokale CI: dieselben Prüfungen wie .github/workflows/ci.yml.
# Voraussetzung: Abhängigkeiten installiert (pip install -r requirements-runtime.txt).
set -euo pipefail

PY="${PYTHON:-python3}"

echo "== Compile =="
$PY -m compileall -q ui providers seo resolver affiliate alerts bundling attest

echo "== Unit (Signatur, Konfigurationswechsel, Billing) =="
$PY -m unittest attest.tests.test_attest_unit attest.tests.test_billing -v

echo "== x402 E2E (Mock-Facilitator) =="
$PY attest/tests/test_x402_flow.py

echo "== Legal (noindex/index) =="
$PY attest/tests/test_legal.py

echo "== Discovery (llms.txt, agent-payments.json, register) =="
$PY attest/tests/test_discovery.py

echo "== Resolver =="
$PY resolver/tests/test_resolver.py

echo "== Affiliate =="
$PY affiliate/tests/test_affiliate.py

echo "== SEO =="
$PY seo/tests/test_seo.py

echo
echo "CI OK"
