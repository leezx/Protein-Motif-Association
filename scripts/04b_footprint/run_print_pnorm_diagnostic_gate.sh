#!/usr/bin/env bash
set -euo pipefail

DIAGNOSTIC=/home/zz950/PMA_fetch/pma_print_pnorm_diag_code_20261020_v1/diagnose_print_pnorm.R
PRINT_SOURCE=/home/zz950/softwares/src/PRINT
V5_MAIN=/home/zz950/DATA/2.PROJECTS/PMA/atac_footprint/processed/round1/runs_print_stream_validation_rcapps3_20261020_v5/print_main_print
PEAKS=/home/zz950/PMA_fetch/pma_print_stream_validation_rcapps3_20261020_v5/eight_frozen_peaks.bed
PEAK_MAP=/home/zz950/PMA_fetch/pma_print_stream_validation_rcapps3_20261020_v5/eight_frozen_peaks.map.tsv
OUTPUT_PREFIX=/home/zz950/DATA/2.PROJECTS/PMA/atac_footprint/processed/round1/runs_print_stream_validation_rcapps3_20261020_v5/print
SHARED_MODELS=/home/zz950/DATA/2.PROJECTS/PMA/atac_footprint/processed/round1/print_shared
EVIDENCE=/home/zz950/PMA_fetch/pma_print_stream_validation_rcapps3_20261020_v5
DIAGNOSTIC_OUTPUT=/home/zz950/PMA_fetch/pma_print_pnorm_diagnostic_rcapps3_20261020_v1
R_SCRIPT=/home/zz950/softwares/miniconda3/envs/r4p3/bin/Rscript

allowed_cpus=
while IFS= read -r line; do
  case "$line" in
    Cpus_allowed_list:*) allowed_cpus=${line#*:} ;;
  esac
done < /proc/self/status
allowed_cpus=${allowed_cpus//[[:space:]]/}
first_cpu=${allowed_cpus%%,*}
cpu=${first_cpu%%-*}
if [[ ! "$cpu" =~ ^[0-9]+$ ]]; then
  printf 'Unable to parse a permitted CPU from Cpus_allowed_list=%s\n' "$allowed_cpus" >&2
  exit 70
fi

export R_LIBS=/home/zz950/PMA_fetch/pma_r_print_overlay_v1/lib:/home/zz950/softwares/R_lib_tracebind:/home/zz950/softwares/R_lib_4
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
export VECLIB_MAXIMUM_THREADS=1 BLIS_NUM_THREADS=1
export CUDA_VISIBLE_DEVICES=''

exec /usr/bin/taskset -c "$cpu" /usr/bin/timeout --signal=TERM --kill-after=60s 1800s \
  "$R_SCRIPT" "$DIAGNOSTIC" "$PRINT_SOURCE" "$V5_MAIN" "$PEAKS" "$PEAK_MAP" \
  "$OUTPUT_PREFIX" "$SHARED_MODELS" "$EVIDENCE" "$DIAGNOSTIC_OUTPUT"
