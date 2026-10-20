#!/bin/bash
# Step 4b-1: HINT-ATAC (RGT) motif-free footprint calling. HINT is single-threaded, so regions are split into N chunks
# that run as N parallel processes ("brute-force" parallelism); outputs are concatenated.
# usage: run_hint.sh <env_bin> <bam> <regions.bed> <outdir> <n_chunks>
set -euo pipefail
B=$1; BAM=$2; BED=$3; O=$4; N=$5
mkdir -p "$O/chunks"
CHUNK_DIR=$(mktemp -d "$O/chunks/run_XXXXXX")
for prior in "$O/failed.txt" "$O/events.bed" "$O/timing.tsv"; do
  [ -e "$prior" ] && mv "$prior" "$CHUNK_DIR/prior_$(basename "$prior")"
done
s=$(date +%s)
split -n l/$N -d -a 3 "$BED" "$CHUNK_DIR/r_"
pids=(); chunks=()
for f in "$CHUNK_DIR"/r_*; do
  [ -f "$f" ] || continue
  chunks+=("$f")
  mkdir -p "$f.out"
  ( "$B/rgt-hint" footprinting --atac-seq --paired-end --organism=hg38 --output-location="$f.out" --output-prefix=fp \
      "$BAM" "$f" > "$f.log" 2>&1 ) &
  pids+=("$!")
done
failed=0
for i in "${!pids[@]}"; do
  if ! wait "${pids[$i]}"; then
    echo "FAIL ${chunks[$i]}" >> "$O/failed.txt"
    failed=1
  fi
  [ -f "${chunks[$i]}.out/fp.bed" ] || {
    echo "MISSING_OUTPUT ${chunks[$i]}.out/fp.bed" >> "$O/failed.txt"
    failed=1
  }
done
if [ "$failed" = 1 ]; then
  cat "$O/failed.txt"
  exit 1
fi
cat "$CHUNK_DIR"/r_*.out/fp.bed | sort -k1,1 -k2,2n > "$O/events.bed"
e=$(date +%s)
printf "stage\tseconds\nhint\t%d\n" $((e-s)) > "$O/timing.tsv"
