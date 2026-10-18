# PMA — handoff to Codex (2026-10-17, written by Claude Code)

## Live status update — 2026-10-18 19:16 EDT — PR #6 design approved; implementation review still required

PI end points remain: (1) a coordinate-unique, experiment-traceable human ChIP-Atlas BED6 reference; (2) a matched-input, motif-free accuracy/runtime comparison of PRINT, TraceBIND, HINT, and TOBIAS on Argos, followed by B1–B4 validation and motif integration. Neither endpoint is complete.

The persistent GPT/technical review concluded that the existing Step 4a output (443,029,514 rows, BED6+18, TF/RNA-polymerase classes) is only a subset and cannot be labeled all human ChIP-seq. The design-only proposal is in PR #6 (https://github.com/leezx/Protein-Motif-Association/pull/6), branch `task_20261018_chipatlas_unique_bed6_design`, based on `origin/step4b-atac-footprinting`. Proposed scope: hg38, include `TFs and others`, `RNA polymerase`, and `Histone`; exclude input/accessibility/bisulfite and non-experimental/unknown tracks; preserve source q<1e-5 peaks; exact-coordinate de-dup only. BED6 uses a stable coordinate-derived region ID, capped distinct experiment support count as score, and `.` strand. Full region–experiment and source-row provenance stays in external sidecars. See the revision section at the top of `docs/STEP4A_CHIPATLAS_OCCUPANCY_DESIGN.md`.

GPT reviewed the exact complete PR #6 HEAD `3e15ab23c42a44d8139f3b4fb04038428fa3bc3c` against base `6c2e323fc80cc3e05f9de05282d1bbce49ba98fa` and returned `APPROVE — Design-only gate`, with zero blockers. It accepted the proposed hg38 class scope, exact-coordinate identity, support-count score, source-row accounting, class-membership reporting, and external provenance/QC contract. Nonblocking implementation advice is recorded in `docs/handoff/2026-10-18-chipatlas-unique-bed6-scope.zh-CN.md`: define mutually exclusive row-status precedence; report seven disjoint class-membership masks alongside global and overlapping class-specific counts; retain Step 4a v1 as a subset; and use external coordinate sort, streaming reduction, a second source-row sort, and final source-order merge for provenance. The two-sort/three-pass approach remains a proposal, not implemented or resource-validated.

Read-only Argos status at 2026-10-18 19:15 EDT: no recognizable PMA computation process and no PMA log modified in the prior hour. One old `singularity help build` process remains; it was not touched. No archive/metadata read, data transformation, test, environment change, footprint analysis, or merge occurred. PR #6 remains OPEN/unmerged at the approved SHA; this design approval does not authorize Argos activity. PR #5 remains OPEN/unmerged at `c1f9329cd395eff82d2374184c3e1f7cc674922c`; its previous G2 attempt timed out and is not authorized for retry. Before implementation or external execution, update the design with implementation decisions, make a reviewable code change, and obtain GPT review of the new complete HEAD with its precise scope. The old 1.843B `out_of_scope_class` count is not a Histone count; class-level source counts and outputs remain unverified.

Measurable progress this round: outcome 1 now has an exact-head GPT-approved design and a scalable implementation architecture; still zero dataset rows and no measured resource feasibility. Outcome 2: no benchmark progress. `HUMAN DECISION: PENDING`.

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
