# Step 2 — Multi-source motif import, harmonisation and QC (design)

Status: draft for review, 2026-10-14. No Step 2 compute has been run.
The raw files listed in §2 have been fetched.
Parent plan: `design/motif_resources.md` Stages 1–2. Inputs from Step 1
review (ChatGPT round 2): freeze similarity calibration, composite
handling and provenance before cross-source comparison.

## 1. Scope

**In scope:**
- Import every source into one raw motif layer (Level 1 in
  `motif_resources.md` §3).
- Give each motif a PMA ID and harmonised metadata.
- Run format/QC checks and record exact-duplicate groups.
- Build the **similarity calibration benchmark** (§6) and evaluate
  TOMTOM matching by motif length on it.

**Out of scope:** clustering, representative selection,
CORE/EXTENDED assignment (Step 3), and genome scanning. No motif is
deleted at this step; QC only adds flags.

## 2. Sources (versions locked)

Raw files are under `$BIO_DATA/2.PROJECTS/PMA/motif_reference/raw/<source>/2026-10-14/`.

| Source | Version | Set used | Motifs | Notes |
|---|---|---|---|---|
| Codebook | Nature 2026, Supp. Data 1 | representative PWMs | 1,685 | 180 inferred; already imported in Step 1 |
| JASPAR | 2026 (release 11) | CORE vertebrates non-redundant | 1,019 | latest version per base ID; species from sqlite |
| JASPAR | 2026 | UNVALIDATED non-redundant | 1,031 | EXTENDED candidates only |
| HOCOMOCO | v14 (website final bundle) | H14CORE | 1,595 (1,107 TFs) | quality A–D; 240 built from mouse data; v14 already includes Codebook/MEX-derived motifs. There is no versioned Zenodo record for v14, so the fetch date is the version anchor. |
| CisBP | 3.10 (updated 2026-04-26) | human, all motifs | 7,434 IDs (1,407 TFs) | TF–motif links: 6,430 direct, 6,202 inferred; 1,003 Transfac motifs have **no matrix** (license) |
| Factorbook | fetched 2026-10-14 | ChIP-seq MEME catalog | 10,477 | ENCODE experiment and file accession, target, biosample |
| Factorbook | — | HT-SELEX ZMotif catalog | 6,700 | **deferred**: factorbook.org returns HTTP 429 to scripts; needs a manual browser download |

Source-file caveats found during fetch:
- **CisBP species archive:** the archive's `PWMs_all_motifs` file
  interleaves matrices with server-side unzip log lines. The ID-to-matrix
  assignment is ambiguous, so this file is **not used**. Matrices come
  from `EntireDataset_PWMs.zip`, which has one file per motif ID (all
  7,434 human IDs present).
- **Codebook:** 4 PWMs contain all-zero spacer rows, set to uniform and
  counted (Step 1).

## 3. Motif identity (frozen)

- `pma_id` = `<SRC>_<source_motif_id>`, where SRC ∈ {CB26, JA26, JU26,
  HO14, CI310, FBC}. JU26 marks JASPAR UNVALIDATED; FBC marks Factorbook
  ChIP. The ID is stable across rebuilds of the same source version.
- Each motif also stores `source_db`, `source_version`, `fetch_date`,
  `source_motif_id`, `source_file` and `matrix_md5`. `matrix_md5` is the
  md5 of the row-normalised matrix rounded to 4 decimals, in the forward
  orientation.
- `exact_dup_group` links motifs whose `matrix_md5` matches in either
  orientation. They are flagged, never merged.

## 4. Evidence model (frozen)

Two independent fields, plus TF assignment. The source database name is
never used as a quality proxy.

| Field | Values |
|---|---|
| `assay_class` | `in_vitro_selection` (HT-SELEX, Methyl-HT-SELEX, GHT-SELEX, SELEX, CAP-SELEX, SMiLE-seq, B1H, DAP-seq), `in_vitro_array` (PBM), `in_vivo_occupancy` (ChIP-seq, ChIP-exo, CUT&RUN), `literature_compiled` (Transfac, Misc, COMPILED), `unknown` |
| `tf_assignment` | `direct` (motif measured for this protein), `inferred` (CisBP TF_Status I, Codebook "Inferred", ortholog/paralog transfer), `none` (pattern without an assigned TF, allowed) |
| `species_basis` | `human`, `mouse_ortholog`, `other_vertebrate`, `unknown` |
| `source_quality` | source-native grade, kept verbatim (HOCOMOCO A–D; JASPAR CORE/UNVALIDATED; none otherwise) |

Source-specific mapping:
- **HOCOMOCO datatype codes:** P = ChIP-seq, S = HT-SELEX, M = Methyl-HT-SELEX,
  G = GHT-SELEX, I = SMiLE-seq, B = PBM, H = inherited from v11.
- **CisBP `MSource_Type`:** mapped as in the table above.
- **CisBP is one row per TF–motif link.** A motif can be direct for one
  TF and inferred for another. Links are stored in
  `PMA_motif_tf_links.tsv`, and the evidence count uses direct links
  only.

## 5. Provenance and derived-from links (frozen)

- **Discovery dataset.** ChIP-derived motifs store `discovery_dataset`
  (ENCODE ENCSR/ENCFF for Factorbook; GTRD PEAKS ID for HOCOMOCO P;
  JASPAR medline/source where present), `discovery_target` and
  `discovery_biosample`. If unknown, `discovery_dataset_known = False`.
  Such motifs cannot be used for strict independent validation later.
- **`derived_from`.** Records the cross-source lineage:
  - CisBP motifs whose source is JASPAR, or Codebook (`Jolma,2026a`);
  - HOCOMOCO v14 motifs built from Codebook/MEX data (name contains
    `@` dataset tags);
  - JASPAR profiles taken from other databases.

  These are not independent evidence for the motif they copy. The
  lineage is recorded where the source metadata states it; it is not
  inferred from similarity.

## 6. Composite motifs (frozen)

- `n_components`, `components_hgnc` and `is_composite` come from the
  source's own annotation: JASPAR `A::B` names, CisBP / HOCOMOCO dimer
  annotations, CAP-SELEX.
- Spacer/gap rows (all-zero or uniform) are counted in `n_gap_rows`.
- A composite is never matched as equivalent to a monomer by name.
- Step 3 decides whether composite-to-monomer TOMTOM hits create
  cluster edges. Default: they do not, and they are recorded as
  `contains_component` links instead.

## 7. QC (flags only)

| Check | Flag |
|---|---|
| Parse failure, non-ACGT alphabet, negative values | `qc_fail_format` (excluded from MEME output, kept in metadata) |
| No matrix available (Transfac license) | `no_matrix_license` |
| Row sum ≠ 1 after normalisation | `qc_fail_norm` |
| Length < 5 (cannot satisfy TOMTOM min-overlap) or > 40 | `short_lt5` / `long_gt40` |
| Mean IC per position < 0.5 | `low_ic` (kept) |
| Exact duplicate | `exact_dup_group` |

## 8. Similarity calibration benchmark (frozen before any cross-source TOMTOM)

Built **only** from metadata, not from similarity scores, to avoid
circularity:
- **Positive pairs:** the same HGNC TF, both `tf_assignment = direct`,
  from **different sources and different assays**. For example, the
  Codebook GHT-SELEX PWM of TF X paired with the JASPAR HT-SELEX PWM of
  TF X.
- **Hard negatives:** TFs from different TFClass superclasses (from the
  HOCOMOCO masterlist), with motif lengths matched within ±2 bp. Hard
  negatives are additionally required to share a top-k-mer consensus
  (≥ 5-mer exact match), so that they look similar at short range.
- **Reporting:** TOMTOM p, per-query BH q and overlap, stratified by
  motif length bin (the Step 1 bins). Output is ROC/PR by length.
- **Decision rule:** choose between a uniform q cutoff, a uniform
  effect-size cutoff (best-alignment Pearson) or length strata. Choose
  the option that gives the best minimum-across-bins F1 on the
  benchmark. Report the chosen rule with its per-bin
  sensitivity/specificity. Name it `statistical_match_v0.2` and keep
  `v0.1` alongside it.

Known limitation: positives assume one TF has one pattern. TFs with
genuine alternative motifs will appear as false negatives, so
sensitivity is a lower bound. The positive set is therefore restricted
to the source-designated primary motif where a source has one
(HOCOMOCO subtype 0; CisBP is not restricted).

## 9. Outputs

- **Processed** (`processed/v0.2_raw_layer/`):
  - `PMA_motifs_raw.meme` (all motifs passing format QC)
  - `PMA_motif_metadata.tsv`
  - `PMA_motif_tf_links.tsv`
  - `PMA_motif_provenance.tsv`
- **Result** (`result/step2_motif_import/`): QC report tables; benchmark
  pairs; TOMTOM benchmark runs; calibration tables.
- **Repo** (`results/02_motif_import/`): summary tables, including
  per-source counts, TF coverage overlap, length/IC distributions, QC
  flag counts and calibration by length.

## 10. Compute

Step 2 TOMTOM covers only the benchmark pairs (thousands), so local
6-core runs suffice. Full all-vs-all is ~22k × 22k ≈ 4.8×10⁸
comparisons, about 30–60 core-hours, and is Step 3. That will need
Argos or an O2 sbatch array, following the O2 DUO rules.

## 11. Done criteria (Step 2)

1. Every source in §2 is imported, except the deferred Factorbook
   HT-SELEX catalog. Counts reconcile with the source manifests, and
   every exclusion has a flag.
2. 100 % of motifs have `pma_id`, `source_*`, `assay_class`,
   `tf_assignment` and `species_basis`. The share with
   `discovery_dataset_known` is reported for ChIP-derived motifs.
3. The calibration benchmark is built and evaluated, and the
   `statistical_match_v0.2` rule is chosen with per-length-bin
   performance.
4. The whole pipeline reruns from raw with one command and gives
   identical `matrix_md5` and metadata.
