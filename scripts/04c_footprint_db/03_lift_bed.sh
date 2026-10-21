#!/bin/bash
# Lift a footprint BED (all columns kept) to hg38 for integrated/consensus files without per-sample data.
# usage: 03_lift_bed.sh <in.bed[.gz]> <chain.gz> <liftOver> <out.liftedFrom<Build>.hg38.bed.gz>  (name must contain liftedFrom)
# Writes out.hg38.bed.gz (+.tbi), <out>.unmapped.bed.gz and <out>.liftover.json (input / lifted / unmapped counts).
set -euo pipefail
IN=$1; CHAIN=$2; LIFT=$3; OUT=$4; T=$(mktemp -d); export LC_ALL=C
[[ $(basename "$OUT") == *liftedFrom* ]] || { echo "output name must contain liftedFrom<build> (lifted files are labelled)" >&2; exit 2; }
{ [[ $IN == *.gz ]] && zcat "$IN" || cat "$IN"; } | grep -v -E '^(track|browser|#)' > "$T/in.bed"
"$LIFT" -bedPlus=3 -tab "$T/in.bed" "$CHAIN" "$T/out.bed" "$T/unmapped.bed" 2> "$T/log" || "$LIFT" "$T/in.bed" "$CHAIN" "$T/out.bed" "$T/unmapped.bed"
sort -k1,1 -k2,2n "$T/out.bed" | bgzip -c > "$OUT" && tabix -f -p bed "$OUT"
gzip -c "$T/unmapped.bed" > "${OUT%.bed.gz}.unmapped.bed.gz"
echo "{\"input\": $(wc -l < "$T/in.bed"), \"lifted\": $(wc -l < "$T/out.bed"), \"unmapped\": $(grep -vc '^#' "$T/unmapped.bed" || true), \"chain\": \"$(basename "$CHAIN")\"}" > "${OUT%.bed.gz}.liftover.json"
printf "LIFTED OVER, NOT NATIVE hg38.\nInput: %s\nChain: %s\nliftOver stats: %s\n" "$IN" "$(basename "$CHAIN")" "$(cat "${OUT%.bed.gz}.liftover.json")" > "${OUT%.bed.gz}.LIFTOVER_NOTICE.txt"
cat "${OUT%.bed.gz}.liftover.json"; rm -rf "$T"
