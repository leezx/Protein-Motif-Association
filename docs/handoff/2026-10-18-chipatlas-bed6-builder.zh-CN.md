# ChIP-Atlas unique BED6 builder implementation handoff

Updated: 2026-10-18 22:46 EDT
Branch: `task_20261019_chipatlas_bed6_builder`  
Parent design PR: [#6](https://github.com/leezx/Protein-Motif-Association/pull/6), exact GPT-approved design HEAD `3c0e48e699073726b9ef7453644cabbe8b277ca4`, OPEN/unmerged.  
Implementation PR: [#7](https://github.com/leezx/Protein-Motif-Association/pull/7), OPEN/unmerged, stacked on PR #6. Verify the complete live HEAD on GitHub before review or execution; this handoff is a timestamped snapshot.

## Direction and current progress

GPT reviewed PR #7 exact code HEAD `05652f09eef0dc83b6c6c80bee1922dddf11d209` (base `3c0e48e699073726b9ef7453644cabbe8b277ca4`) and returned `APPROVE — Implementation code-review gate`, with zero blockers. This is static code review only and does not authorize Argos, data reads, disk preflight, builder/QC/tests, analysis, or merge. The subsequent preflight proposal at `23f5f43b8f02c26f8c52863d66620d5cd9a7f105` received `REQUEST_CHANGES` for manifest scope, optional Git index writes, dangling-symlink checks, and overstated disk-feasibility stop conditions. Commit `23e19339bb1b7b8f1281f8b72d97f262e8aca81c` repairs those exact findings in the audit proposal. The complete current PR head is pending exact-head review; no external data or metadata has been read and no Argos command has been run.

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

The code review passed for exact HEAD `05652f09eef0dc83b6c6c80bee1922dddf11d209`, but no remote action is approved by that verdict. Preflight proposal commit `23e19339bb1b7b8f1281f8b72d97f262e8aca81c` is pending exact-head review. Planned destination: `ssh -o BatchMode=yes zz950@rcapps3.dfci.harvard.edu`. Planned inputs: `/home/zz950/DATA/2.PROJECTS/PMA/occupancy_chipatlas/raw/2026-10-17/{allPeaks_light.hg38.05.bed.gz,experimentList.tab,reference/hg38.chrom.sizes,MD5SUMS}`. Planned output candidate (not to be created during preflight): `/home/zz950/DATA/2.PROJECTS/PMA/occupancy_chipatlas/processed/unique_bed6_v1/`; scratch candidate: the sibling `unique_bed6_v1_work/`. Preflight will only inspect the PR checkout identity/status, the checksum manifest and the three allowlisted inputs, free bytes/inodes on the data filesystem, existing output-path state, and Python/GNU sort/bgzip/tabix/systemd availability. It will run a tiny no-input `systemd-run --user --scope` probe capped at 44 GiB with swap disabled and read the child cgroup's actual `memory.max`, `memory.swap.max`, and `memory.peak`; it will not create output/work directories, install software, fetch/checkout code, modify data, or run a builder. It must stop if an input/checksum is missing, output path already exists, checksum fails, or cgroup cap/swap check fails. Disk values are report-only and are not treated as proof of build feasibility. The exact command is to be reviewed against the complete current PR HEAD before any SSH command is run.

Exact read-only preflight proposal (not yet run):

```bash
ssh -o BatchMode=yes zz950@rcapps3.dfci.harvard.edu 'bash -s' <<'REMOTE'
set -euo pipefail
RAW=/home/zz950/DATA/2.PROJECTS/PMA/occupancy_chipatlas/raw/2026-10-17
BASE=/home/zz950/DATA/2.PROJECTS/PMA/occupancy_chipatlas
OUT=$BASE/processed/unique_bed6_v1
WORK=$BASE/processed/unique_bed6_v1_work
CODE=/home/zz950/PMA_code_4b
PY=/home/zz950/softwares/miniforge3/envs/pmafp/bin/python
test -d "$RAW" && test -d "$BASE" && test -d "$CODE" && test -x "$PY"
GIT_OPTIONAL_LOCKS=0 git -c core.fsmonitor=false -C "$CODE" status --short --branch
git -C "$CODE" rev-parse HEAD
git ls-remote https://github.com/leezx/Protein-Motif-Association.git refs/heads/task_20261019_chipatlas_bed6_builder
cd "$RAW"
test -s allPeaks_light.hg38.05.bed.gz
test -s experimentList.tab
test -s reference/hg38.chrom.sizes
test -s MD5SUMS
"$PY" - "$RAW/MD5SUMS" "$RAW" <<'PY'
import hashlib, os, re, sys
from pathlib import Path, PurePosixPath
manifest, root = Path(sys.argv[1]), Path(sys.argv[2]).resolve()
if manifest.is_symlink() or not manifest.is_file() or os.path.commonpath((str(root), str(manifest.resolve()))) != str(root):
    raise SystemExit("unsafe or missing checksum manifest")
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
    path = root / name
    if path.is_symlink() or not path.is_file() or os.path.commonpath((str(root), str(path.resolve()))) != str(root):
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
stat -c '%n %s bytes %y' allPeaks_light.hg38.05.bed.gz experimentList.tab reference/hg38.chrom.sizes
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
  "$PY" -c 'from pathlib import Path; import json; p=next(x.split(":",2)[2] for x in Path("/proc/self/cgroup").read_text().splitlines() if x.startswith("0::")); c=Path("/sys/fs/cgroup")/p.lstrip("/"); v={n:(c/n).read_text().strip() for n in ("memory.max","memory.swap.max","memory.peak")}; print(json.dumps({"cgroup":p,**v})); assert int(v["memory.max"]) <= 44*1024**3 and v["memory.swap.max"] == "0"'
REMOTE
```

This preflight reads the checksum manifest and hashes exactly the three allowlisted inputs; it rejects malformed, duplicate, or path-traversing manifest entries and does not open other manifest targets. It performs read-only status/path/filesystem/tool queries plus the proposed transient cgroup scope. It does not create output/work directories, install software, fetch/checkout code, modify data, or run a builder. It stops if an input/checksum is missing, either candidate path exists (including dangling symlinks), checksum fails, or cgroup verification fails. Disk values are collected for reporting only: this stage does not establish disk feasibility, and a zero exit code does not open the full-build gate. A separate review must assess estimated sort/output peak before any build. No SSH command has been run.

Any full build is a later stage requiring a separate explicit scope decision. The preflight only reports free capacity; a later review must compare that measurement with a defensible temporary-space estimate from the pinned input and algorithm before deciding whether to build. The correct PR checkout must also be prepared on Argos under an approved scope. Keep every task at or below the 44 GiB configured cap and below the user's 50 GB limit. Do not merge PR #6 or PR #7 without the user's separate approval.

## Next acceptance

Finish static review, update the PR body and this handoff with the final exact HEAD, request exact-head GPT review, and fix only review findings in the same PR. After preflight review, use the reported free capacity plus a defensible temporary-space estimate to request a separate exact-scope review before any build; never use Mac mini compute. Then verify full row reconciliation, coordinate and region-ID uniqueness, provenance/linkage cardinality, class-mask counts, tabix queries, and reproducible hashes. Keep all data and results outside the repository.
