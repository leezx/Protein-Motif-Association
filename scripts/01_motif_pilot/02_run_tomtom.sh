#!/usr/bin/env bash
# Step 1 pilot: TOMTOM JASPAR->Codebook and Codebook->Codebook.
# Design §3.3 (amended): TOMTOM reports ALL pairs (-evalue -thresh 1e9);
# per-query BH q-values are computed downstream (03_pilot_analysis.py).
# Reason: TOMTOM's own q-values use a randomised pi0 estimate whose RNG state
# carries across queries, so they shift (<=0.5%) with query order/chunking.
# p-values are deterministic, so queries are chunked and run in parallel.
set -euo pipefail
source "$(dirname "$0")/../../config/pma_env.sh"

IN="$PMA_MOTIF_PROCESSED/v0.1_pilot"
OUT="$PMA_MOTIF_RESULT/step1_motif_pilot/tomtom"
NJOBS="${PMA_NJOBS:-6}"
ARGS=(-no-ssc -dist pearson -min-overlap 5 -evalue -thresh 1e9 -text)
mkdir -p "$OUT"

run_pair() {  # run_pair <name> <query.meme> <target.meme>
  local name=$1 query=$2 target=$3 tmp
  tmp=$(mktemp -d "$OUT/.${name}.XXXX")
  python -I "$(dirname "$0")/split_meme.py" "$query" "$NJOBS" "$tmp/chunk"
  local c pids=()
  for c in "$tmp"/chunk_*.meme; do
    "$PMA_MEME_BIN/tomtom" "${ARGS[@]}" "$c" "$target" > "$c.tsv" 2> "$c.log" &
    pids+=($!)
  done
  for c in "${pids[@]}"; do wait "$c"; done
  { head -1 "$(ls "$tmp"/chunk_*.tsv | head -1)"
    for f in "$tmp"/chunk_*.tsv; do grep -v -e '^Query_ID' -e '^#' "$f" || true; done; } > "$OUT/$name.tsv"
  cat "$tmp"/chunk_*.log > "$OUT/$name.log"
  rm -r "$tmp"
}

run_pair jaspar_vs_codebook   "$IN/jaspar2026_core_vert_nr.meme"     "$IN/codebook2026_representative.meme"
run_pair codebook_vs_codebook "$IN/codebook2026_representative.meme" "$IN/codebook2026_representative.meme"

{ echo "tomtom_version	$("$PMA_MEME_BIN/tomtom" --version)"
  echo "args	${ARGS[*]} (query chunks: $NJOBS)"
  echo "run_date	$(date +%F)"; } > "$OUT/run_info.tsv"
wc -l "$OUT"/*.tsv
