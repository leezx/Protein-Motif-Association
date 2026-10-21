#!/usr/bin/env bash
# Run each footprint caller once, sequentially, on the same inputs with the same core budget, under measure.py.
# usage: 02_run_callers.sh <result_root> <cores> <tool,tool,...>   tools: tobias hint print
set -uo pipefail
R=$1; N=$2; TOOLS=$3
C=$(cd "$(dirname "$0")" && pwd)
E=/home/zz950/softwares/miniforge3/envs/pmafp/bin
HINT_BIN=/home/zz950/PMA_fetch/pma_hint_overlay_v1/bin
RAW=/home/zz950/DATA/2.PROJECTS/PMA/atac_footprint/raw/2026-10-17
W=/home/zz950/DATA/2.PROJECTS/PMA/atac_footprint/processed/round1
FA=$RAW/reference/hg38.fa
BL=$W/hg38-blacklist.v2.bed
PRINT_REPO=/home/zz950/softwares/src/PRINT
PRINT_SHARED=$W/print_shared
RSCRIPT=/home/zz950/softwares/miniconda3/envs/r4p3/bin/Rscript
export R_LIBS=/home/zz950/PMA_fetch/pma_r_print_overlay_v1/lib:/home/zz950/softwares/R_lib_tracebind:/home/zz950/softwares/R_lib_4
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 CUDA_VISIBLE_DEVICES=''
export PYTHONNOUSERSITE=1 PATH="$E:$PATH"
BAM=$R/inputs/atac.filt.bam; FRAGS=$R/inputs/atac.frags.tsv.gz; BED=$R/inputs/regions_1kb.bed
IFS=, read -r -a T <<< "$TOOLS"
for tool in "${T[@]}"; do
  O=$R/callers/$tool; mkdir -p "$O"
  echo "[$(date -Is)] start $tool"
  case $tool in
    tobias) "$E/python" "$C/measure.py" "$O/resource.json" -- bash "$C/run_tobias.sh" "$E" "$BAM" "$BED" "$FA" "$BL" "$O" "$N" ;;
    hint)   "$E/python" "$C/measure.py" "$O/resource.json" -- bash "$C/run_hint.sh" "$HINT_BIN" "$BAM" "$BED" "$O" "$N" ;;
    print)  "$E/python" "$C/measure.py" "$O/resource.json" -- "$RSCRIPT" "$C/run_print.R" "$PRINT_REPO" "$PRINT_SHARED" "$BED" "$FRAGS" "$O" "$N" 10,20 > "$O/print.log" 2>&1 ;;
    tracebind) "$E/python" "$C/measure.py" "$O/resource.json" -- bash "$C/run_tracebind.sh" "$BED" "$FRAGS" "$FA" "$PRINT_SHARED" "$O" "$N" > "$O/tracebind.log" 2>&1 ;;
    *) echo "unknown tool $tool"; continue ;;
  esac
  echo "[$(date -Is)] end $tool exit=$?"
done
