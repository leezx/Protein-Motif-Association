#!/bin/bash
# Step 4b-1 round 1: every caller x {naked gDNA tiles, HCT116 ctrl 2k peaks, HCT116 auxin 2k peaks}, all jobs in
# parallel on Argos (background processes; each wrapped in /usr/bin/time -v for wall time and peak RSS).
# usage: run_round1.sh <raw_dir> <work_dir> <env_prefix> <print_repo> <python_for_tracebind> <cores_per_job> <hint_env_bin>
# env SMOKE=1: first 20 regions of each set, outputs under runs_smoke/ (fast end-to-end check of every runner)
set -uo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
RAW=$1; W=$2; ENV=$3; PRINTREPO=$4; TBPY=$5; C=$6; HINT_ENV_BIN=$7
B=$ENV/bin
FA=$RAW/reference/hg38.fa
BL=$W/hg38-blacklist.v2.bed
SH=$W/print_shared
RUNS=$W/runs; [ "${SMOKE:-0}" = 1 ] && RUNS=$W/runs_smoke
source "$HERE/prepare_bams.sh"
source "$HERE/hint_env.sh"
HINT_BIN=$(select_hint_bin "$HINT_ENV_BIN") || { echo "HINT_ENV_BIN_INVALID $HINT_ENV_BIN" >&2; exit 1; }
BAM_DIR=$(select_bam_cache_dir "$W" "${SMOKE:-0}")
mkdir -p $RUNS $BAM_DIR
[ -s $BL ] || zcat $RAW/../../../occupancy_chipatlas/raw/2026-10-17/reference/hg38-blacklist.v2.bed.gz | cut -f1-3 > $BL
declare -A REG=( [gdna]=$W/regions/gdna_tiles_1kb.bed [ctrl]=$W/regions/hct116_peaks_1kb.sub2000.bed
                 [aux]=$W/regions/hct116_peaks_1kb.sub2000.bed )
declare -A FR=( [gdna]=$W/frags/gDNA.frags.tsv.gz [ctrl]=$W/frags/HCT116_ctrl.frags.tsv.gz
                [aux]=$W/frags/HCT116_aux.frags.tsv.gz )
if [ "${SMOKE:-0}" = 1 ]; then
  mkdir -p $RUNS/regions
  for d in gdna ctrl aux; do head -20 ${REG[$d]} > $RUNS/regions/$d.bed; REG[$d]=$RUNS/regions/$d.bed; done
fi
prepare_bams "$B/python" "$B/samtools" "$HERE/frags_to_bam.py" "$W/hg38.chrom.sizes" "$BAM_DIR" \
  gdna "${FR[gdna]}" "${REG[gdna]}" ctrl "${FR[ctrl]}" "${REG[ctrl]}" \
  aux "${FR[aux]}" "${REG[aux]}" || exit 1
source "${CONDA_PROFILE:-/home/zz950/softwares/miniconda3/etc/profile.d/conda.sh}"
pids=(); labels=()
for d in gdna ctrl aux; do
  O=$RUNS/$d; mkdir -p $O
  ( set +u
    conda activate r4p3
    activation_rc=$?
    set -u
    if [ "$activation_rc" -ne 0 ]; then echo "R_ENV_ACTIVATION_FAIL r4p3 rc=$activation_rc" >&2; exit "$activation_rc"; fi
    if [ "${CONDA_DEFAULT_ENV:-}" != r4p3 ]; then echo "R_ENV_WRONG_ENV ${CONDA_DEFAULT_ENV:-unset}" >&2; exit 1; fi
    command -v Rscript >/dev/null || { echo "RSCRIPT_NOT_FOUND" >&2; exit 1; }
    # PRINT's isolated cladoRcpp overlay must be visible to the PSOCK workers as well as the parent R process.
    export R_LIBS=/home/zz950/PMA_fetch/pma_r_print_overlay_v1/lib:/home/zz950/softwares/R_lib_tracebind:/home/zz950/softwares/R_lib_4
    /usr/bin/time -v Rscript $HERE/run_print.R $PRINTREPO $SH ${REG[$d]} ${FR[$d]} $O/print $C 10,20
      ) > $O/print.log 2>&1 &
  pids+=("$!")
  labels+=("$d/PRINT")
  ( set +u
    conda activate r4p3
    activation_rc=$?
    set -u
    if [ "$activation_rc" -ne 0 ]; then echo "R_ENV_ACTIVATION_FAIL r4p3 rc=$activation_rc" >&2; exit "$activation_rc"; fi
    if [ "${CONDA_DEFAULT_ENV:-}" != r4p3 ]; then echo "R_ENV_WRONG_ENV ${CONDA_DEFAULT_ENV:-unset}" >&2; exit 1; fi
    command -v Rscript >/dev/null || { echo "RSCRIPT_NOT_FOUND" >&2; exit 1; }
    export R_LIBS=/home/zz950/PMA_fetch/pma_r_print_overlay_v1/lib:/home/zz950/softwares/R_lib_tracebind:/home/zz950/softwares/R_lib_4
    /usr/bin/time -v Rscript $HERE/run_tracebind.R $TBPY $SH ${REG[$d]} ${FR[$d]} $O/tracebind $C 0.05
      ) > $O/tracebind.log 2>&1 &
  pids+=("$!")
  labels+=("$d/TraceBIND")
  ( export PATH=$HINT_BIN:$B:$PATH; /usr/bin/time -v bash $HERE/run_hint.sh "$HINT_BIN" "$BAM_DIR/$d.bam" ${REG[$d]} $O/hint $C \
      > $O/hint.log 2>&1 ) &
  pids+=("$!")
  labels+=("$d/HINT")
  ( export PATH=$B:$PATH; /usr/bin/time -v bash $HERE/run_tobias.sh $B "$BAM_DIR/$d.bam" ${REG[$d]} $FA $BL $O/tobias $C \
      > $O/tobias.log 2>&1 ) &
  pids+=("$!")
  labels+=("$d/TOBIAS")
done
source "$HERE/wait_all_jobs.sh"
wait_all_jobs || { echo "CALLER_FAILURE" >&2; exit 1; }
echo ROUND1_DONE
