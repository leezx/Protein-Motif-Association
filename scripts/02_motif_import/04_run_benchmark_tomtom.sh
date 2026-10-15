#!/usr/bin/env bash
# Step 2 benchmark TOMTOM (design §8.1): every benchmark motif as a query
# against the whole v0.2 raw layer. Same TOMTOM args as Step 1. Each chunk
# is reduced to benchmark rows after per-query BH, then the full chunk
# output is deleted (rerun to regenerate).
set -euo pipefail
cd "$(dirname "$0")"
source ../../config/pma_env.sh
PROC="$PMA_MOTIF_PROCESSED/v0.2_raw_layer"
B="$PMA_MOTIF_RESULT/step2_motif_import/benchmark"
OUT="$B/tomtom"
NJOBS="${PMA_NJOBS:-7}"      # concurrent TOMTOM processes
NCHUNK="${PMA_NCHUNK:-21}"   # smaller chunks bound bh_extract memory
LIMIT="${PMA_BENCH_LIMIT:-0}"  # >0: smoke test on the first N queries
ARGS=(-no-ssc -dist pearson -min-overlap 5 -evalue -thresh 1e9 -text)
mkdir -p "$OUT"
TARGET="$PROC/PMA_motifs_raw.meme"
NT=$(grep -c '^MOTIF' "$TARGET")

tmp=$(mktemp -d "$OUT/.run.XXXX")
python -I - "$TARGET" "$B/benchmark_queries.txt" "$tmp/queries.meme" "$LIMIT" <<'EOF'
import sys
sys.path.insert(0, ".")
import pma_motif as pm
target, ids, out = sys.argv[1:4]
want = [l.strip() for l in open(ids) if l.strip()]
limit = int(sys.argv[4]) if len(sys.argv) > 4 else 0
want = want[:limit] if limit else want
mats = {m: (m, a, x) for m, a, x in pm.read_meme(target)}
pm.write_meme([mats[w] for w in want], out)
EOF
python -I ../01_motif_pilot/split_meme.py "$tmp/queries.meme" "$NCHUNK" "$tmp/chunk"
run_chunk() {  # run_chunk <chunk.meme>
  "$PMA_MEME_BIN/tomtom" "${ARGS[@]}" "$1" "$TARGET" > "$1.tsv" 2> "$1.log"
  python -I bh_extract.py "$1.tsv" "$NT" "$B/benchmark_pairs.tsv" "$1.keep.tsv"
  rm "$1.tsv"
}
export -f run_chunk; export PMA_MEME_BIN TARGET NT B
export ARGS_STR="${ARGS[*]}"
ls "$tmp"/chunk_*.meme | xargs -P "$NJOBS" -I{} bash -c 'ARGS=($ARGS_STR); run_chunk "$@"' _ {}
[[ $(ls "$tmp"/chunk_*.keep.tsv | wc -l) -eq $(ls "$tmp"/chunk_*.meme | wc -l) ]] || { echo "chunk failed" >&2; exit 1; }
{ head -1 "$(ls "$tmp"/chunk_*.keep.tsv | head -1)"
  for f in "$tmp"/chunk_*.keep.tsv; do tail -n +2 "$f"; done; } > "$OUT/benchmark_tomtom.tsv"
cat "$tmp"/chunk_*.log > "$OUT/tomtom.log"
rm -r "$tmp"
{ echo "tomtom_version	$("$PMA_MEME_BIN/tomtom" --version)"
  echo "args	${ARGS[*]} (query chunks: $NCHUNK, parallel: $NJOBS)"
  echo "targets	$NT"
  echo "run_date	$(date +%F)"; } > "$OUT/run_info.tsv"
wc -l "$OUT/benchmark_tomtom.tsv"
