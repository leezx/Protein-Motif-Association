#!/usr/bin/env bash
# TOBIAS 0.17.5: ATACorrect (Tn5 bias correction) + FootprintScores (motif-free per-base footprint score).
# usage: run_tobias.sh <env_bin> <bam> <regions.bed> <genome.fa> <blacklist.bed> <outdir> <cores>
set -euo pipefail
B=$1; BAM=$2; BED=$3; FA=$4; BL=$5; O=$6; N=$7
mkdir -p "$O"
"$B/TOBIAS" ATACorrect --bam "$BAM" --genome "$FA" --peaks "$BED" --blacklist "$BL" --outdir "$O" --prefix tobias --cores "$N" > "$O/atacorrect.log" 2>&1
"$B/TOBIAS" FootprintScores --signal "$O/tobias_corrected.bw" --regions "$BED" --output "$O/tobias_footprints.bw" --cores "$N" > "$O/fpscores.log" 2>&1
