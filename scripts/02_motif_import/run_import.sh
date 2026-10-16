#!/usr/bin/env bash
# Step 2 end-to-end: raw sources -> processed/<layer>_raw_layer -> QC summary.
# Design: docs/STEP2_MOTIF_IMPORT_DESIGN.md (§12: v0.2.1). PMA_RAW_LAYER=v0.2
# rebuilds the frozen v0.2 layer; default v0.2.1. Fetch (00_fetch_sources.sh) is
# run separately; raw/ is append-only.
set -euo pipefail
cd "$(dirname "$0")"
source ../../config/pma_env.sh
export PMA_RAW_LAYER="${PMA_RAW_LAYER:-v0.2.1}"
OUT="$PMA_MOTIF_PROCESSED/${PMA_RAW_LAYER}_raw_layer"
python -I 01_import_motifs.py
python -I 02_qc_summary.py

# processed-layer provenance: commit, session, checksums
{
  echo "commit: $(git rev-parse HEAD)$(git diff --quiet HEAD -- . || echo ' (dirty)')"
  echo "date: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "fetch_date: ${PMA_FETCH_DATE:-2026-10-14}"
  python -c 'import sys,numpy,pandas;print("python:",sys.version.split()[0]);print("numpy:",numpy.__version__);print("pandas:",pandas.__version__)'
} > "$OUT/session_info.txt"
( cd "$OUT" && md5 -r PMA_* codebook_table13_mapping.tsv 2>/dev/null || md5sum PMA_* codebook_table13_mapping.tsv ) \
  | sort -k2 > "$OUT/checksums.md5"
