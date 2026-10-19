# PMA — handoff to Codex (2026-10-17, written by Claude Code)

## Live status update — 2026-10-19 05:38 EDT — first-round full runs and BED6 retry

On Argos, ctrl/aux 2,000-region HINT, TOBIAS and PRINT calls completed with real outputs. HINT emitted 20,233/20,531 native events in ~2 min; TOBIAS 84,513/83,344 in ~15 min; PRINT r10 4,455/4,564 and r20 2,756/2,711 in ~17 min, with ~37 GB peak RSS. These are native-threshold counts, not an accuracy ranking. gDNA 20-region PRINT passed after indexed fragment slicing; full gDNA HINT, TOBIAS and PRINT are running as `BG_FULL_GDNA_HINT_V1`, `BG_FULL_GDNA_TOBIAS_V1`, `BG_PRINT_FULL_gdna_V2`. TraceBIND v7 reached real bias/count calculations but failed because `foreach` was not attached for `%dopar%`; a one-line import fix is running as ctrl/aux/gdna v8 smoke tasks. TraceBIND results are pending. A descriptive `eval_round1.py` was drafted but not yet run.

ChIP-Atlas job 58 exited 2 at an integer/string class-mask key bug after producing only partial sidecars. PR #7 fixed the bug; a small three-class fixture completed end-to-end (5 source rows, 2 unique regions). The full rebuild `BG_BED6_RETRY_A3C0C68` is active in a fresh external output directory with 44-GiB RLIMIT_AS. No BED6 release, collision QC or footprint caller selection is yet claimed. All heavy work is on Argos; no GPU, no PR merge.

## Live status update — 2026-10-19 00:49 EDT — full HINT results and Argos queue state

The only Grid Engine queue `normal.q` is in QERROR after jobs 85/86 failed; `qstat -f -explain E` identifies those jobs, and `qmod -c` was denied to this account. Unstarted jobs 89–96 were canceled. Existing jobs 58 (ChIP-Atlas unique BED6) and 81 (2,000-region gDNA BAM) remain running. Per the historical Argos background-compute procedure, further Step 4b calls run on the same Argos host through `/home/zz950/PMA_fetch/pma_bg_gate.sh`, which enforces 44-GiB soft/hard address-space limits, one-thread CPU settings and no GPU, and stores PID/log/exit records under `/home/zz950/PMA_fetch/pma_bg_pr8_20261019/`. HINT full 2,000-region ctrl/aux finished in ~2 minutes each, 20,233/20,531 events; not an accuracy ranking. TOBIAS full ctrl/aux first failed because long `TMPDIR` caused `AF_UNIX path too long`; retries use short `/home/zz950/PMA_tmp` symlink to DATA. PRINT smoke retries use DATA temp dirs after node `/tmp` filled. TraceBIND must override `~/.Renviron` through `R_ENVIRON_USER`; a probe confirmed pmafp Python, ctrl call is active. See dated handoff for exact IDs, hashes, failures, and results. Do not merge PR #8 or infer method ranking from event counts.

## Live status update — 2026-10-19 00:38 EDT — analysis jobs are running on Argos

Step 4b: HINT and TOBIAS passed real three-group, 20-region smoke calls. TOBIAS jobs 72–74 produced 845/834/816 events. PRINT and TraceBIND initially stalled in the existing `r4p3` conda activation hook (`javareconf`), so jobs 66–71 were canceled before analysis. Direct `r4p3` Rscript invocation resolved that startup block. PRINT then exposed missing `cladoRcpp`; Argos job 84 built CRAN 0.15.1 into a separate external R library, verified `rcpp_convolve`, and left `r4p3` untouched. PRINT rerun jobs 86–88 are active. TraceBIND jobs 78–80 were canceled after `reticulate` internally reactivated conda; job 85 probes `RETICULATE_PYTHON` on control and is active. Full 2,000-region BAM jobs 81–83 were submitted; ctrl and aux passed BAM/index checks, gdna remains in progress. All are Grid Engine one-slot `h_vmem=44G` CPU jobs. ChIP-Atlas unique BED6 job 58 is scanning its frozen 21.40-GB compressed source, with final result and QC pending. Run IDs, hashes, paths and failed-job evidence are in `docs/handoff/2026-10-19-hint-overlay-smoke.zh-CN.md`. The previous handoff text below is historical; do not treat its "no Argos" or "awaiting smoke" statements as current state. Do not choose a footprint caller from smoke event counts.

## Live status update — 2026-10-19 00:22 EDT — HINT wrapper smoke passes all three input groups

PR #8 code commit `22667dc2afac7dfdf320f41b5cf1213783174f0b` fixed the missing per-chunk output directory. Argos one-slot `h_vmem=44G` jobs `63` (gdna), `64` (HCT116 ctrl), `65` (HCT116 aux) all exited 0 with the same 20-region smoke inputs used by the earlier TOBIAS attempt. HINT emitted 66, 234 and 214 BED rows; maximum virtual memory was 2.333G, 2.318G and 2.332G, respectively. The ctrl BED SHA-256 matched the successful direct CLI run exactly. Full paths, SHA-256 values and accounting are in `docs/handoff/2026-10-19-hint-overlay-smoke.zh-CN.md`. This establishes HINT executability on the small matched inputs, not its accuracy or genome-wide speed. ChIP-Atlas unique BED6 job `58` remains running; release QC pending. Next run PRINT, TraceBIND and TOBIAS with the same smoke inputs and complete the first-round comparison.

## Live status update — 2026-10-19 00:19 EDT — HINT runtime restored; BED6 build continues

Argos Grid Engine job `58` is running the human hg38 ChIP-Atlas unique BED6 builder under one-slot `h_vmem=44G`; code commit `15ed3d644283e56a2223e86a82623862181173f4`, result and QC pending. For Step 4b, the existing `pmafp` RGT/HINT CLI failed with NumPy 2 (`numpy.mat` removed). An external venv overlay at `/home/zz950/PMA_fetch/pma_hint_overlay_v1` now uses pinned NumPy 1.26.4 and SciPy 1.11.4 wheels over the unchanged `pmafp` packages. Grid Engine job `60` passed RGT import and HINT CLI help; source `pmafp` pip-freeze SHA-256 remained `5d413fd24ed1f812ff05aa562e960f30a2c83fdc33ad72478d4b052216d3a207`. A direct HINT CLI call in job `62` produced 234 footprint BED rows from the existing 20-region HCT116 control smoke input, exit 0, output SHA-256 `ec51ecd31ca5d8bac90bc959d9a812a67b6bb0b5706d0f002a4e75dd195e223e`. The repository wrapper failed in job `61` because it did not create each chunk's output directory; a one-line fix is being committed on branch `task_20261019_hint_overlay_smoke`. These are smoke results only; no accuracy/speed comparison or tool selection yet. See `docs/handoff/2026-10-19-hint-overlay-smoke.zh-CN.md`.

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

## 6. Current execution state (2026-10-18 06:17 EDT; verify live before any external action)

- **Inputs and prior run:** the user confirmed all first-round inputs are downloaded and checksums/byte counts match. The last Argos activity was the reviewed HINT clone attempt at 4d099df; offline Conda cache lacked packages. The pmafp conda/pip manifests compared byte-identical. The partial /home/zz950/softwares/miniforge3/envs/pma_hint must be preserved. No real HINT CLI, small-BED, smoke callers or full round ran.
- **GPT gate:** GPT approved complete code HEAD `b76da4d9f2bb8a32126cc83b55537e1325f6e060`, stage-audit HEAD `62868bf4a42e04e5959901636e59077064211c05`, and subsequent audit-only heads through `9c3a0735b3761378236949f00a03d383269feb8e`. GPT returned `REQUEST_CHANGES` on builder HEAD `e4826ca599603016cc19a451b64d4f5734c77b3d` (F1–F4 plus behavior-test gaps). It clarified F1: a digest-pinned Docker image may contain pre-provisioned build tools, but builder runtime must only run Conda dry-run solves and must not create/update/install into any prefix; Argos remains untouched. Focused repairs were committed and pushed as `db5bb33c0df957b464efcf5b24fc7477cd4121d8`; GPT returned `REQUEST_CHANGES` on `18c12617ff2cdfd04bcd906a9fe9d9d4132904b8`; F1/F2/F4 are resolved, with one F3 blocker: native pip/RGT wheels lacked ELF/provider checks. F3 was repaired and pushed in commit `ba26845f57dcdb3a7ea6585f70a7897c03c484e7`; GPT approved builder code at exact HEAD `b43b8772b5c357a05125428e6c997b4e3d299fbf`, resolving F1–F5, and approved the audit-only sync at exact HEAD `515cd767053f6fe83760ecba39b625734a5bb19b`. No compliant Linux builder is available on the current host, so external bundle construction remains blocked. Existing stage scope permits only external bundle preparation and Argos offline preflight after a complete valid bundle; installation, CLI, small-BED, smoke, full jobs, and merge are not authorized by this current stage gate.
- **Remote branch:** PR #4 is OPEN and unmerged, branch `task_20261018_step4b_setup_fix`. Last live-verified full remote HEAD `ba26845f57dcdb3a7ea6585f70a7897c03c484e7`. The F3 repair is pushed and approved at exact full HEAD `b43b8772b5c357a05125428e6c997b4e3d299fbf`; no bundle has been built. Preserve unrelated untracked `design/protein_binding_resources.md`; stage only task files.
- **Builder host blocker:** local host is macOS arm64; Docker Desktop is installed, but its daemon did not start because its backend requested administrator authorization to configure privileged port mapping. No such authorization was accepted; there is no Docker socket and no alternative local OCI runtime was found. No bundle was built, no Argos command ran, and no environment changed. See `docs/handoff/2026-10-18-hint-bundle-preflight.zh-CN.md`.
- **Validation:** after the local GPT-requested repair, 13 Python builder contract tests (including native-wheel GLIBCXX-provider and unresolved-DT_NEEDED failure behavior), `tests/test_hint_bundle_builder_wrapper.sh`, `tests/test_hint_env_builder.sh`, `tests/test_step4b_runner_contract.sh`, shell syntax checks, AST parse, and `git diff --check` pass. The Python fixture now builds a mocked bundle through the repository validator. These are local/mock checks; real Linux Conda/pip behavior, Docker image build, native wheel/ELF audit, and Argos preflight remain UNVERIFIED. L2 package closure/runtime remains BLOCKED; human L3 acceptance is pending.
- **Repository cleanliness:** preserve unrelated untracked `design/protein_binding_resources.md`. Stage only this task's explicit files. No Argos command has run since the recorded 04:09 clone failure.

**Next:** synchronize the PR description to full HEAD `ba26845f57dcdb3a7ea6585f70a7897c03c484e7` and ask GPT to review that exact new full HEAD. Do not build a bundle or contact Argos before that approval and a compliant Linux builder. No real bundle build before that review and a compliant builder host. After both gates, within the user's earlier §6 scope:

1. Prepare and audit the Linux CPython 3.11/glibc ≤2.23 HINT bundle entirely outside this repository; record source provenance, full dependency closure, wheel/Conda hashes, and bundle digest.
2. Run the bundle `preflight` on Argos. If any package, wheel, hash, marker, closure, or target compatibility check fails, stop before target creation and return the complete audit report for GPT review. No network fallback, no mutation of `pmafp`, and preserve the existing partial `pma_hint`.
3. Only after complete preflight success, install to the fresh `pma_hint_v2` prefix. On any install/integrity/CLI failure, stop, preserve the partial new prefix and all logs, and do not write READY or launch HINT callers.
4. After install and source-manifest checks pass, verify the real HINT CLI/reference configuration and run the approved small-BED/smoke gate. Stop on any caller error or required-output failure; do not start the 12 full callers until every smoke caller passes.
5. Preserve all bundles, manifests, logs, and outputs outside the repository. Update this PR's Worklog/handoff and obtain GPT review before each dependent external stage under the repository gate. Never merge without separate user confirmation.
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

### 2026-10-19 05:42 EDT — TraceBIND resumed

`BG_TRACE_CTRL_V8` exited 0 with 31 native events on the 20-region control smoke after attaching `foreach`; aux and sliced-gDNA smoke continue. Four-worker 2,000-region ctrl/aux TraceBIND PRINT-bias tasks are active as `BG_TRACE_FULL_{ctrl,aux}_V10` under the 44-GiB soft/hard cap. V9 failed before analysis solely from external shell execute permissions; logs retained. gDNA 2,000-region HINT exited 0 with 7,810 events and SHA-256 `64c6b6c42c8b3eca2391990b9c0288a37f103bbe6d0d4cc784fa7965fddc7862`. Full gDNA TOBIAS/PRINT remain active. No accuracy winner or genome-wide speed conclusion.

### 2026-10-19 05:47 EDT — four-tool smoke gate complete

All four callers now passed the same frozen 20-region smoke inputs for gdna/ctrl/aux. TraceBIND v8 native events: 363/31/29, all exit 0; exact hashes and resource metrics in `docs/handoff/2026-10-19-hint-overlay-smoke.zh-CN.md`. This confirms execution only: no sensitivity matching, B2–B4 truth, accuracy ranking or speed-gate pass. Full 2,000-region TraceBIND ctrl/aux/gdna tasks are running under 44-GiB RLIMIT_AS with four CPU workers. Continue monitoring full calls and evaluating B1 descriptively; do not select a caller yet.

### 2026-10-19 05:49 EDT — gDNA PRINT full output

`BG_PRINT_FULL_gdna_V2` completed: PRINT r10/r20 native events 2,943/1,376 on the 2,000 gDNA tiles; wall 17:12.08, max RSS 30,121,176 KB, plus ~76 s indexed fragment slicing. Hashes and paths in dated handoff. B1 matched-sensitivity FPR remains pending, as do full gDNA TOBIAS and all full TraceBIND outputs.

### 2026-10-19 05:50 EDT — whole-sample speed-gate BAM preparation

`BG_BAM_MERGE_{ctrl,aux}_V1` are active on Argos, merging the four validated ENCODE filtered BAMs into indexed whole-sample ctrl/aux BAMs outside the repository. Inputs pass `samtools quickcheck` and have coordinate-sort headers. Each merge is capped at 44 GiB, one worker, CPU only; prep time is separate from caller timing. Do not claim a genome-wide speed pass until merged BAMs and whole-region caller runs complete.

### 2026-10-19 05:54 EDT — round-one native-density spec

External `processed/round1/benchmark_round1/spec_77d8556.json` pins all three 2,000-region BEDs and the five native event outputs per group; SHA-256 `13fc4061742d9e399795d32bd570cb3ae956a9a97cae0d96c4b0f4aa2a73e184`. Committed evaluator copied to `/home/zz950/PMA_fetch/eval_round1_77d8556.py`, SHA-256 `d5b85b1a3d9946d8da8c8e4a59dfd3e9b9ab2a3aa4e50361026c6a2abe417570`. Do not run until all pinned files exist; output is descriptive native-threshold density only.

### 2026-10-19 06:06 EDT — whole-sample HINT run active

The ctrl/aux whole-sample merge tasks both exited 0 and produced indexed, quickcheck-passing BAMs under external `processed/round1/bam/genome_wide/`: ctrl 4,960,640,917 bytes, SHA-256 `a87821a4c33544f6534d7a1d51c6a54241af0f09c98dca7e652e491dd5ed452d`; aux 4,877,771,562 bytes, SHA-256 `2259792d005017284166fad448783418dd4d97bcf16bff8c743e2df6dc47ca88`. `BG_HINT_GENOME_ctrl_32_V1` started at 06:06:37 EDT with ctrl BAM, 91,210 peak windows, 32 chunks and 44-GiB soft/hard RLIMIT_AS. Status/logs are under `/home/zz950/PMA_fetch/pma_bg_pr8_20261019/`; output prefix is external `processed/round1/runs_genomewide_pr8_77d8556/ctrl/hint_32`. Monitor exit, all chunks, output hash, wall and aggregate RSS before any speed claim. Other first-round and BED6 tasks remain active.

### 2026-10-19 06:18 EDT — TraceBIND fast sequence precompute

Installed `tracebind::get_bias()` skips per-region BSgenome sequence extraction if its work directory already has `regionSeqs.txt`. Its old V10 tasks were I/O-bound on remote 2bit data, so they were intentionally stopped; all three show exit 143 and retain logs. New `prepare_tracebind_seqs.py` reproduces 50-bp flanks from the indexed hg38 FASTA and matched the native 20-region ctrl BSgenome output byte-for-byte. Capped Argos precompute tasks for all three 2,000-region beds exited 0. Sequence SHA-256: ctrl/aux `c071c1cd80e229510ac2f96ac552548e70b3e41ec8fdeea11c6e24ab82f5e91a`, gDNA `d821f7654bab067df730112bfb1979748bd179331756aedf784370ad819bbfff`. Fresh `BG_TRACE_FULL_{ctrl,aux,gdna}_V11` tasks use these files and the unchanged native R statistical caller; runner SHA-256 `e05b46e872c1cf668c293b5e0d80ddcf22ce72b16708fcf9b95776cb29115710`. Updated external evaluation spec is `processed/round1/benchmark_round1/spec_trace_v11_77d8556.json`, SHA-256 `2f182a61960a39606b5712e97e7c68d11799e1362bfafacf5064c4a2debe08a0`. Do not run evaluation until all V11 events and gDNA TOBIAS exist and pass.

### 2026-10-19 06:22 EDT — HINT whole-sample pilot measured

Ctrl full HINT `BG_HINT_GENOME_ctrl_32_V1` exited 0 in 10:03.94 wall on 91,210 peak windows, 32/32 chunk BEDs present, 927,584 event rows, SHA-256 `ea2b730c79e82637a63bf18f0493b689d3ad40f8f6c81b011ebeaee8660225d5`. Child peak RSS 239,532 KB; sampled aggregate 32-process RSS was about 7.25 million KiB. Independent capped BAM count exited 0 with 46,158,731 primary proper-pair MAPQ>=30 fragments, so this is **not** the 100-M-fragment gate and must not be reported as a gate pass. `BG_HINT_GENOME_aux_32_V1` and `BG_COUNT_AUX_FRAGMENTS_V1` have started with the corresponding aux BAM. Preserve full output/logs outside the repo. Next: wait for aux and first-round V11/gDNA TOBIAS; run the native-density evaluator only after all required files pass, then source a genuine 100-M-fragment ATAC sample for the speed gate.

### 2026-10-19 06:24 EDT — aux depth confirmed

The capped aux fragment-count task exited 0 with 44,789,228 primary proper-pair MAPQ>=30 fragments under the same flags as ctrl. `BG_HINT_GENOME_aux_32_V1` is still active. Neither HCT116 whole-sample condition meets the 100-M-fragment speed-gate input, even though the ctrl full HINT run succeeded. Use these runs as whole-sample pilot and CTCF perturbation coverage, not as a 100-M gate pass.
