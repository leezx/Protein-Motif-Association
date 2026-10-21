#!/bin/bash
# Step 4a §11-§12: genome-wide evidence tracks.
# Env: PMA_OCC_RAW, PMA_OCC_PROCESSED; python, pigz, mawk, tabix, bgzip, bedGraphToBigWig, bedToBigBed on PATH.
# usage: run_tracks.sh [workers] MODE
#   protein   proteins/TF/CAP/experiments (v1 Output A) + class-split light protein BED     -> light_v1/tracks
#   histone   histone experiments/modifications/core marks (histone_v1)                      -> light_v1/tracks_histone
#   pol       RNA polymerase II / III experiments (v1 Output A)                              -> light_v1/tracks_rnapol
#   atac|dnase  experiment-level BED6+18 via the Step 4a pipeline (if absent), then
#             <assay>_experiments / <assay>_celltypes                                         -> light_v1/tracks_<assay>
#   filter    experiment inclusion table for atac/dnase/histone (11_experiment_filter.py, >= PMA_MIN_PEAKS peaks)
#   mask_<protein|histone|pol|atac|dnase>  split at the ENCODE hg38 v2 blacklist into <dir>_{noBlacklist,blacklistOnly}
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd); N=${1:-5}; MODE=${2:-protein}
P=$PMA_OCC_PROCESSED; RAW=$PMA_OCC_RAW/2026-10-17; SIZES=$RAW/reference/hg38.chrom.sizes
ANN=${PMA_CLASS_ANN:-$P/light_v1/PMA_chipatlas_hg38_protein_class_annotation.v1_1.csv}
declare -A DIR=([protein]=tracks [histone]=tracks_histone [pol]=tracks_rnapol [atac]=tracks_atac [dnase]=tracks_dnase)
FILT=$P/light_v1/PMA_chipatlas_hg38_experiment_filter.tsv
declare -A CLASS=([atac]="ATAC-Seq" [dnase]="DNase-seq")
case $MODE in
filter)
  python $HERE/11_experiment_filter.py $RAW/experimentList.tab $P/v1_work/peak_counts_all.tsv $FILT ${PMA_MIN_PEAKS:-10000} ;;
protein)
  python $HERE/05_occupancy_tracks.py $P/v1/PMA_chipatlas_hg38_occupancy.bed.gz $ANN $SIZES $P/light_v1/tracks $N
  python $HERE/06_split_by_class.py $P/light_v1/protein/PMA_chipatlas_hg38_protein_nr.bed.gz $ANN $SIZES \
    $P/light_v1/protein_by_class ;;
histone)
  test -s $FILT
  PMA_EXCLUDE_TSV=$FILT PMA_TRACK_MODE=histone python $HERE/05_occupancy_tracks.py $P/histone_v1/PMA_chipatlas_hg38_histone_occupancy.bed.gz \
    ${PMA_HISTONE_ANN:-$P/light_v1/PMA_chipatlas_hg38_histone_label_annotation.tsv} $SIZES $P/light_v1/tracks_histone $N ;;
pol)
  PMA_TRACK_MODE=pol python $HERE/05_occupancy_tracks.py $P/v1/PMA_chipatlas_hg38_occupancy.bed.gz - $SIZES \
    $P/light_v1/tracks_rnapol $N ;;
atac|dnase)
  ST=$P/${MODE}_v1_work; REL=$P/${MODE}_v1; BED=$REL/PMA_chipatlas_hg38_${MODE}_occupancy.bed.gz
  if [ ! -s $BED.tbi ]; then
    mkdir -p $ST $REL
    ( cd $HERE && PMA_OCC_CLASSES="${CLASS[$MODE]}" python 01_experiments.py $RAW $ST > $ST/01.log 2>&1 )
    pigz -dc -p 4 $RAW/allPeaks_light.hg38.05.bed.gz \
      | mawk -v ids=$ST/scope_ids.txt 'BEGIN{while((getline l < ids)>0) keep[l]=1} ($4 in keep){print}' \
      | ( cd $HERE && python 02_peaks.py $ST $RAW/reference 2> $ST/02.log ) \
      | bgzip -@ $N > $BED
    tabix -f -p bed $BED
  fi
  test -s $FILT
  PMA_EXCLUDE_TSV=$FILT PMA_TRACK_MODE=access PMA_TRACK_PREFIX=$MODE python $HERE/05_occupancy_tracks.py $BED - $SIZES \
    $P/light_v1/tracks_$MODE $N ;;
mask_*)
  K=${MODE#mask_}; T=$P/light_v1/${DIR[$K]}
  python $HERE/10_mask_blacklist.py $RAW/reference/hg38-blacklist.v2.bed.gz $SIZES $T ${T}_noBlacklist ${T}_blacklistOnly ;;
*) echo "usage: run_tracks.sh [workers] protein|histone|pol|atac|dnase|mask_<kind>" >&2; exit 2 ;;
esac
echo TRACKS_DONE $MODE
