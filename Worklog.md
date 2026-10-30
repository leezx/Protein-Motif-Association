# Worklog — Protein-Motif-Association

Chronological log, newest entry at the bottom. Entry shape and rules:
see `PR/_TEMPLATE/WORKLOG_TEMPLATE.md`.

## Progress tracker

| Step | Status | PR | Notes |
|---|---|---|---|
| 0. Scope freeze (v0.2) + repo init | closed | — | design/PMA_pseudo_figures_v0.2.md |
| 1. Motif reference pilot (Codebook vs JASPAR) | merged | #1 | docs/STEP1_MOTIF_PILOT_RESULTS.md |
| 2. Multi-source motif import + QC + calibration benchmark | merged (0318026, 2026-10-16) | #2 (draft) | docs/STEP2_MOTIF_IMPORT_RESULTS.md; §8 fallback (no curator), v0.1 stays operational |
| 2b. Raw layer v0.2.1 (+840 HOCOMOCO INVITRO/INVIVO) | merged (a19666f, 2026-10-16) | #3 | docs/STEP2_MOTIF_IMPORT_RESULTS.md §3; design §12 |
| 3. Motif clustering + CORE/EXTENDED | not started | — | |
| 4. Motif reference QC + freeze v0.1 (gates G1–G4) | not started | — | |
| 5. Statistical Framework v0.1 design | not started | — | core association risk |

Weights against the 100 % definition in the charter: motif reference
(steps 1–4) 25 %; occupancy reference 20 %; association statistics
25 %; evidence grading + replication 15 %; Fig. 1/2 + release 15 %.

Overall: `19% → 20% (+1%)`: completeness check closed the HOCOMOCO
sub-collection gap; raw layer v0.2.1 (30,781 records, 1,771 TFs).
Engineering and calibration progress only; no association result exists
yet. Blocker for Step 3: compute location for the all-vs-all
(~30k × 30k) TOMTOM. Curator labels remain optional (v0.2 rule not
issued).

---

## 2026-10-14 — Step 0: scope freeze + repo init

**What**: Initialized the git repo and public GitHub repo. Instantiated
the charter, README, Worklog and .gitignore from `PR/_TEMPLATE`.

**Why**: v0.2 design froze PMA as a protein–motif association reference
(not a recruitment-mechanism project), with two core figures.

**Next**: PMA Statistical Framework v0.1 design.

## 2026-10-14 — Step 1: motif reference pilot (branch step1-motif-pilot, PR pending)

**What**: Imported Codebook 2026 (1,685 representative PWMs, 1,421 TFs) and
JASPAR 2026 CORE vertebrates non-redundant (1,019 motifs) into
`DATA/2.PROJECTS/PMA/motif_reference/`. Ran TOMTOM (MEME 5.5.9) to answer
the Codebook-first pilot questions from `design/motif_resources.md`.

**Why**: the plan says to check how much Codebook already covers before
integrating all five sources.

**How**: per-query BH q < 0.01 on TOMTOM p-values, with overlap ≥ 60 %
of the shorter motif. Mid-step amendment, made before any result was
read: TOMTOM's own q-values shift with query order because of its
randomised π₀ estimate.

**Real findings**:
- TF coverage is near-complete: 759 of 762 JASPAR human TFs are in Codebook.
- Motif coverage is partial: 66 % of JASPAR human motifs match a same-TF
  Codebook PWM under the primary criterion. 105 have no match even at
  q < 0.05: 69 are ≤ 10 bp (power-limited), 18 are composites and 18 are
  longer single-protein motifs.
- The fixed q-threshold is length-biased: 27 % of ≤ 8 bp motifs are
  missed versus 12 % of > 15 bp.
- Codebook Table-10 clusters have a coarse tail (one cluster of 225
  PWMs), and 13 % of TOMTOM similarity edges cross clusters. PMA will
  build its own clusters and use Codebook as a benchmark.
- 4 Codebook PWMs contain all-zero spacer rows, set to uniform.

**Review**: ChatGPT (RA-Xiaolu / PMA项目), round 1: REQUEST CHANGES, 4
merge conditions, all verified as valid:
- objective labels instead of paralog/unrelated;
- cutoff-dependent wording instead of "absent";
- universe assertions and BH tests;
- Q3 framed as an agreement check between similarity definitions.

All were fixed. The 105 split, prompted by the review, overturned my
earlier characterisation: most of the 105 are short motifs.

## 2026-10-15 — Step 2: multi-source import, QC, calibration benchmark (PR #2)

**What**: Built raw layer v0.2 (`processed/v0.2_raw_layer/`): Codebook,
JASPAR CORE + UNVALIDATED, HOCOMOCO v14, CisBP 3.10, Factorbook ChIP-seq
and Factorbook HT-SELEX (downloaded manually; TF/ligand/batch from ENA
run reports). 29,941 records, 28,938 matrices, 1,771 HGNC TFs. Ran the
§8.1 benchmark: 1,740 queries × 28,938 targets.

**Why**: Step 3 clustering needs every source in one provenance-aware
layer, and a description of how the v0.1 match rule behaves.

**Real findings**:
- v0.1 links 71 % of P-provisional (same TF, independent sources) and
  4.8 % of N-challenge pairs. Both weaknesses sit in ≤ 8 bp motifs
  (56 % and 15 %); from 9 bp up, N-challenge ≤ 6 %.
- 21 of the 24 N-challenge links are plausible shared specificities
  (E-boxes, TALE/MyoD sites, MGA T-box, SKOR–TAATTA). The N-challenge
  rate is therefore not an FPR.
- The SELEX key makes 416 HOCOMOCO–Factorbook SELEX pairs one
  experiment. CisBP/Codebook copies of Yin 2017 cannot be linked.
- No curator: §8 fallback, `statistical_match_v0.2` not issued.

**Repro**: rerun of `run_import.sh` after TOMTOM gave identical md5s;
9 tests pass. Bug fixed in `05_benchmark_analysis.py` before any output
was written (source-pair labels were built from the full table).

**Review**: ChatGPT results review round 1 (14c5215): REQUEST CHANGES, 3
merge conditions, each verified in the code and fixed in b091c88:
- F1 (P1): P-provisional excluded only *known* shared experiments.
  Per-pair `independence_status` gives 36/500 confirmed distinct (all
  Factorbook SELEX vs HOCOMOCO, 0.83); 464 unresolved. Unresolved
  same-publication pairs link more than different-publication pairs
  (0.76 vs 0.60).
- F2/F3: N-challenge and CI wording narrowed to the sampled benchmark.
- F4: query-set and row-count assertions.

Round 2 (b091c88): APPROVE. Non-blocking: F8 CIs stay descriptive; F9
Step 3 must not treat v0.1 as a calibrated equivalence classifier (check
short motifs, composites, large clusters and threshold sensitivity).

**Next**: PR #2 merged 2026-10-16 (0318026) on user confirmation;
Step 3 compute location. Unresolved pairs must not count as independent
replication in later evidence grading.

## 2026-10-16 — Step 2b: completeness check + raw layer v0.2.1 (branch step2b-hocomoco-subcollections)

**What**: Checked v0.2 against design §2. Only gap: HOCOMOCO H14INVITRO/
H14INVIVO were never imported. Added the 840 matrices not identical to an
H14CORE matrix as `processed/v0.2.1_raw_layer/` (design §12). HOCOMOCO v13
(user download) assessed and archived only: refits of v14, no new TFs.
TF coverage vs Lambert 2018: 1,536/1,639 with a motif; the 103 without are
98 Lambert "No motif" + 5 renamed genes that are covered.

**Checks**: v0.2 rebuild reproduces checksums; v0.2.1 rerun identical;
no existing record changed except duplicate flags.

**Review** (ChatGPT PMA conversation): round 1 REQUEST CHANGES. F10:
merge on identical matrix alone could merge across TFs/experiments
(verified: 0 such of 2,334; rule now also requires same TF, origin,
assay). F11: merged entries lost provenance (fix: per-entry
`PMA_hocomoco_collection_memberships.tsv`, 4,769 rows; 817 keep their own
collection quality). F12–F15 docs/tests. Round 2 (07de20e): APPROVE.
For Step 3: F16 read collection-specific quality from the membership
table; F17 experiment count is not cluster size.

**Next**: PR #3 merged 2026-10-16 (a19666f) on user confirmation; Step 3 design on v0.2.1.

## 2026-10-30 — Hotspot follow-up: protein support, context, HT29 ATAC (branch task_20261030_hotspot_followup)

**Scope**: exploratory, user-directed; hotspot expansion (P-04) is still an unapproved L3 proposal, so this
does not change the design baseline or FG-1 progress. G1 (TODO #3) put on hold by the user the same day.

**What** (scripts `04a_chipatlas/29–42`; results under `DATA/2.PROJECTS/PMA/occupancy_chipatlas/result/`):
- `hotspot_protein_support_v1` (29–30): proteins per hotspot with >= 2 independent experiments; DBP
  (Lambert 2018) counts and shares; QC PASS (300-region light-BED recount, 0 mismatches).
- `hotspot_annotation_v1` (31, 33): 500 bp bin annotation (TSS, ENCODE cCRE V4, CpG, GC); covariates
  explain R² 0.71 of log occupancy; ~9 % of top1 bins remain residual hotspots, mostly distal.
- `hotspot_context_v1` (32, 34, 35): breadth across 21 cell types, consistency, Jaccard, replicate
  noise ceiling. `hotspot_matched_v1` (36): batch-matched HepG2 vs K562 (107 target-lab sets).
- `hotspot_ht29_atac_v1` (37–42): HT29 DMSO_1 ATAC vs hotspots in both directions, genome coverage vs
  recall (2.83 Gb universe), combined figure A–K.
- Raw annotation inputs: `raw/2026-10-30_region_annotation/` (cCRE V4, UCSC CpG islands; MD5SUMS).

**Result docs**: `Figures/Figure1/Figure1.hotspot_{protein_support,context,ht29_atac}.result.md`.

**Open**: 3D genome annotation of hotspots added as TODO #10 (HD-10); core + extension reference
proposal (GPT) awaits a user decision. Not reviewed by GPT yet.

## 2026-10-30 — Context Query v0.1: HT29 SOX9–BAF × PMA (branch task_20261030_context_atlas_sox9baf)

**Scope**: exploratory application from the GPT design note `UDE/design/history/Context-conditioned
Regulatory Evidence Atlas-v1.0.md` (§8 minimal deliverable); not an approved design change; FG-1 unchanged,
G1 stays on HOLD (HD-11).

**What** (scripts `04a_chipatlas/45–49`, SGE wrapper `45_47_context_query_jobs.sh`; results
`DATA/2.PROJECTS/PMA/occupancy_chipatlas/result/context_query_ht29_sox9baf_v1/`): 249,725 HT29 consensus ATAC
regions; dTAG-SOX9 time course ATAC + SOX9/SMARCC1 CUT&RUN (DESeq2; CUT&RUN library-size normalised because the
E. coli spike-in fails QC in the D4 batch); PMA per-region × target experiment evidence; tests T0–T5 and figure A–J.

**Result**: the design's hypothesis (BAF-associated loci are preferentially SOX9-dependent) is not supported:
HT29 SMARCC1 occupancy is negatively associated with D4 ATAC loss at SOX9 sites (adjusted OR 0.39), PMA BAF
evidence is null after covariates (1.26, CI 0.87–1.83). PMA SOX-family occupancy (SOX10/8/9/13/5) ranks top among
810 targets. SMARCC1 at SOX9 sites drops with SOX9 (D4 −0.69 vs −0.21 log2 at SMARCC1-only sites).

**Result doc**: `Figures/ContextQuery/ContextQuery.sox9_baf.result.md`. **Open**: dTAG schedule to confirm;
choice of next direction (doc §7); not reviewed by GPT.

**2026-10-30 — GPT review round 1 (REQUEST_CHANGES; push approved, no merge)**: scripts 50–52. dTAG schedule not
recorded in metadata → day labels only. SMARCC1 relative drop at SOX9 vs SMARCC1-only sites is matched by IgG
background (D4 −0.20 to −0.29) → v0.1 §3.4 withdrawn; ATAC-lost vs not-lost SMARCC1 drop is replicate-consistent and
exceeds IgG (relative signal only). SOX-family ChIP (non-SOX9, external) given 6 SOX PWMs + baseline ATAC/SOX9:
OR 2.22 (1.78–2.77), CV AUROC +0.005–0.015, positive only in the high-motif tertile. BAF null result robust.
User confirmed the time design (2026-10-30): D2, D4 = SOX9 degradation; D7, D10, D13 = SOX9 recovery.
