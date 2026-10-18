# PMA — handoff to Codex (2026-10-17, written by Claude Code)

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

## 6. Current execution state (2026-10-18 03:59 EDT; verify live before next Argos action)

- **Inputs:** user confirmed all downloads are complete and checksums/byte counts match their ENCODE, Zenodo, UCSC, and GEO references. The prior Argos inspection also found `download.done`, `refs.done`, `reference/hg38.fa.gz.ok`, `MD5SUMS`, and `MD5SUMS.refs`.
- **Environment:** `/home/zz950/PMA_fetch/fp_env6.log` reports TraceBIND 0.17.5, Keras 3.15.1, MACS3 3.0.4, pysam 0.24.1, RGT 1.0.2, and TOBIAS 0.17.5. After the reviewed `e1f1bc2` audit gate, setuptools 80.9.0 was installed offline from the local conda cache. Python 3.11.17, setuptools 80.9.0, `pkg_resources`, and `import rgt` pass. However, `rgt-hint --help` exits 1 because RGT 1.0.2 imports `numpy.mat`, removed in the installed NumPy 2.4.6. This newly observed incompatibility is not yet fixed or reviewed.
- **Code and review:** PR #4 is open on `task_20261018_step4b_setup_fix`, based on `step4b-atac-footprinting`. Latest pushed PR HEAD is `feba417ab83881546c13b6c60ad94ed6e7a07874`; GPT returned `REQUEST_CHANGES` with F1 (pmafp source manifest checks must run on setup success and failure) and F2 (current handoff/PR description incorrectly called `9cff517` unpushed). Both fixes are in the local uncommitted worktree. Earlier GPT approvals at `d837246`, `e1f1bc2`, and `4ebea92` remain valid for their reviewed content; F1 (BAM prep/cache integrity) and F2 (runner behavior fixtures) from the prior review remain resolved. GitHub formal review registration returned HTTP 403; verdicts are recorded in the persistent RA-Xiaolu / PMA项目 conversation. No merge authorization.
- **Latest Argos attempts:** `229ad96` (03:05–03:13 EDT) setup/prep succeeded but smoke failed on missing `pkg_resources` and R activation's unset `GDAL_DATA`; no full jobs ran. On 2026-10-18 at 03:39 EDT, checkout `/home/zz950/PMA_code_4b` fast-forwarded cleanly from `229ad96` to approved `e1f1bc2`. Driver PID 25079, launched from `/home/zz950/PMA_fetch/pma_step4b1_launch_e1f1bc2.sh`, log `/home/zz950/PMA_fetch/fp_4b1_e1f1bc2_20261018.log`, exited immediately with `HINT_CLI_PREFLIGHT_FAIL`. Direct CLI reproduction: `rgt-hint --help` exit 1, `ImportError: cannot import name 'mat' from numpy`; environment has NumPy 2.4.6. This occurred before setup, prep, smoke callers, or full jobs; no raw input changed and no Step 4b process remains. The last run that reached prep retains counts: 91,210 regions; 90,992 positive-coverage regions; 2,000 B1 tiles; 215 queryable zero-coverage regions; 3 absent-chrY peaks; BAM counts gDNA 577,891, control 11,438, auxin 11,687.
- **Reviewed repairs:** `d837246` pins setuptools 80.9.0 and preflights HINT/R; propagates HINT and caller status; uses local nounset-safe R activation; separates smoke/full BAM caches and archives stale smoke artifacts; validates BAM/index integrity before cache reuse/publication; stops callers after BAM preparation failure; and adds mock behavior tests. The latest GPT approval explicitly states it does not itself grant execution authorization. The user's earlier instruction “开始做吧” plus §6 request independently authorizes the first-round run; run only the approved smoke/full-round scope, with no changed data, caller method, threshold, or benchmark scope.
- **Compatibility diagnosis and implementation candidate:** GPT confirmed NumPy 2.4.6 removed `numpy.mat`, which RGT 1.0.2 still imports; TOBIAS 0.17.5 declares NumPy >=2. GPT advises keeping `pmafp` unchanged and routing only HINT through an isolated `pma_hint` with RGT 1.0.2, setuptools 80.9.0, and NumPy 1.26.4. Pushed code commit `9cff517` implements that runtime; GPT approved its isolation/routing design but requested failure-path auditing and current-state corrections. The local fix now installs an EXIT audit handler that compares `pmafp` conda/pip manifests on success or failure, preserves the original failing exit code, reports `PMAFP_INTEGRITY_FAIL` on mismatch/unavailable snapshots, and leaves partial `pma_hint` intact. Added mock fixtures for clone failure, dependency-install failure, source-env audit, and refusal to overwrite an existing destination. Runner fixture, shell syntax checks, and `git diff --check` pass locally. No real HINT workflow or Argos `pma_hint` creation has occurred.
- **Next:** update the PR current-state audit/description to show pushed HEAD `feba417` and GPT's two findings, push the minimal fix, and obtain explicit GPT approval of the resulting full PR HEAD. Only then create `pma_hint` and verify HINT CLI/imports, `pip check`, actual small-BED HINT execution with frozen BAMs, and unchanged `pmafp` manifests before rerunning the smoke. Do not launch the 12 full jobs unless all smoke callers succeed and output checks pass. Do not merge without separate user confirmation.

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
