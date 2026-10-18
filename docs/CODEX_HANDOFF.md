# PMA — handoff to Codex (2026-10-17, written by Claude Code)

## Live status update — 2026-10-18 15:01 EDT — Conda child environment patch awaiting review

Persistent PMA GPT independently confirmed the G2 failure as builder-only `PYTHONPATH` leaking into the audited Conda CLI, before any solver work. It recommended a same-PR `run_conda()` that clears only `PYTHONPATH`, `PMA_HINT_EXTERNAL_TOOLCHAIN_PYTHON_ROOT`, and `PMA_HINT_ALLOWED_WORKSPACE` for Conda children while preserving package cache, executable identity, builder/pip provenance and command logging. Local uncommitted patch replaces all five direct Conda call sites and adds focused contract coverage for online/offline dry-runs, version/list/index/create commands and unchanged parent environment. Existing real pip-wheel backend test remains. `git diff --check` passes; no Mac mini tests/build/analysis or new Argos run. Next: explicit commit/push to OPEN PR #5, exact-full-HEAD GPT review, then only approved Argos contract tests and, on all pass, a fresh artifact-only G2. Both PI scientific outcomes remain pending; do not merge PR #5.

## Live status update — 2026-10-18 14:57 EDT — G2 stopped at Conda CLI import

PR #5 remains OPEN at exact HEAD `0aaf8a00c52000490782d95bf1efe5508f4d1a1a`; the prior 41/41 Argos contract suite and real pip-wheel backend passed. The approved config-only G2 retry used an independent external WORK `/home/zz950/PMA_fetch/pma_pr5_g2_0aaf8a0_env_retry` and preserved both upstream before repodata files. It stopped at the first Conda `create --dry-run --json`: `ModuleNotFoundError: No module named 'conda'` in the Conda launcher. Builder `PYTHONPATH` appears to have leaked into the Conda child. Raw evidence: `evidence/builder/commands.log`, `evidence/argos-builder.stdout.log`, `evidence/builder/build-failure.txt`, and `.runner.log` beside WORK. `pmafp-integrity.json` says `PMAFP_INTEGRITY_OK`; Conda explicit and pip freeze match before/after byte-for-byte. No bundle, ABI audit, offline preflight, environment change, HINT CLI, smoke, or benchmark. Persistent PMA GPT has been asked for the minimum technical correction; no new Argos run until a corrected same-PR full HEAD receives explicit approval. Both PI outcomes remain incomplete: unique human ChIP-Atlas BED6 and four-caller motif-free accuracy/speed plus motif integration.

## Live status update — 2026-10-18 14:25 EDT — PR #5 G2 retry running

PI 的验收仍是 (1) human ChIP-Atlas 坐标唯一、可追溯多实验的 BED6 reference 及 QC，(2) Argos 上四个无 motif footprint 工具的准确度和全基因组速度比较，经 B1–B4 选工具后整合冻结 motif reference。两项科学产物均未完成；当前 G2 只是 HINT 运行环境的前置 artifact。

PR #5 OPEN，当前精确 HEAD `0aaf8a00c52000490782d95bf1efe5508f4d1a1a`。持久 PMA GPT 已批准此完整 HEAD 的 Argos 合同测试，继而在全部通过时执行限定的 artifact-only G2/offline preflight。新 Argos checkout `/home/zz950/PMA_fetch/pma_pr5_code_0aaf8a0` 中，41/41 合同测试通过（含真实 pip-wheel backend），Python 编译与 wrapper shell 语法检查通过；日志在 `/home/zz950/PMA_fetch/pma_pr5_g2_tests_0aaf8a0/contract-tests-discovery.log`。运行前后 `pmafp` Conda explicit 相同；清理继承测试环境变量后，pip freeze 也与运行前清单逐字节相同。

首次 G2 调用在读取 `config/pma_env.sh` 时因 Argos 缺少 `/home/zz950/setup_env.sh` 立即退出，未进入 bundle/solver，失败日志保留于 `/home/zz950/PMA_fetch/pma_pr5_g2_0aaf8a0.runner.log`。GPT 明确 `APPROVE — CONFIG-ONLY G2 RETRY, SAME EXACT HEAD`：以 `BIO_DATA=/home/zz950/DATA`、`BIO_SOFTWARES=/home/zz950/softwares` 跳过缺失的 setup 脚本，用新的外部 WORK 和同一 HTTPS Conda channel 重试，不改代码或环境。按此范围已启动 `/home/zz950/PMA_fetch/pma_pr5_g2_0aaf8a0_env_retry`，PID 文件与 runner log 同前缀，Argos 进程仍在运行。尚未确认 G2 成功；以最终 bundle manifest、ABI/离线预检及 `pmafp` 完整性证据为准。不得在本运行期间提交新 HEAD 并把旧批准当作新批准；不安装环境、不运行 HINT CLI/footprint 分析、不合并 PR #5。

## Live status update — 2026-10-18 12:00 EDT — PR #5 repair awaiting review

PI 的两个验收目标：human hg38 ChIP-Atlas 全部 ChIP-seq 的坐标唯一 BED6（多 experiment 可追溯），以及 Argos 上四个 motif-free footprint 工具的准确度/全基因组速度比较和后续 motif 整合。15 分钟 heartbeat 已恢复 ACTIVE，持续跟踪两项直到 QC/审计真实完成。既有原始 ChIP-Atlas archive 可复用；现有 443,029,514 行 BED6+18 不是目标 BED6。

PR #5 仍 OPEN，当前已推送 HEAD `46f973278e5801b25b85e7b1a1d6b98c4c1c9ae1` 获持久 PMA GPT **audit-only APPROVE**，并未放行失败的 Argos 合同测试重跑。针对 40 项中 3 个失败，同一 PR 工作区已有尚未提交的定向修复：明确使用 pmafp Python 3.11；从 import path 排除 Conda host site-packages，同时使用 setuptools 80.9.0 已 hash 锁定 wheel 中自带的 vendored jaraco；修复 canonical PYTHONPATH fixture，增加 host/路径顺序负例。官方 wheel 静态检查显示 setuptools 会将 `_vendor` 追加到 `sys.path` 尾部，解释了 host jaraco 被先选中的风险。`git diff --check` 通过；按 PI 要求未在 Mac mini 跑测试/构建/分析，未向 Argos 发新命令。

下一步仅为静态复核、同步 Worklog/dated handoff、显式暂存并提交推送同一 PR，随后请求 **新完整 HEAD** 的 GPT APPROVE。获批后先在 Argos 独立 external workspace 跑全部合同测试和真实 pip-wheel 子进程，全部通过才可执行已批准范围内的 artifact-only G2/offline preflight。HINT 环境安装、CLI、smoke/full benchmark 要按后续阶段门逐项进入；不改 pmafp/partial pma_hint，不合并 PR #5。失败日志仍在 `/home/zz950/PMA_fetch/pma_pr5_g2_tests_6ec6fc2/contract-tests-discovery.log`。

## Live status update — 2026-10-18 11:48 EDT — PI north star and current blockers

The PI's two outcome targets now govern every task review and PR review:

1. Reuse/download ChIP-Atlas human ChIP-seq data to produce one standard BED6 reference with unique genomic regions and support for multiple experiments per region.
2. Compare all motif-free footprint callers for unbiased genome-wide detection, accuracy and runtime; then integrate the selected calls with the frozen motif reference.

Every review must name which target it advances, the concrete artifact or measurement it produces, and the next acceptance criterion. A maintenance or environment task counts only when it removes a named blocker on that path; report explicitly when it produces no scientific result.

**Ten-round progress contract:** Each review identifies its round and expected measurable output: (1) approve the revised BED6 semantics from existing source metadata; (2) reviewed builder and fixtures; (3) Argos BED6 build plus uniqueness/source-count QC; (4) isolated HINT runtime ready; (5) four callers pass the same-input smoke gate; (6) first-round calls and wall/RSS/event metrics; (7) matched-recall accuracy and speed evaluation; (8) B2/B3 validation; (9) genome-wide run and tool selection; (10) join selected footprints to frozen PMA motifs and report. If a gate fails, the round's output is the named diagnosis and reviewed corrective patch, not a claim of completion.

**Step 4a reality check:** Argos already holds the 21 GB raw `allPeaks_light.hg38.05.bed.gz` archive plus `experimentList.tab` and `fileList.tab`; no redownload is needed for the next BED6 build. The existing processed reference is 443,029,514 rows, 24 columns (BED6+18), filtered to 38,795 experiments from selected antigen classes. It is not the requested all-human, coordinate-unique BED6 reference. The source `fileList.tab` contains genome and antigen-class fields that can support a corrected human ChIP-seq selection; exact grouping/score semantics still need to be recorded in a reviewed design before processing.

**Step 4b reality check:** Required fragments and regions are staged under Argos and no caller process is running. Existing tools include TOBIAS 0.17.5, RGT 1.0.2 and the r4p3 PRINT/TraceBIND R stack. HINT cannot run in shared `pmafp`: RGT imports the removed `numpy.mat` under NumPy 2.4.6, while TOBIAS requires NumPy >=2, so HINT needs an isolated compatible runtime. The current PR #5 builder is only that HINT prerequisite; it has produced no benchmark result.

**Current gate:** PR #5 HEAD `6ec6fc230aec422c1124aeb42ee71c308d23de81` had exact-head GPT `APPROVE`, but its Argos contract suite ran 40 tests and failed 3. Failures: an import-origin fixture path-order mismatch; the real pip-wheel subprocess correctly failed closed on a `jaraco` module loaded from host `pmafp/site-packages`; and a wrapper test selected system Python 3.5.2 because the test invocation did not put `pmafp/bin` first in `PATH`. The complete log is `/home/zz950/PMA_fetch/pma_pr5_g2_tests_6ec6fc2/contract-tests-discovery.log`. `py_compile` and `bash -n` passed; `pmafp` Conda/pip manifests are identical before/after. No artifact build, environment change, HINT call, smoke, or benchmark ran. Do not retry these tests or advance to caller analysis until a minimal same-PR correction receives exact-head approval.

The next reviews must connect any approved HINT-runtime repair to the four-caller benchmark and avoid expanding the builder beyond what is needed to reach caller smoke. In parallel, the next ChIP-Atlas design must convert the existing raw archive/metadata into the requested unique BED6 without downloading the same archive again. Both targets remain scientifically incomplete. `HUMAN DECISION: PENDING`.

## Live status update — 2026-10-18 10:55 EDT

PR #5 is OPEN and unmerged at reviewed HEAD `ede0f811e14c3d1e133b120c6afafaf433f91cd6`; GPT approved this exact HEAD for G2 artifact-only bundle construction and the existing offline preflight. Argos SSH works, and its available Conda/Python and data paths were verified. A separate checkout at the approved SHA was created under `/home/zz950/PMA_fetch/pma_pr5_code_ede0f81`; the existing `/home/zz950/PMA_code_4b` checkout was not changed.

The G2 wrapper was invoked after selecting `pmafp` Python 3.11.17, because the host default `python3` is 3.5.2 and cannot parse the reviewed scripts. Six hash-locked tool wheels downloaded and were unpacked in `/home/zz950/PMA_fetch/pma_pr5_g2_ede0f81/`; preparation then stopped at `ARGOS_TOOLCHAIN_WHEEL_METADATA_INVALID` for `setuptools-80.9.0`. Inspection proved the official wheel has one canonical root `.dist-info` plus multiple legitimate nested vendored `.dist-info` directories. The validator incorrectly counts nested metadata as duplicates. No Conda solver, bundle, offline preflight, environment install, HINT command, or analysis ran. Wrapper integrity evidence reports `PMAFP_INTEGRITY_OK`; before/after Conda and pip manifests match byte-for-byte. The partial `pma_hint` was not targeted.

Read-only Conda inventory found registered `pmafp` and `argos-codex` prefixes. `/home/zz950/softwares/miniforge3/envs/pma_hint` is a partial directory created on 2026-10-18 at 04:07, absent from `conda env list`, and has no `conda-meta/history`; it is not a complete registered environment. All three prefixes were preserved. The failed G2 workspace and evidence remain under `/home/zz950/PMA_fetch/pma_pr5_g2_ede0f81/`.

The same PR now has a local minimal fix: require exactly the filename-derived root `.dist-info`, exactly one root `METADATA`/`WHEEL`, and continue scanning every wheel member for unsafe paths and native payloads. GPT independently confirmed the false rejection and recommended rejecting duplicate or extra root metadata while allowing nested vendor metadata; it considers the proposed fix acceptable but does not approve G2 retry before exact-HEAD code review. Added fixtures cover legitimate nested vendored metadata, an extra/mismatched root `.dist-info`, missing canonical `METADATA` despite vendored metadata, and duplicate root `METADATA`. The 32 contract tests, Python compilation, wrapper `bash -n`, and `git diff --check` pass; the updated code is not yet committed/reviewed. The actual Argos setuptools wheel (SHA-256 `062d34222ad13e0cc312a4c02d73f059e86a4acbfbdea8f8f76b28c99f306922`) also passes the corrected validator locally. G2 remains stopped pending same-PR exact-HEAD GPT review. No environment creation/install, HINT CLI, small-BED/smoke/full analysis, or PR #5 merge is authorized.

## Live status update — 2026-10-18 10:43 EDT

PR #4 was merged at `2026-10-18T13:13:02Z` as merge commit `6c2e323fc80cc3e05f9de05282d1bbce49ba98fa` into `step4b-atac-footprinting`. PR #5 is OPEN on `task_20261018_argos_artifact_builder`, base `6c2e323fc80cc3e05f9de05282d1bbce49ba98fa`, at pushed HEAD `222a82690ee8e41beab407c6e18c0a41de2b0071`. GPT reviewed that exact HEAD: F1–F8 passed; the verdict is `REQUEST_CHANGES` solely for F9, because this handoff/worklog live status still described already-pushed fixes as uncommitted. The F9 audit-only synchronization is the next change. No PR #5 Argos artifact build or analysis has run.

Argos is available. Read-only SSH confirmed the host `rcGPUs.dfci.harvard.edu` has 72 CPUs and about 1 TiB RAM. The Docker CLI exists, but the account cannot access `/var/run/docker.sock`; `/usr/games/singularity` is a Debian game launcher rather than a container runtime. The `pmafp` prefix remains unmodified by PR #5; preserve the partial `pma_hint`. These findings block the old Docker-image route, not access to Argos compute.

The PR #5 adapter prepares bundle artifacts externally and supports the existing offline preflight contract. It must receive GPT `APPROVE` on the exact full HEAD before any Argos download or bundle construction. Current stage scope excludes environment installation, HINT CLI, smoke, and full analysis; those need later gates. Do not merge PR #5 without a separate user instruction.

Validation for the current local fixes: `python3 -m unittest tests/test_hint_bundle_build_contract.py` passes 27 tests; Python compilation, wrapper `bash -n`, and `git diff --check` pass. The wrapper now confines pip cache and temporary files under external work, and builder logs are streamed through URL sanitization even on child failure. Real Conda repodata/solver behavior, external wheel/ELF audit, bundle generation, and Argos preflight remain unverified.

**Read this first, then `docs/PROJECT_CHARTER.md`, the workspace `AGENTS.md` and `HANDOFF.md`, and the step design
doc for whatever you touch.** Everything below was true at handoff time; verify live state before acting.

## 1. What this repository is

PMA (Protein–Motif-Association) builds a statistically calibrated reference of human protein–motif genomic
associations. For each chromatin-associated protein with occupancy data, it asks which DNA motifs are associated with
the protein's occupied regions:
- against a matched genomic background (*genomic association*);
- relative to other proteins in the same biosample (*protein-specific association*).

Evidence is graded, HOT regions are controlled for, and associations must replicate in independent datasets. PMA is an
**association reference, not a recruitment-mechanism study**.

Frozen scope: `design/PMA_pseudo_figures_v0.2.md`.
- **Figure 1:** resource construction (motif repertoire, occupancy data, association matrix).
- **Figure 2:** statistical calibration and reproducibility.

The work has three pillars:
1. **Motif reference.** Steps 1–3b, **closed**.
2. **Protein occupancy atlas.** ChIP-Atlas, Step 4a: **built**; closure check pending.
3. **Protein-agnostic ATAC footprint atlas.** Step 4b: **in progress**.

After these, the protein–motif association framework comes next.

## 2. Hard rules (non-negotiable; from the PI, the charter and the workspace)

**Data**
- **No data in this repo.** Data lives under `DATA/2.PROJECTS/PMA/<dataset>/{raw,processed,result}`. The repo holds
  code, manifests, docs and small summary tables only.
- **Raw is append-only.** Adding new files is fine; never edit or delete raw files in place.
- **Do not modify `Zhixins-KB`** (the Obsidian vault symlink).
- **No hard-coded mount paths in reusable scripts.** Use `config/pma_env.sh`. Launcher scripts that run on Argos may
  use explicit paths.

**Workflow**
- **Step lifecycle:**
  1. Write the design doc before any compute.
  2. Use one branch per step.
  3. Make small, real commits.
  4. Get a ChatGPT review in the **one** persistent conversation (see below).
  5. Independently verify every reviewer finding before acting on it.
  6. **Never merge a PR without explicit, separate user confirmation per PR.**
- **Reviewer conversation:** ChatGPT project "RA-Xiaolu", conversation "PMA项目"
  (https://chatgpt.com/g/g-p-6a70c0b8e77c81919ffc6390e12eacb0-ra-xiaolu/c/6acfe12c-a128-83ea-8465-9bf5feca5a0b).
  Reuse it; never open a new one.
- **Review gate:** at each completed scientific milestone, run the `review-task` skill in Quick mode. The AI never
  approves L3; end with `HUMAN DECISION: PENDING`.
- **Progress reporting:** give the overall percentage plus the delta and update HANDOFF. Current: **33 %**; the motif
  reference workstream is closed.
- **Commit attribution:** commits end with a co-author trailer for the agent you are; PR bodies end with the generator
  line used so far.

**Compute**
- **Compute location:** heavy compute runs on **Argos** (multi-core), never on the user's Mac mini.
- **Memory cap:** keep every Argos task under **about 50 GB RAM**. Estimate memory before launching.
- **O2 (HMS) DUO limit:** at most 2 DUO prompts per hour.
  - Always run `ssh -O check o2` first.
  - If no master connection is running, stop and tell the user; never open a new connection.
  - O2 is currently unused; all work is on Argos.

**Reporting**
- Report faithfully: failed QC is reported as failed, and thresholds are never relaxed after the fact.
- The user writes in Chinese; reply in Chinese.
- Result write-ups go in `Figures/FigureN/FigureN.<key>.result.md` (Chinese, non-submission "result" style: why, what,
  results, evidence, conclusion, short discussion).

## 3. Argos practicalities (learned the hard way)

**Access**
- Command: `ssh -o BatchMode=yes zz950@rcapps3.dfci.harvard.edu` (key auth, non-interactive).
- Hardware: 72 cores and 1 TB RAM, but the **50 GB cap still applies**.
- GPUs are Tesla K80, which current PyTorch does not support. **Treat Argos as CPU-only.** The PI ruled out GPU tools.

**Running jobs**
- **SLURM is misconfigured** (`sinfo` fails). Run work as `nohup` background processes on rcapps3. Parallelise by
  launching several processes ("brute-force parallel" is approved by the PI).
- **Never put `pgrep -f`/`pkill -f` patterns inside `ssh '…'` one-liners.** The pattern matches the remote shell's
  own command line and kills your session. Put kill/launch logic in a script file, `scp` it over, then run it.
- A local `timeout` kills only the local ssh, not the remote command; check `ps -u $USER` afterwards.
- `timeout` around `Rscript` does not kill the R child process; kill the `exec/R` process.

**Environments**
- **Conda:** `conda.anaconda.org` times out from Argos.
  - `~/.condarc` points to the ustc/tuna mirrors; don't use `--override-channels` with anaconda.org URLs.
  - For bioconda, use `-c https://mirrors.tuna.tsinghua.edu.cn/anaconda/cloud/{conda-forge,bioconda}`.
- **Env location:** new envs are created in `~/softwares/miniforge3/envs/`, which is listed first in `envs_dirs`.
- **glibc 2.23:** many recent pip wheels (pysam, numpy ≥ 2.3 …) cannot be installed. Prefer conda packages; use
  pip only for what conda lacks (`--prefer-binary`).
- **Envs in use:**
  - `r4p3` (miniconda3): R 4.x + Python 3.8. Seurat needs `R_LIBS_USER=/home/zz950/softwares/R_lib_4`.
  - `pmafp` (miniforge3): Python 3.11 with TOBIAS 0.17.5, RGT/HINT-ATAC 1.0.2, MACS3 3.0.4, pysam 0.24,
    tensorflow-cpu/keras 3.15, samtools, bedtools.
    - RGT downgraded hmmlearn to 0.2.2, which conflicts with MACS3; this is irrelevant unless you call MACS3.
- **R library for TraceBIND/PRINT:** `R_LIBS=/home/zz950/softwares/R_lib_tracebind:/home/zz950/softwares/R_lib_4`
  (tracebind, ACAT, survcomp, hdf5r, BSgenome.Hsapiens.UCSC.hg38, …).
- **`set -u` and r4p3:** under `set -u`, `conda activate r4p3` dies on an unbound `GDAL_DATA` variable. Don't use
  `set -u` around activation.

**Code checkouts**
- `/home/zz950/PMA_code_v03` is on branch `step4a-chipatlas-occupancy` and was used by the 4a build.
- `/home/zz950/PMA_code_4b` is on `step4b-atac-footprinting` and is used by the running 4b driver.
- Pull before running. Never switch the branch of a checkout that a running job uses.
- The Argos `git` is old (no `git branch --show-current`).

**Scratch scripts:** launch scripts and logs live in `/home/zz950/PMA_fetch/`.

## 4. Branches (none of the open ones is merged; each merge needs user confirmation)

The branches form a chain. **`step4b-atac-footprinting` contains everything**: main, 2c, 3, 3b and 4a. Continue from
it, or branch from it for a new step.

| Branch | Content | State |
|---|---|---|
| main | Steps 1, 2, 2b (PRs #1–#3 merged) | — |
| step2c-denovo-sources | de novo source fetchers | open |
| step3-motif-clustering | v0.2.1 legacy clustering (benchmark record only) | open |
| step3b-v03-integration | v0.3 integration, dedup, tiers, Figure 1C result doc | **closed scientifically** (ChatGPT CLOSED WITH QC FLAGS), not merged |
| step4a-chipatlas-occupancy | ChIP-Atlas annotated occupancy BED | built, not merged |
| step4b-atac-footprinting | footprint benchmark | in progress |

## 5. What has been done

**Step 1–2 (merged).** Codebook-first pilot, multi-source raw layer v0.2/v0.2.1 (30,781 records), calibration
benchmark. See `docs/STEP1_*`, `docs/STEP2_*`.

**Step 2c + 3b — motif reference v0.3 (CLOSED WITH QC FLAGS; frozen, do not extend or optimise).**
- **Raw layer:** 472,964 records. ENCODE BPNet/ChromBPNet/ProCapNet, Cistrome DB2 and HDMA were added to the curated
  sources. 211,457 records passed QC into the clustering pool.
- **Similarity and dedup:**
  - Similarity score s = alignment Pearson × overlap; coverage threshold τ = 0.825 (strict 0.95).
  - Dedup at s ≥ 0.99: 211,431 nodes → **101,228 unique motifs** (`PMU_*`). All source records are kept.
- **Tiers (§19):**
  - Core set: 24,194 unique motifs with evidence tier ≤ 2 or ≥ 2 independent experiments.
  - Coverage-greedy hubs give LOW / MEDIUM / HIGH = **500 / 1,000 / 2,000 PWMs**, plus a 64-PWM composite
    supplement.
- **QC:**

  | Metric | LOW / MEDIUM / HIGH |
  |---|---|
  | Core coverage at τ | 0.664 / 0.791 / 0.897 (HIGH fails the 0.90 bar) |
  | N-challenge | 0.020 / 0.018 / 0.008 (pass) |
  | Pairwise hub redundancy | 0.19–0.25 (fail; marginal analysis shows almost no removable hubs) |
  | Held-out coverage, subsamples | 0.39 / 0.52 / 0.64 |

  Earlier attempts (§14–§18.1: k-mer Seurat, PCA candidates, all-node graph, Louvain tiers) failed QC and are kept
  on record.
- **Deliverables** on Argos `DATA/2.PROJECTS/PMA/motif_reference/result/step3b_v03/align_tiers_greedy/`:
  - `reference_{LOW,MEDIUM,HIGH}/PMA_representatives.meme`;
  - cluster summaries, motif → cluster tables and unrepresented-motif tables;
  - `MANIFEST.json` (sha256 + integrity block).
- **Docs:** design `docs/STEP3B_V03_INTEGRATION_DESIGN.md` (§12–§19). Result write-up
  `Figures/Figure1/Figure1.motif_reference.result.md` (v0.3).

**Step 4a — ChIP-Atlas hg38 protein occupancy atlas (built 2026-10-17 23:14; ChatGPT closure check not yet done).**
- **Contract:** `docs/STEP4A_CHIPATLAS_OCCUPANCY_DESIGN.md`, approved with revisions.
  - Scope: antigen classes `TFs and others` + `RNA polymerase`, MACS2 q < 1e-5; 39,099 experiments.
  - Output A: BED6+18 (bgzip + tabix), with antigen → HGNC mapping, context and antibody fields, and QC flags.
  - Output B: a full experiment table.
  - Flags only; nothing is filtered. The ENCODE blacklist flag is per peak.
- **Code:** `scripts/04a_chipatlas/`.
  - `chipatlas_rules.py`: rules 4a.v1.
  - `01_experiments.py`, `02_peaks.py` (streaming), `03_finalize.py`.
  - `run_4a.sh`, `00_pilot.sh`.
  - `config/chipatlas_antigen_exceptions.tsv`.
- **Result:** `DATA/2.PROJECTS/PMA/occupancy_chipatlas/processed/v1/` holds `PMA_chipatlas_hg38_occupancy.bed.gz`
  (16.5 GB, `.tbi`), the experiment table, `.as`, `schema.json`, `reconciliation_report.json` and `MANIFEST.json`.
  - 443,029,514 rows from 38,795 experiments; 0 rejected rows, 0 sort violations.
  - All 2,289,107,185 archive rows are accounted for. 18 experiments missing from the metadata are quarantined;
    304 metadata experiments have no peaks; 9 have a peak-count mismatch.
  - 6.3 % of rows have blacklist_majority_overlap.
- **Important pilot finding:** filtering the q < 1e-5 file at score ≥ 100 / ≥ 200 is **not** equivalent to
  ChIP-Atlas's q < 1e-10 / 1e-20 archives, which are separate peak calls (§7.1).
- **Raw:** `occupancy_chipatlas/raw/2026-10-17/`, with README.source.md, MD5SUMS and reference/ (HGNC, blacklist,
  chrom.sizes, Lambert TFs).

**Step 4b — motif-free ATAC footprinting (IN PROGRESS).**
- **PI direction:**
  - Starting point: Hu et al. 2025 *Nature* (PRINT).
  - Pick the most accurate **fast, CPU-parallel, motif-free** genome-wide footprint caller: footprints first, then de
    novo motifs.
  - GPU tools are excluded for now.
  - If the most accurate caller is too slow, re-implement its core in C/C++.
- **Design:** `docs/STEP4B_ATAC_FOOTPRINT_BENCHMARK_DESIGN.md` (ChatGPT: APPROVE DESIGN WITH REVISIONS).
  - Candidates: TraceBIND (primary) → PRINT (R, CPU) → HINT-ATAC → TOBIAS (score baseline).
  - Validation:
    - B1: naked-DNA false positives;
    - B2: perturbation (in vitro MYC/MAX, CEBPA; HCT116 CTCF degron);
    - B3: K562 ChIP-exo / CUT&RUN, matched negatives;
    - B4: STREME on the calls, annotated against PMA v0.3 only afterwards.
  - Selection rule: lower naked-DNA FPR at matched recall (±5 pp). If the FPR difference is < 20 %, median AUPRC
    decides (difference ≥ 0.03). Uncertainty by 1 Mb block bootstrap.
  - **Speed gate:** 100 M fragments in ≤ 4 h on 32 CPUs within ≤ 40 GiB.
  - A C++ port only after profiling, and only for the accuracy winner if it fails the gate. The port must reproduce
    the native outputs (−log10 p within 0.01, event F1 ≥ 0.99).
- **Code:** `scripts/04b_footprint/`.
  - `00_setup.sh`: unpack PRINT shared resources, index hg38, configure RGT.
  - `01_prep_inputs.py`: produces identical inputs for all callers:
    - HCT116 control and auxin fragments from the ENCODE BAMs (+4/−5 shift);
    - pooled naked-gDNA fragments;
    - HCT116 replicated peaks, summit ±500 bp, de-overlapped, plus a 2,000-region subset;
    - the 2,000 best naked-gDNA-covered tiles.
  - `run_print.R`: PRINT native R, precomputed hg38 bias, radii 10 and 20; writes the track and PRINT's own calls.
  - `run_tracebind.R`: round 1 runs in **PRINT-bias mode**, labelled as such (no mtDNA fine-tuning, no mito FDR,
    adjusted p < 0.05).
  - `run_hint.sh`: regions split into N parallel processes.
  - `run_tobias.sh`: ATACorrect + FootprintScores, then the common adapter.
  - `frags_to_bam.py`: for BAM-only callers, so every caller sees identical reads.
  - `events_from_track.py`: common non-maximum-suppression adapter.
  - `run_round1.sh`: 4 callers × {gdna, ctrl, aux}, all in parallel, each under `/usr/bin/time -v`; `SMOKE=1` runs
    20 regions per set.
  - `run_4b1.sh`: driver that waits for inputs → setup → prep → smoke → round 1.
- **Data** under `DATA/2.PROJECTS/PMA/atac_footprint/raw/2026-10-17/`:
  - `geo/`: GSE280532 human naked gDNA, GSE216403 BAC, GSE280479 in vitro.
  - `encode/`: HCT116 CTCF degron ATAC filtered BAMs ENCFF784ATG / ENCFF794FUH (untreated) and ENCFF877LRY /
    ENCFF745WLX (auxin), plus peaks ENCFF849MMH / ENCFF530VSF.
  - `print_zenodo/`: hg38Tn5Bias.tar.gz, dispModel.tar.gz, Tn5_NN_model.h5.
  - `reference/hg38.fa.gz`.
- **Working directory:** `processed/round1/`.

## 6. Current execution state (2026-10-18 14:14 EDT; verify live before any external action)

- **Two PI outcomes:** (1) human-only ChIP-Atlas ChIP-seq consolidated to coordinate-unique BED6 with multi-experiment linkage; (2) four motif-free footprint callers compared on matched inputs for unbiased genome-wide accuracy and speed, followed by motif-reference integration. Every review must state measurable progress toward these outcomes. Existing 443,029,514-row BED6+18 is **not** outcome 1.
- **Data and compute:** inputs are checksum/size verified; the 21 GB raw hg38 ChIP-Atlas archive and metadata are already on Argos. Argos has 72 CPUs and about 1 TiB RAM. Use Argos for all tests, builds and analyses, not the Mac mini. The previous HINT CLI preflight failed without starting an analysis. `pmafp` manifests remained unchanged, and partial `pma_hint` must be preserved.
- **PR #4:** merged into `step4b-atac-footprinting` at `6c2e323fc80cc3e05f9de05282d1bbce49ba98fa` after the user's explicit “合并 继续”.
- **PR #5 review:** OPEN and unmerged on `task_20261018_argos_artifact_builder`, base `6c2e323fc80cc3e05f9de05282d1bbce49ba98fa`, remote HEAD `fc8cd411fff5e30b90a04ac32d192fb8f4839983`. Persistent PMA GPT explicitly `APPROVE`d this exact HEAD for Argos contract tests only. The earlier F4/F5 import isolation, production CWD and backend provenance corrections passed static review.
- **Latest Argos evidence:** independent checkout `/home/zz950/PMA_fetch/pma_pr5_code_fc8cd41`; external test workspace `/home/zz950/PMA_fetch/pma_pr5_g2_tests_fc8cd41`. Python compilation and wrapper `bash -n` passed; 41 contract tests ran in 83.526 s: 39 pass, 2 fail. Real `pip wheel` backend origin test passed. Failures are (1) negative path fixture unpacks 3 argv values into 2 before reaching intended rejection; (2) hosthelper negative expects a later PYTHONPATH marker but correctly fails closed earlier on the loaded host module. Full log: `.../contract-tests-discovery.log` in the named test workspace. Post-run Conda launcher initially saw the test PYTHONPATH and could not import conda; read-only inventories rerun with startup variables unset matched both before snapshots byte-for-byte (`PMAFP_INTEGRITY_OK`). No G2 artifact build/offline preflight, environment change, HINT CLI/smoke or benchmark.
- **Local same-PR repair:** the path fixture now uses `sys.argv[1:3]`; hosthelper test expects the observed earlier fail-closed marker. Production code, real pip/backend test and scientific method unchanged. This patch is not yet committed/pushed/approved. No Mac test/build/analysis and no Argos command for this patch.
- **Next gate:** explicitly commit/push the two test fixes and three audit records to PR #5, update PR body, request exact-full-HEAD GPT review. Without new explicit `APPROVE`, issue no Argos command. After approval, rerun the complete contract suite in a fresh Argos external workspace with clean before/after inventory commands; only on all-pass resume bounded artifact-only G2/offline preflight in a fresh workspace. Do not create/modify Conda environments, run HINT CLI/smoke/full analysis, or merge PR #5 without separate user confirmation.

## 7. Next steps (in order)

1. **Get round 1 running.**
   - Pass the smoke test, then the 12 jobs.
   - Collect wall time, peak RSS, number of events, and events per callable Mb on naked gDNA (B1), each at the tool's
     default threshold and swept over thresholds.
   - Write `eval_round1.py`. Don't claim accuracy from round 1 alone.
2. **Speed gate.** Run the fastest plausible callers genome-wide on the full HCT116 peak set and extrapolate per 100 M
   fragments.
   - HCT116 has far fewer than 100 M fragments; report the actual numbers.
   - Drop callers over 4 h unless they meet the accuracy exception in design §5.
3. **TraceBIND full mode.** Fine-tune the bias model on mtDNA and add the mito empirical FDR.
   - This needs chrM reads: the ENCODE *unfiltered* BAMs ENCFF534JUB/ENCFF077TQF/ENCFF882WHI/ENCFF979SQQ, about 7 GB
     each.
   - Compare with PRINT-bias mode.
4. **B2.**
   - In vitro MYC/MAX and CEBPA: footprint response to concentration at the bound sites.
   - HCT116 CTCF degron: footprint loss at CTCF sites, using matched ChIP from Step 4a (ChIP-Atlas HCT116 CTCF).
5. **B3.**
   - Pick a deep K562 ATAC dataset and ChIP-exo (GSE151287) / CUT&RUN.
   - Build matched negatives (same peaks; similar accessibility, GC, mappability and summit distance).
   - Compute AUPRC with the 1 Mb block bootstrap.
6. **B4.** STREME on TF-scale calls (centre ±25 bp, matched background), then annotate against PMA v0.3.
7. **Selection.** Apply design §4. Only if the winner fails the speed gate: profile it and port its statistical kernel
   to C++ (design §6 acceptance criteria). Report to ChatGPT at each milestone.
8. **Step 4a housekeeping.**
   - Send the build results to ChatGPT for the closure check.
   - Add a dataset manifest `datasets/occupancy_chipatlas/dataset.md`.
   - Later: copy the Argos raw data back to local `DATA` (also the Step 2c de novo raw data). Never delete a working
     copy before the archive is confirmed.
9. **Figure 1C:** panels for the motif repertoire count flow and the coverage curves.
10. **Then the PMA association framework:** genomic and protein-specific motif association, HOT control and
    replication, joining Step 4a (protein-labelled occupancy) with Step 4b (protein-agnostic footprints) and the
    frozen motif reference.

## 8. Pending user decisions

- Merge `step3b-v03-integration` (with `step2c-denovo-sources`): needs explicit confirmation.
- Merge `step4a-chipatlas-occupancy`: after the closure check.
- When to copy the Argos raw data back to local DATA.
