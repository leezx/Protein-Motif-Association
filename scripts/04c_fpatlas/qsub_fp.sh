#!/bin/bash
# SGE wrapper for fp_sample.sh. One task = one experiment; the task list is "<ATAC|DNase>\t<SRX>" per line.
# h_vmem is a per-process ulimit on Argos (not scaled by slots, not a scheduling limit); m_mem_free is the per-slot reservation.
# submit: qsub -t 1-<n> -tc <max_parallel> -v LIST=<tasks.tsv>,OUT=<outroot> qsub_fp.sh
#   outputs: <outroot>/<assay>/<SRX>.hint_fp.bed.gz and <outroot>/<assay>/qc.tsv; failed tasks in <outroot>/failed.tsv
#            <outroot>/resources/<SRX>.{json,log,scratch_peak_bytes}: CPU, memory, scratch disk, pipeline log
#$ -q all.q
#$ -pe smp 16
#$ -l h_vmem=100G,m_mem_free=4G
#$ -N fpatlas
#$ -j y
#$ -cwd
set -uo pipefail
C=$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")
[ -f "$C/fp_sample.sh" ] || C=${FPATLAS_CODE:?}
export FPATLAS_ENV=/home/zz950/softwares/miniforge3/envs/pma_fpatlas/bin
export FPATLAS_PMAFP=/home/zz950/softwares/miniforge3/envs/pmafp/bin
export FPATLAS_HINT=/home/zz950/PMA_fetch/pma_hint_overlay_v1/bin
export FPATLAS_REF=/home/zz950/DATA/2.PROJECTS/PMA/atac_footprint/processed/fpatlas_ref
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
RA=/home/zz950/DATA/2.PROJECTS/PMA/occupancy_chipatlas/processed/light_v1/raw_accessions
i=${SGE_TASK_ID:-1}; [ "$i" = undefined ] && i=1
IFS=$'\t' read -r ASSAY SRX < <(sed -n "${i}p" "$LIST")
RUNS=$RA/PMA_chipatlas_hg38_${ASSAY}_included_runs.tsv
echo "[$(date -Is)] $(hostname) task $i $ASSAY $SRX"; df -h /tmp | tail -1
[ -s "$OUT/$ASSAY/$SRX.hint_fp.bed.gz" ] && { echo "already done"; exit 0; }
# resources: process-tree CPU and PSS (measure.py, 1 s sampling) + peak node-local scratch (15 s sampling)
mkdir -p "$OUT/resources"
SCRD=${TMPDIR:-/tmp}
( peak=0; while sleep 15; do d=$(du -sb "$SCRD" 2>/dev/null | cut -f1); [ "${d:-0}" -gt "$peak" ] && peak=$d && echo "$peak" > "$OUT/resources/$SRX.scratch_peak_bytes"; done ) &
dpid=$!
# fp_sample.sh watches this shell (FPATLAS_PARENT) and kills its own process group if the job is killed
export FPATLAS_PARENT=$$
"$FPATLAS_PMAFP/python" "$C/measure.py" "$OUT/resources/$SRX.json" -- \
  bash "$C/fp_sample.sh" "$ASSAY" "$SRX" "$RUNS" "$OUT/$ASSAY" "${NSLOTS:-16}" > "$OUT/resources/$SRX.log" 2>&1
rc=$?
kill $dpid 2>/dev/null
[ $rc -eq 0 ] || printf '%s\t%s\t%s\t%s\t%s\n' "$ASSAY" "$SRX" "$rc" "$(hostname)" "$(date -Is)" >> "$OUT/failed.tsv"
echo "[$(date -Is)] exit $rc"
exit $rc
