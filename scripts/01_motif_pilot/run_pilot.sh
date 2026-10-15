#!/usr/bin/env bash
# Step 1 pilot end-to-end: fetch -> convert -> TOMTOM -> analysis.
set -euo pipefail
cd "$(dirname "$0")"
source ../../config/pma_env.sh
bash 00_fetch_sources.sh
python -I 01_build_motif_sets.py
bash 02_run_tomtom.sh
python -I 03_pilot_analysis.py
