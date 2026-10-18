#!/bin/bash
# Step 4b-1: HINT-ATAC (RGT) motif-free footprint calling. HINT is single-threaded, so regions are split into N chunks
# that run as N parallel processes ("brute-force" parallelism); outputs are concatenated.
# usage: run_hint.sh <env_bin> <bam> <regions.bed> <outdir> <n_chunks>
set -euo pipefail
B=$1; BAM=$2; BED=$3; O=$4; N=$5
mkdir -p $O/chunks
s=$(date +%s)
split -n l/$N -d -a 3 $BED $O/chunks/r_
for f in $O/chunks/r_*; do
  ( $B/rgt-hint footprinting --atac-seq --paired-end --organism=hg38 --output-location=$f.out --output-prefix=fp \
      $BAM $f > $f.log 2>&1 || echo "FAIL $f" >> $O/failed.txt ) &
done
wait
cat $O/chunks/r_*.out/fp.bed 2>/dev/null | sort -k1,1 -k2,2n > $O/events.bed
e=$(date +%s)
printf "stage\tseconds\nhint\t%d\n" $((e-s)) > $O/timing.tsv
[ -s $O/failed.txt ] && cat $O/failed.txt || true
