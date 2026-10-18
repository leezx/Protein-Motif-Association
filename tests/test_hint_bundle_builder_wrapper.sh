#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
wrapper="$repo_root/scripts/04b_footprint/run_hint_bundle_builder.sh"
tmp=$(mktemp -d)
trap 'python3 -c "import shutil,sys; shutil.rmtree(sys.argv[1],ignore_errors=True)" "$tmp"' EXIT

mkdir -p "$tmp/bin"
cat > "$tmp/bin/docker" <<'SH'
#!/usr/bin/env bash
printf '%s\n' "$*" > "$DOCKER_ARGS_FILE"
SH
chmod +x "$tmp/bin/docker"
export PATH="$tmp/bin:$PATH"
export DOCKER_ARGS_FILE="$tmp/docker-args.txt"
export PMA_HINT_BUILDER_IMAGE="builder.example/pma@sha256:$(printf 'a%.0s' {1..64})"

if "$wrapper" "$repo_root/outside-bundle" "$tmp/evidence-inside" 2>"$tmp/inside.err"; then
  echo "wrapper accepted output inside the checkout" >&2
  exit 1
fi
cat "$tmp/inside.err" >&2
grep -q BUNDLE_OUTPUT_MUST_BE_OUTSIDE_GIT_CHECKOUT "$tmp/inside.err"
[[ ! -e "$DOCKER_ARGS_FILE" ]]

mkdir -p "$tmp/external-parent"
ln -s "$repo_root" "$tmp/external-parent/checkout-alias"
if "$wrapper" "$tmp/external-parent/checkout-alias/bundle" "$tmp/external-evidence" 2>"$tmp/symlink.err"; then
  echo "wrapper accepted symlink alias into the checkout" >&2
  exit 1
fi
grep -q BUNDLE_OUTPUT_MUST_BE_OUTSIDE_GIT_CHECKOUT "$tmp/symlink.err"
[[ ! -e "$DOCKER_ARGS_FILE" ]]

"$wrapper" "$tmp/external-bundle" "$tmp/external-evidence"
grep -q -- "--platform linux/amd64" "$DOCKER_ARGS_FILE"
bundle_real=$(python3 -c 'import os,sys; print(os.path.realpath(sys.argv[1]))' "$tmp/external-bundle")
evidence_real=$(python3 -c 'import os,sys; print(os.path.realpath(sys.argv[1]))' "$tmp/external-evidence")
grep -q -- "type=bind,src=$bundle_real,dst=/output/bundle" "$DOCKER_ARGS_FILE"
grep -q -- "type=bind,src=$evidence_real,dst=/output/evidence" "$DOCKER_ARGS_FILE"
! grep -q "$repo_root" "$DOCKER_ARGS_FILE"
echo "HINT bundle builder wrapper fixtures passed"
