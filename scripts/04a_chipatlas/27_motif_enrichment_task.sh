#!/bin/bash
# One comparison of the hotspot motif enrichment (§18.3): HOMER matched control, then SEA against every library.
# usage: 27_motif_enrichment_task.sh <prep_dir> <genome.fa> <row number in manifest.tsv, 1-based; default $SGE_TASK_ID>
# Needs homer2, sea and samtools on PATH. Writes <prep_dir>/runs/<comparison>/{hb.*,sea_<library>.tsv,task.json}.
set -euo pipefail
ulimit -c 0
PREP=$1; G=$2; ROW=${3:-$SGE_TASK_ID}
IFS=$'\t' read -r CMP TGT MODE POOL N < <(sed -n "$((ROW + 1))p" "$PREP/manifest.tsv")
OUT=$PREP/runs/$CMP; mkdir -p "$OUT"; cd "$OUT"
echo "comparison=$CMP target=$TGT mode=$MODE pool=$POOL N=$N host=$(hostname) start=$(date -Is)"
if [ "$N" -lt 50 ]; then echo "skip: N=$N"; echo "{\"comparison\":\"$CMP\",\"status\":\"skipped_small\"}" > task.json; exit 0; fi
NN=$(( N * 20 > 200000 ? N * 20 : 200000 ))
if [ -s hb.bg.sequences.fasta ] && [ -s hb.info.txt ]; then
  echo "reusing existing HOMER control"
elif [ "$MODE" = bgr ]; then
  homer2 bg -p "$PREP/$TGT" -g "$G" -bgr "$PREP/$POOL" -N "$N" -NN "$NN" -seed 1 -o hb > hb.log 2>&1
else
  homer2 bg -p "$PREP/$TGT" -g "$G" -bg "$PREP/$POOL" -N "$N" -seed 1 -o hb > hb.log 2>&1
fi
tail -3 hb.log
# SEA per motif chunk, in parallel. Per-motif p-values do not depend on the other motifs in the file; E- and
# q-values are recomputed over the whole library by 28_motif_enrichment_collect.py.
K=${PMA_SEA_CHUNKS:-8}; NP=${NSLOTS:-8}; rm -rf chunks; mkdir chunks
for M in "$PREP"/motifs/*.meme; do
  L=$(basename "$M" .meme)
  awk -v K="$K" -v pre="chunks/$L" '
    /^MOTIF/ {n++; c = n % K} 
    n == 0 {hdr = hdr $0 "\n"; next}
    {f = pre "." c ".meme"; if (!(f in seen)) {printf "%s", hdr > f; seen[f] = 1}; print > f}' "$M"
done
ls chunks/*.meme | xargs -P "$NP" -I{} sh -c 'sea --p hb.target.sequences.fasta --n hb.bg.sequences.fasta --m "$1" --thresh 1e9 --text > "${1%.meme}.tsv" 2> "${1%.meme}.log"' _ {}
for M in "$PREP"/motifs/*.meme; do
  L=$(basename "$M" .meme); first=1
  for f in chunks/$L.*.tsv; do
    if [ $first = 1 ]; then grep -v '^#' "$f"; first=0; else grep -v '^#' "$f" | tail -n +2; fi
  done > "sea_$L.tsv"
  test "$(grep -c '^MOTIF' "$M")" -eq "$(( $(wc -l < "sea_$L.tsv") - 1 ))" || echo "WARNING: $L motif count mismatch"
done
NT=$(grep -c '^>' hb.target.sequences.fasta); NB=$(grep -c '^>' hb.bg.sequences.fasta)
echo "{\"comparison\":\"$CMP\",\"status\":\"ok\",\"n_target\":$NT,\"n_bg\":$NB,\"freq_diff\":\"$(sed -n 's/^frequency difference = //p' hb.info.txt)\"}" > task.json
rm -f hb.target.sequences.fasta.fai
echo "end=$(date -Is)"; cat task.json
