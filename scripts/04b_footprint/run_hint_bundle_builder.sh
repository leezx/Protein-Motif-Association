#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "usage: run_hint_bundle_builder.sh <external-bundle-dir> <external-evidence-dir>" >&2
  exit 2
fi

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
repo_root=$(git -C "$script_dir/../.." rev-parse --show-toplevel)
canonicalize() {
  python3 - "$1" <<'PY'
import os, sys
print(os.path.realpath(os.path.abspath(sys.argv[1])))
PY
}
bundle=$(canonicalize "$1")
evidence=$(canonicalize "$2")
outside_repo() {
  python3 - "$repo_root" "$1" <<'PY'
import os, sys
repo, path = map(os.path.realpath, sys.argv[1:])
try:
    outside = os.path.commonpath((repo, path)) != repo
except ValueError:
    outside = True
sys.exit(0 if outside else 1)
PY
}
outside_repo "$bundle" || { echo "BUNDLE_OUTPUT_MUST_BE_OUTSIDE_GIT_CHECKOUT" >&2; exit 1; }
outside_repo "$evidence" || { echo "EVIDENCE_OUTPUT_MUST_BE_OUTSIDE_GIT_CHECKOUT" >&2; exit 1; }
[[ "$bundle" != "$evidence" ]] || { echo "OUTPUT_DIRS_MUST_BE_DISTINCT" >&2; exit 1; }
[[ "$bundle" != "$evidence"/* && "$evidence" != "$bundle"/* ]] || {
  echo "OUTPUT_DIRS_MUST_NOT_NEST" >&2; exit 1;
}

image=${PMA_HINT_BUILDER_IMAGE:-}
[[ "$image" =~ ^[^[:space:]]+@sha256:[0-9a-f]{64}$ ]] || {
  echo "PMA_HINT_BUILDER_IMAGE_MUST_BE_DIGEST_PINNED" >&2; exit 1;
}
command -v docker >/dev/null || { echo "DOCKER_EXECUTABLE_MISSING" >&2; exit 1; }
for path in "$bundle" "$evidence"; do
  if [[ -e "$path" && -n "$(find "$path" -mindepth 1 -maxdepth 1 -print -quit)" ]]; then
    echo "OUTPUT_DIRECTORY_MUST_BE_EMPTY:$path" >&2; exit 1
  fi
done
mkdir -p -- "$bundle" "$evidence"

# Only the two validated external paths are mounted. The checkout is never mounted.
docker run --rm --platform linux/amd64 \
  --env "PMA_HINT_BUILDER_IMAGE=$image" \
  --mount "type=bind,src=$bundle,dst=/output/bundle" \
  --mount "type=bind,src=$evidence,dst=/output/evidence" \
  "$image" /output/bundle --evidence-dir /output/evidence
