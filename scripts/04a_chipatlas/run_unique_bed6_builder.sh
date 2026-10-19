#!/usr/bin/env bash
set -euo pipefail

# Run only inside a single-slot Grid Engine job requested with h_vmem=44G.
# Grid Engine applies h_vmem as a per-job combined-virtual-memory hard limit;
# Python rechecks the job record and process RLIMIT_AS before reading inputs.
[[ -n "${JOB_ID:-}" && "${NSLOTS:-}" == 1 ]] || { echo "ERROR: submit as a one-slot Grid Engine job" >&2; exit 2; }
for value in "$(ulimit -Sv)" "$(ulimit -Hv)"; do
  [[ "$value" =~ ^[0-9]+$ ]] || { echo "ERROR: finite soft/hard RLIMIT_AS required" >&2; exit 2; }
  (( 10#$value > 0 && 10#$value <= 44*1024*1024 )) || { echo "ERROR: RLIMIT_AS exceeds 44 GiB" >&2; exit 2; }
done
exec "$@"
