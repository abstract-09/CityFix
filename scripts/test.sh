#!/usr/bin/env bash
# Runs everything: backend tests, frontend unit tests, production build, end-to-end smoke test.
set -euo pipefail
cd "$(dirname "$0")/.."
echo "== Backend tests";            python3 -m unittest discover -s backend/tests -t . 2>&1 | grep -v -E "^(CityFix demo|  (officer|admin|\(saved))" | tail -n 6
echo "== Frontend unit tests";      (cd frontend && node --test tests/*.test.mjs 2>&1 | grep -E "^# (tests|pass|fail)")
echo "== Frontend production build"; node frontend/build.mjs
echo "== End-to-end smoke test";    bash scripts/smoke.sh
echo; echo "All checks passed."
