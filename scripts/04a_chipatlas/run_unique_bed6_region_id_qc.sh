#!/usr/bin/env bash
set -euo pipefail

# Release-level exact ID QC; hard-capped below the PI's 50 GB per-task limit.
if ! command -v systemd-run >/dev/null 2>&1; then
  echo "ERROR: systemd-run is required to enforce the collision-QC memory ceiling" >&2
  exit 2
fi

exec systemd-run --user --scope --quiet \
  --property=MemoryMax=44G \
  --property=MemorySwapMax=0 \
  --property=TasksMax=8 \
  -- "$@"
