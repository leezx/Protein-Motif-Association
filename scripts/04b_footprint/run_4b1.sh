#!/bin/bash
# Step 4b-1 driver (Argos): wait for inputs and environment, then setup -> prep -> smoke test -> round 1.
# usage: run_4b1.sh <raw_dir> <work_dir> <env_prefix> <print_repo> <chrom.sizes> <hg38_blacklist.bed.gz> <env_done_log> <hint_env_prefix>
set -uo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
RAW=$1; W=$2; ENV=$3; PR=$4; SIZES=$5; BLGZ=$6; ENVLOG=$7; HINT_ENV=$8
until [ -f $RAW/download.done ] && [ -f $RAW/refs.done ] && [ -f $RAW/reference/hg38.fa.gz.ok ] \
      && grep -q ENV_DONE $ENVLOG; do sleep 60; done
grep -q tracebind_OK $ENVLOG || { echo "TRACEBIND_NOT_INSTALLED"; }
# HINT's RGT 1.0.2 needs NumPy 1.x; keep TOBIAS and the other callers in pmafp's NumPy 2.x runtime.
CODE_ROOT=$(cd "$HERE/../.." && pwd)
CODE_COMMIT=$(git -C "$CODE_ROOT" rev-parse HEAD) || { echo "CODE_COMMIT_UNAVAILABLE"; exit 1; }
if ! "$HINT_ENV/bin/python" - "$HINT_ENV/HINT_ENV_READY.json" "$HINT_ENV" "$CODE_COMMIT" <<'PY'
import json, os, sys
from importlib.metadata import PackageNotFoundError, version
import numpy, pkg_resources, rgt
from numpy import mat
ready_file, prefix, commit = sys.argv[1:]
with open(ready_file, encoding="utf-8") as handle:
    ready = json.load(handle)
assert ready["status"] == "HINT_ENV_READY"
assert os.path.realpath(ready["prefix"]) == os.path.realpath(prefix)
assert ready["code_commit"] == commit
assert ready["bundle_lock_sha256"]
assert version("RGT") == "1.0.2"
assert version("setuptools") == "80.9.0"
assert numpy.__version__ == "1.26.4"
try:
    version("TOBIAS")
except PackageNotFoundError:
    pass
else:
    raise SystemExit("TOBIAS must stay isolated in pmafp")
PY
then
  echo "HINT_ENV_FAIL: READY manifest or required HINT runtime validation failed"
  exit 1
fi
"$HINT_ENV/bin/python" -m pip check || { echo "HINT_DEPENDENCY_CHECK_FAIL"; exit 1; }
"$HINT_ENV/bin/rgt-hint" --help >/dev/null 2>&1 || { echo "HINT_CLI_PREFLIGHT_FAIL"; exit 1; }
"$HINT_ENV/bin/rgt-hint" footprinting --help >/dev/null 2>&1 || { echo "HINT_FOOTPRINTING_PREFLIGHT_FAIL"; exit 1; }
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
for prior in "$W/runs_smoke" "$W/bam/smoke" "$W/HINT_SMALLBED_VALIDATED.json"; do
  if [ -e "$prior" ]; then
    mkdir -p "$ARCHIVE"
    mv "$prior" "$ARCHIVE/$(basename "$prior")" || { echo "SMOKE_ARCHIVE_FAIL $prior"; exit 1; }
  fi
done
SMOKE=1 bash $HERE/run_round1.sh $RAW $W $ENV $PR $ENV/bin/python 4 "$HINT_ENV/bin" || { echo SMOKE_CALLER_FAIL; exit 1; }
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
SMALLBED_MARKER="$W/HINT_SMALLBED_VALIDATED.json"
"$HINT_ENV/bin/python" - "$SMALLBED_MARKER" "$W/runs_smoke" "$W/bam/smoke" "$HINT_ENV" "$CODE_COMMIT" <<'PY' || { echo HINT_SMALLBED_MARKER_WRITE_FAIL; exit 1; }
import hashlib, json, os, sys
from datetime import datetime, timezone
marker, runs, bam_dir, hint_env, commit = sys.argv[1:]
def digest(path):
    value = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()
ready_path = os.path.join(hint_env, "HINT_ENV_READY.json")
with open(ready_path, encoding="utf-8") as handle:
    ready = json.load(handle)
if ready.get("status") != "HINT_ENV_READY" or ready.get("code_commit") != commit:
    raise SystemExit("HINT_READY_MARKER_MISMATCH")
groups = {}
for group in ("gdna", "ctrl", "aux"):
    events = os.path.join(runs, group, "hint", "events.bed")
    failed = os.path.join(runs, group, "hint", "failed.txt")
    bam = os.path.join(bam_dir, group + ".bam")
    regions = os.path.join(runs, "regions", group + ".bed")
    if not (os.path.isfile(events) and os.path.isfile(bam) and os.path.isfile(regions)):
        raise SystemExit("HINT_SMALLBED_OUTPUT_MISSING:" + group)
    if os.path.isfile(failed) and os.path.getsize(failed):
        raise SystemExit("HINT_SMALLBED_CHUNK_FAILURE:" + group)
    groups[group] = {
        "events": os.path.abspath(events), "events_sha256": digest(events),
        "bam": os.path.abspath(bam), "bam_sha256": digest(bam),
        "regions": os.path.abspath(regions), "regions_sha256": digest(regions),
    }
payload = {
    "status": "HINT_SMALLBED_VALIDATED",
    "code_commit": commit,
    "hint_env_prefix": os.path.realpath(hint_env),
    "hint_env_lock_sha256": ready["bundle_lock_sha256"],
    "groups": groups,
    "verified_at_utc": datetime.now(timezone.utc).isoformat(),
}
temporary = marker + ".tmp." + str(os.getpid())
with open(temporary, "x", encoding="utf-8") as handle:
    json.dump(payload, handle, sort_keys=True, indent=2)
    handle.write("\n")
os.replace(temporary, marker)
PY
"$HINT_ENV/bin/python" - "$SMALLBED_MARKER" "$HINT_ENV" "$CODE_COMMIT" <<'PY' || { echo HINT_SMALLBED_MARKER_VERIFY_FAIL; exit 1; }
import json, os, sys
marker, hint_env, commit = sys.argv[1:]
with open(marker, encoding="utf-8") as handle:
    payload = json.load(handle)
with open(os.path.join(hint_env, "HINT_ENV_READY.json"), encoding="utf-8") as handle:
    ready = json.load(handle)
assert payload["status"] == "HINT_SMALLBED_VALIDATED"
assert payload["code_commit"] == commit
assert os.path.realpath(payload["hint_env_prefix"]) == os.path.realpath(hint_env)
assert payload["hint_env_lock_sha256"] == ready["bundle_lock_sha256"]
assert set(payload["groups"]) == {"gdna", "ctrl", "aux"}
def digest(path):
    import hashlib
    value = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()
for record in payload["groups"].values():
    for key in ("events", "bam", "regions"):
        assert digest(record[key]) == record[key + "_sha256"]
PY
echo "HINT_SMALLBED_VALIDATED $SMALLBED_MARKER"
echo SMOKE_DONE
bash $HERE/run_round1.sh $RAW $W $ENV $PR $ENV/bin/python 6 "$HINT_ENV/bin"
