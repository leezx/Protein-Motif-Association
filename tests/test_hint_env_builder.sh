#!/bin/bash
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
TMP=$(mktemp -d)
trap 'if [[ "${KEEP_HINT_TEST_TMP:-0}" == 1 ]]; then echo "fixture temp: $TMP" >&2; else rm -rf "$TMP"; fi' EXIT
SETUP="$ROOT/scripts/04b_footprint/setup_hint_env.sh"
MOCK_ROOT="$TMP/mock"
CONDA="$MOCK_ROOT/conda"
PMAFP="$MOCK_ROOT/pmafp"
BUNDLE="$MOCK_ROOT/bundle"
AUDIT="$MOCK_ROOT/audit"
mkdir -p "$MOCK_ROOT/bin" "$PMAFP/bin" "$BUNDLE/conda/linux-64" "$BUNDLE/conda/noarch" "$BUNDLE/wheels"

PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$ROOT/scripts/04b_footprint" python3 - <<'PY'
from packaging.tags import Tag
from validate_hint_bundle import (
    hint_marker_environment, marker_environment_supported,
    wheel_requires_hint_python, wheel_targets_hint,
)

assert wheel_targets_hint({Tag("py3", "none", "any")})
assert wheel_targets_hint({Tag("cp311", "cp311", "manylinux_2_17_x86_64")})
assert not wheel_targets_hint({Tag("cp310", "cp310", "manylinux_2_17_x86_64")})
assert not wheel_targets_hint({Tag("cp311", "cp311", "macosx_14_0_arm64")})
assert not wheel_targets_hint({Tag("cp311", "cp311", "linux_x86_64")})
assert wheel_requires_hint_python(">=3.11,<3.12", "3.11.17")
assert not wheel_requires_hint_python(">=3.12", "3.11.17")
marker_env = hint_marker_environment("3.11.17")
assert marker_env["platform_system"] == "Linux" and marker_env["implementation_name"] == "cpython"
assert marker_env["python_version"] == "3.11" and marker_env["sys_platform"] == "linux"
from packaging.requirements import Requirement
assert Requirement("demo; platform_system == 'Linux' and implementation_name == 'cpython' and python_version >= '3.11'").marker.evaluate(marker_env)
assert not marker_environment_supported("somepkg; platform_release == 'x'")
PY

cat > "$MOCK_ROOT/bin/python" <<'PYTHON'
#!/usr/bin/env bash
set -euo pipefail
if [[ "${1:-}" == *validate_hint_bundle.py || "${1:-}" == -c ]]; then
  exec python3 "$@"
elif [[ "${1:-}" == -m && "${2:-}" == pip ]]; then
  case "${3:-}" in
    freeze) echo 'mock-source-package==1.0' ;;
    install)
      for arg in "$@"; do [[ "$arg" == --dry-run ]] && exit 0; done
      [[ "${MOCK_PIP_INSTALL_FAIL:-0}" == 0 ]] || exit 44
      ;;
    check) exit 0 ;;
  esac
elif [[ "${1:-}" == - ]]; then
  if [[ "$#" -ge 6 && "${3:-}" == */HINT_ENV_READY.json ]]; then
    tmp_file=$2; ready_file=$3; prefix=$4; commit=$5; locksha=$6
    cat >/dev/null
    printf '{"status":"HINT_ENV_READY","prefix":"%s","code_commit":"%s","bundle_lock_sha256":"%s"}\n' \
      "$prefix" "$commit" "$locksha" > "$tmp_file"
    mv "$tmp_file" "$ready_file"
  elif [[ "$#" -ge 3 ]]; then
    exec python3 "$@"
  else
    cat >/dev/null
  fi
fi
exit 0
PYTHON
chmod +x "$MOCK_ROOT/bin/python"
cp "$MOCK_ROOT/bin/python" "$PMAFP/bin/python"
cat > "$MOCK_ROOT/bin/rgt-hint" <<'HINTCLI'
#!/usr/bin/env bash
exit 0
HINTCLI
chmod +x "$MOCK_ROOT/bin/rgt-hint"

cat > "$CONDA" <<'CONDA'
#!/usr/bin/env bash
set -euo pipefail
command_name=$1; shift
prefix=
dry_run=0
file_arg=
while [[ "$#" -gt 0 ]]; do
  case "$1" in
    --prefix) prefix=$2; shift 2 ;;
    --file) file_arg=$2; shift 2 ;;
    --dry-run) dry_run=1; shift ;;
    *) shift ;;
  esac
done
case "$command_name" in
  list)
    count=0
    [[ ! -f "$MOCK_HINT_ROOT/list.count" ]] || read -r count < "$MOCK_HINT_ROOT/list.count"
    count=$((count + 1)); echo "$count" > "$MOCK_HINT_ROOT/list.count"
    if [[ "${MOCK_CHANGE_MANIFEST:-0}" == 1 && "$count" -gt 1 ]]; then echo "changed:$prefix"; else echo "manifest:$prefix"; fi
    ;;
  create)
    if [[ "$dry_run" == 1 ]]; then
      if [[ "${MOCK_CONDA_FILENAME_MISMATCH:-0}" == 1 ]]; then
        echo '{"success":true,"actions":{"LINK":[{"name":"python","version":"3.11.17","build_string":"mock_0","subdir":"linux-64","fn":"other-python.tar.bz2"},{"name":"numpy","version":"1.26.4","build_string":"mock_0","subdir":"linux-64","fn":"numpy-mock.tar.bz2"},{"name":"setuptools","version":"80.9.0","build_string":"mock_0","subdir":"noarch","fn":"setuptools-mock.tar.bz2"}]}}'
        exit 0
      fi
      if [[ "${MOCK_CONDA_CLOSURE_MISMATCH:-0}" == 1 ]]; then
        echo '{"success":true,"actions":{"LINK":[{"name":"python","version":"3.11.17","build_string":"mock_0","subdir":"linux-64","fn":"python-mock.tar.bz2"},{"name":"numpy","version":"1.26.4","build_string":"mock_0","subdir":"linux-64","fn":"numpy-mock.tar.bz2"}]}}'
      else
        echo '{"success":true,"actions":{"LINK":[{"name":"python","version":"3.11.17","build_string":"mock_0","subdir":"linux-64","fn":"python-mock.tar.bz2"},{"name":"numpy","version":"1.26.4","build_string":"mock_0","subdir":"linux-64","fn":"numpy-mock.tar.bz2"},{"name":"setuptools","version":"80.9.0","build_string":"mock_0","subdir":"noarch","fn":"setuptools-mock.tar.bz2"}]}}'
      fi
      exit 0
    fi
    [[ "$(head -n 1 "$file_arg")" == "@EXPLICIT" ]]
    grep -q 'python-mock.tar.bz2' "$file_arg"
    grep -q 'numpy-mock.tar.bz2' "$file_arg"
    grep -q 'setuptools-mock.tar.bz2' "$file_arg"
    mkdir -p "$prefix/bin"
    cp "$MOCK_HINT_ROOT/bin/python" "$prefix/bin/python"
    cp "$MOCK_HINT_ROOT/bin/rgt-hint" "$prefix/bin/rgt-hint"
    [[ "${MOCK_CONDA_CREATE_FAIL:-0}" == 0 ]] || exit 43
    ;;
  *) exit 64 ;;
esac
CONDA
chmod +x "$CONDA"

printf 'mock-conda-archive\n' > "$BUNDLE/conda/linux-64/python-mock.tar.bz2"
printf 'mock-numpy-archive\n' > "$BUNDLE/conda/linux-64/numpy-mock.tar.bz2"
printf 'mock-setuptools-archive\n' > "$BUNDLE/conda/noarch/setuptools-mock.tar.bz2"
python3 - "$BUNDLE/wheels/RGT-1.0.2-py3-none-any.whl" <<'WHEEL'
import sys, zipfile
with zipfile.ZipFile(sys.argv[1], "w") as archive:
    archive.writestr("RGT-1.0.2.dist-info/METADATA", "Name: RGT\nVersion: 1.0.2\n\n")
    archive.writestr("RGT-1.0.2.dist-info/WHEEL", "Wheel-Version: 1.0\nGenerator: mock\nRoot-Is-Purelib: true\nTag: py3-none-any\n")
WHEEL
printf '{"packages":{},"packages.conda":{}}\n' > "$BUNDLE/conda/linux-64/repodata.json"
printf '{"packages":{},"packages.conda":{}}\n' > "$BUNDLE/conda/noarch/repodata.json"
python_sha=$(shasum -a 256 "$BUNDLE/conda/linux-64/python-mock.tar.bz2" | awk '{print $1}')
numpy_sha=$(shasum -a 256 "$BUNDLE/conda/linux-64/numpy-mock.tar.bz2" | awk '{print $1}')
setuptools_sha=$(shasum -a 256 "$BUNDLE/conda/noarch/setuptools-mock.tar.bz2" | awk '{print $1}')
wheel_sha=$(shasum -a 256 "$BUNDLE/wheels/RGT-1.0.2-py3-none-any.whl" | awk '{print $1}')
python3 - "$BUNDLE/conda/linux-64/repodata.json" "$BUNDLE/conda/noarch/repodata.json" \
  "$python_sha" "$numpy_sha" "$setuptools_sha" <<'REPODATA'
import json, sys
linux_path, noarch_path, python_sha, numpy_sha, setuptools_sha = sys.argv[1:]
with open(linux_path, "w", encoding="utf-8") as handle:
    json.dump({"packages": {
        "python-mock.tar.bz2": {"name": "python", "version": "3.11.17", "build": "mock_0", "sha256": python_sha},
        "numpy-mock.tar.bz2": {"name": "numpy", "version": "1.26.4", "build": "mock_0", "sha256": numpy_sha},
    }, "packages.conda": {}}, handle)
with open(noarch_path, "w", encoding="utf-8") as handle:
    json.dump({"packages": {
        "setuptools-mock.tar.bz2": {"name": "setuptools", "version": "80.9.0", "build": "mock_0", "sha256": setuptools_sha},
    }, "packages.conda": {}}, handle)
REPODATA
mkdir -p "$BUNDLE/reports"
python3 - "$BUNDLE/reports/rgt-wheel-audit.json" "$wheel_sha" <<'REPORT'
import json, sys
with open(sys.argv[1], "w", encoding="utf-8") as handle:
    json.dump({
        "rgt_sdist_sha256": "2169e71f2018340d101146bab09bb933a384611c5f7b76f4be5999fa835cac7e",
        "rgt_wheel": "RGT-1.0.2-py3-none-any.whl",
        "rgt_wheel_sha256": sys.argv[2],
        "builder": "mock-linux-builder",
        "python_abi": "cp311",
        "glibc_symbol_max": "2.17",
        "auditwheel_policy": "py3-none-any",
        "native_dependencies": [],
    }, handle)
REPORT
printf 'linux-64\tpython\t3.11.17\tmock_0\tpython-mock.tar.bz2\t%s\nlinux-64\tnumpy\t1.26.4\tmock_0\tnumpy-mock.tar.bz2\t%s\nnoarch\tsetuptools\t80.9.0\tmock_0\tsetuptools-mock.tar.bz2\t%s\n' \
  "$python_sha" "$numpy_sha" "$setuptools_sha" > "$BUNDLE/conda-explicit-linux-64.lock"
printf 'RGT==1.0.2 --hash=sha256:%s\n' "$wheel_sha" > "$BUNDLE/pip-requirements.lock"
printf '%s  %s\n%s  %s\n%s  %s\n%s  %s\n' \
  "$python_sha" 'conda/linux-64/python-mock.tar.bz2' \
  "$numpy_sha" 'conda/linux-64/numpy-mock.tar.bz2' \
  "$setuptools_sha" 'conda/noarch/setuptools-mock.tar.bz2' \
  "$wheel_sha" 'wheels/RGT-1.0.2-py3-none-any.whl' > "$BUNDLE/artifacts.sha256"
printf '%s  %s\n%s  %s\n' \
  "$(shasum -a 256 "$BUNDLE/conda/linux-64/repodata.json" | awk '{print $1}')" 'conda/linux-64/repodata.json' \
  "$(shasum -a 256 "$BUNDLE/conda/noarch/repodata.json" | awk '{print $1}')" 'conda/noarch/repodata.json' >> "$BUNDLE/artifacts.sha256"
printf '%s  %s\n' \
  "$(shasum -a 256 "$BUNDLE/reports/rgt-wheel-audit.json" | awk '{print $1}')" 'reports/rgt-wheel-audit.json' >> "$BUNDLE/artifacts.sha256"
conda_lock_sha=$(shasum -a 256 "$BUNDLE/conda-explicit-linux-64.lock" | awk '{print $1}')
pip_lock_sha=$(shasum -a 256 "$BUNDLE/pip-requirements.lock" | awk '{print $1}')
artifacts_sha=$(shasum -a 256 "$BUNDLE/artifacts.sha256" | awk '{print $1}')
python3 - "$BUNDLE/bundle-manifest.json" "$conda_lock_sha" "$pip_lock_sha" "$artifacts_sha" <<'JSON'
import json, sys
path, conda_sha, pip_sha, artifacts_sha = sys.argv[1:]
with open(path, "w", encoding="utf-8") as handle:
    json.dump({
        "schema_version": 1,
        "target_platform": "linux-64",
        "python_abi": "cp311",
        "glibc_max": "2.23",
        "builder": "mock-linux-builder",
        "conda_version": "mock-1",
        "pip_version": "mock-1",
        "rgt_build_report": "reports/rgt-wheel-audit.json",
        "rgt_build_report_sha256": open(sys.argv[1].replace("bundle-manifest.json", "reports/rgt-wheel-audit.json"), "rb").read() and __import__("hashlib").sha256(open(sys.argv[1].replace("bundle-manifest.json", "reports/rgt-wheel-audit.json"), "rb").read()).hexdigest(),
        "rgt_sdist_sha256": "2169e71f2018340d101146bab09bb933a384611c5f7b76f4be5999fa835cac7e",
        "rgt_wheel": "RGT-1.0.2-py3-none-any.whl",
        "rgt_wheel_sha256": open(sys.argv[1].replace("bundle-manifest.json", "pip-requirements.lock"), encoding="utf-8").read().split("sha256:")[1].strip(),
        "conda_lock_sha256": conda_sha,
        "pip_lock_sha256": pip_sha,
        "artifacts_sha256": artifacts_sha,
    }, handle)
JSON

MOCK_HINT_ROOT="$MOCK_ROOT" bash "$SETUP" preflight "$CONDA" "$PMAFP" "$MOCK_ROOT/pma_hint_v2" "$BUNDLE" "$AUDIT" \
  > "$TMP/preflight.log" 2>&1
grep -q HINT_OFFLINE_PREFLIGHT_OK "$TMP/preflight.log"
grep -q HINT_PREFLIGHT_ONLY "$TMP/preflight.log"
[[ ! -e "$MOCK_ROOT/pma_hint_v2" ]]

cp "$BUNDLE/bundle-manifest.json" "$TMP/bundle-manifest.valid.json"
python3 - "$BUNDLE/bundle-manifest.json" <<'JSON'
import json, sys
with open(sys.argv[1], encoding="utf-8") as handle:
    value = json.load(handle)
value["rgt_sdist_sha256"] = "0" * 64
with open(sys.argv[1], "w", encoding="utf-8") as handle:
    json.dump(value, handle)
JSON
if MOCK_HINT_ROOT="$MOCK_ROOT" bash "$SETUP" preflight "$CONDA" "$PMAFP" "$MOCK_ROOT/pma_hint_bad_sdist" "$BUNDLE" "$AUDIT/bad-sdist" \
  > "$TMP/bad-sdist.log" 2>&1; then
  echo "expected RGT source provenance failure" >&2; exit 1
fi
grep -q RGT_SDIST_PROVENANCE_MISMATCH "$TMP/bad-sdist.log"
[[ ! -e "$MOCK_ROOT/pma_hint_bad_sdist" ]]
cp "$TMP/bundle-manifest.valid.json" "$BUNDLE/bundle-manifest.json"
python3 - "$BUNDLE/bundle-manifest.json" <<'JSON'
import json, sys
with open(sys.argv[1], encoding="utf-8") as handle:
    value = json.load(handle)
value["target_platform"] = "osx-arm64"
with open(sys.argv[1], "w", encoding="utf-8") as handle:
    json.dump(value, handle)
JSON
if MOCK_HINT_ROOT="$MOCK_ROOT" bash "$SETUP" preflight "$CONDA" "$PMAFP" "$MOCK_ROOT/pma_hint_bad_platform" "$BUNDLE" "$AUDIT/bad-platform" \
  > "$TMP/bad-platform.log" 2>&1; then
  echo "expected platform mismatch failure" >&2; exit 1
fi
grep -q BUNDLE_PLATFORM_INVALID "$TMP/bad-platform.log"
[[ ! -e "$MOCK_ROOT/pma_hint_bad_platform" ]]
cp "$TMP/bundle-manifest.valid.json" "$BUNDLE/bundle-manifest.json"

if MOCK_HINT_ROOT="$MOCK_ROOT" MOCK_CONDA_CREATE_FAIL=1 bash "$SETUP" install "$CONDA" "$PMAFP" "$MOCK_ROOT/pma_hint_fail" "$BUNDLE" "$AUDIT/fail" \
  > "$TMP/install-fail.log" 2>&1; then
  echo "expected mocked Conda install failure" >&2; exit 1
else
  rc=$?
fi
[[ "$rc" == 43 ]]
grep -q PMAFP_INTEGRITY_OK "$TMP/install-fail.log"
[[ -d "$MOCK_ROOT/pma_hint_fail" ]]
[[ ! -e "$MOCK_ROOT/pma_hint_fail/HINT_ENV_READY.json" ]]

if MOCK_HINT_ROOT="$MOCK_ROOT" MOCK_PIP_INSTALL_FAIL=1 bash "$SETUP" install "$CONDA" "$PMAFP" "$MOCK_ROOT/pma_hint_pip_fail" "$BUNDLE" "$AUDIT/pip-fail" \
  > "$TMP/pip-fail.log" 2>&1; then
  echo "expected mocked pip install failure" >&2; exit 1
else
  rc=$?
fi
[[ "$rc" == 44 ]]
grep -q PMAFP_INTEGRITY_OK "$TMP/pip-fail.log"
[[ -d "$MOCK_ROOT/pma_hint_pip_fail" ]]
[[ ! -e "$MOCK_ROOT/pma_hint_pip_fail/HINT_ENV_READY.json" ]]

rm -f "$MOCK_ROOT/list.count"
if MOCK_HINT_ROOT="$MOCK_ROOT" MOCK_CHANGE_MANIFEST=1 bash "$SETUP" install "$CONDA" "$PMAFP" "$MOCK_ROOT/pma_hint_integrity_fail" "$BUNDLE" "$AUDIT/integrity-fail" \
  > "$TMP/integrity-fail.log" 2>&1; then
  echo "expected source-manifest integrity failure" >&2; exit 1
else
  rc=$?
fi
[[ "$rc" == 1 ]]
grep -q PMAFP_INTEGRITY_FAIL "$TMP/integrity-fail.log"
[[ ! -e "$MOCK_ROOT/pma_hint_integrity_fail/HINT_ENV_READY.json" ]]

MOCK_HINT_ROOT="$MOCK_ROOT" bash "$SETUP" install "$CONDA" "$PMAFP" "$MOCK_ROOT/pma_hint_success" "$BUNDLE" "$AUDIT/success" \
  > "$TMP/install-ok.log" 2>&1
grep -q PMAFP_INTEGRITY_OK "$TMP/install-ok.log"
grep -q HINT_ENV_READY "$TMP/install-ok.log"
grep -q '"status":"HINT_ENV_READY"' "$MOCK_ROOT/pma_hint_success/HINT_ENV_READY.json"

if MOCK_HINT_ROOT="$MOCK_ROOT" bash "$SETUP" preflight "$CONDA" "$PMAFP" "$MOCK_ROOT/pma_hint_success" "$BUNDLE" "$AUDIT/existing" \
  > "$TMP/existing.log" 2>&1; then
  echo "expected existing-prefix refusal" >&2; exit 1
else
  rc=$?
fi
[[ "$rc" == 2 ]]

MISSING_BUNDLE="$MOCK_ROOT/missing-bundle"
cp -R "$BUNDLE" "$MISSING_BUNDLE"
rm "$MISSING_BUNDLE/conda/linux-64/python-mock.tar.bz2"
rm "$MISSING_BUNDLE/conda/linux-64/numpy-mock.tar.bz2"
if MOCK_HINT_ROOT="$MOCK_ROOT" bash "$SETUP" preflight "$CONDA" "$PMAFP" "$MOCK_ROOT/pma_hint_missing" "$MISSING_BUNDLE" "$AUDIT/missing" \
  > "$TMP/missing.log" 2>&1; then
  echo "expected missing-artifact preflight failure" >&2; exit 1
else
  rc=$?
fi
[[ "$rc" != 0 ]]
grep -q MISSING_OR_INVALID_ARTIFACT "$TMP/missing.log"
grep -q numpy-mock.tar.bz2 "$TMP/missing.log"
[[ ! -e "$MOCK_ROOT/pma_hint_missing" ]]

MISSING_WHEEL_BUNDLE="$MOCK_ROOT/missing-wheel-bundle"
cp -R "$BUNDLE" "$MISSING_WHEEL_BUNDLE"
rm "$MISSING_WHEEL_BUNDLE/wheels/RGT-1.0.2-py3-none-any.whl"
if MOCK_HINT_ROOT="$MOCK_ROOT" bash "$SETUP" preflight "$CONDA" "$PMAFP" "$MOCK_ROOT/pma_hint_missing_wheel" "$MISSING_WHEEL_BUNDLE" "$AUDIT/missing-wheel" \
  > "$TMP/missing-wheel.log" 2>&1; then
  echo "expected missing-wheel preflight failure" >&2; exit 1
fi
grep -q MISSING_OR_INVALID_ARTIFACT "$TMP/missing-wheel.log"
[[ ! -e "$MOCK_ROOT/pma_hint_missing_wheel" ]]

if MOCK_HINT_ROOT="$MOCK_ROOT" MOCK_CONDA_CLOSURE_MISMATCH=1 bash "$SETUP" preflight "$CONDA" "$PMAFP" "$MOCK_ROOT/pma_hint_bad_closure" "$BUNDLE" "$AUDIT/bad-closure" \
  > "$TMP/bad-closure.log" 2>&1; then
  echo "expected Conda dependency-closure mismatch" >&2; exit 1
fi
grep -q CONDA_DEPENDENCY_CLOSURE_UNVERIFIED "$TMP/bad-closure.log"
[[ ! -e "$MOCK_ROOT/pma_hint_bad_closure" ]]

if MOCK_HINT_ROOT="$MOCK_ROOT" MOCK_CONDA_FILENAME_MISMATCH=1 bash "$SETUP" preflight "$CONDA" "$PMAFP" "$MOCK_ROOT/pma_hint_bad_filename" "$BUNDLE" "$AUDIT/bad-filename" \
  > "$TMP/bad-filename.log" 2>&1; then
  echo "expected Conda LINK filename mismatch" >&2; exit 1
fi
grep -q CONDA_LINK_FILENAME_MISMATCH "$TMP/bad-filename.log"
[[ ! -e "$MOCK_ROOT/pma_hint_bad_filename" ]]

REPODATA_GAP_BUNDLE="$MOCK_ROOT/repodata-gap-bundle"
cp -R "$BUNDLE" "$REPODATA_GAP_BUNDLE"
python3 - "$REPODATA_GAP_BUNDLE" <<'PY'
import hashlib, json, sys
from pathlib import Path
root = Path(sys.argv[1])
inventory = root / "artifacts.sha256"
lines = [line for line in inventory.read_text().splitlines() if not line.endswith("conda/linux-64/repodata.json")]
inventory.write_text("\n".join(lines) + "\n")
manifest_path = root / "bundle-manifest.json"
manifest = json.loads(manifest_path.read_text())
manifest["artifacts_sha256"] = hashlib.sha256(inventory.read_bytes()).hexdigest()
manifest_path.write_text(json.dumps(manifest))
PY
if MOCK_HINT_ROOT="$MOCK_ROOT" bash "$SETUP" preflight "$CONDA" "$PMAFP" "$MOCK_ROOT/pma_hint_repodata_gap" "$REPODATA_GAP_BUNDLE" "$AUDIT/repodata-gap" \
  > "$TMP/repodata-gap.log" 2>&1; then
  echo "expected missing repodata inventory failure" >&2; exit 1
fi
grep -q REPODATA_NOT_IN_ARTIFACT_INVENTORY "$TMP/repodata-gap.log"
[[ ! -e "$MOCK_ROOT/pma_hint_repodata_gap" ]]

REPODATA_LOCK_BUNDLE="$MOCK_ROOT/repodata-lock-bundle"
cp -R "$BUNDLE" "$REPODATA_LOCK_BUNDLE"
python3 - "$REPODATA_LOCK_BUNDLE" <<'PY'
import hashlib, json, sys
from pathlib import Path
root = Path(sys.argv[1])
repodata = root / "conda/linux-64/repodata.json"
value = json.loads(repodata.read_text())
value["packages"]["python-mock.tar.bz2"]["sha256"] = "0" * 64
repodata.write_text(json.dumps(value))
inventory = root / "artifacts.sha256"
updated = hashlib.sha256(repodata.read_bytes()).hexdigest()
lines = []
for line in inventory.read_text().splitlines():
    _digest, relative = line.split(None, 1)
    lines.append(f"{updated}  {relative}" if relative == "conda/linux-64/repodata.json" else line)
inventory.write_text("\n".join(lines) + "\n")
manifest_path = root / "bundle-manifest.json"
manifest = json.loads(manifest_path.read_text())
manifest["artifacts_sha256"] = hashlib.sha256(inventory.read_bytes()).hexdigest()
manifest_path.write_text(json.dumps(manifest))
PY
if MOCK_HINT_ROOT="$MOCK_ROOT" bash "$SETUP" preflight "$CONDA" "$PMAFP" "$MOCK_ROOT/pma_hint_repodata_lock" "$REPODATA_LOCK_BUNDLE" "$AUDIT/repodata-lock" \
  > "$TMP/repodata-lock.log" 2>&1; then
  echo "expected repodata/lock SHA mismatch" >&2; exit 1
fi
grep -q CONDA_REPODATA_SHA256_MISMATCH "$TMP/repodata-lock.log"
[[ ! -e "$MOCK_ROOT/pma_hint_repodata_lock" ]]

echo "HINT offline builder fixtures passed"
