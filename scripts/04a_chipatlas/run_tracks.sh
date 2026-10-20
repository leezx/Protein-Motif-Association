#!/bin/bash
# Step 4a §11: genome-wide occupancy evidence tracks.
# Env: PMA_OCC_RAW, PMA_OCC_PROCESSED; python, tabix, bgzip, bedGraphToBigWig, bedToBigBed on PATH.
# usage: run_tracks.sh [workers] [protein|histone|mask_protein|mask_histone]
#   mask_*: split at the ENCODE hg38 v2 blacklist (base-wise) into tracks{,_histone}_{noBlacklist,blacklistOnly}
#   protein: proteins/TF/CAP/experiments bigWigs (v1 Output A) + class-split light protein BED
#   histone: histone experiments/marks + core-mark bigWigs (histone_v1 BED6+18)
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd); N=${1:-5}; MODE=${2:-protein}
P=$PMA_OCC_PROCESSED; SIZES=$PMA_OCC_RAW/2026-10-17/reference/hg38.chrom.sizes
ANN=${PMA_CLASS_ANN:-$P/light_v1/PMA_chipatlas_hg38_protein_class_annotation.v1_1.csv}
case $MODE in
protein)
  python $HERE/05_occupancy_tracks.py $P/v1/PMA_chipatlas_hg38_occupancy.bed.gz $ANN $SIZES $P/light_v1/tracks $N
  python $HERE/06_split_by_class.py $P/light_v1/protein/PMA_chipatlas_hg38_protein_nr.bed.gz $ANN $SIZES \
    $P/light_v1/protein_by_class ;;
histone)
  PMA_TRACK_MODE=histone python $HERE/05_occupancy_tracks.py $P/histone_v1/PMA_chipatlas_hg38_histone_occupancy.bed.gz \
    ${PMA_HISTONE_ANN:-$P/light_v1/PMA_chipatlas_hg38_histone_label_annotation.tsv} $SIZES $P/light_v1/tracks_histone $N ;;
mask_protein|mask_histone)
  T=$P/light_v1/tracks; [ $MODE = mask_histone ] && T=$P/light_v1/tracks_histone
  python $HERE/10_mask_blacklist.py $PMA_OCC_RAW/2026-10-17/reference/hg38-blacklist.v2.bed.gz $SIZES $T ${T}_noBlacklist ${T}_blacklistOnly ;;
*) echo "usage: run_tracks.sh [workers] [protein|histone|mask_protein|mask_histone]" >&2; exit 2 ;;
esac
echo TRACKS_DONE $MODE
