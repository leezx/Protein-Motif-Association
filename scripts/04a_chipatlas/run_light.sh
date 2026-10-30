#!/bin/bash
# Step 4a §10: light per-target BEDs. Env: PMA_OCC_RAW, PMA_OCC_PROCESSED; python, pigz, mawk, bgzip, tabix,
# bedToBigBed on PATH. Proteins from the v1 release; histone via the Step 4a pipeline with PMA_OCC_CLASSES=Histone.
# usage: run_light.sh protein|histone [workers]
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
GCFG=$(python $HERE/genome_config.py); eval "$GCFG"  # G, RAW_RELEASE, PEAKS, SIZES_NAME, BLACKLIST_NAME (PMA_GENOME, default hg38)
RAW=$PMA_OCC_RAW/$RAW_RELEASE; P=$PMA_OCC_PROCESSED; N=${2:-4}
SIZES=$RAW/reference/$SIZES_NAME
case $1 in
protein)
  python $HERE/04_light_bed.py $P/v1/PMA_chipatlas_${G}_occupancy.bed.gz $P/v1/PMA_chipatlas_${G}_experiments.tsv.gz \
    $SIZES $P/light_v1/protein PMA_chipatlas_${G}_protein_nr $N ;;
histone)
  ST=$P/histone_v1_work; REL=$P/histone_v1; mkdir -p $ST $REL
  if [ "${PMA_LIGHT_ONLY:-0}" != 1 ]; then  # PMA_LIGHT_ONLY=1 reuses an existing histone BED6+18
  ( cd $HERE && PMA_OCC_CLASSES=Histone python 01_experiments.py $RAW $ST > $ST/01.log 2>&1 )
  pigz -dc -p 4 $RAW/$PEAKS \
    | mawk -v ids=$ST/scope_ids.txt 'BEGIN{while((getline l < ids)>0) keep[l]=1} ($4 in keep){print}' \
    | ( cd $HERE && python 02_peaks.py $ST $RAW/reference 2> $ST/02.log ) \
    | bgzip -@ $N > $REL/PMA_chipatlas_${G}_histone_occupancy.bed.gz
  tabix -f -p bed $REL/PMA_chipatlas_${G}_histone_occupancy.bed.gz
  fi
  [ -s $REL/PMA_chipatlas_${G}_histone_occupancy.bed.gz.tbi ] || { echo "histone BED missing" >&2; exit 1; }
  PMA_LIGHT_TARGET=antigen python $HERE/04_light_bed.py $REL/PMA_chipatlas_${G}_histone_occupancy.bed.gz $ST/experiments_stage1.tsv.gz \
    $SIZES $P/light_v1/histone PMA_chipatlas_${G}_histone_nr $N ;;
*) echo "usage: run_light.sh protein|histone [workers]" >&2; exit 2 ;;
esac
echo LIGHT_DONE $1
