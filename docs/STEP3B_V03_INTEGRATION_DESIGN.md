# Step 3b — v0.3 unified motif reference: de novo integration, clustering, annotation

Status: **revision 1 — FROZEN 2026-10-16**, before any v0.3 import,
clustering or metric.
- Decisions D1–D7: ChatGPT, "APPROVE WITH CONDITIONS".
- Rev 0 (89d2cce): ChatGPT REQUEST CHANGES on P1–P12 with blockers B1–B4.
  Each was verified independently and all are applied here (§11).

The whole P1–P12 contract is now fixed. QC, τ, grid, resolution and
splitting are **not** changed after seeing cluster counts.

## 1. Direction and scope

User (PI) direction, 2026-10-16: once the de novo motif downloads are
complete, finish motif annotation first. Then rerun the earlier pipeline
on all motifs together: cluster, annotate the clusters, and choose one
representative motif per cluster.

Scope of this step: raw layer v0.3, then evidence annotation v2, then a
single unified clustering. After that come cluster annotation and one
primary PWM per final cluster. The main contribution is a non-redundant,
evidence-annotated reference that spans curated/in-vitro PWMs, ChIP-derived
de novo motifs and deep-learning accessibility motifs. We do not claim
"hundreds of thousands of new recognition patterns".

The v0.2.1 Step 3 run (§9 of `STEP3_MOTIF_CLUSTERING_DESIGN.md`, all-vs-all
TOMTOM over 27,751 nodes) is kept as a **frozen legacy benchmark** (D7).
It is not optimised further and does not set the v0.3 cluster count.

## 2. Counting units (D1, kept separate everywhere)

| Unit | Definition |
|---|---|
| source entry | one record in a source file |
| motif profile | one PFM/PPM usable for scanning (CWMs are not profiles) |
| node | exact-dedup (and within-experiment near-dedup) matrix that enters clustering |
| independent experiment | distinct biological discovery dataset after cross-resource identity resolution (§4.3) |

Every count in results and figures names its unit.

## 3. Sources and inclusion (D1)

Measured 2026-10-16 (Argos `raw/*/2026-10-16`):

| Source | Entries | Enters clustering | Annotation / validation only |
|---|---|---|---|
| v0.2.1 (Codebook, JASPAR, HOCOMOCO v14, CisBP, Factorbook) | 29,778 | as in Step 3 (27,751 clusterable nodes) | — |
| ENCODE BPNet (TF ChIP) | 80,311 PFMs, 2,345 models (incl. ProCapNet) | counts head, positive patterns, unique MotifCompendium join with `flag_remove = 0` | profile head; negative; flagged; unmatched / ambiguous join; **all ProCapNet** (P12) |
| ENCODE ChromBPNet (DNase/ATAC) | ~75k est., 1,531 models (downloading) | counts head, positive patterns, unique MotifCompendium join with `flag_remove = 0` | profile head; negative; flagged; unmatched / ambiguous join |
| ENCODE MotifCompendium TF / Chromatin / unified | 19,739 / 75,813 / 3,473 CWMs | no (CWMs; derived from the same models) | QC flags, `direct_type`, composite, lineage; descriptive concordance only (shared provenance) |
| Cistrome DB 2 de novo (MDSeqPos) | 147,569 from 9,922 samples | sample QC ≥ 5 of 6 **and** `peaks` pass; motif rule §3.2 | the rest |
| HDMA per-cell-cluster patterns | 6,362 from 189 clusters | counts head; patterns that the authors kept in the 508-motif merge | patterns the authors excluded |
| HDMA merged compendium | 508 PPMs | no (derived from the 6,362) | descriptive concordance only; lineage map |

### 3.1 ENCODE BPNet / ChromBPNet QC

The authors' MotifCompendium QC is reused rather than reinvented. Each
per-model counts-head pattern is joined to `TF-` / `Chromatin-motifcompendium_metadata.tsv`
on (experiment ENCSR, head, posneg, pattern index). Its `flag_remove` (CpG,
tandem repeat, high-GC/AC, low complexity, unvalidated) excludes the
pattern from clustering; `flag_type` is kept. Patterns with no
MotifCompendium row (`qc_unavailable`) or with a one-to-many join
(`qc_join_ambiguous`) are **annotation-only**. Missing metadata is never
treated as a QC pass (P1). Matched, unmatched and ambiguous join rates are
reported.

- **Profile head (D1):** excluded from clustering by default, because the
  profile head can carry Tn5/DNase bias. It is kept for annotation and
  sensitivity analysis.
- **Negative-contribution patterns:** excluded from clustering and
  annotation-only (P1).
- **ProCapNet** (`transcription_model_derived`): annotation-only in v0.3,
  kept with TSS context (P12). A later promoter-pattern coverage audit
  decides whether it is included.

### 3.2 Cistrome QC (needs confirmation)

- **Sample:** Cistrome's own ChIP QC (`map, peaks, fastqc, frip, pbc, dhs`);
  `motif_judge` is excluded because it is circular and false for all
  samples. Of the 9,922 samples with de novo motifs:
  - pass ≥ 5 of 6: 7,301 samples, 124,278 motifs, 773 factors;
  - pass ≥ 4 of 6: 8,911 samples, 139,809 motifs, 965 factors.

  **Frozen: ≥ 5 of 6 and `peaks` must pass** (P2).
- **Motif:** MDSeqPos −log10 p (`pvalue` field, capped at 690.78) ≥ 10, and
  z-score < 0 (central enrichment; true for 100 %). These cuts barely
  discriminate, so sample QC, matrix QC and dedup do the filtering.
  - No top-k per sample and no extra z cut (P2), so weaker real
    alternative patterns are kept.
  - Then intrinsic QC and within-sample near-dedup (§4.2).
- **Non-TF factors** (POLR2A, EP300, chromatin regulators): kept, and
  annotated `assayed_protein_target` with binding_mode `indirect_candidate`.

### 3.3 HDMA

The 6,362 per-cluster patterns are counts head. A pattern enters
clustering if `merged_modisco_patterns_map.tsv` lists it as a component of
one of the 508 merged motifs; the authors excluded low-complexity, noisy
and CG-dominated patterns before that merge. The merged 508 are a
validation reference only (D1).

### 3.4 Intrinsic matrix QC (all new profiles)

- valid PFM: rows sum to 1 ± 0.01, no NaN, ≥ 1 column;
- MoDISco PFMs (BPNet, ChromBPNet, HDMA): trim only **contiguous**
  leading and trailing columns with IC < 0.25 bits; internal low-IC
  columns stay. The untrimmed matrix stays in raw permanently (P4);
- trimmed length ≥ 5 (as the v0.2.1 `short_lt5` rule); length > 30 is
  flagged and kept.

## 4. Matrix contract, dedup and experiment identity

### 4.1 Matrix contract (condition 2)

Only PFM/PPM enter the PWM pipeline. CWMs (signed contribution scores) are
metadata. Per profile we record: source matrix type, head, posneg,
trimming (columns removed), orientation, a sha1 checksum of the 6-dp
matrix, and the extraction script commit.

### 4.2 Dedup (D2)

1. **Global exact:** as Step 3: node = min(sha1 fwd, sha1 rc) of the 6-dp
   matrix. Every source entry is kept in `PMA_motif_to_cluster.tsv`.
2. **Within-experiment near-duplicate:** only between profiles from the
   **same experiment/model**. Two profiles qualify when:
   - mean column Pearson ≥ 0.98 at the best offset and orientation, and
   - the overlap covers ≥ 90 % of the **longer** profile (P5), so flank
     variants stay distinct.

   Merging uses complete linkage, which prevents chaining. The kept
   profile has the most seqlets/hits, with ID as the tiebreak.

   **Stop rule (zero errors):** before the merge is applied, it is checked
   on distinct alternative-pattern controls with independent evidence:
   - curated alternative motifs of the same TF (JASPAR/HOCOMOCO subtypes,
     CTCF alternatives);
   - composites against their components.

   P-high pairs are positives and are not used here. If any control pair
   would merge, or if there are fewer than 50 controls, near-dedup is
   switched off and only exact dedup is used. The threshold is not tuned.
3. Different experiments are never merged at the evidence level. They may
   share a node only by exact identity.

### 4.3 Experiment identity (condition 1)

Experiment IDs:
- ENCODE: ENCSR.
- Cistrome: GSM.
- v0.2.1: `experiment_ids`.
- HDMA: **not** an independent experiment per cell cluster (P6). The 189
  cell clusters are analysis groupings of shared donors and libraries:
  `cell_cluster_id` is kept and `independent_experiment_id =
  unresolved`.

Cistrome reprocesses public GEO data, ENCODE included:
- ENCODE experiments map to GEO GSM via ENCODE `dbxrefs`. A Cistrome sample
  whose GSM equals an ENCODE experiment's GSM is the **same experiment**.
- If no confirmed crosswalk exists, two accessions are
  `independence_unresolved`. They are not assumed independent and get no
  double weight in experiment counts or purity.

MotifCompendium and HDMA-508 entries are lineage records, never
experiments.

## 5. Unified clustering (D2, D3)

### 5.1 Representation

Same as Step 3 §8.1: floor 0.01, log-odds, 32,896 RC-collapsed 8-mer
affinities, centred and L2-normalised, no per-8-mer scaling. Features are
computed blockwise, never as a dense matrix of all nodes (300k × 32,896
float32 ≈ 40 GB).

### 5.2 PCA basis

- **Basis sample:** randomized PCA (**51 PCs**, so representation B at
  d = 50 can use PCs 2:51) is fit on a balanced basis
  sample of ≤ 50,000 nodes. Strata are (source family × evidence type),
  each capped at 50,000 / n_strata; under-full strata contribute all their
  nodes and the unused quota is redistributed in proportion to the
  remaining available nodes. Seed 20261016 (P7).
- **Projection:** all nodes are projected onto the basis.
- **Composite partition (B4):**
  - v0.2.1 composites, plus new de novo profiles with MotifCompendium
    `composite = True` from a unique provenance match, go to the composite
    partition.
  - De novo profiles without composite annotation get
    `composite_status = unknown` and go to the ordinary partition, but are
    never labelled verified monomers. Their count and the merge risk are
    reported.

### 5.3 Graph and communities

kNN/SNN over **all** nodes (approximate NN, Annoy) and Louvain
(algorithm 1). Projected nodes take part in the joint graph. If the full
graph does not fit in Argos memory, the engineering limit is reported and
the sketch → project → novelty-refit fallback is used, labelled as such.
UMAP is for display only.

### 5.4 Grid (frozen once approved)

- dims {20, 30, 50} × k.param {15, 20, 30} × resolution
  {0.8, 1.2, 2.0, 3.0, 4.0, 6.0, 8.0, 12.0} (72 configurations);
- representation A (PCs 1:d), plus B (PCs 2:d+1). PC1 is kept by default.
  B replaces A only under the Step 3 §9 GC decision rule, with v0.3
  metrics reported per source;
- seed 20261016.

## 6. Fidelity, splitting, gates and selection (D3, D6)

### 6.1 Fidelity similarity

A fixed, universe-independent alignment score replaces per-query TOMTOM
q-values:

- s(A, B) = max over offsets and both orientations (overlap ≥ 5) of
  clip(mean column Pearson, 0, 1) × L_overlap / max(L_A, L_B).
- This is the Step 3 §3.2 score, computed by our own aligner rather than
  at TOMTOM's offset.
- "B is covered by A" when s ≥ τ.

τ is **calibrated once on the frozen v0.2.1 legacy TOMTOM**, before any
v0.3 clustering (P8 / B2).

**Calibration set:** v0.2.1 nodes, stratified by source family × length
tertile × GC quintile, with at most 20 query nodes per TF and per
experiment; seed 20261016. For each query node it holds:
- every TOMTOM-positive pair (kept rows), plus
- its 20 nearest neighbours by s that are **not** TOMTOM matches
  (hard negatives).

TOMTOM-significant rows alone are never used.

**Rule:** candidates τ ∈ {0.650, 0.675, …, 0.950}. τ is the smallest
candidate at which:
- ≥ 95 % of calibration pairs with s ≥ τ pass `statistical_match_v0.1` in
  both directions, and
- every major source stratum (≥ 500 pairs) reaches ≥ 90 %.

If no candidate qualifies, the outcome is `tau_calibration_failed`: formal
v0.3 splitting stops and τ is not revised after clustering.

**Saved:** the pair manifest, seed, n per stratum, the full agreement
curve and a per-stratum Wilson CI.

**Scope:** this only establishes agreement with the legacy statistical-match
rule; it does not prove 95 % precision for biological equivalence.

**Sanity check only:** P-high / N-challenge do not set τ.

TOMTOM q-values are reported only against a fixed reference universe
(v0.2.1 nodes plus the final representatives) and are never mixed across
universes.

### 6.2 Representative and splitting (one primary PWM per final cluster)

1. **Representative:** within each Louvain community, the candidates are
   members within 0.05 of the best mean affinity-profile correlation
   (medoid-first). Among them, a high-evidence member is preferred: direct
   in vitro or curated, ranked by evidence → source-native quality →
   independent experiments → length/IC → ID. If no high-evidence member
   is within 0.05, the medoid is used and high-evidence members are listed
   in the annotation. All-de-novo clusters use the QC-passing medoid; lack
   of a TF label never disqualifies a representative.
2. **Coverage:** the fraction of QC-passing members with
   s(representative, member) ≥ τ.
3. **Split if coverage < 90 %, once (P9 / B3):**
   - The community is split **once** by complete linkage on 1 − s, cut at
     1 − τ. Every pair inside a subcluster then has s ≥ τ, so the
     representative chosen by steps 1–2 covers 100 % by construction.
     This is asserted as an implementation test, not used as evidence.
   - Complete linkage uses the **full** pairwise s matrix of the community.
     Pairs the ANN graph did not search are never treated as s = 0. If a
     community is too large for a full matrix, a compute limitation is
     reported; complete linkage is not silently approximated.
   - Recorded: `parent_louvain_cluster`, `split_reason`, and the
     fragmentation ratio (final clusters per split community).
4. **Extras:** `representative_extra` is allowed only in a separate
   secondary sensitivity set and never counts in the
   one-PWM-per-cluster reference.

### 6.3 Gates (selection_contract_v0.3)

| Gate | Criterion |
|---|---|
| G1 community representability | ≥ 80 % of Louvain communities reach ≥ 90 % coverage **before** splitting |
| G2 node representability (pre-split) | node-weighted: ≥ 90 % of QC-passing nodes covered by their community's primary representative **before** splitting, and ≥ 85 % in each major source family (≥ 1,000 nodes). Post-split coverage is an implementation assertion, not a gate (B3). |
| G3 redundancy | ≤ 15 % of final representatives have a representative in another cluster with s ≥ 0.85 |
| G4 N-challenge (legacy subset only) | ≤ 5 % of the 500 v0.2.1 N-challenge pairs share a final cluster; not an overall FPR |
| G5 seed stability | median ARI ≥ 0.85 over seeds 20261016–25 |
| G6 subsample stability | median ARI ≥ 0.75, 10 × 80 % subsamples stratified by source × experiment × GC quintile |
| G7 external concordance | shared-motif AMI against Codebook T10 and HOCOMOCO H14CORE-CLUSTERED (legacy concordance constraints), each within 1 bootstrap SE of the grid's best; no target cluster count. MotifCompendium unified and HDMA-508 share provenance with the inputs: their AMI is **descriptive only**, never called independent validation (B4) |

**Selection:**
- Among configurations that pass every gate, choose the one with the
  **fewest final primary representatives**.
- Ties within 2 % go to higher G2 coverage, then higher G5/G6 stability,
  then smaller resolution. Final cluster count = representatives after the
  single split.
- If none passes, report "no feasible configuration"; thresholds are not
  relaxed.
- Order of work: deterministic gates (G1–G4, G7) on the whole grid first,
  then G5/G6 for the survivors.

## 7. Evidence annotation v2 (D4) and cluster annotation (D5)

### 7.1 Motif-level evidence types

| Source | evidence_type | Claim allowed |
|---|---|---|
| measured in vitro (HT-SELEX, PBM, …) | `direct_in_vitro` | direct sequence-specific binding |
| curated (JASPAR CORE, HOCOMOCO CORE) | `curated_reference` (assay kept) | curated specificity |
| BPNet TF ChIP | `chip_model_derived` | contributes to that TF's ChIP signal |
| Cistrome MDSeqPos | `chip_denovo_derived` | enriched in that ChIP's peaks |
| ChromBPNet, HDMA | `accessibility_model_derived` | contributes to accessibility prediction |
| ProCapNet | `transcription_model_derived` | contributes to transcription-initiation prediction |

ChIP-derived motifs are never automatically "direct binding". The
MotifCompendium `direct_type` values are defined in the authors' README:

| `direct_type` | Meaning | PMA `chip_cognate_status` |
|---|---|---|
| A | confirmed in vitro | `cognate_invitro_supported` |
| B-NZ | confirmed via paralog | `paralog_invitro_supported` |
| B-Z | confirmed via B1H | `b1h_supported` |
| C | highest contribution, unconfirmed | `cognate_unconfirmed` |
| X | indirect | `indirect_association` |

`direct_type_raw` is always kept. None of these values is mapped to
"direct binding confirmed in this experiment". The Step 2 evidence tiers
stay, and the new types are added beside them.

### 7.2 Outputs

- `PMA_motif_to_cluster.tsv`: source entry → profile → node → Louvain
  community → final cluster, with QC status and exclusion reason for every
  entry.
- `PMA_motif_evidence.tsv`: source entry → experiment/model/dataset →
  source-native evidence and context (biosample, cell type, organ,
  disease, study).
- `PMA_cluster_summary.tsv`:
  - `cluster_id`, `representative_id`, `partition`
  - `n_nodes`, `n_raw_motifs`, `n_independent_experiments`
  - `source_composition`, `evidence_composition`
  - `tf_family_primary`, `tf_family_purity` (weighted by independent
    experiment, not by motif count), `candidate_tf_ids` (DNA-binding TFs,
    NA allowed), `assayed_protein_targets`
  - `biosample_distribution`, `organ_distribution`
  - length, IC, GC, composite flag
  - `representative_coverage`, `parent_louvain_cluster`, `split_reason`
  - `annotation_status`, one of `known`, `alternative`, `unresolved`,
    `accessibility_only`
  - `qc_flags`
- `recurrent_uncharacterized`: a cluster with no candidate TF that is
  supported by ≥ 3 independent experiments across ≥ 2 studies/biosamples.
  This label raises the evidence level only; it never deletes anything.

## 8. Legacy benchmark use of v0.2.1 (D7)

The finished v0.2.1 TOMTOM is used for four things:
- τ calibration (§6.1);
- a check that 8-mer nearest neighbours agree with TOMTOM;
- a v0.2.1 → v0.3 concordance report (curated patterns kept, merged or
  split; giant clusters);
- G4.

The 90-configuration v0.2.1 grid is not re-optimised.

## 9. Compute and reproducibility (condition 4)

- **Compute:** all on Argos, multi-core and multi-job: rcapps3 (x86, 72
  cores) and rcapps8 (aarch64, 128 cores). Never on the Mac mini.
  - R: r4p3 with `R_LIBS_USER=R_lib_4` (Seurat 5.0.1).
  - Python: conda env; blockwise features.
- **Raw:** each raw source gets `README.source.md`, `source_manifest.tsv`
  (URL/accession, release, download md5, extraction script commit) and
  `checksums.md5` for the kept files. Deleted originals stay re-fetchable
  by accession and md5.
- **Processed and result layers:** config, code commit, session info,
  checksums and changelog.

## 10. Plan (unchanged order)

1. Finish the ChromBPNet download; write raw manifests for the four new
   sources.
2. Write `scripts/02c_denovo_sources/import_v03.py`, which builds raw layer
   v0.3 from v0.2.1 plus the new profiles, applies the §3 QC and records
   lineage and experiment identity.
3. Extend `evidence_tier.py` to evidence annotation v2.
4. τ calibration on v0.2.1 TOMTOM (frozen before step 5).
5. Dedup, then features, then PCA basis/projection, then the grid (Argos).
6. Gates, then selection, then splitting and representatives, then
   cluster annotation.
7. Results doc, then review-task Quick, then ChatGPT review, then PR.

## 11. Revision 1 log (ChatGPT freeze review of 89d2cce: REQUEST CHANGES → applied)

Each finding was checked independently before it was applied.

| Item | Change | Verification |
|---|---|---|
| F-a | X → `indirect_association` | X means "indirect" in the README; it does not prove non-cognate binding |
| F-b / P1 | unmatched or ambiguous MotifCompendium join → annotation-only | missing QC metadata cannot count as a pass |
| P2 | add `peaks` must-pass; no top-k | `peaks` has the lowest pass rate (69 %), the most informative check |
| P4 | contiguous end-trimming only | — |
| P5 | overlap ≥ 90 % of the longer profile; controls with independent evidence | 80 % of the shorter would merge a 6-mer core into a 12-mer with distinct flanks |
| P6 / B1 | HDMA cell clusters unresolved; no crosswalk → `independence_unresolved` | cell clusters share donors and libraries |
| P7 / P11 | 51 PCs | B at d = 50 needs PCs 2:51 (the Step 3 grid used 2:50, noted in §9 there) |
| P8 / B2 | stratified hard-pair τ calibration | an unstratified 95 % is dominated by CTCF / Factorbook duplicates |
| P9 / P10 / B3 | single split; G2 moved before the split | **confirmed:** a complete-linkage cut at 1 − τ makes post-split coverage 100 % by construction, so the old G2 was tautological |
| P12 | ProCapNet annotation-only | different prediction target (transcription initiation) |
| B4 | de novo composites go to the composite partition; MotifCompendium / HDMA-508 concordance is descriptive only | they share provenance with the inputs |
