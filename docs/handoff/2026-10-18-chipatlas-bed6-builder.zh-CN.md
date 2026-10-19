# ChIP-Atlas unique BED6 builder implementation handoff

Updated: 2026-10-19 03:30 UTC
Branch: `task_20261019_chipatlas_bed6_builder`  
Parent design PR: [#6](https://github.com/leezx/Protein-Motif-Association/pull/6), exact GPT-approved design HEAD `3c0e48e699073726b9ef7453644cabbe8b277ca4`, OPEN/unmerged.  
Implementation PR: [#7](https://github.com/leezx/Protein-Motif-Association/pull/7), OPEN/unmerged, stacked on PR #6. Verify the complete live HEAD on GitHub before review or execution; this handoff is a timestamped snapshot.

## Live update — 2026-10-18 23:10 EDT / 2026-10-19 03:10 UTC — local transcript recovered; preflight stopped at manifest gate

PR #7 remains OPEN at `012b59c35bae3271605b00d8c3a77ed82061e27a` (base `3c0e48e699073726b9ef7453644cabbe8b277ca4`). GPT approved the exact static implementation/audit and one execution of this revised read-only preflight. The one-time command ran once; its result was recovered from the local Codex session rollout `01a14d07-a237-7ca2-ae3e-6c61140234bd`, tool call `call_f154707f9548495583f795ac1154580a` (result record ordinal 34954). The recorded tool result has exit code `1`; it reports the existing Argos checkout `task_20261018_step4b_setup_fix` at `4d099df44dc4bb48a93e110241168fadea1b1de6`, remote PR branch ref `012b59c35bae3271605b00d8c3a77ed82061e27a`, and canonical RAW path `/data/sysdir/home/zz950/DATA/2.PROJECTS/PMA/occupancy_chipatlas/raw/2026-10-17`. It then stopped with `required checksum entries missing/ambiguous: ['reference/hg38.chrom.sizes']`. Thus the command read the MD5SUMS manifest but did not hash or stat any of the three data inputs, inspect output paths or filesystems, report tool versions, or create the transient cgroup. No checksum, capacity, tool, or cgroup check passed; neither build nor output was produced. The one-time authorization is consumed. Do not rerun the command. Any manifest investigation or corrected preflight requires a newly reviewed, exact-scope operation. Outcomes 1 and 2 remain incomplete.
## Proposed next query — repaired after GPT REQUEST_CHANGES; not approved or run

Purpose: identify why the approved preflight's MD5SUMS parser did not find the exact `reference/hg38.chrom.sizes` key. This is a new, independent one-time read-only query, not a retry of the consumed preflight. It reads only `MD5SUMS` content and inspects names/type metadata for matching entries in the `reference/` directory; it does not open or hash any ChIP-Atlas data file, inspect output/storage/tool/cgroup state, or create files. It will stop on any path/symlink guard failure. GPT found that `Path.is_file()` would follow a matching symlink. The proposal now inspects `lstat()` mode only, streams the manifest, avoids sorting, caps candidate output at 100 with a nonzero incomplete-report exit, and repr-escapes names. It remains unapproved and unrun. Exact command proposed for fresh GPT review:

```bash
ssh -o BatchMode=yes zz950@rcapps3.dfci.harvard.edu 'bash -s' <<'REMOTE'
set -euo pipefail
RAW=/home/zz950/DATA/2.PROJECTS/PMA/occupancy_chipatlas/raw/2026-10-17
PY=/home/zz950/softwares/miniforge3/envs/pmafp/bin/python
"$PY" - "$RAW" <<'PY'
import os, re, stat, sys
from pathlib import Path
logical_root = Path(os.path.abspath(sys.argv[1]))
logical_parent = logical_root.parent.parent.resolve(strict=True)
raw_parent = logical_parent / logical_root.parent.name
root = raw_parent / logical_root.name
if raw_parent.is_symlink() or not raw_parent.is_dir():
    raise SystemExit("RAW parent is missing or symlinked")
if root.is_symlink() or not root.is_dir() or root.resolve(strict=True) != root:
    raise SystemExit("RAW root is missing, symlinked, or resolves unexpectedly")
def safe_path(value):
    logical = Path(os.path.abspath(value))
    try:
        relative = logical.relative_to(logical_root)
    except ValueError:
        raise SystemExit(f"path outside logical RAW: {logical}")
    if not relative.parts or ".." in relative.parts:
        raise SystemExit(f"invalid relative path: {relative}")
    current = root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise SystemExit(f"symlink inside RAW: {current}")
    resolved = current.resolve(strict=True)
    if os.path.commonpath((str(root), str(resolved))) != str(root) or resolved != current:
        raise SystemExit(f"path escapes canonical RAW: {current}")
    return current
manifest = safe_path(logical_root / "MD5SUMS")
reference = safe_path(logical_root / "reference")
if not manifest.is_file() or not reference.is_dir():
    raise SystemExit("MD5SUMS or reference directory has unexpected type")
pattern = re.compile(r"([0-9A-Fa-f]{32}) [ *](.+)")
candidate_count = 0
def emit_candidate(line):
    global candidate_count
    candidate_count += 1
    if candidate_count > 100:
        raise SystemExit("candidate limit exceeded; report incomplete")
    print(line)
with manifest.open(encoding="ascii") as manifest_stream:
    for line_no, line in enumerate(manifest_stream, 1):
        match = pattern.fullmatch(line.rstrip("\n"))
        if match and "chrom" in match.group(2).lower() and "size" in match.group(2).lower():
            emit_candidate(f"MANIFEST_CANDIDATE line={line_no} path={match.group(2)!r}")
for entry in reference.iterdir():
    if "chrom" in entry.name.lower() and "size" in entry.name.lower():
        mode = entry.lstat().st_mode
        emit_candidate(f"REFERENCE_CANDIDATE name={entry.name!r} symlink={stat.S_ISLNK(mode)} regular_file={stat.S_ISREG(mode)}")
PY
REMOTE
```

This command has not been run. It requires fresh exact-HEAD review and a separate one-time scope approval. A result would only resolve the manifest-name discrepancy; it would not authorize input hashing beyond the original allowlist, a builder, QC, tests, benchmark, install, or merge.

## Direction and current progress

**Live update — 2026-10-18 22:55 EDT.** GPT approved PR #7 exact HEAD `1432f6211b3e3411bf62a6f5e5f951bf9df17863` for implementation static review and for one execution of the exact read-only preflight below. The command was run once and exited `1` when the path guard found `/home` is a symlink. Captured stdout before exit: Argos checkout `task_20261018_step4b_setup_fix`, HEAD `4d099df44dc4bb48a93e110241168fadea1b1de6`, and remote PR branch ref `1432f6211b3e3411bf62a6f5e5f951bf9df17863`. It stopped before opening MD5SUMS or any input, checking output paths/filesystem/tools, or creating the transient cgroup. No checksum, disk, or cgroup result was obtained. Stderr included the SSH post-quantum key-exchange warning. No retry or other Argos command has been run. GPT's final scope approval is recorded in the persistent PMA review conversation; it excludes all build/QC/benchmark work.

**Historical proposal state — 2026-10-18 22:57 EDT (before later approval/execution).** GPT recommended canonicalizing only the trusted parent above RAW, while rejecting symlinks at RAW and below and keeping all resolved targets under the canonical RAW root. The command below now follows that proposal and explicitly checks the cgroup result without Python `assert`. Static syntax/AST/diff checks passed. This is a modified SSH command: the earlier one-time permission is consumed, so request fresh exact-head and one-time scope approval before any retry. No new SSH command has run.

GPT reviewed PR #7 exact code HEAD `05652f09eef0dc83b6c6c80bee1922dddf11d209` (base `3c0e48e699073726b9ef7453644cabbe8b277ca4`) and returned `APPROVE — Implementation code-review gate`, with zero blockers. This was static code review only. Later preflight reviews resolved the scope blockers; see the live update above for the exact approved head and one failed execution. No MD5SUMS or source data contents were read.

GPT subsequently verified HEAD `e61fccda1fc03c2b0326a09def3d5ea1b206757d`; it approved the code but requested a symlink-component guard for the preflight. That repair is commit `1432f6211b3e3411bf62a6f5e5f951bf9df17863`, which then received approval for exactly one read-only preflight execution. The outcome of that authorized single execution is described above.

The user's two endpoints remain: (1) produce a coordinate-unique, experiment-traceable human hg38 ChIP-Atlas BED6 reference with QC; (2) compare PRINT, TraceBIND, HINT, and TOBIAS on matched motif-free footprint accuracy and genome-wide speed on Argos, then complete B1–B4 and motif integration. Neither endpoint is complete.

PR #6's current design-only approval does not include implementation or Argos operations. This branch contains a proposed streaming builder for endpoint 1 and an implementation-stage clarification to the approved design. It has not read external datasets, run a builder, or measured memory/disk/runtime. The latest static checks are Python compilation via `python3 -m py_compile`, shell parse (`bash -n`), and `git diff --check`; no functional tests were run.

## Builder contract in this branch

- CLI consumes the pinned hg38 peaks archive, experiment metadata snapshot, and chromosome sizes, and writes to a new external output directory. It rejects output/work paths inside a Git checkout.
- It assigns every source row one primary status, streams eligible rows to an external-sort spool, de-duplicates exact coordinates only, and retains every included source row in provenance.
- Core build uses two GNU external sorts. The builder records collision QC as `NOT_RUN`; separate `verify_unique_bed6_region_ids.py` performs a third compact sort by full region ID once per formal release. Zero duplicate IDs and zero coordinate/hash mismatches are required for `PASS`.
- The builder produces BED6, region–experiment links, source-row provenance, region summary, experiment metadata (including zero-peak eligible experiments), reconciliation counts, deterministic tabix query QC, collision-QC `NOT_RUN`, and a SHA-256 manifest. The separate collision checker validates chromosome order/bounds, coordinates, full ID hashes, and exact ID uniqueness, then updates the release QC/manifest.
- The builder and release-QC launchers fail closed unless `systemd-run --user` can place Python and child processes in a cgroup capped at 44 GiB with swap disabled. GNU sort defaults to 4 GiB and two workers. Disk peak remains unknown and must be assessed by an approved read-only Argos preflight before any build.
- Both Python entrypoints independently verify the live cgroup-v2 `memory.max` (finite, <=44 GiB), `memory.swap.max=0`, and readable memory peak; direct invocation outside this enforced limit fails before data reading. GNU sort uses `LC_ALL=C`.
- The builder requires explicit `--metadata-release` (the pinned source is 2026-10-14; never infer this from `raw/2026-10-17/`). After writing, it fully rereads BED6, region summaries, region-experiment links, and peak provenance, verifies cross-file cardinalities/order/IDs/source hashes and chromosome bounds, and consumes gzip streams to validate CRCs before marking output integrity `PASS`.
- Tabix QC uses byte-for-byte comparisons for 48 seeded random windows and includes a guaranteed positive control derived from an emitted region.

## Review and execution gates

The code review passed for PR #7 exact HEAD `1432f6211b3e3411bf62a6f5e5f951bf9df17863`. GPT approved one execution of the read-only preflight at the same SHA. It stopped at the source-path symlink guard (`/home`); see the live update. The remainder of the proposal documents the intended scope and was not reached in that run. No second SSH invocation is authorized by the one-time approval.

Revised read-only preflight proposal (not yet approved; the prior version stopped at the first path guard):

```bash
ssh -o BatchMode=yes zz950@rcapps3.dfci.harvard.edu 'bash -s' <<'REMOTE'
set -euo pipefail
RAW=/home/zz950/DATA/2.PROJECTS/PMA/occupancy_chipatlas/raw/2026-10-17
BASE=/home/zz950/DATA/2.PROJECTS/PMA/occupancy_chipatlas
OUT=$BASE/processed/unique_bed6_v1
WORK=$BASE/processed/unique_bed6_v1_work
CODE=/home/zz950/PMA_code_4b
PY=/home/zz950/softwares/miniforge3/envs/pmafp/bin/python
test -d "$CODE" && test -x "$PY"
GIT_OPTIONAL_LOCKS=0 git -c core.fsmonitor=false -C "$CODE" status --short --branch
git -C "$CODE" rev-parse HEAD
git ls-remote https://github.com/leezx/Protein-Motif-Association.git refs/heads/task_20261019_chipatlas_bed6_builder
"$PY" - "$RAW/MD5SUMS" "$RAW" <<'PY'
import hashlib, os, re, sys
from pathlib import Path, PurePosixPath
logical_root = Path(os.path.abspath(sys.argv[2]))
logical_parent = logical_root.parent.parent.resolve(strict=True)
raw_parent = logical_parent / logical_root.parent.name
root = raw_parent / logical_root.name
if raw_parent.is_symlink() or not raw_parent.is_dir():
    raise SystemExit("RAW parent is missing or symlinked")
if root.is_symlink() or not root.is_dir() or root.resolve(strict=True) != root:
    raise SystemExit("RAW root is missing, symlinked, or resolves unexpectedly")
print(f"CANONICAL_RAW_ROOT {root}")
def guarded_path(value):
    logical = Path(os.path.abspath(value))
    try:
        relative = logical.relative_to(logical_root)
    except ValueError:
        raise SystemExit(f"path outside logical raw root: {logical}")
    if not relative.parts or ".." in relative.parts:
        raise SystemExit(f"invalid relative source path: {relative}")
    current = root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise SystemExit(f"symlink inside raw root: {current}")
    resolved = current.resolve(strict=True)
    if os.path.commonpath((str(root), str(resolved))) != str(root):
        raise SystemExit(f"resolved path escapes raw root: {resolved}")
    if resolved != current:
        raise SystemExit(f"unexpected path resolution: {current}")
    return current
manifest = guarded_path(sys.argv[1])
if not manifest.is_file():
    raise SystemExit("missing checksum manifest")
allowed = {"allPeaks_light.hg38.05.bed.gz", "experimentList.tab", "reference/hg38.chrom.sizes"}
seen, expected = set(), {}
for line_no, line in enumerate(manifest.read_text(encoding="ascii").splitlines(), 1):
    if not line:
        continue
    match = re.fullmatch(r"([0-9A-Fa-f]{32}) [ *](.+)", line)
    if not match:
        raise SystemExit(f"invalid MD5SUMS row {line_no}")
    digest, raw_name = match.groups()
    name_path = PurePosixPath(raw_name)
    if name_path.is_absolute() or ".." in name_path.parts:
        raise SystemExit(f"unsafe MD5SUMS path at row {line_no}")
    name = name_path.as_posix()
    if name in seen:
        raise SystemExit(f"duplicate MD5SUMS path: {name}")
    seen.add(name)
    if name in allowed:
        expected[name] = digest.lower()
if set(expected) != allowed:
    raise SystemExit(f"required checksum entries missing/ambiguous: {sorted(allowed-set(expected))}")
for name in sorted(allowed):
    path = guarded_path(logical_root / name)
    if not path.is_file():
        raise SystemExit(f"unsafe or missing input file: {name}")
    digest = hashlib.md5()
    size = 0
    with path.open("rb") as source:
        for block in iter(lambda: source.read(8 << 20), b""):
            digest.update(block)
            size += len(block)
    if digest.hexdigest() != expected[name]:
        raise SystemExit(f"MD5 mismatch: {name}")
    print(f"MD5_OK {name} {size} bytes {digest.hexdigest()}")
PY
stat -c '%n %s bytes %y' "$RAW/allPeaks_light.hg38.05.bed.gz" "$RAW/experimentList.tab" "$RAW/reference/hg38.chrom.sizes"
if [ -e "$OUT" ] || [ -L "$OUT" ] || [ -e "$WORK" ] || [ -L "$WORK" ]; then
  echo "ERROR: output or work candidate already exists" >&2
  exit 2
fi
if [ -d "$BASE/processed" ]; then TARGET_FS=$BASE/processed; else TARGET_FS=$BASE; fi
df -B1 -P "$RAW" "$TARGET_FS"
df -i -P "$RAW" "$TARGET_FS"
findmnt -T "$RAW"
findmnt -T "$TARGET_FS"
"$PY" --version
sort --version | sed -n '1p'
bgzip --version 2>&1 | sed -n '1p'
tabix --version 2>&1 | sed -n '1p'
systemd-run --version | sed -n '1p'
systemd-run --user --scope --quiet --property=MemoryMax=44G --property=MemorySwapMax=0 --property=TasksMax=8 -- \
  "$PY" -c 'from pathlib import Path; import json,sys; p=next(x.split(":",2)[2] for x in Path("/proc/self/cgroup").read_text().splitlines() if x.startswith("0::")); c=Path("/sys/fs/cgroup")/p.lstrip("/"); v={n:(c/n).read_text().strip() for n in ("memory.max","memory.swap.max","memory.peak")}; print(json.dumps({"cgroup":p,**v})); ok=v["memory.max"]!="max" and int(v["memory.max"])<=44*1024**3 and v["memory.swap.max"]=="0" and v["memory.peak"].isdigit(); sys.exit(0 if ok else 1)'
REMOTE
```

The authorized run exited `1` at `guarded_path()` with `symlink path component: /home`. The command had already printed the remote checkout state and branch HEAD and completed `git ls-remote`; it stopped before opening MD5SUMS, hashing or statting inputs, inspecting output paths/filesystems/tool versions, or creating a cgroup. No output/work path was created and no analysis ran. GPT recommended resolving only the trusted parent above RAW (to permit a system-level `/home` symlink), then rejecting a symlink at RAW itself and every component below RAW, while requiring resolved inputs to remain under the canonical RAW root. This revised command needs fresh exact-head and one-time scope review; the previous one-time approval is consumed. Do not retry or issue another SSH command before that review.

Any full build is a later stage requiring a separate explicit scope decision. The preflight only reports free capacity; a later review must compare that measurement with a defensible temporary-space estimate from the pinned input and algorithm before deciding whether to build. The correct PR checkout must also be prepared on Argos under an approved scope. Keep every task at or below the 44 GiB configured cap and below the user's 50 GB limit. Do not merge PR #6 or PR #7 without the user's separate approval.

## Next acceptance

Finish static review, update the PR body and this handoff with the final exact HEAD, request exact-head GPT review, and fix only review findings in the same PR. After preflight review, use the reported free capacity plus a defensible temporary-space estimate to request a separate exact-scope review before any build; never use Mac mini compute. Then verify full row reconciliation, coordinate and region-ID uniqueness, provenance/linkage cardinality, class-mask counts, tabix queries, and reproducible hashes. Keep all data and results outside the repository.
