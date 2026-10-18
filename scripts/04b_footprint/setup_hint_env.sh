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
EXPLICIT_TMP=${AUDIT}/conda-explicit.generated.txt
AUDIT_DONE=0
RGT_SDIST_SHA256=2169e71f2018340d101146bab09bb933a384611c5f7b76f4be5999fa835cac7e

sha256_file() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$1" | awk '{print $1}'
  else
    shasum -a 256 "$1" | awk '{print $1}'
  fi
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
  local line subdir name version build filename digest source explicit_file uri
  [[ -s "$CONDA_LOCK" ]] || { echo "CONDA_LOCK_MISSING $CONDA_LOCK" >&2; return 1; }
  [[ -s "$PIP_LOCK" ]] || { echo "PIP_LOCK_MISSING $PIP_LOCK" >&2; return 1; }
  [[ -s "$ARTIFACTS" ]] || { echo "ARTIFACT_HASHES_MISSING $ARTIFACTS" >&2; return 1; }
  [[ -s "$BUNDLE_META" ]] || { echo "BUNDLE_MANIFEST_MISSING $BUNDLE_META" >&2; return 1; }
  if ! "$PMAFP/bin/python" - "$BUNDLE_META" "$CONDA_LOCK" "$PIP_LOCK" "$ARTIFACTS" "$RGT_SDIST_SHA256" <<'PY'
import hashlib, json, re, sys
manifest_path, conda_lock, pip_lock, artifact_list, expected_sdist = sys.argv[1:]
with open(manifest_path, encoding="utf-8") as handle:
    manifest = json.load(handle)
assert manifest["schema_version"] == 1
assert manifest["target_platform"] == "linux-64"
assert manifest["python_abi"] == "cp311"
assert tuple(map(int, manifest["glibc_max"].split("."))) <= (2, 23)
assert len(manifest["builder"])
assert manifest["rgt_sdist_sha256"] == expected_sdist
wheel = manifest["rgt_wheel"]
wheel_sha = manifest["rgt_wheel_sha256"]
assert wheel.endswith(".whl") and "/" not in wheel and ".." not in wheel
assert re.fullmatch(r"[a-fA-F0-9]{64}", wheel_sha)
for key, path in (("conda_lock_sha256", conda_lock), ("pip_lock_sha256", pip_lock), ("artifacts_sha256", artifact_list)):
    digest = hashlib.sha256(open(path, "rb").read()).hexdigest()
    assert manifest[key] == digest, f"{key} mismatch"
with open(pip_lock, encoding="utf-8") as handle:
    pip_text = handle.read()
assert "RGT==1.0.2" in pip_text and wheel_sha in pip_text
with open(artifact_list, encoding="utf-8") as handle:
    assert any(line.split()[-1:] == ["wheels/" + wheel] and line.split()[0] == wheel_sha
               for line in handle if line.strip() and not line.lstrip().startswith("#"))
with open(conda_lock, encoding="utf-8") as handle:
    rows = [line.rstrip("\n").split("\t") for line in handle
            if line.strip() and not line.lstrip().startswith("#")]
packages = {row[1].lower(): row[2] for row in rows if len(row) == 6}
assert packages.get("python", "").startswith("3.11."), "Python 3.11 absent from Conda lock"
assert packages.get("numpy") == "1.26.4", "NumPy 1.26.4 absent from Conda lock"
assert packages.get("setuptools") == "80.9.0", "setuptools 80.9.0 absent from Conda lock"
PY
  then
    echo "HINT_BUNDLE_MANIFEST_INVALID: platform, runtime, RGT provenance, wheel, or lock digest mismatch" >&2
    return 1
  fi
  : > "$AUDIT/artifact-hashes.log"
  while read -r digest relative_path; do
    [[ -n "$digest" && "$digest" != \#* ]] || continue
    case "/$relative_path/" in *"/../"*|"//"*) echo "ARTIFACT_PATH_INVALID $relative_path" >> "$AUDIT/artifact-hashes.log"; return 1 ;; esac
    [[ "$digest" =~ ^[a-fA-F0-9]{64}$ && -s "$BUNDLE/$relative_path" ]] || {
      echo "MISSING_OR_INVALID_ARTIFACT $relative_path" >> "$AUDIT/artifact-hashes.log"
      echo "MISSING_OR_INVALID_ARTIFACT $relative_path" >&2
      return 1
    }
    [[ "$(sha256_file "$BUNDLE/$relative_path")" == "$digest" ]] || {
      echo "HINT_ARTIFACT_HASH_FAIL $relative_path" >> "$AUDIT/artifact-hashes.log"
      echo "HINT_ARTIFACT_HASH_FAIL $relative_path" >&2
      return 1
    }
  done < "$ARTIFACTS"
  : > "$EXPLICIT_TMP"
  printf '@EXPLICIT\n' >> "$EXPLICIT_TMP"
  while IFS=$'\t' read -r subdir name version build filename digest; do
    [[ -n "$subdir" && "$subdir" != \#* ]] || continue
    [[ "$subdir" == linux-64 || "$subdir" == noarch ]] || { echo "CONDA_LOCK_BAD_SUBDIR $subdir" >&2; return 1; }
    [[ "$filename" != */* && "$filename" != *..* && "$digest" =~ ^[a-fA-F0-9]{64}$ ]] || {
      echo "CONDA_LOCK_BAD_ROW $name $version $build $filename" >&2; return 1;
    }
    source="$BUNDLE/conda/$subdir/$filename"
    [[ -s "$source" ]] || { echo "MISSING_CONDA_ARTIFACT $name=$version=$build ($source)" >&2; return 1; }
    [[ "$(sha256_file "$source")" == "$digest" ]] || {
      echo "CONDA_ARTIFACT_HASH_MISMATCH $filename" >&2; return 1;
    }
    uri=$("$PMAFP/bin/python" -c 'from pathlib import Path; import sys; print(Path(sys.argv[1]).resolve().as_uri())' "$source")
    printf '%s\n' "$uri" >> "$EXPLICIT_TMP"
  done < "$CONDA_LOCK"
  [[ "$(wc -l < "$EXPLICIT_TMP" | tr -d ' ')" -gt 1 ]] || { echo "CONDA_LOCK_EMPTY" >&2; return 1; }
  if ! CONDA_JSON="$AUDIT/conda-dry-run.json" "$CONDA" create --dry-run --json --offline \
      --override-channels --no-default-packages --prefix "$TARGET" --file "$EXPLICIT_TMP" \
      > "$AUDIT/conda-dry-run.stdout" 2> "$AUDIT/conda-dry-run.stderr"; then
    echo "CONDA_PREFLIGHT_FAIL; inspect $AUDIT/conda-dry-run.{stdout,stderr}" >&2
    return 1
  fi
  if ! PIP_NO_CACHE_DIR=1 "$PMAFP/bin/python" -m pip install --dry-run --ignore-installed --no-index \
      --find-links "$BUNDLE/wheels" --only-binary=:all: --require-hashes -r "$PIP_LOCK" \
      > "$AUDIT/pip-dry-run.log" 2>&1; then
    echo "PIP_PREFLIGHT_FAIL: missing/incompatible wheel or unresolved locked dependency; see $AUDIT/pip-dry-run.log" >&2
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
"$CONDA" create --yes --offline --override-channels --no-default-packages \
  --prefix "$TARGET" --file "$EXPLICIT_TMP"
PIP_NO_CACHE_DIR=1 "$TARGET/bin/python" -m pip install --no-index \
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
