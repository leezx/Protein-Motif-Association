#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/bin"
cat > "$TMP/bin/python" <<'PY'
#!/usr/bin/env bash
set -euo pipefail
if [ "${1:-}" = -c ]; then
  bam=${@: -1}
  [ -s "$bam" ] && [ -s "$bam.bai" ] && [ "$(cat "$bam")" = VALID ]
  exit
fi
frags=$2; out=$5
printf '%s\n' "$frags" >> "$CONVERSION_LOG"
[ "$frags" != "${FAIL_FRAG:-}" ] || exit 9
printf 'VALID\n' > "$out"
printf 'INDEX\n' > "$out.bai"
PY
chmod +x "$TMP/bin/python"
cat > "$TMP/bin/samtools" <<'SAMTOOLS'
#!/usr/bin/env bash
set -euo pipefail
[ "${1:-}" = quickcheck ] && [ -s "$2" ] && [ "$(cat "$2")" = VALID ]
SAMTOOLS
chmod +x "$TMP/bin/samtools"
touch "$TMP/sizes" "$TMP/gdna.frag" "$TMP/ctrl.frag" "$TMP/aux.frag"
touch "$TMP/gdna.bed" "$TMP/ctrl.bed" "$TMP/aux.bed" "$TMP/frags_to_bam.py"
export CONVERSION_LOG="$TMP/conversions.log"
HELPER="$ROOT/scripts/04b_footprint/ensure_bam_cache.sh"
bash "$HELPER" "$TMP/bin/python" "$TMP/bin/samtools" "$TMP/frags_to_bam.py" "$TMP/gdna.frag" "$TMP/sizes" "$TMP/gdna.bed" "$TMP/cache/gdna.bam"
[ "$(wc -l < "$CONVERSION_LOG")" -eq 1 ]
bash "$HELPER" "$TMP/bin/python" "$TMP/bin/samtools" "$TMP/frags_to_bam.py" "$TMP/gdna.frag" "$TMP/sizes" "$TMP/gdna.bed" "$TMP/cache/gdna.bam"
[ "$(wc -l < "$CONVERSION_LOG")" -eq 1 ]
printf 'CORRUPT\n' > "$TMP/cache/gdna.bam"
bash "$HELPER" "$TMP/bin/python" "$TMP/bin/samtools" "$TMP/frags_to_bam.py" "$TMP/gdna.frag" "$TMP/sizes" "$TMP/gdna.bed" "$TMP/cache/gdna.bam"
[ "$(wc -l < "$CONVERSION_LOG")" -eq 2 ]

source "$ROOT/scripts/04b_footprint/prepare_bams.sh"
source "$ROOT/scripts/04b_footprint/hint_env.sh"
[ "$(select_bam_cache_dir "$TMP/work" 1)" = "$TMP/work/bam/smoke" ]
[ "$(select_bam_cache_dir "$TMP/work" 0)" = "$TMP/work/bam/full" ]
mkdir -p "$TMP/hint_env/bin" "$TMP/main_env/bin"
touch "$TMP/hint_env/bin/rgt-hint" "$TMP/main_env/bin/rgt-hint"
chmod +x "$TMP/hint_env/bin/rgt-hint" "$TMP/main_env/bin/rgt-hint"
[ "$(select_hint_bin "$TMP/hint_env/bin")" = "$TMP/hint_env/bin" ]
if select_hint_bin "$TMP/missing/bin"; then echo "expected invalid HINT env" >&2; exit 1; fi
before=$(wc -l < "$CONVERSION_LOG")
if FAIL_FRAG="$TMP/ctrl.frag" prepare_bams "$TMP/bin/python" "$TMP/bin/samtools" "$TMP/frags_to_bam.py" "$TMP/sizes" "$TMP/prepared" \
  gdna "$TMP/gdna.frag" "$TMP/gdna.bed" ctrl "$TMP/ctrl.frag" "$TMP/ctrl.bed" aux "$TMP/aux.frag" "$TMP/aux.bed"; then
  echo "expected prepare_bams failure" >&2; exit 1
fi
[ "$(wc -l < "$CONVERSION_LOG")" -eq $((before + 2)) ]
[ ! -e "$TMP/prepared/aux.bam" ]

cat > "$TMP/bin/rgt-hint" <<'HINT'
#!/usr/bin/env bash
set -euo pipefail
for arg in "$@"; do case "$arg" in --output-location=*) out=${arg#*=};; esac; done
bed=${@: -1}
if [ "${MOCK_HINT_FAIL:-0}" = 1 ] && [[ "$bed" == *r_000 ]]; then exit 7; fi
mkdir -p "$out"; : > "$out/fp.bed"
HINT
chmod +x "$TMP/bin/rgt-hint"
cat > "$TMP/bin/split" <<'SPLIT'
#!/usr/bin/env bash
set -euo pipefail
n=${2#l/}; input=$6; prefix=$7
awk -v n="$n" -v prefix="$prefix" '{f=sprintf("%s%03d",prefix,(NR-1)%n); print >> f}' "$input"
SPLIT
chmod +x "$TMP/bin/split"
printf 'chr1\t1\t10\na\nchr1\t20\t30\nb\n' > "$TMP/regions.bed"
mkdir -p "$TMP/hint"
PATH="$TMP/bin:$PATH" MOCK_HINT_FAIL=0 bash "$ROOT/scripts/04b_footprint/run_hint.sh" "$TMP/bin" "$TMP/cache/gdna.bam" "$TMP/regions.bed" "$TMP/hint" 2
[ -f "$TMP/hint/events.bed" ] && [ ! -s "$TMP/hint/events.bed" ]
if PATH="$TMP/bin:$PATH" MOCK_HINT_FAIL=1 bash "$ROOT/scripts/04b_footprint/run_hint.sh" "$TMP/bin" "$TMP/cache/gdna.bam" "$TMP/regions.bed" "$TMP/hint" 2 > "$TMP/hint-fail.log" 2>&1; then
  echo "expected HINT chunk failure" >&2; exit 1
fi
[ -s "$TMP/hint/failed.txt" ] && [ ! -e "$TMP/hint/events.bed" ]

source "$ROOT/scripts/04b_footprint/wait_all_jobs.sh"
declare -a pids=() labels=()
( exit 7 ) & pids+=("$!"); labels+=("gdna/PRINT")
( sleep 0.1; touch "$TMP/reaped" ) & pids+=("$!"); labels+=("ctrl/TOBIAS")
if wait_all_jobs 2> "$TMP/wait.log"; then
  echo "expected aggregated caller failure" >&2; exit 1
fi
grep -q 'gdna/PRINT.*status=7' "$TMP/wait.log"
[ -f "$TMP/reaped" ]

HINT_SETUP="$ROOT/scripts/04b_footprint/setup_hint_env.sh"
MOCK_ENV_ROOT="$TMP/hint-env-mocks"
MOCK_CONDA="$MOCK_ENV_ROOT/conda"
mkdir -p "$MOCK_ENV_ROOT/bin" "$MOCK_ENV_ROOT/pmafp/bin"
cat > "$MOCK_ENV_ROOT/bin/python" <<'PYTHON'
#!/usr/bin/env bash
set -euo pipefail
prefix=${0%/bin/python}
if [ "${1:-}" = -m ] && [ "${2:-}" = pip ]; then
  case "${3:-}" in
    freeze) echo 'mock-package==1.0' ;;
    show) [ ! -f "$prefix/TOBIAS_REMOVED" ] ;;
    uninstall) touch "$prefix/TOBIAS_REMOVED" ;;
    check) exit 0 ;;
  esac
elif [ "${1:-}" = - ]; then
  cat >/dev/null
fi
exit 0
PYTHON
chmod +x "$MOCK_ENV_ROOT/bin/python"
cp "$MOCK_ENV_ROOT/bin/python" "$MOCK_ENV_ROOT/pmafp/bin/python"
cat > "$MOCK_ENV_ROOT/bin/rgt-hint" <<'HINTCLI'
#!/usr/bin/env bash
exit 0
HINTCLI
chmod +x "$MOCK_ENV_ROOT/bin/rgt-hint"
cat > "$MOCK_CONDA" <<'CONDA'
#!/usr/bin/env bash
set -euo pipefail
command_name=$1; shift
prefix=
while [ "$#" -gt 0 ]; do
  if [ "$1" = --prefix ]; then prefix=$2; shift 2; else shift; fi
done
case "$command_name" in
  list)
    echo "manifest:$prefix"
    ;;
  create)
    mkdir -p "$prefix/bin"
    cp "$MOCK_ENV_ROOT/bin/python" "$prefix/bin/python"
    cp "$MOCK_ENV_ROOT/bin/rgt-hint" "$prefix/bin/rgt-hint"
    [ "${MOCK_CLONE_FAIL:-0}" = 0 ] || exit 31
    ;;
  install)
    [ "${MOCK_INSTALL_FAIL:-0}" = 0 ] || exit 42
    ;;
  *) exit 64 ;;
esac
CONDA
chmod +x "$MOCK_CONDA"

MOCK_ENV_ROOT="$MOCK_ENV_ROOT" bash "$HINT_SETUP" "$MOCK_CONDA" "$MOCK_ENV_ROOT/pmafp" "$MOCK_ENV_ROOT/pma_hint_ok" > "$TMP/hint-setup-ok.log" 2>&1
grep -q PMAFP_INTEGRITY_OK "$TMP/hint-setup-ok.log"
[ ! -f "$MOCK_ENV_ROOT/pmafp/TOBIAS_REMOVED" ]
[ -f "$MOCK_ENV_ROOT/pma_hint_ok/TOBIAS_REMOVED" ]

if MOCK_ENV_ROOT="$MOCK_ENV_ROOT" MOCK_CLONE_FAIL=1 bash "$HINT_SETUP" "$MOCK_CONDA" "$MOCK_ENV_ROOT/pmafp" "$MOCK_ENV_ROOT/pma_hint_clone_fail" > "$TMP/hint-clone-fail.log" 2>&1; then
  echo "expected HINT clone failure" >&2; exit 1
else
  rc=$?
fi
[ "$rc" -eq 31 ]
grep -q PMAFP_INTEGRITY_OK "$TMP/hint-clone-fail.log"
[ -d "$MOCK_ENV_ROOT/pma_hint_clone_fail" ]

if MOCK_ENV_ROOT="$MOCK_ENV_ROOT" MOCK_INSTALL_FAIL=1 bash "$HINT_SETUP" "$MOCK_CONDA" "$MOCK_ENV_ROOT/pmafp" "$MOCK_ENV_ROOT/pma_hint_install_fail" > "$TMP/hint-install-fail.log" 2>&1; then
  echo "expected HINT dependency install failure" >&2; exit 1
else
  rc=$?
fi
[ "$rc" -eq 42 ]
grep -q PMAFP_INTEGRITY_OK "$TMP/hint-install-fail.log"
[ -d "$MOCK_ENV_ROOT/pma_hint_install_fail" ]

mkdir -p "$MOCK_ENV_ROOT/pma_hint_existing/bin"
touch "$MOCK_ENV_ROOT/pma_hint_existing/bin/python" "$MOCK_ENV_ROOT/pma_hint_existing/keep"
chmod +x "$MOCK_ENV_ROOT/pma_hint_existing/bin/python"
if MOCK_ENV_ROOT="$MOCK_ENV_ROOT" bash "$HINT_SETUP" "$MOCK_CONDA" "$MOCK_ENV_ROOT/pmafp" "$MOCK_ENV_ROOT/pma_hint_existing" > "$TMP/hint-existing.log" 2>&1; then
  echo "expected existing HINT environment rejection" >&2; exit 1
else
  rc=$?
fi
[ "$rc" -eq 2 ] && [ -f "$MOCK_ENV_ROOT/pma_hint_existing/keep" ]
echo "Step 4b runner contract fixtures passed"
