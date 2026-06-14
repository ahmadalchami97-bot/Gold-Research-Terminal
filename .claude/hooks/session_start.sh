#!/usr/bin/env bash
# Ensure the Gold Research Terminal can run tests and linters in a web session.
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 0

if ! python3 -c "import streamlit, pandas, numpy, scipy, statsmodels, arch, plotly, pyarrow" 2>/dev/null; then
  echo "Installing Gold Research Terminal dependencies…"
  python3 -m pip install -q -r requirements-dev.txt || \
    python3 -m pip install -q -r requirements.txt pytest ruff || true
fi

# Make sure the offline sample snapshot exists (so the app + tests run offline).
if [ ! -f data_samples/prices.parquet ]; then
  python3 scripts/seed_samples.py || true
fi

echo "Gold Research Terminal environment ready (DATA_MODE defaults to auto; use demo offline)."
