# Step 1 — Motif reference pilot: Codebook 2026 vs JASPAR 2026 (design)

Status: design locked before compute, 2026-10-14.
Parent plan: `design/motif_resources.md` (PMA Human Motif Reference). Its
"最终建议" section says to run a small Codebook-first architecture check
before downloading all five sources. This step is that check.

## 1. Questions

1. **Q1 Coverage**: how many JASPAR 2026 CORE human TF motifs does the
   Codebook 2026 representative collection already cover? Measured at
   the TF level and at the motif level.
2. **Q2 Alternative patterns**: how many JASPAR sequence patterns does
   the Codebook representative collection *not* keep (alternative motifs,
   dimers, ChIP-derived patterns)?
3. **Q3 Clustering reuse**: can Codebook's motif clustering
   (Supp. Table 10/11) be reused as the PMA reference clustering, or
   only as an anchor?

Out of scope: HOCOMOCO, CisBP, Factorbook, building PMA clusters,
CORE/EXTENDED assignment, and genome scanning. Those are Steps 2–4.

## 2. Inputs (all under `$BIO_DATA/2.PROJECTS/PMA/motif_reference/raw/`)

| Source | Version | Files | Use |
|---|---|---|---|
| Codebook (Jolma et al., Nature 2026, doi:10.1038/s41586-026-10798-9) | published 2026-08-05 | Supp. Data 1 (1,685 representative PWMs, 1,421 TFs); Supp. Tables 1–16 | target motif set; metadata (Table 10), MARA clusters (Table 11), TF census (Table 14) |
| Codebook MARA (Zenodo 17307845) | v2, 2025-10-09 | `representative_motifs.zip` (653 HOCOMOCO v13 + Codebook representatives) | Q3 reference only |
| Codebook MEX (Zenodo 15667805) | 2025-06-15 | README, `MEX_top1.zip`, `metadata_complete_dataset.tsv` | provenance only in Step 1 |
| JASPAR 2026 (release 11) | 2026 | CORE vertebrates non-redundant + redundant (MEME/JASPAR), UNVALIDATED non-redundant, `JASPAR2026.sqlite` | query motif set; species/type/class metadata |
| HGNC mapping | workspace `DATA/1.Databases/HGNC_gene_id_mapping/processed/v0.1` | symbol/alias/previous | TF symbol harmonisation |

Tool: MEME Suite 5.5.9 (`tomtom`), built from source at
`$BIO_SOFTWARES/tools/meme-5.5.9`.

## 3. Methods (locked)

### 3.1 Motif conversion
- Codebook: each Supp. Data 1 file holds a TF, a motif ID and a
  probability matrix (Pos × A,C,G,T). Rows are renormalised to sum to 1
  and written to MEME format. The PMA ID is `CB26_<file stem>`.
  Metadata is joined from Supp. Table 10 on `Representative motif filename`.
- JASPAR: `JASPAR2026_CORE_vertebrates_non-redundant_pfms_meme.txt`
  is the primary query set: latest version per base ID, 1,019 motifs.
  Per-matrix metadata (species tax IDs, `type`, `class`, `family`,
  UniProt) comes from `JASPAR2026.sqlite`.
- Background: uniform (0.25 each) for both sets, so neither side
  carries a dataset-specific background.

### 3.2 TF symbol harmonisation
- JASPAR `NAME` is split on `::` (heterodimers) into component TFs.
- Each component is uppercased, then mapped through HGNC (symbol →
  previous → alias) to the current HGNC symbol. Unmapped names are kept
  and flagged.
- Human motifs are those whose species include tax 9606. Non-human
  motifs (mainly mouse) are mapped by uppercase symbol, flagged
  `ortholog_by_symbol`, and reported separately. They are never counted
  as human-measured motifs.

### 3.3 Similarity (TOMTOM)
- `tomtom -no-ssc -dist pearson -min-overlap 5 -evalue -thresh 1e9 -text`,
  run twice: JASPAR → Codebook (Q1/Q2) and Codebook → Codebook (Q3). This
  reports every pair, so cutoffs are applied downstream.
- **Amendment (2026-10-14, before results):** TOMTOM's built-in q-values
  are not reproducible across query order. The π₀ bootstrap's RNG state
  carries over between queries, so a serial run and a 6-chunk run
  differed by ≤0.5 %, and 2 of 12,001 pairs flipped at q < 0.01.
  p-values were identical. PMA therefore uses per-query
  Benjamini–Hochberg q-values (π₀ = 1) over all targets, computed from
  TOMTOM p-values. TOMTOM's own π₀ estimates were ≈1, so this is the
  same or slightly more conservative.
- **Primary match criterion**: TOMTOM q < 0.01 **and** aligned overlap
  ≥ 60 % of the shorter motif's length. The overlap rule addresses the
  "shared short core" failure mode named in `motif_resources.md` §4.
- **Sensitivity**: q ∈ {0.001, 0.01, 0.05} × overlap ∈ {0.5, 0.6, 0.75}.
  The primary cutoff is not presented as validated.

### 3.4 Q1 — coverage
- TF-level: the fraction of JASPAR human component TFs that have at
  least one Codebook representative PWM for the same HGNC symbol.
- Motif-level: each JASPAR human motif is classed as
  (a) `same_TF`: matches a Codebook PWM of one of its own component TFs;
  (b) `other_TF_only`: matches only Codebook PWMs of other TFs, so the
  pattern is present but assigned elsewhere; or
  (c) `not_represented`: no match under the primary criterion.

### 3.5 Q2 — alternative patterns
- Q2 counts JASPAR motifs in class (c), and in class (b) when the TF
  itself has a Codebook PWM. These are broken down by JASPAR `type`
  (ChIP-seq, HT-SELEX, …), TF class, heterodimer status and motif IC.
- Q2 counts TFs with more than one JASPAR non-redundant motif, and how
  many of those motifs match the same Codebook PWM versus different ones.

### 3.6 Q3 — clustering reuse
- **Cohesion / separation** of Supp. Table 10 clusters under TOMTOM:
  the fraction of within-cluster pairs that match (primary criterion)
  versus the fraction of between-cluster pairs.
- **Consistency**: for each JASPAR motif with matches, whether all its
  matched Codebook PWMs fall in one Table-10 cluster.
- **Method comparison**: Table 10 uses MoSBAT affinity correlation,
  average linkage and a silhouette-chosen cut (613 clusters on 1,582
  PWMs). Table 11 uses HOCOMOCO v13 + Codebook (653 clusters). The
  result doc states whether these clusterings can be the PMA reference
  or only an anchor.

## 4. Outputs

- Processed: `$BIO_DATA/2.PROJECTS/PMA/motif_reference/processed/v0.1_pilot/`
  - `codebook2026_representative.meme`, `codebook2026_motif_metadata.tsv`
  - `jaspar2026_core_vert_nr.meme` (copy), `jaspar2026_core_vert_nr_metadata.tsv`
- Result: `$BIO_DATA/2.PROJECTS/PMA/motif_reference/result/step1_motif_pilot/`
  - `tomtom/jaspar_vs_codebook.tsv`, `tomtom/codebook_vs_codebook.tsv`
  - per-motif classification tables, sensitivity grid
- Repo: `results/01_motif_pilot/` holds small summary tables and
  `docs/STEP1_MOTIF_PILOT_RESULTS.md`.

## 5. Decision rule after Step 1

- **Q1 high and Q2 small** (most JASPAR human patterns covered): use
  Codebook as the backbone. Later sources add only `not_represented`
  patterns and provenance.
- **Q2 substantial**: confirms the plan's multi-source design.
  Step 2 then integrates HOCOMOCO, CisBP and Factorbook at the raw level.
- **Q3**: if Table-10 clusters are cohesive and well separated under
  TOMTOM, use them as the reference anchor for PMA clustering.
  Otherwise, PMA clusters are built independently and compared to
  Codebook's afterwards.

Also flagged for Step 2: HOCOMOCO is now at v13/v14, not v12 as written
in `motif_resources.md`. The version will be chosen in the Step 2 design.
