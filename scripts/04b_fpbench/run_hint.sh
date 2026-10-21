#!/usr/bin/env bash
# HINT-ATAC (RGT 1.0.2) motif-free footprint calling. HINT is single-threaded; regions are split into N chunks run in parallel.
# usage: run_hint.sh <hint_bin_dir> <bam> <regions.bed> <outdir> <n_chunks>
set -euo pipefail
B=$1; BAM=$2; BED=$3; O=$4; N=$5
mkdir -p "$O/chunks"
split -n l/$N -d -a 3 "$BED" "$O/chunks/r_"
pids=()
for f in "$O"/chunks/r_*; do
  [[ "$(basename "$f")" == *.* ]] && continue
  mkdir -p "$f.out"
  "$B/rgt-hint" footprinting --atac-seq --paired-end --organism=hg38 --output-location="$f.out" --output-prefix=fp \
      "$BAM" "$f" > "$f.log" 2>&1 &
  pids+=("$!")
done
for p in "${pids[@]}"; do wait "$p"; done
cat "$O"/chunks/r_*.out/fp.bed | sort -k1,1 -k2,2n > "$O/hint_footprints.bed"
