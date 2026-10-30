#!/bin/bash
# Step 4a full build. Env: PMA_OCC_RAW, PMA_OCC_PROCESSED (config/pma_env.sh or the Argos launcher);
# PMA_GENOME=hg38 (default) | mm10 (design §19; point PMA_OCC_* at that genome's dataset).
# python (r4p3), pigz, mawk, bgzip, tabix on PATH. Memory: a few GB; disk: output BED.gz in processed/v1.
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
GCFG=$(python $HERE/genome_config.py); eval "$GCFG"  # G, RAW_RELEASE, PEAKS, SIZES_NAME, BLACKLIST_NAME (PMA_GENOME, default hg38)
RAW=$PMA_OCC_RAW/$RAW_RELEASE; ST=$PMA_OCC_PROCESSED/v1_work; REL=$PMA_OCC_PROCESSED/v1
mkdir -p $ST $REL
cd $HERE
python 01_experiments.py $RAW $ST > $ST/01.log 2>&1
gzip -t $RAW/$PEAKS
pigz -dc -p 4 $RAW/$PEAKS \
  | mawk -v ids=$ST/scope_ids.txt -v cnt=$ST/peak_counts_all.tsv \
      'BEGIN{while((getline l < ids)>0) keep[l]=1} {n[$4]++} ($4 in keep){print} END{for(k in n) print k"\t"n[k] > cnt}' \
  | python 02_peaks.py $ST $RAW/reference 2> $ST/02.log \
  | bgzip -@ 8 > $REL/PMA_chipatlas_${G}_occupancy.bed.gz
tabix -f -p bed $REL/PMA_chipatlas_${G}_occupancy.bed.gz
for r in $TABIX_CHECKS; do  # retrieval check
  tabix $REL/PMA_chipatlas_${G}_occupancy.bed.gz $r | mawk -v r=$r 'BEGIN{split(r,a,/[:-]/)} {n++; if ($1!=a[1] || $3<=a[2] || $2>=a[3]) bad++} END{print r, n+0, "rows,", bad+0, "outside"}'
done > $ST/tabix_check.txt
python 03_finalize.py $RAW $ST $REL > $ST/03.log 2>&1
echo BUILD_DONE
