#!/bin/bash
# Step 4b-1 driver (Argos): wait for inputs and environment, then setup -> prep -> smoke test -> round 1.
# usage: run_4b1.sh <raw_dir> <work_dir> <env_prefix> <print_repo> <chrom.sizes> <hg38_blacklist.bed.gz> <env_done_log>
set -uo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
RAW=$1; W=$2; ENV=$3; PR=$4; SIZES=$5; BLGZ=$6; ENVLOG=$7
until [ -f $RAW/download.done ] && [ -f $RAW/refs.done ] && [ -f $RAW/reference/hg38.fa.gz.ok ] \
      && grep -q ENV_DONE $ENVLOG; do sleep 60; done
grep -q tracebind_OK $ENVLOG || { echo "TRACEBIND_NOT_INSTALLED"; }
# RGT 1.0.2 imports pkg_resources at startup; fail before setup/prep unless the reviewed runtime pin is present.
"$ENV/bin/python" -c 'from importlib.metadata import version; assert version("setuptools") == "80.9.0"; import pkg_resources, rgt' \
  || { echo "HINT_ENV_FAIL: require setuptools==80.9.0 and importable RGT/pkg_resources"; exit 1; }
"$ENV/bin/rgt-hint" --help >/dev/null 2>&1 || { echo "HINT_CLI_PREFLIGHT_FAIL"; exit 1; }
source /home/zz950/softwares/miniconda3/etc/profile.d/conda.sh
if ! (
  set +u
  conda activate r4p3
  activation_rc=$?
  set -u
  [ "$activation_rc" -eq 0 ] || exit "$activation_rc"
  [ "${CONDA_DEFAULT_ENV:-}" = r4p3 ] || exit 1
  export R_LIBS=/home/zz950/softwares/R_lib_tracebind:/home/zz950/softwares/R_lib_4
  command -v Rscript >/dev/null || exit 1
  Rscript -e 'suppressPackageStartupMessages({library(GenomicRanges); library(data.table); library(tracebind); library(reticulate)})'
); then
  echo "R_ENV_PREFLIGHT_FAIL"
  exit 1
fi
mkdir -p $W
bash $HERE/00_setup.sh $RAW $W $ENV $SIZES || { echo SETUP_FAIL; exit 1; }
$ENV/bin/python $HERE/01_prep_inputs.py $RAW $W $BLGZ || { echo PREP_FAIL; exit 1; }
# Retain failed smoke outputs and region-filtered BAMs before starting a fresh attempt; never let stale outputs pass.
ATTEMPT=$(date -u +%Y%m%dT%H%M%SZ)
ARCHIVE=$W/smoke_attempt_archive/$ATTEMPT
for prior in "$W/runs_smoke" "$W/bam/smoke"; do
  if [ -e "$prior" ]; then
    mkdir -p "$ARCHIVE"
    mv "$prior" "$ARCHIVE/$(basename "$prior")" || { echo "SMOKE_ARCHIVE_FAIL $prior"; exit 1; }
  fi
done
SMOKE=1 bash $HERE/run_round1.sh $RAW $W $ENV $PR $ENV/bin/python 4 || { echo SMOKE_CALLER_FAIL; exit 1; }
echo SMOKE_DONE
ok=1
for d in gdna ctrl aux; do
  for t in print.r10.track.tsv.gz tracebind.events.bed hint/events.bed tobias/events.bed; do
    [ -f $W/runs_smoke/$d/$t ] || { echo "SMOKE_MISSING $d/$t"; ok=0; }
  done
  [ -s "$W/runs_smoke/$d/print.r10.track.tsv.gz" ] || { echo "SMOKE_PRINT_TRACK_EMPTY $d"; ok=0; }
  gzip -t "$W/runs_smoke/$d/print.r10.track.tsv.gz" 2>/dev/null || { echo "SMOKE_PRINT_TRACK_INVALID $d"; ok=0; }
  [ ! -s $W/runs_smoke/$d/hint/failed.txt ] || { echo "SMOKE_HINT_CHUNK_FAIL $d"; ok=0; }
done
[ $ok = 1 ] || { echo "SMOKE_FAIL: fix runners before round 1"; exit 1; }
bash $HERE/run_round1.sh $RAW $W $ENV $PR $ENV/bin/python 6
