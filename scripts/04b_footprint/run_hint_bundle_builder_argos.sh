#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "usage: $0 <atac-footprint-data-root> <external-workspace> <external-bundle-dir> <external-evidence-dir> <explicit-conda-forge-url>" >&2
  exit 64
}
[[ $# -eq 5 ]] || usage

DATA_ROOT=$(python3 - "$1" <<'PY'
import os, sys
print(os.path.realpath(os.path.abspath(sys.argv[1])))
PY
)
WORK=$(python3 - "$2" <<'PY'
import os, sys
print(os.path.realpath(os.path.abspath(sys.argv[1])))
PY
)
BUNDLE=$(python3 - "$3" <<'PY'
import os, sys
print(os.path.realpath(os.path.abspath(sys.argv[1])))
PY
)
EVIDENCE=$(python3 - "$4" <<'PY'
import os, sys
print(os.path.realpath(os.path.abspath(sys.argv[1])))
PY
)
CHANNEL=$5
HERE=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
REPO=$(git -C "$HERE/../.." rev-parse --show-toplevel)
PMAFP=${PMA_HINT_SOURCE_PREFIX:-/home/zz950/softwares/miniforge3/envs/pmafp}
CONDA=${PMA_HINT_CONDA:-/home/zz950/softwares/miniforge3/bin/conda}
PYTHON="$PMAFP/bin/python"
TOOLCHAIN="$WORK/toolchain"
PACKAGE_CACHE="$WORK/conda-pkgs"
DOWNLOADS="$TOOLCHAIN/downloads"
PYTHON_ROOT="$TOOLCHAIN/python"
TOOLCHAIN_REPORT="$TOOLCHAIN/host-toolchain.json"

[[ "$CHANNEL" == https://* ]] || { echo "ARGOS_CONDA_CHANNEL_MUST_BE_EXPLICIT_HTTPS_URL" >&2; exit 2; }
[[ -x "$PYTHON" && -x "$CONDA" ]] || { echo "ARGOS_PYTHON_OR_CONDA_MISSING" >&2; exit 2; }
[[ -d "$DATA_ROOT/raw" && -d "$DATA_ROOT/processed/round1" ]] || {
  echo "ARGOS_DATA_ROOT_LAYOUT_INVALID:$DATA_ROOT" >&2; exit 2;
}

python3 - "$REPO" "$PMAFP" "$CONDA" "$DATA_ROOT" "$WORK" "$BUNDLE" "$EVIDENCE" <<'PY'
import json, os, subprocess, sys
import shutil
repo, pmafp, conda, data_root, work, bundle, evidence = map(os.path.realpath, sys.argv[1:])
protected = [repo, pmafp, os.path.dirname(pmafp), os.path.dirname(os.path.dirname(pmafp)),
             data_root, os.path.join(data_root, "raw"), os.path.join(data_root, "processed", "round1")]
envs = subprocess.run([conda, "env", "list", "--json"], check=True, text=True,
                      stdout=subprocess.PIPE, stderr=subprocess.PIPE)
for prefix in json.loads(envs.stdout).get("envs", []):
    protected.append(os.path.realpath(prefix))
def within(parent, child):
    try:
        return os.path.commonpath((parent, child)) == parent
    except ValueError:
        return False
outputs = [work, bundle, evidence]
for output in outputs:
    if any(within(root, output) for root in protected):
        raise SystemExit(f"ARGOS_OUTPUT_PATH_PROTECTED:{output}")
if bundle == work or evidence == work or not within(work, bundle) or not within(work, evidence):
    raise SystemExit("ARGOS_BUNDLE_AND_EVIDENCE_MUST_BE_INSIDE_EXTERNAL_WORKSPACE")
if within(bundle, evidence) or within(evidence, bundle):
    raise SystemExit(f"ARGOS_BUNDLE_AND_EVIDENCE_PATHS_OVERLAP:{bundle}:{evidence}")
PY

mkdir -p "$WORK"
for path in "$BUNDLE" "$EVIDENCE" "$WORK"; do
  if [[ -e "$path" && -n "$(find "$path" -mindepth 1 -maxdepth 1 -print -quit)" ]]; then
    echo "ARGOS_OUTPUT_DIRECTORY_MUST_BE_EMPTY:$path" >&2; exit 2
  fi
done
mkdir -p "$BUNDLE" "$EVIDENCE" "$TOOLCHAIN" "$PACKAGE_CACHE"

CONDA_BEFORE="$EVIDENCE/pmafp-conda-before.txt"
PIP_BEFORE="$EVIDENCE/pmafp-pip-before.txt"
CONDA_AFTER="$EVIDENCE/pmafp-conda-after.txt"
PIP_AFTER="$EVIDENCE/pmafp-pip-after.txt"
"$CONDA" list --explicit --prefix "$PMAFP" > "$CONDA_BEFORE"
env -u PYTHONPATH PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 \
  "$PYTHON" -m pip freeze --all > "$PIP_BEFORE"

env -u PYTHONPATH PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 \
  "$PYTHON" "$HERE/prepare_hint_argos_toolchain.py" \
    --python "$PYTHON" --lock "$HERE/hint-builder-requirements.lock" \
    --downloads "$DOWNLOADS" --python-root "$PYTHON_ROOT" \
    --report "$TOOLCHAIN/toolchain-wheels.json"

python3 - "$TOOLCHAIN/toolchain-wheels.json" "$TOOLCHAIN/host-toolchain.json" \
  "$PYTHON" "$CONDA" "$PMAFP" "$REPO" "$CHANNEL" "$CONDA_BEFORE" "$PIP_BEFORE" <<'PY'
import hashlib, json, os, platform, subprocess, sys
source_report, output, python, conda, pmafp, repo, channel, conda_before, pip_before = sys.argv[1:]
def sha(path):
    h=hashlib.sha256()
    with open(path,"rb") as f:
        for block in iter(lambda:f.read(1024*1024),b""): h.update(block)
    return h.hexdigest()
def out(argv):
    return subprocess.run(argv,check=True,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT).stdout.strip()
with open(source_report,encoding="utf-8") as f: report=json.load(f)
report.update({"mode":"argos-native","host":platform.node(),"system":platform.platform(),
               "machine":platform.machine(),"glibc":platform.libc_ver(),
               "python_executable":os.path.realpath(python),"python_sha256":sha(python),
               "conda_executable":os.path.realpath(conda),"conda_sha256":sha(conda),
               "conda_version":out([conda,"--version"]),"git_commit":out(["git","-C",repo,"rev-parse","HEAD"]),
               "conda_channel":channel,"pmafp_prefix":os.path.realpath(pmafp),
               "pmafp_conda_before_sha256":sha(conda_before),"pmafp_pip_before_sha256":sha(pip_before),
               "gcc":out(["gcc","--version"]).splitlines()[0],
               "readelf":out(["readelf","--version"]).splitlines()[0]})
for tool in ("gcc","readelf"):
    path=shutil.which(tool) or ""
    if not path or not os.path.isfile(path): raise SystemExit(f"HOST_TOOL_PATH_MISSING:{tool}")
    report[tool+"_path"]=os.path.realpath(path)
    report[tool+"_sha256"]=sha(path)
with open(output,"w",encoding="utf-8") as f: json.dump(report,f,indent=2,sort_keys=True); f.write("\n")
PY

export PMA_HINT_BUILDER_MODE=argos-native
export PMA_HINT_EXTERNAL_TOOLCHAIN="$TOOLCHAIN"
export PMA_HINT_HOST_TOOLCHAIN_REPORT="$TOOLCHAIN/host-toolchain.json"
export PMA_HINT_ARGOS_CONDA_CHANNEL="$CHANNEL"
export CONDA_PKGS_DIRS="$PACKAGE_CACHE"
export PATH="$CONDA/bin:$PATH"
export PYTHONPATH="$PYTHON_ROOT"
export PYTHONNOUSERSITE=1
export PYTHONDONTWRITEBYTECODE=1
ulimit -v 48000000 || { echo "MEMORY_LIMIT_UNAVAILABLE" >&2; exit 125; }

set +e
# The builder requires a fresh evidence directory; wrapper integrity manifests live in the parent.
"$PYTHON" "$HERE/build_hint_bundle.py" "$BUNDLE" --evidence-dir "$EVIDENCE/builder" \
  > "$EVIDENCE/argos-builder.stdout.log" 2>&1
BUILD_STATUS=$?
set -e
python3 - "$EVIDENCE/argos-builder.stdout.log" <<'PY'
import re, sys
from urllib.parse import urlsplit, urlunsplit
path = sys.argv[1]
def clean(match):
    parsed = urlsplit(match.group(0))
    host = parsed.hostname or ""
    if parsed.port:
        host += f":{parsed.port}"
    return urlunsplit((parsed.scheme, host, parsed.path, "", ""))
with open(path, encoding="utf-8", errors="replace") as stream:
    content = stream.read()
with open(path, "w", encoding="utf-8") as stream:
    stream.write(re.sub(r'''https?://[^\s"'<>]+''', clean, content))
PY

env -u PYTHONPATH PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 \
  "$CONDA" list --explicit --prefix "$PMAFP" > "$CONDA_AFTER" || BUILD_STATUS=1
env -u PYTHONPATH PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 \
  "$PYTHON" -m pip freeze --all > "$PIP_AFTER" || BUILD_STATUS=1
if ! cmp -s "$CONDA_BEFORE" "$CONDA_AFTER" || ! cmp -s "$PIP_BEFORE" "$PIP_AFTER"; then
  printf '%s\n' 'PMAFP_INTEGRITY_FAIL' > "$EVIDENCE/pmafp-integrity-failure.txt"
  BUILD_STATUS=1
else
  python3 - "$CONDA_BEFORE" "$PIP_BEFORE" > "$EVIDENCE/pmafp-integrity.json" <<'PY'
import hashlib,json,sys
def sha(p): return hashlib.sha256(open(p,"rb").read()).hexdigest()
print(json.dumps({"status":"PMAFP_INTEGRITY_OK","conda_explicit_sha256":sha(sys.argv[1]),
                  "pip_freeze_sha256":sha(sys.argv[2])},indent=2,sort_keys=True))
PY
fi
if [[ "$BUILD_STATUS" -ne 0 ]]; then
  echo "ARGOS_BUNDLE_BUILD_FAILED; preserve $EVIDENCE" >&2
  exit "$BUILD_STATUS"
fi
echo "ARGOS_BUNDLE_BUILD_OK bundle=$BUNDLE evidence=$EVIDENCE"
