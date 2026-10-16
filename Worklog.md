# Worklog — Protein-Motif-Association

Chronological log, newest entry at the bottom. Entry shape and rules:
see `PR/_TEMPLATE/WORKLOG_TEMPLATE.md`.

## Progress tracker

| Step | Status | PR | Notes |
|---|---|---|---|
| 0. Scope freeze (v0.2) + repo init | closed | — | design/PMA_pseudo_figures_v0.2.md |
| 1. Motif reference pilot (Codebook vs JASPAR) | merged | #1 | docs/STEP1_MOTIF_PILOT_RESULTS.md |
| 2. Multi-source motif import + QC + calibration benchmark | merged (0318026, 2026-10-16) | #2 (draft) | docs/STEP2_MOTIF_IMPORT_RESULTS.md; §8 fallback (no curator), v0.1 stays operational |
| 2b. Raw layer v0.2.1 (+840 HOCOMOCO INVITRO/INVIVO) | review APPROVE (07de20e), awaiting merge | #3 | docs/STEP2_MOTIF_IMPORT_RESULTS.md §3; design §12 |
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

**Next**: merge on user confirmation; Step 3 on v0.2.1.
