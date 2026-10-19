#!/usr/bin/env bash
set -euo pipefail

# Fail closed unless the entire builder and all GNU sort/tabix children run in a
# cgroup with a hard memory ceiling. The capped scope is below the PI's 50 GiB
# per-task limit; sort's -S setting alone is not considered a process limit.
if ! command -v systemd-run >/dev/null 2>&1; then
  echo "ERROR: systemd-run is required to enforce the builder memory ceiling" >&2
  exit 2
fi

exec systemd-run --user --scope --quiet \
  --property=MemoryMax=44G \
  --property=MemorySwapMax=0 \
  --property=TasksMax=8 \
  -- "$@"
