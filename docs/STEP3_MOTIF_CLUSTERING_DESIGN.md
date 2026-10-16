# Step 3 — Motif clustering, representatives, CORE/EXTENDED (design)

Status: revision 1, 2026-10-16, after ChatGPT pre-compute review of
draft 0 (61728de, REQUEST CHANGES, F18–F23). No Step 3 compute has been
run.
Parent plan: `design/motif_resources.md` §3 (Levels 2–3), §4, §6, Stage 3.
Input: raw layer **v0.2.1** (`processed/v0.2.1_raw_layer/`, 29,778 motifs
in `PMA_motifs_raw.meme`). Carried-over notes: F9 (v0.1 is not a
calibrated equivalence classifier), F13/F17 (profiles ≠ independent
experiments), F16 (HOCOMOCO quality per collection entry).

## 1. Goal and scope

Goal: a **non-redundant reference** whose representatives are the input
to genome scanning, so downstream cost scales with the number of distinct
sequence patterns, not with 29,778 raw motifs. Motifs are grouped by DNA
sequence pattern. A cluster or archetype is **not** a TF family: one
family may span several archetypes and one archetype may hold several
families (F18). An archetype hit is never attributed to every TF in it;
the member → TF mapping is kept.

Priority (F23 closing note): when compression and preserving distinct
patterns conflict, keep the extra representative.

In scope: similarity graph, fine clusters, archetypes, representatives,
CORE/EXTENDED tiers, Stage 3 QC report. Out of scope: Stage 4 gates
G1–G4 and freeze (Step 4), genome scanning. No raw motif is deleted;
every raw motif maps to exactly one fine cluster, or is listed as
`unclusterable`.

## 2. Input facts (v0.2.1, measured 2026-10-16)

| Fact | Value |
|---|---|
| Motifs in MEME | 29,778; 29,011 distinct normalised matrices |
| By source | Factorbook 17,177; CisBP 6,431; HOCOMOCO 2,435; JASPAR 2,050; Codebook 1,685 |
| Distinct `motif_tf_assignment` strings | 2,899 (2,149 single TFs; 2,371 motifs carry a multi-TF assignment, 489 of them `is_composite`) |
| Motifs per assignment | median 4; max 1,713 (CTCF) |
| Targets with no supported motif and not in the HOCOMOCO v14 masterlist | e.g. POLR2A 357, EP300 226 motifs |
| QC flags | low_ic 833, short_lt5 26, long_gt40 3 |
| Experiment identity | accession 19,456; publication_record 5,499; unknown 5,826 records |

## 3. Pipeline (frozen by this revision)

### 3.0 Nodes and partitions (F19, F23)

- **Node** = one exact normalised matrix (`normalized_matrix_hash`, either
  orientation via `exact_dup_group`). Rounded-equivalent groups are **not**
  collapsed; they are compared in a sensitivity table only.
- `short_lt5` nodes are `unclusterable`: not in TOMTOM, never CORE or
  scanning representatives.
- **Partition:** `is_composite` motifs form the *composite partition*;
  everything else is the *monomer partition*. Similarity edges are only
  formed within a partition; composite → monomer matches are recorded as
  `contains_component` links, not equivalence.
- Multi-TF (non-composite) motifs cluster by matrix like any monomer;
  their TFs stay in the many-to-many `PMA_motif_tf_links.tsv`.
- **Target class** (for CORE, F23): a motif's HGNC target is
  `sequence_specific_TF` if it is in the HOCOMOCO v14 masterlist or has
  at least one `direct_binding_evidence = supported` motif in v0.2.1;
  otherwise `non_TF_target` (e.g. EP300, POLR2A). Non-TF targets are
  clustered by pattern but never make a cluster CORE on their own.

### 3.1 Similarity computation (F19)

TOMTOM 5.5.9, Step 1/2 arguments
(`-no-ssc -dist pearson -min-overlap 5 -evalue -thresh 1e9 -text`),
**every node vs every node** (one fixed target universe of all nodes
except `short_lt5`). Per-query BH over the full target set. Chunking
changes scheduling only: each chunk asserts the full target count per
query, then keeps rows with q < 0.05 (gzip) and deletes the rest.
Run on Argos (SGE array or a standalone node), MEME 5.5.9 installed by
conda; versions, arguments and chunk checksums are recorded.

### 3.2 Edges and similarity score (F20)

- **Edge eligibility** = `statistical_match_v0.1` in **both** directions:
  BH q < 0.01 and overlap ≥ 60 % of the shorter motif, each direction.
- **Similarity** for an eligible pair, per direction, at TOMTOM's
  reported offset and orientation:
  r = mean over aligned columns of the Pearson correlation of the two
  probability columns, clipped to [0, 1];
  s_dir = r × L_overlap / max(L_A, L_B).
  s_AB = min(s_A→B, s_B→A). Non-eligible pairs have s = 0.
  This is a heuristic engineering score, not a calibrated probability.
- q is used only for eligibility, never as a distance.

### 3.3 Clustering (F20)

Distance d = 1 − s. Within each connected component of the eligible-edge
graph of one partition (non-edges d = 1; with cuts strictly below d = 1
per-component clustering gives the same partition as a global run):

1. Average-linkage dendrogram.
2. **Fine clusters:** cut at similarity c_f, then a **floor**: every pair
   in a fine cluster must have s ≥ 0.50. A candidate cluster failing the
   floor is re-split by complete linkage at s = 0.50 (all pairs then
   satisfy it).
3. **Archetypes:** units are fine clusters. Cut the average-linkage
   distance between fine clusters at c_a; floor: every member pair
   s ≥ 0.30, enforced by complete linkage over fine clusters
   (inter-cluster distance = max member-pair distance). Archetypes are
   therefore unions of whole fine clusters.

Pre-registered grids: c_f ∈ {0.80, **0.85**, 0.90}; c_a ∈ {0.65,
**0.70**, 0.75} (defaults bold). Floors are fixed (0.50, 0.30).

**Cut selection without curator labels** (F20). Defaults are used unless
a pre-registered failure moves the cut one step to the conservative
side (higher similarity), repeated until it passes or the grid ends:
- fine: N-challenge pairs co-clustered > 5 %, or largest fine cluster
  > 1 % of nodes;
- archetype: N-challenge pairs co-archetyped > 10 %, or largest
  archetype > 2 % of nodes.
P-provisional agreement is reported but never used to choose cuts.
Reported for every grid point: number of clusters/archetypes,
compression ratio, size distribution, cluster diameter (min pair s),
P-high retention, N-challenge co-clustering, ARI/purity vs Codebook
Table 10, Table 11 and HOCOMOCO H14CORE-CLUSTERED, and FOX / ETS /
GATA / NR / bHLH case listings.

### 3.4 Representatives (F21)

Per fine cluster:
1. **Eligible:** members with no QC flag; `low_ic` members only if every
   member is `low_ic`; not `non_TF_target`-only unless the cluster has no
   other member.
2. **Pattern fidelity:** mean s to the other members (non-edges 0).
   Candidates are eligible members within 0.05 of the best mean s.
3. Among candidates: direct-binding evidence (`supported` >
   `transferred` > `not_established`) → source quality, native to each
   source and never compared across sources: HOCOMOCO best
   collection-specific quality from the memberships table (F16), JASPAR
   CORE over UNVALIDATED → number of confirmed distinct experiments in
   the cluster with the candidate's pattern (accessions only; unknown and
   publication_record add nothing; F17) → mean s → length closest to the
   cluster median → pma_id.

Per archetype: the same rule over the fine-cluster representatives. A
fine cluster whose representative has s < 0.50 to the archetype
representative keeps its own representative in the scanning set
(`scan_role = archetype_extra`), so no fine pattern is represented only
by a poorly matching PWM.

### 3.5 CORE / EXTENDED (F22)

Tiers are assigned to **fine clusters** from all qualifying members, not
from the representative's assay:
- **CORE-sequence:** ≥ 1 member with `direct_binding_evidence =
  supported`, `species_basis = human`, no QC flag, target class
  `sequence_specific_TF`.
- **CORE-occupancy:** not CORE-sequence, and ≥ 2 distinct experiment
  accessions from `in_vivo_occupancy` members whose target is a
  `sequence_specific_TF`. Labelled occupancy-derived, never direct
  specificity.
- **EXTENDED:** every other cluster (JASPAR-UNVALIDATED-only,
  `non_TF_target`-only, `low_ic`-only, single unverified de novo, etc.).

Database count never substitutes for experiment count. CTCF clusters are
treated like any other; its many records count only as distinct
experiment accessions. An archetype's tier is the best tier of its fine
clusters. Scanning sets: `PMA_motifs_core.meme` = representatives of
CORE-sequence archetypes/extras; CORE-occupancy and EXTENDED are separate
files so analyses can add them explicitly.

## 4. Outputs

`processed/v0.3_reference/`:
- `PMA_motif_clusters.tsv`: every raw motif → node, partition, fine
  cluster, archetype, tier, `unclusterable` flag;
- `PMA_motif_representatives.tsv`: representative per fine cluster and
  archetype, scan role, mean s, selection reasons;
- `PMA_motifs_core.meme`, `PMA_motifs_core_occupancy.meme`,
  `PMA_motifs_extended.meme`;
- `PMA_motif_edges.tsv.gz` (eligible edges with s) and
  `PMA_motif_contains_component.tsv`;
- config, code commit, session info, checksums, CHANGELOG.

QC report and grid tables: `docs/STEP3_MOTIF_CLUSTERING_RESULTS.md`,
`results/03_motif_clustering/`.

## 5. Done criteria (Step 3)

1. TOMTOM universe asserted complete for every query; run info recorded.
2. Every raw motif appears exactly once in `PMA_motif_clusters.tsv`.
3. All fine clusters satisfy the 0.50 floor and archetypes the 0.30
   floor (asserted).
4. Grid table and the cut-selection trace are reported; chosen cuts
   follow §3.3 rules.
5. Unit tests for the similarity score, floor splitting, representative
   ranking and tier rules pass.
6. Two runs from the same TOMTOM edges give identical checksums.
