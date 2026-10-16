# Step 3 — Motif clustering, representatives, CORE/EXTENDED (design)

Status: draft 0, 2026-10-16, before ChatGPT pre-compute review. No Step 3
compute has been run.
Parent plan: `design/motif_resources.md` §3 (Levels 2–3), §4, §6, Stage 3.
Input: raw layer **v0.2.1** (`processed/v0.2.1_raw_layer/`, 29,778 motifs
in `PMA_motifs_raw.meme`). Carried-over review notes: F16 (read
collection-specific HOCOMOCO quality from the memberships table), F17
(experiment count ≠ cluster size).

## 1. Goal and scope

Goal: a **non-redundant reference** whose representatives are the input
to genome scanning, so downstream cost scales with the number of distinct
sequence patterns (expected order 10³), not with 29,778 raw motifs.
Similar motifs from related TFs (e.g. FOX, ETS) are grouped by sequence
pattern; a cluster is not a TF family (`motif_resources.md` §3).

In scope: similarity graph, clusters, representatives, CORE/EXTENDED,
the Stage 3 QC report. Out of scope: Stage 4 gates G1–G4 and freeze
(Step 4), genome scanning. No raw motif is deleted; every raw motif maps
to exactly one cluster (or is listed as unclusterable).

## 2. Input facts (v0.2.1, measured 2026-10-16)

| Fact | Value |
|---|---|
| Motifs in MEME | 29,778; 29,011 distinct normalised matrices |
| By source | Factorbook 17,177; CisBP 6,431; HOCOMOCO 2,435; JASPAR 2,050; Codebook 1,685 |
| Distinct `motif_tf_assignment` strings | 2,899 (2,149 single TFs; 2,371 motifs carry a multi-TF assignment, 489 of them `is_composite`) |
| Motifs per assignment | median 4; max 1,713 (CTCF); 59 assignments ≥ 50 motifs hold 6,358 motifs |
| Non-TF ChIP targets present | e.g. POLR2A 357, EP300 226 (Factorbook) |
| QC flags | low_ic 831 (+2), short_lt5 26, long_gt40 3 |
| Σ n² within assignment | 3.9 M comparisons |
| Full all-vs-all | ~29k × 29k ≈ 8.6 × 10⁸ comparisons |

Throughput (Step 1): 4.6 M TOMTOM comparisons in 14 min on 6 cores.
Full all-vs-all ≈ 40 h on the Mac mini (6 cores), ≈ 3–4 h on 128 cores.

## 3. Pipeline (proposed)

**3.0 Nodes.** Collapse `exact_dup_group` / `rounded_equiv_group` into one
node (≈ 29k nodes). Motifs with `short_lt5` cannot meet TOMTOM
min-overlap 5 and are listed as `unclusterable` singletons.

**3.1 Similarity.** TOMTOM 5.5.9 with the Step 1/2 arguments
(`-no-ssc -dist pearson -min-overlap 5 -evalue -thresh 1e9 -text`),
every node as query against all nodes. Per-query BH over the full
universe (Step 2 convention). Each chunk keeps only rows with q < 0.05
(plus offset, overlap, orientation) and discards the rest.
Edge rule = `statistical_match_v0.1` (BH q < 0.01 and overlap ≥ 60 % of
the shorter motif, in **both** directions for clustering).

**3.2 Clustering.** Distance d = 1 − s, with s a pair similarity derived
from the TOMTOM edge (non-edges d = 1). Average-linkage hierarchical
clustering run per connected component of the edge graph (exact,
because components never merge below d = 1). Two cut levels:
- **cluster** (fine): keeps alternative patterns of one TF apart;
- **archetype** (coarse): one row per family-level sequence pattern;
  used for genome scanning.
Each cluster records its minimum within-cluster similarity; clusters
below a floor are split further.

**3.3 Representatives.** One existing PWM per cluster/archetype (no
averaging). Ranked by: (1) direct-binding evidence
(`supported` > `transferred` > `not_established`); (2) source quality
(HOCOMOCO A/B per collection via the memberships table (F16), JASPAR
CORE); (3) number of independent experiments in the cluster supporting
it (F17); (4) centrality (mean similarity to members); (5) IC within
the cluster's IC range (not maximised). Ties → deterministic by pma_id.

**3.4 CORE/EXTENDED** (§6 of the parent plan). EXTENDED = all clusters.
CORE = clusters whose representative has supported direct-binding
evidence, or ≥ 2 independent experiments / sources supporting the
pattern; excludes JASPAR UNVALIDATED-only, non-TF-target-only and
low_ic-only clusters.

**3.5 Calibration and checks (descriptive, no curator labels).**
Cut levels are reported over a grid: number of clusters/archetypes,
P-high and P-provisional pairs kept together, N-challenge pairs
separated, ARI/purity vs Codebook Table 10 and Table 11, and the
known-family check (FOX, ETS, GATA, NR, bHLH). The cut is fixed from
these before CORE/representatives are frozen.

## 4. Outputs

`processed/v0.3_reference/`: `PMA_motif_clusters.tsv` (every raw motif →
node, cluster, archetype), `PMA_motif_representatives.tsv`,
`PMA_motifs_core.meme`, `PMA_motifs_extended.meme`,
`PMA_motif_evidence.tsv`, config, checksums, CHANGELOG. QC report in
`docs/STEP3_MOTIF_CLUSTERING_RESULTS.md`.

## 5. Open decisions (for review)

- **D1 Granularity:** two levels (cluster + archetype) vs one.
- **D2 Compute:** full all-vs-all TOMTOM on Argos/rcapps8 (MEME 5.5.9 to
  be installed via conda) vs within-assignment collapse first (3.9 M
  comparisons, local) then cross-TF all-vs-all on the reduced set.
- **D3 Similarity s and cut:** what s to use (−log10 q? best-alignment
  Pearson? overlap-weighted), and how to choose the cluster and archetype
  cut without curator labels.
- **D4 Representative ranking** as in 3.3.
- **D5 CORE rule** as in 3.4.
- **D6 Special motifs:** non-TF ChIP targets (POLR2A, EP300…),
  multi-TF assignments (2,371; 489 composite), CTCF's 1,713 motifs, low_ic motifs.
