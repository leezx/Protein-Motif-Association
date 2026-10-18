#!/bin/bash
# Build a minimal, offline-only HINT environment from a pre-audited Linux bundle.
# usage: setup_hint_env.sh {preflight|install} <conda> <pmafp_prefix> <target_prefix> <bundle_dir> <audit_dir>
set -euo pipefail
MODE=$1; CONDA=$2; PMAFP=$3; TARGET=$4; BUNDLE=$5; AUDIT=$6
HERE=$(cd "$(dirname "$0")" && pwd)
PMAFP_CONDA_BEFORE=${AUDIT}/pmafp-conda-before.txt
PMAFP_PIP_BEFORE=${AUDIT}/pmafp-pip-before.txt
PMAFP_CONDA_AFTER=${AUDIT}/pmafp-conda-after.txt
PMAFP_PIP_AFTER=${AUDIT}/pmafp-pip-after.txt
CONDA_LOCK=${BUNDLE}/conda-explicit-linux-64.lock
PIP_LOCK=${BUNDLE}/pip-requirements.lock
ARTIFACTS=${BUNDLE}/artifacts.sha256
BUNDLE_META=${BUNDLE}/bundle-manifest.json
CONDA_SPECS_TMP=${AUDIT}/conda-specs.generated.txt
CONDA_EXPLICIT_TMP=${AUDIT}/conda-explicit.generated.txt
AUDIT_DONE=0

sha256_file() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$1" | awk '{print $1}'
  else
    shasum -a 256 "$1" | awk '{print $1}'
  fi
}

# Bound each serial Conda/pip subprocess below 50 GB. The limit is conservative
# on virtual address space; installations that need more fail closed.
run_bounded() {
  (
    if [[ "$(uname -s)" == Linux ]]; then
      ulimit -v 48000000 || { echo "MEMORY_LIMIT_UNAVAILABLE" >&2; exit 125; }
    fi
    exec "$@"
  )
}

usage() {
  echo "usage: $0 {preflight|install} <conda> <pmafp_prefix> <target_prefix> <bundle_dir> <audit_dir>" >&2
  exit 64
}

[[ "$MODE" == preflight || "$MODE" == install ]] || usage
[[ -x "$CONDA" && -x "$PMAFP/bin/python" ]] || { echo "SOURCE_ENV_INVALID $PMAFP" >&2; exit 2; }
[[ -d "$BUNDLE" ]] || { echo "HINT_BUNDLE_MISSING $BUNDLE" >&2; exit 2; }
[[ ! -e "$TARGET" ]] || { echo "HINT_TARGET_EXISTS; preserve and inspect $TARGET" >&2; exit 2; }
mkdir -p "$AUDIT"

audit_source() {
  local failed=0
  if ! "$CONDA" list --explicit --prefix "$PMAFP" > "$PMAFP_CONDA_AFTER"; then failed=1; fi
  if ! "$PMAFP/bin/python" -m pip freeze --all > "$PMAFP_PIP_AFTER"; then failed=1; fi
  if [[ ! -s "$PMAFP_CONDA_BEFORE" ]] || ! cmp -s "$PMAFP_CONDA_BEFORE" "$PMAFP_CONDA_AFTER"; then failed=1; fi
  if [[ ! -s "$PMAFP_PIP_BEFORE" ]] || ! cmp -s "$PMAFP_PIP_BEFORE" "$PMAFP_PIP_AFTER"; then failed=1; fi
  AUDIT_DONE=1
  if (( failed )); then
    echo "PMAFP_INTEGRITY_FAIL: source environment manifests unavailable or changed" >&2
    return 1
  fi
  echo PMAFP_INTEGRITY_OK
}

on_exit() {
  local original_status=$?
  trap - EXIT
  if [[ "$MODE" == install && "$AUDIT_DONE" == 0 ]]; then
    if ! audit_source && (( original_status == 0 )); then original_status=1; fi
  fi
  exit "$original_status"
}

# Validate bundle paths and hashes before passing any package archive to Conda or pip.
preflight_bundle() {
  local subdir name version build filename digest source failed
  [[ -s "$CONDA_LOCK" ]] || { echo "CONDA_LOCK_MISSING $CONDA_LOCK" >&2; return 1; }
  [[ -s "$PIP_LOCK" ]] || { echo "PIP_LOCK_MISSING $PIP_LOCK" >&2; return 1; }
  [[ -s "$ARTIFACTS" ]] || { echo "ARTIFACT_HASHES_MISSING $ARTIFACTS" >&2; return 1; }
  [[ -s "$BUNDLE_META" ]] || { echo "BUNDLE_MANIFEST_MISSING $BUNDLE_META" >&2; return 1; }
  if ! "$PMAFP/bin/python" "$HERE/validate_hint_bundle.py" "$BUNDLE" > "$AUDIT/bundle-validation.log" 2>&1; then
    cat "$AUDIT/bundle-validation.log" >&2
    return 1
  fi
  : > "$AUDIT/artifact-hashes.log"
  failed=0
  while read -r digest relative_path; do
    [[ -n "$digest" && "$digest" != \#* ]] || continue
    case "/$relative_path/" in
      *"/../"*|"//"*) echo "ARTIFACT_PATH_INVALID $relative_path" >> "$AUDIT/artifact-hashes.log"; failed=1; continue ;;
    esac
    if [[ ! "$digest" =~ ^[a-fA-F0-9]{64}$ || ! -s "$BUNDLE/$relative_path" ]]; then
      echo "MISSING_OR_INVALID_ARTIFACT $relative_path" >> "$AUDIT/artifact-hashes.log"
      failed=1
      continue
    fi
    if [[ "$(sha256_file "$BUNDLE/$relative_path")" != "$digest" ]]; then
      echo "HINT_ARTIFACT_HASH_FAIL $relative_path" >> "$AUDIT/artifact-hashes.log"
      failed=1
    fi
  done < "$ARTIFACTS"
  : > "$CONDA_SPECS_TMP"
  while IFS=$'\t' read -r subdir name version build filename digest; do
    [[ -n "$subdir" && "$subdir" != \#* ]] || continue
    if [[ "$subdir" != linux-64 && "$subdir" != noarch ]]; then
      echo "CONDA_LOCK_BAD_SUBDIR $subdir" >> "$AUDIT/artifact-hashes.log"; failed=1; continue
    fi
    if [[ "$filename" == */* || "$filename" == *..* || ! "$digest" =~ ^[a-fA-F0-9]{64}$ ]]; then
      echo "CONDA_LOCK_BAD_ROW $name $version $build $filename" >> "$AUDIT/artifact-hashes.log"; failed=1; continue
    fi
    source="$BUNDLE/conda/$subdir/$filename"
    if [[ ! -s "$source" ]]; then
      echo "MISSING_CONDA_ARTIFACT $name=$version=$build ($source)" >> "$AUDIT/artifact-hashes.log"; failed=1; continue
    fi
    if [[ "$(sha256_file "$source")" != "$digest" ]]; then
      echo "CONDA_ARTIFACT_HASH_MISMATCH $filename" >> "$AUDIT/artifact-hashes.log"; failed=1; continue
    fi
    printf '%s=%s=%s\n' "$name" "$version" "$build" >> "$CONDA_SPECS_TMP"
  done < "$CONDA_LOCK"
  if [[ "$failed" != 0 ]]; then cat "$AUDIT/artifact-hashes.log" >&2; return 1; fi
  [[ -s "$BUNDLE/conda/linux-64/repodata.json" && -s "$BUNDLE/conda/noarch/repodata.json" ]] || {
    echo "CONDA_LOCAL_CHANNEL_REPODATA_MISSING" >&2; return 1;
  }
  [[ "$(wc -l < "$CONDA_SPECS_TMP" | tr -d ' ')" -gt 0 ]] || { echo "CONDA_LOCK_EMPTY" >&2; return 1; }
  CONDA_CHANNEL_URI=$("$PMAFP/bin/python" -c 'from pathlib import Path; import sys; print(Path(sys.argv[1]).resolve().as_uri())' "$BUNDLE/conda")
  if ! run_bounded "$CONDA" create --dry-run --json --offline --override-channels --no-default-packages --copy \
      --channel "$CONDA_CHANNEL_URI" --prefix "$TARGET" --file "$CONDA_SPECS_TMP" \
      > "$AUDIT/conda-dry-run.json" 2> "$AUDIT/conda-dry-run.stderr"; then
    echo "CONDA_PREFLIGHT_FAIL; inspect $AUDIT/conda-dry-run.json and .stderr" >&2
    return 1
  fi
  if ! "$PMAFP/bin/python" - "$AUDIT/conda-dry-run.json" "$CONDA_LOCK" <<'PY'
import json, sys
with open(sys.argv[1], encoding="utf-8") as handle:
    result = json.load(handle)
with open(sys.argv[2], encoding="utf-8") as handle:
    expected = {(fields[1].lower(), fields[2], fields[3]): (fields[0], fields[4])
                for line in handle if line.strip() and not line.lstrip().startswith("#")
                for fields in [line.rstrip("\n").split("\t")] if len(fields) == 6}
linked = (result.get("actions") or {}).get("LINK")
if not isinstance(linked, list):
    raise SystemExit("CONDA_DRY_RUN_ACTIONS_UNVERIFIABLE")
actual = {}
for item in linked:
    identity = (item.get("name", "").lower(), item.get("version", ""),
                item.get("build_string", item.get("build", "")))
    if identity in actual:
        raise SystemExit(f"CONDA_DRY_RUN_DUPLICATE_LINK:{identity}")
    if identity not in expected:
        raise SystemExit(f"CONDA_DEPENDENCY_CLOSURE_MISMATCH unexpected={identity}")
    expected_subdir, expected_filename = expected[identity]
    observed_subdir = item.get("subdir", item.get("platform"))
    if observed_subdir and observed_subdir != expected_subdir:
        raise SystemExit(f"CONDA_LINK_SUBDIR_MISMATCH:{identity}:{observed_subdir}:{expected_subdir}")
    observed_filename = item.get("fn", item.get("filename"))
    if observed_filename and observed_filename != expected_filename:
        raise SystemExit(f"CONDA_LINK_FILENAME_MISMATCH:{identity}:{observed_filename}:{expected_filename}")
    actual[identity] = item
if set(actual) != set(expected):
    raise SystemExit(f"CONDA_DEPENDENCY_CLOSURE_MISMATCH expected={sorted(expected)} actual={sorted(actual)}")
PY
  then
    echo "CONDA_DEPENDENCY_CLOSURE_UNVERIFIED; inspect $AUDIT/conda-dry-run.json" >&2
    return 1
  fi
  if ! "$PMAFP/bin/python" - "$CONDA_LOCK" "$BUNDLE/conda" "$CONDA_EXPLICIT_TMP" <<'PY'
from pathlib import Path
import sys
lock_path, channel, output_path = sys.argv[1:]
rows = []
with open(lock_path, encoding="utf-8") as handle:
    for line_number, line in enumerate(handle, 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        fields = line.rstrip("\n").split("\t")
        if len(fields) != 6:
            raise SystemExit(f"CONDA_LOCK_ROW_INVALID:{line_number}")
        subdir, _name, _version, _build, filename, _digest = fields
        rows.append((Path(channel, subdir, filename).resolve().as_uri()))
if not rows:
    raise SystemExit("CONDA_LOCK_EMPTY")
with open(output_path, "w", encoding="utf-8") as handle:
    handle.write("@EXPLICIT\n")
    handle.writelines(url + "\n" for url in rows)
PY
  then
    echo "CONDA_EXPLICIT_LOCK_GENERATION_FAIL" >&2
    return 1
  fi
  if ! run_bounded env PIP_NO_CACHE_DIR=1 "$PMAFP/bin/python" -m pip install --dry-run --no-deps --no-index \
      --find-links "$BUNDLE/wheels" --only-binary=:all: --require-hashes -r "$PIP_LOCK" \
      > "$AUDIT/pip-dry-run.log" 2>&1; then
    echo "PIP_PREFLIGHT_FAIL: missing/incompatible locked wheel; see $AUDIT/pip-dry-run.log" >&2
    return 1
  fi
  echo HINT_OFFLINE_PREFLIGHT_OK
}

preflight_bundle || { echo "HINT_OFFLINE_PREFLIGHT_FAIL; inspect $AUDIT" >&2; exit 1; }
if [[ "$MODE" == preflight ]]; then
  echo "HINT_PREFLIGHT_ONLY target=$TARGET; no Conda environment was created"
  exit 0
fi

trap on_exit EXIT
"$CONDA" list --explicit --prefix "$PMAFP" > "$PMAFP_CONDA_BEFORE"
"$PMAFP/bin/python" -m pip freeze --all > "$PMAFP_PIP_BEFORE"

# Create at the final prefix only after preflight has verified every locked artifact.
run_bounded "$CONDA" create --yes --offline --no-default-packages --copy \
  --prefix "$TARGET" --file "$CONDA_EXPLICIT_TMP"
run_bounded env PIP_NO_CACHE_DIR=1 "$TARGET/bin/python" -m pip install --no-deps --no-index \
  --find-links "$BUNDLE/wheels" --only-binary=:all: --require-hashes -r "$PIP_LOCK"
"$TARGET/bin/python" -m pip check
"$TARGET/bin/python" - <<'PY'
from importlib.metadata import PackageNotFoundError, version
import numpy
import pkg_resources
import rgt
from numpy import mat
assert version("RGT") == "1.0.2"
assert version("setuptools") == "80.9.0"
assert numpy.__version__ == "1.26.4"
try:
    version("TOBIAS")
except PackageNotFoundError:
    pass
else:
    raise SystemExit("TOBIAS must not be installed in the isolated HINT environment")
print("HINT_IMPORT_OK", version("RGT"), numpy.__version__, version("setuptools"))
PY
"$TARGET/bin/rgt-hint" --help
"$TARGET/bin/rgt-hint" footprinting --help
audit_source

CODE_ROOT=$(cd "$HERE/../.." && pwd)
CODE_COMMIT=$(git -C "$CODE_ROOT" rev-parse HEAD)
LOCK_SHA="$(sha256_file "$CONDA_LOCK"):$(sha256_file "$PIP_LOCK"):$(sha256_file "$ARTIFACTS"):$(sha256_file "$BUNDLE_META")"
READY_TMP="$TARGET/.HINT_ENV_READY.json.tmp.$$"
"$TARGET/bin/python" - "$READY_TMP" "$TARGET/HINT_ENV_READY.json" "$TARGET" "$CODE_COMMIT" "$LOCK_SHA" <<'PY'
import json, os, sys
from datetime import datetime, timezone
from importlib.metadata import version
from platform import python_version
import numpy
temporary_file, target_file, prefix, commit, lock_sha = sys.argv[1:]
payload = {
    "status": "HINT_ENV_READY",
    "prefix": prefix,
    "code_commit": commit,
    "bundle_lock_sha256": lock_sha,
    "python": python_version(),
    "numpy": numpy.__version__,
    "rgt": version("RGT"),
    "setuptools": version("setuptools"),
    "verified_at_utc": datetime.now(timezone.utc).isoformat(),
}
with open(temporary_file, "x", encoding="utf-8") as handle:
    json.dump(payload, handle, sort_keys=True, indent=2)
    handle.write("\n")
os.replace(temporary_file, target_file)
PY
echo "HINT_ENV_READY $TARGET/HINT_ENV_READY.json"
