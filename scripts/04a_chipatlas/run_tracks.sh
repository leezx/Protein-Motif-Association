#!/bin/bash
# Step 4a §11: genome-wide occupancy evidence tracks + class-split protein BED.
# Env: PMA_OCC_RAW, PMA_OCC_PROCESSED; python, tabix, bgzip, bedGraphToBigWig, bedToBigBed on PATH.
# usage: run_tracks.sh [workers]
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd); N=${1:-5}
P=$PMA_OCC_PROCESSED; SIZES=$PMA_OCC_RAW/2026-10-17/reference/hg38.chrom.sizes
ANN=${PMA_CLASS_ANN:-$P/light_v1/PMA_chipatlas_hg38_protein_class_annotation.v1_1.csv}
python $HERE/05_occupancy_tracks.py $P/v1/PMA_chipatlas_hg38_occupancy.bed.gz $ANN $SIZES $P/light_v1/tracks $N
python $HERE/06_split_by_class.py $P/light_v1/protein/PMA_chipatlas_hg38_protein_nr.bed.gz $ANN $SIZES \
  $P/light_v1/protein_by_class
echo TRACKS_DONE
