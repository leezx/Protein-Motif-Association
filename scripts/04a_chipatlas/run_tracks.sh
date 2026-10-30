#!/bin/bash
# Step 4a §11-§12: genome-wide evidence tracks.
# Env: PMA_OCC_RAW, PMA_OCC_PROCESSED; python, pigz, mawk, tabix, bgzip, bedGraphToBigWig, bedToBigBed on PATH.
# usage: run_tracks.sh [workers] MODE
#   protein   proteins/TF/CAP/experiments (v1 Output A) + class-split light protein BED     -> light_v1/tracks
#   histone   histone experiments/modifications/core marks (histone_v1)                      -> light_v1/tracks_histone
#   pol       RNA polymerase II / III experiments (v1 Output A)                              -> light_v1/tracks_rnapol
#   atac|dnase  experiment-level BED6+18 via the Step 4a pipeline (if absent), then
#             <assay>_experiments / <assay>_celltypes                                         -> light_v1/tracks_<assay>
#   classes   non-hg38 only: GO-rule protein class annotation (29_go_class_annotation.py)       -> $ANN_DEFAULT
#   labels    histone label annotation from the light histone targets (08_histone_labels.py)
#   filter    experiment inclusion table for atac/dnase/histone (11_experiment_filter.py, >= PMA_MIN_PEAKS peaks)
#   mask_<protein|histone|pol|atac|dnase>  split at the ENCODE v2 blacklist of the genome into <dir>_{noBlacklist,blacklistOnly}
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd); N=${1:-5}; MODE=${2:-protein}
GCFG=$(python $HERE/genome_config.py); eval "$GCFG"  # G, RAW_RELEASE, PEAKS, SIZES_NAME, BLACKLIST_NAME (PMA_GENOME, default hg38)
P=$PMA_OCC_PROCESSED; RAW=$PMA_OCC_RAW/$RAW_RELEASE; SIZES=$RAW/reference/$SIZES_NAME
ANN_DEFAULT=$P/light_v1/PMA_chipatlas_${G}_protein_class_annotation.v1_1.csv
[ "$G" = hg38 ] || ANN_DEFAULT=$P/light_v1/PMA_chipatlas_${G}_protein_class_annotation.go_v1.csv  # §19.3 GO-rule draft
ANN=${PMA_CLASS_ANN:-$ANN_DEFAULT}
declare -A DIR=([protein]=tracks [histone]=tracks_histone [pol]=tracks_rnapol [atac]=tracks_atac [dnase]=tracks_dnase)
FILT=$P/light_v1/PMA_chipatlas_${G}_experiment_filter.tsv
declare -A CLASS=([atac]="ATAC-Seq" [dnase]="DNase-seq")
case $MODE in
classes)
  [ "$G" != hg38 ] || { echo "hg38 uses the curated v1.1 annotation" >&2; exit 2; }
  python $HERE/29_go_class_annotation.py $P/v1/PMA_chipatlas_${G}_experiments.tsv.gz $RAW/reference $ANN_DEFAULT ;;
labels)
  awk -F'\t' 'BEGIN{OFS="\t"} NR==1{print "mark","n_experiments","n_regions","n_peaks"; next} {print $1,$4,$2,$3}' \
    $P/light_v1/histone/PMA_chipatlas_${G}_histone_nr.targets.tsv > $P/light_v1/PMA_chipatlas_${G}_histone_marks.tsv
  python $HERE/08_histone_labels.py $P/light_v1/PMA_chipatlas_${G}_histone_marks.tsv \
    $P/light_v1/PMA_chipatlas_${G}_histone_label_annotation.tsv ;;
filter)
  python $HERE/11_experiment_filter.py $RAW/experimentList.tab $P/v1_work/peak_counts_all.tsv $FILT ${PMA_MIN_PEAKS:-10000} ;;
protein)
  python $HERE/05_occupancy_tracks.py $P/v1/PMA_chipatlas_${G}_occupancy.bed.gz $ANN $SIZES $P/light_v1/tracks $N
  python $HERE/06_split_by_class.py $P/light_v1/protein/PMA_chipatlas_${G}_protein_nr.bed.gz $ANN $SIZES \
    $P/light_v1/protein_by_class ;;
histone)
  test -s $FILT
  PMA_EXCLUDE_TSV=$FILT PMA_TRACK_MODE=histone python $HERE/05_occupancy_tracks.py $P/histone_v1/PMA_chipatlas_${G}_histone_occupancy.bed.gz \
    ${PMA_HISTONE_ANN:-$P/light_v1/PMA_chipatlas_${G}_histone_label_annotation.tsv} $SIZES $P/light_v1/tracks_histone $N ;;
pol)
  PMA_TRACK_MODE=pol python $HERE/05_occupancy_tracks.py $P/v1/PMA_chipatlas_${G}_occupancy.bed.gz - $SIZES \
    $P/light_v1/tracks_rnapol $N ;;
atac|dnase)
  ST=$P/${MODE}_v1_work; REL=$P/${MODE}_v1; BED=$REL/PMA_chipatlas_${G}_${MODE}_occupancy.bed.gz
  if [ ! -s $BED.tbi ]; then
    mkdir -p $ST $REL
    ( cd $HERE && PMA_OCC_CLASSES="${CLASS[$MODE]}" python 01_experiments.py $RAW $ST > $ST/01.log 2>&1 )
    pigz -dc -p 4 $RAW/$PEAKS \
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
  python $HERE/10_mask_blacklist.py $RAW/reference/$BLACKLIST_NAME $SIZES $T ${T}_noBlacklist ${T}_blacklistOnly ;;
*) echo "usage: run_tracks.sh [workers] classes|labels|filter|protein|histone|pol|atac|dnase|mask_<kind>" >&2; exit 2 ;;
esac
echo TRACKS_DONE $MODE
