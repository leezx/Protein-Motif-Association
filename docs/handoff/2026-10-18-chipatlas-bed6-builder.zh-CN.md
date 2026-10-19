# ChIP-Atlas unique BED6 builder implementation handoff

Updated: 2026-10-19 03:18 UTC
Branch: `task_20261019_chipatlas_bed6_builder`  
Parent design PR: [#6](https://github.com/leezx/Protein-Motif-Association/pull/6), exact GPT-approved design HEAD `3c0e48e699073726b9ef7453644cabbe8b277ca4`, OPEN/unmerged.  
Implementation PR: [#7](https://github.com/leezx/Protein-Motif-Association/pull/7), OPEN/unmerged, stacked on PR #6. Verify the complete live HEAD on GitHub before review or execution; this handoff is a timestamped snapshot.

## Live update — 2026-10-18 23:10 EDT / 2026-10-19 03:10 UTC — local transcript recovered; preflight stopped at manifest gate

PR #7 remains OPEN at `012b59c35bae3271605b00d8c3a77ed82061e27a` (base `3c0e48e699073726b9ef7453644cabbe8b277ca4`). GPT approved the exact static implementation/audit and one execution of this revised read-only preflight. The one-time command ran once; its result was recovered from the local Codex session rollout `01a14d07-a237-7ca2-ae3e-6c61140234bd`, tool call `call_f154707f9548495583f795ac1154580a` (result record ordinal 34954). The recorded tool result has exit code `1`; it reports the existing Argos checkout `task_20261018_step4b_setup_fix` at `4d099df44dc4bb48a93e110241168fadea1b1de6`, remote PR branch ref `012b59c35bae3271605b00d8c3a77ed82061e27a`, and canonical RAW path `/data/sysdir/home/zz950/DATA/2.PROJECTS/PMA/occupancy_chipatlas/raw/2026-10-17`. It then stopped with `required checksum entries missing/ambiguous: ['reference/hg38.chrom.sizes']`. Thus the command read the MD5SUMS manifest but did not hash or stat any of the three data inputs, inspect output paths or filesystems, report tool versions, or create the transient cgroup. No checksum, capacity, tool, or cgroup check passed; neither build nor output was produced. The one-time authorization is consumed. Do not rerun the command. Any manifest investigation or corrected preflight requires a newly reviewed, exact-scope operation. Outcomes 1 and 2 remain incomplete.
## One-time manifest/name diagnostic — GPT-approved and executed once at PR HEAD `1478fb7`

Purpose: identify why the earlier preflight did not find the exact `reference/hg38.chrom.sizes` manifest key. GPT reviewed the exact command at PR #7 HEAD `1478fb71bfe7b8e4dce19d4b3360ee4a6d8697da` / base `3c0e48e699073726b9ef7453644cabbe8b277ca4` and approved this independent, one-time, read-only scope. The exact command below was executed once. It reads only `MD5SUMS` text and names/type metadata for matching entries in `reference/`; it does not open or hash ChIP-Atlas data files, inspect output/storage/tools/cgroup state, or create files. The path guard rejects internal symlinks; candidate types use no-follow metadata. `os.scandir()` streams directory enumeration. Candidate records are capped at 100; that is not a strict output-byte cap and individual manifest line length is not separately bounded.

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
with os.scandir(reference) as entries:
    for entry in entries:
        if "chrom" in entry.name.lower() and "size" in entry.name.lower():
            mode = entry.stat(follow_symlinks=False).st_mode
            emit_candidate(f"REFERENCE_CANDIDATE name={entry.name!r} symlink={stat.S_ISLNK(mode)} regular_file={stat.S_ISREG(mode)}")
PY
REMOTE
```

**Observed result (one invocation):** exit code `0`. stdout contained one line: `REFERENCE_CANDIDATE name='hg38.chrom.sizes' symlink=False regular_file=True`. No `MANIFEST_CANDIDATE` line was emitted, meaning the streaming parser found no MD5SUMS line in the expected GNU-style form with a chromosome/size-like path. This establishes that the named reference file exists as a regular, non-symlink entry and that the query found no matching manifest candidate; it does not establish why the manifest differs, verify the file checksum/content, or prove other manifest formats absent. stderr contained only the SSH post-quantum key-exchange warning. Complete local stdout/stderr and exit status are retained outside the repository at `/tmp/pma_pr7_manifest_diag_1478fb7.RLXv0N/` (SHA-256 stdout `f800af4128b3ce247863b197ef628bc6040a905d3e26a1fa2980a83976e31b78`; stderr `048e2ba89ae430962e02f5341cf60c694fb7e131cb417790075a56b32ca09992`). No input checksum, source-content, output-capacity, tool, or cgroup check was performed. The one-time diagnostic authorization is consumed. No additional remote command is authorized by this result; a next query or full preflight requires fresh exact-head/scope review. Builder, QC, tests, benchmark, install, and merge remain outside this scope.

## Checksum-name discovery — GPT-approved and executed once at PR HEAD `b347d8e`

GPT's technical recommendation was to check existing local staging/download records first, then—only if those do not establish checksum provenance—request a new narrow remote discovery operation that lists checksum-like names and types in the fixed RAW root and `reference/`, without reading their contents. The following local-only search was performed: repository docs, Worklog, handoffs, and retained local Codex session JSONL for `MD5SUMS.refs` and `hg38.chrom.sizes`. It confirmed the design identifies `reference/hg38.chrom.sizes` as a UCSC source with 455 contigs, and older Step 4b logs mention `MD5SUMS.refs` for the separate ATAC raw dataset. It found no local record showing the ChIP-Atlas reference checksum manifest path or checksum. The ATAC manifest mention is not evidence that an occupancy-ChIP-Atlas companion manifest exists.

GPT approved the exact-name discovery command at PR #7 HEAD `b347d8e87bfc541990bab1647119dc848056ac87` / base `3c0e48e699073726b9ef7453644cabbe8b277ca4` for one invocation. It only listed candidate manifest/checksum-like names and no-follow types in the fixed RAW root and `reference/` child; it did not read file contents, source data, hashes, output/storage/tool/cgroup state, and created no files.

```bash
ssh -o BatchMode=yes zz950@rcapps3.dfci.harvard.edu 'bash -s' <<'REMOTE'
set -euo pipefail
RAW=/home/zz950/DATA/2.PROJECTS/PMA/occupancy_chipatlas/raw/2026-10-17
PY=/home/zz950/softwares/miniforge3/envs/pmafp/bin/python
"$PY" - "$RAW" <<'PY'
import os, stat, sys
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
reference = safe_path(logical_root / "reference")
if not reference.is_dir():
    raise SystemExit("reference is not a directory")
candidate_count = 0
tokens = ("md5", "sha256", "checksum", "checksums", "manifest")
def scan_candidates(label, directory):
    global candidate_count
    with os.scandir(directory) as entries:
        for entry in entries:
            if not any(token in entry.name.lower() for token in tokens):
                continue
            candidate_count += 1
            if candidate_count > 100:
                raise SystemExit("candidate limit exceeded; report incomplete")
            mode = entry.stat(follow_symlinks=False).st_mode
            kind = ("symlink" if stat.S_ISLNK(mode) else
                    "regular_file" if stat.S_ISREG(mode) else
                    "directory" if stat.S_ISDIR(mode) else "other")
            print(f"CHECKSUM_CANDIDATE dir={label} name={entry.name!r} type={kind}")
scan_candidates("RAW", root)
scan_candidates("reference", reference)
PY
REMOTE
```

**Observed result (one invocation):** exit code `0`. stdout listed exactly two candidates: `RAW/MD5SUMS` and `reference/MD5SUMS`, both regular files. It did not find a name containing `MD5SUMS.refs`, `SHA256`, `checksum`, or `manifest` in either scanned top-level directory. stderr contained only the SSH post-quantum warning. Complete stdout/stderr/exit record is outside the repository at `/tmp/pma_pr7_checksum_discovery_b347d8e.ofZvuy/`; stdout SHA-256 `00ee47447c514792aa69a9c1e92d40d91cb1f3133adf0514c09e1baf81006117`, stderr SHA-256 `048e2ba89ae430962e02f5341cf60c694fb7e131cb417790075a56b32ca09992`. This establishes candidate names and file types only. It does not establish the contents, provenance, or expected hash in either manifest. The one-time scope is consumed.

## Live update — 2026-10-18 23:38 EDT — two-manifest read-only preflight repaired locally

After the one-time approved reference-manifest read, corrected the draft preflight mapping: the two source inputs are matched only against `RAW/MD5SUMS`; `reference/hg38.chrom.sizes` is matched against `RAW/reference/MD5SUMS` using the basename `hg38.chrom.sizes`. The parser uses an explicit three-file map, rejects duplicate/unsafe manifest names, caps manifest reads at 1 MiB, and checks source MD5s only after both required manifest entries are present. Static embedded-Python parsing, `bash -n`, and `git diff --check` pass. This new command has not been reviewed or run. No Argos access, input hashing, storage/tool/cgroup inspection, build, QC, or analysis occurred. It requires a new exact-head review and one-time scope approval.

## One-time reference/MD5SUMS read — GPT-approved and executed at PR HEAD `4212f78`

The command below reads only the observed regular file `reference/MD5SUMS`. GPT reviewed PR #7 HEAD `9138d5bca5a0f9b59bf2724a7ec4481b681306b8` and returned `REQUEST_CHANGES` for two file-descriptor boundary issues: buffered `fdopen().read()` may prefetch beyond the requested amount, and blocking `os.open()` could hang if a path race replaces the target with a FIFO. It also recommended a strict formatted-output cap. The command was repaired to open with `O_NOFOLLOW | O_NONBLOCK`, verify the opened descriptor using `fstat()`, read through an unbuffered stream in chunks totaling at most 65,537 bytes, reject >64 KiB, and build/check the complete formatted output against 16 KiB before writing it. GPT approved this exact command at HEAD `4212f782f5936ebc8c6456a17d4de3263aa56911` / base `3c0e48e699073726b9ef7453644cabbe8b277ca4` for one execution.

```bash
ssh -o BatchMode=yes zz950@rcapps3.dfci.harvard.edu 'bash -s' <<'REMOTE'
set -euo pipefail
RAW=/home/zz950/DATA/2.PROJECTS/PMA/occupancy_chipatlas/raw/2026-10-17
PY=/home/zz950/softwares/miniforge3/envs/pmafp/bin/python
"$PY" - "$RAW" <<'PY'
import os, stat, sys
from pathlib import Path
MAX_BYTES = 65536
MAX_OUTPUT_BYTES = 16384
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
reference = safe_path(logical_root / "reference")
manifest = safe_path(logical_root / "reference" / "MD5SUMS")
if not reference.is_dir():
    raise SystemExit("reference is not a directory")
if not hasattr(os, "O_NOFOLLOW"):
    raise SystemExit("O_NOFOLLOW is unavailable")
fd = os.open(str(manifest), os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
try:
    st = os.fstat(fd)
    if not stat.S_ISREG(st.st_mode):
        raise SystemExit("reference/MD5SUMS is not a regular file")
    if st.st_size > MAX_BYTES:
        raise SystemExit("reference/MD5SUMS exceeds 64 KiB; report incomplete")
    with os.fdopen(fd, "rb", buffering=0) as stream:
        fd = -1
        chunks = []
        remaining = MAX_BYTES + 1
        while remaining:
            block = stream.read(remaining)
            if not block:
                break
            chunks.append(block)
            remaining -= len(block)
        data = b"".join(chunks)
    if len(data) > MAX_BYTES:
        raise SystemExit("reference/MD5SUMS grew beyond 64 KiB; report incomplete")
finally:
    if fd >= 0:
        os.close(fd)
text = data.decode("ascii")
lines = text.splitlines()
output = [f"MANIFEST_BYTES={len(data)} MANIFEST_LINES={len(lines)}"]
for line_no, line in enumerate(lines, 1):
    output.append(f"MANIFEST_LINE number={line_no} text={line!r}")
formatted = "\n".join(output) + "\n"
if len(formatted.encode("ascii")) > MAX_OUTPUT_BYTES:
    raise SystemExit("formatted output exceeds 16 KiB; report incomplete")
sys.stdout.write(formatted)
PY
REMOTE
```

**Observed result (one invocation):** exit code `0`. stdout reported 274 bytes and five ASCII lines:

```text
83fe6bf8187a64dee8079b80f75ba289  hg38-blacklist.v2.bed.gz
c42e9f75fff906c6a7143cb2fac86602  hg38.chrom.sizes
cfb3e2337755e56baa4fa648a96765b2  hgnc_complete_set.txt
41fc0baff1d7012a94cc2fb9d97c366b  lambert2018_TF_names_v_1.01.txt
296c7c3951482117b55c6b6a68dfa371  MD5SUMS
```

The manifest uses basenames, so the `hg38.chrom.sizes` record is `c42e9f75fff906c6a7143cb2fac86602`; the previous preflight expected the prefixed path `reference/hg38.chrom.sizes` in the root manifest and therefore failed. This is an observed manifest-format/path mismatch, not verification that the file contents match the expected MD5. stderr contained only the SSH post-quantum warning. Complete stdout/stderr/exit record is outside the repository at `/tmp/pma_pr7_ref_manifest_read_4212f78.dYuB9u/` (stdout SHA-256 `2bdaf495ffa6a903782b256163c1a1bf465476fed428a151ac8394d6fdf60195`; stderr SHA-256 `048e2ba89ae430962e02f5341cf60c694fb7e131cb417790075a56b32ca09992`). The one-time scope is consumed. It did not read the root manifest, hash any reference or source input, inspect resources, or run analysis.

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

Corrected read-only Argos preflight proposal — not yet approved; requires fresh exact-head review and one execution approval. It reads `RAW/MD5SUMS` for the two raw inputs and `RAW/reference/MD5SUMS` for chromosome sizes, mapping each basename only to its fixed allowlisted path before hashing.

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
import hashlib, os, re, sys, stat
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
    if os.path.commonpath((str(root), str(resolved))) != str(root) or resolved != current:
        raise SystemExit(f"path escapes or resolves unexpectedly: {current}")
    return current

def parse_manifest(relpath, required_names):
    manifest = guarded_path(logical_root / relpath)
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    fd = os.open(manifest, flags)
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_size > (1 << 20):
            raise SystemExit(f"unsafe, missing, or oversized manifest: {relpath}")
        chunks, total = [], 0
        while total <= (1 << 20):
            block = os.read(fd, min(65536, (1 << 20) + 1 - total))
            if not block:
                break
            chunks.append(block)
            total += len(block)
        if total > (1 << 20):
            raise SystemExit(f"manifest grew beyond 1 MiB: {relpath}")
        raw = b"".join(chunks)
    finally:
        os.close(fd)
    try:
        rows = raw.decode("ascii").splitlines()
    except UnicodeError as exc:
        raise SystemExit(f"non-ASCII checksum manifest {relpath}: {exc}")
    seen, found = set(), {}
    for line_no, line in enumerate(rows, 1):
        if not line:
            continue
        match = re.fullmatch(r"([0-9A-Fa-f]{32}) [ *](.+)", line)
        if not match:
            raise SystemExit(f"invalid checksum row {relpath}:{line_no}")
        digest, raw_name = match.groups()
        name_path = PurePosixPath(raw_name)
        if name_path.is_absolute() or ".." in name_path.parts or "\\" in raw_name:
            raise SystemExit(f"unsafe manifest path {relpath}:{line_no}")
        name = name_path.as_posix()
        if name in seen:
            raise SystemExit(f"duplicate manifest path {relpath}:{name}")
        seen.add(name)
        if name in required_names:
            found[name] = digest.lower()
    missing = set(required_names) - set(found)
    if missing:
        raise SystemExit(f"required entries missing in {relpath}: {sorted(missing)}")
    return found

# The two manifests use paths relative to their own directories.
expected = {}
expected.update(parse_manifest("MD5SUMS", {"allPeaks_light.hg38.05.bed.gz", "experimentList.tab"}))
for name, digest in parse_manifest("reference/MD5SUMS", {"hg38.chrom.sizes"}).items():
    expected[f"reference/{name}"] = digest
source_paths = {
    "allPeaks_light.hg38.05.bed.gz": logical_root / "allPeaks_light.hg38.05.bed.gz",
    "experimentList.tab": logical_root / "experimentList.tab",
    "reference/hg38.chrom.sizes": logical_root / "reference/hg38.chrom.sizes",
}
if set(expected) != set(source_paths):
    raise SystemExit("checksum manifest mapping is incomplete or ambiguous")
for name in sorted(source_paths):
    path = guarded_path(source_paths[name])
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
