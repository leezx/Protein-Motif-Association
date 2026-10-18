# Step 4a — ChIP-Atlas hg38 protein occupancy atlas: design

Status: **contract approved** (ChatGPT, 2026-10-17: APPROVE WITH REVISIONS; the revisions are
already applied below). A small pilot must validate the implementation assumptions (§7) before the
full archive is processed.

**PI direction.** Download all human ChIP-seq data from ChIP-Atlas and build one unified,
annotated BED on GRCh38 (hg38). It records which regions are bound by which protein, in which
context (tissue or cell source), and with which antibody.

**Positioning.** This is a source-preserving, experiment-resolved, metadata-annotated atlas of
ChIP-seq peak intervals on hg38.
- One record is one peak interval reported by one ChIP-Atlas experiment.
- A record is evidence that the assayed antigen associates with chromatin there. It is not proof
  of direct DNA contact, and it is not a consensus site merged across experiments.

## 1. Inputs (raw, append-only)

Location: `DATA/2.PROJECTS/PMA/occupancy_chipatlas/raw/2026-10-17/` (Argos). Every file has an
md5 and the server's `Last-Modified` date (`remote_headers.txt`).

| File | Release | Content |
|---|---|---|
| `experimentList.tab` | 2026-10-14 | one row per experiment (see below) |
| `allPeaks_light.hg38.05.bed.gz` | 2026-09-26 | all hg38 experiments, MACS2 q < 1e-5 |
| `fileList.tab`, `antigenList.tab`, `celltypeList.tab` | 2026-09/10 | provenance only |
| `reference/hgnc_complete_set.txt` | downloaded 2026-10-17 | HGNC approved, previous and alias symbols |
| `reference/hg38-blacklist.v2.bed.gz` | Boyle lab v2 | ENCODE hg38 blacklist |
| `reference/hg38.chrom.sizes` | UCSC | 455 contigs |

**`experimentList.tab` columns** (0-based):

| Column | Content |
|---|---|
| 0 | experiment ID (SRX / ERX / DRX) |
| 1 | genome |
| 2 | antigen class |
| 3 | antigen |
| 4 | cell type class |
| 5 | cell type |
| 6 | cell type description |
| 7 | QC as `reads, % mapped, % duplicates, peaks at q < 1e-5` |
| 8 | title (often `GSMxxxx: ...`) |
| 9+ | SRA attributes as `key=value` |

**Peak file columns:** chrom, start, end, experiment ID, −10·log10(MACS2 q).

## 2. Scope

**Included.** hg38 rows whose antigen class is `TFs and others` (34,651 experiments, 1,874
antigens) or `RNA polymerase` (4,448), giving 39,099 candidate experiments.

**Excluded.** Histone, ATAC-Seq, DNase-seq, Input control, Bisulfite-Seq, Unclassified, No
description and Annotation tracks. Histone and accessibility assays can become separate resources
later.

**Wording.** Describe the file as "human hg38 TF/other-protein and RNA-polymerase ChIP-seq peaks,
q < 1e-5". Never call it "all human ChIP-seq".

**Threshold.** q < 1e-5, from the 05 archive. The raw score is kept, so stricter views are
possible:

| q cutoff | macs2_qscore |
|---|---|
| 1e-10 | ≥ 100 |
| 1e-20 | ≥ 200 |

These are views of the q < 1e-5 calls only. The pilot (§7.1) showed they do not reproduce the 10 and
20 archives.

**Out of scope for Step 4a:**
- peak merging across experiments, consensus peaks, summit recentering, width normalisation;
- motif scans;
- full ontology harmonisation.

## 3. Output A — `PMA_chipatlas_hg38_occupancy.bed.gz`

- BED6+18, 24 columns, 0-based half-open.
- Coordinate-sorted, then bgzip + tabix.
- No header row. The column contract ships as `PMA_chipatlas_hg38_occupancy.as` (autoSql) plus
  `schema.json`.
- One row per original peak per experiment.
- Chromosome names are kept as in the source.
- Missing values are `.`. Fields never contain tabs.

| # | Column | Content |
|---|---|---|
| 1–3 | chrom, chromStart, chromEnd | source coordinates |
| 4 | name | experiment ID |
| 5 | score | min(1000, max(0, round(macs2_qscore))), for browser display only |
| 6 | strand | `.` |
| 7 | macs2_qscore | raw −10·log10 q, never capped |
| 8 | antigen_raw | ChIP-Atlas curated antigen |
| 9–11 | antigen_hgnc_symbol, antigen_hgnc_id, antigen_map_status | §5.1 |
| 12 | antigen_class | ChIP-Atlas class |
| 13–14 | cell_type_class, cell_type | ChIP-Atlas curated |
| 15–18 | tissue, biosample_type, disease, treatment_status | §5.3 |
| 19–21 | antibody_id, antibody_label, antibody_status | §5.2 |
| 22–23 | gsm, study_id | provenance |
| 24 | qc_flags | experiment flags (§6) plus the per-peak `blacklist_majority_overlap` |

## 4. Output B — `PMA_chipatlas_hg38_experiments.tsv.gz`

One row per in-scope experiment, including experiments with zero peaks. Fields that cannot be
resolved are present and empty or flagged, never dropped. The key is `experiment_id`; SRX, ERX and
DRX are all valid.

| Group | Fields |
|---|---|
| Identity | experiment_id, genome, antigen_class, gsm, study_id, biosample_id (where traceable) |
| Antigen | antigen_raw, antigen_hgnc_symbol, antigen_hgnc_id, antigen_map_method, antigen_map_status, target_modification, target_category, target_candidates |
| Antibody | antibody_raw, antibody_source_field, antibody_target_raw, antibody_vendor, antibody_catalog, antibody_clone, antibody_host, antibody_type, antibody_id, antibody_label, epitope_tag, antibody_status |
| Context | cell_type_class, cell_type, cell_type_description, tissue, biosample_type, disease, treatment_status, perturbation, genotype, cellosaurus_id, uberon_id, cl_id, context_mapping_status |
| QC | reads, pct_mapped, pct_duplicates, n_peaks_reported, n_peaks_in_archive, qc_flags, primary_protein_occupancy_eligible |
| Provenance | title, attributes_raw (JSON), metadata_release, rules_version |

The ontology IDs are nullable and left empty in v1. Full ontology mapping is deferred.

## 5. Normalisation rules (deterministic, versioned `rules_version = 4a.v1`)

### 5.1 Antigen → HGNC

Mapping uses the versioned HGNC complete set, in this priority:
1. exact approved symbol;
2. unique previous symbol;
3. unique alias, after case and punctuation normalisation;
4. manual exceptions (`config/chipatlas_antigen_exceptions.tsv`, versioned);
5. otherwise unresolved. A protein is never forced.

**Status values:** approved_exact, previous_symbol, unique_alias, manual_curated, ambiguous,
complex_or_family, tag_only, non_gene_target, unmapped.

**Rules for difficult antigens:**
- Complexes and families (for example SMAD2/3 or NF-κB) get a `target_candidates` set and no single
  HGNC ID.
- Modified targets (for example POLR2A Ser2P or phospho-STAT3) keep `target_modification` and may
  map to the base gene.
- `target_category`: sequence_specific_tf, chromatin_regulator_or_cofactor, polymerase,
  other_protein or ambiguous_or_unmapped. It is derived and does not replace the ChIP-Atlas class.

### 5.2 Antibody

Parsed only from attributes whose key contains `antibod`. The raw text and its source key are kept.

**Structured fields** are vendor, catalog, clone, host, type and epitope_tag (FLAG, HA, V5, GFP,
Myc-tag, other, none or unknown).
- An anti-Myc-tag antibody is never treated as an anti-MYC protein antibody.
- An anti-FLAG ChIP of a tagged SOX9 construct keeps antigen SOX9, epitope_tag FLAG and the flag
  `tagged_construct`.

**`antibody_id`.** Set to `vendor:catalog` only when both are explicit, or to an ENCODE ENCAB
accession. Two antibodies are never merged just because both are "anti-X".

**`antibody_status`:** catalog_resolved, clone_resolved, description_only, not_reported or
ambiguous.

**Experiments with no antibody text** (about 19 % of experiments) keep all their peaks. They get
status `not_reported` and the flag `antibody_metadata_missing`; they are not called low quality.

Registry lookups (RRID, validation data) are a later enhancement.

### 5.3 Context

Context is multidimensional; raw values are always kept next to the normalised ones.

| Field | Values |
|---|---|
| biosample_type | cell_line, primary_cells, primary_tissue, organoid, stem_cell_derived, other, unknown |
| tissue | from attributes or the ChIP-Atlas description, where explicit |
| disease | from attributes or `Tissue Diagnosis` |
| treatment_status | treated, untreated, not_reported, ambiguous |
| perturbation | knockdown, knockout, overexpression, drug, stimulation, … (B only) |
| genotype | from attributes (B only) |

A cancer cell line does not automatically get the disease "patient tumour". Cell-line origin and
the experimental condition are separate concepts.

## 6. QC (flags only; the primary BED is never silently filtered)

**Experiment flags.** These are screening warnings, not universal standards. The numeric values
are stored as well.

| Flag | Rule |
|---|---|
| low_reads | < 5 M reads |
| low_mapping | < 50 % mapped |
| high_duplication | > 80 % duplicates |
| few_peaks | < 100 peaks at q < 1e-5 |
| antibody_metadata_missing | no usable reported antibody information |
| target_ambiguous | no unique supported HGNC target |
| tagged_construct | explicit tagged protein or exogenous construct |
| perturbed_sample | explicit treatment or genetic perturbation |
| control_like | IgG, mock, input-like or other likely negative control; sets `primary_protein_occupancy_eligible = false` |

**Peak flag.** `blacklist_majority_overlap` when more than 50 % of the peak overlaps the ENCODE hg38
blacklist v2.

**Integrity (hard; rejected rows go to `rejected_records.tsv` with a reason):**
- 0 ≤ start < end ≤ chromosome length;
- chromosome present in `hg38.chrom.sizes`;
- valid experiment ID;
- finite numeric score;
- the experiment is in the metadata with genome hg38 and an in-scope class.

All source contigs are kept. A canonical-chromosome view is a derived product.

**Sorting.** Sorting is verified, not assumed: each chromosome forms one contiguous block, starts
are non-decreasing, and tabix retrieves test regions. If the check fails, a disk-backed external
sort runs before bgzip.

**Reconciliation report.** The peak archive (2026-09-26) is older than the metadata (2026-10-14).
The report must show:
- zero duplicate metadata keys;
- peak experiment IDs that are missing from the metadata, counted and quarantined;
- metadata experiments with no peaks, counted but not assumed invalid;
- zero genome or class mismatches accepted;
- per-experiment peak counts compared with the metadata count, quantified and flagged;
- every source row accounted for as included, out of scope or rejected.

## 7. Pilot (required before full scale)

Run on the first chunk of the archive (a valid gzip prefix) and on the full metadata table. Verify:
- the 5 raw columns;
- chromosome sort order;
- SRX/ERX/DRX joins;
- coordinate validity;
- antibody parsing (manual review of a stratified sample);
- antigen mapping coverage, including the list of unmapped and ambiguous antigens;
- that 05 filtered at score ≥ 100 / ≥ 200 equals the 10 / 20 archives within a shared prefix window.

### 7.1 Pilot results (2026-10-17)

**Metadata (full table).**
- 39,099 in-scope experiments (38,566 SRX, 312 ERX, 221 DRX); no duplicate or malformed IDs.

| Antigen mapping | Experiments |
|---|---|
| approved_exact | 31,118 |
| previous_symbol | 287 |
| manual_curated | 37 |
| complex_or_family (mostly RNA polymerase II) | 4,465 |
| tag_only | 2,619 |
| non_gene_target | 548 |
| ambiguous | 9 |
| unmapped | 16 |

| Antibody status | Experiments |
|---|---|
| catalog_resolved | 17,363 |
| clone_resolved | 1,129 |
| description_only | 13,361 |
| ambiguous (several reagents) | 388 |
| not_reported | 6,858 |

- A stratified manual review led to these rule fixes (rules 4a.v1, before any release):
  - `NA` values count as not_reported, not as a control;
  - secondary-antibody keys are excluded;
  - new patterns for RRID, Roche, Covance, legacy Santa Cruz product names and CST clone IDs;
  - vehicle and non-targeting controls count as untreated;
  - `hESC derived` counts as stem_cell_derived.
- Exception table addition: PAD2 → PADI2.

**Peaks (first 400 MB of the archive, chr1).**
- 8,156,733 of 43,092,967 rows are in scope.
- 0 rejected rows, 0 sort violations.
- tabix retrieval works.
- 334,215 rows (4.1 %) have blacklist_majority_overlap.

**Threshold views (shared window chr1:0–21.3 Mb).** Filtering the 05 archive at score ≥ 100 / ≥ 200
is **not** equivalent to the 10 / 20 archives: ChIP-Atlas calls peaks separately at each threshold,
and only 110 / 41 intervals are identical.

| Cutoff | 10/20-archive peaks overlapped by a same-experiment 05 peak with score ≥ cutoff | Filtered-05 peaks overlapped by a 10/20-archive peak |
|---|---|---|
| ≥ 100 | 99.99 % | 62.6 % |
| ≥ 200 | 99.99 % | 56.3 % |

So a score filter on Output A is a peak-score view of the q < 1e-5 calls. Analyses that need the
stricter ChIP-Atlas calls must use the 10 / 20 archives, which can be built as separate releases
with the same pipeline. §2 is amended accordingly.

## 8. Release and provenance

**Release name:** `PMA_ChIPAtlas_hg38_20260926peaks_20261014meta_v1`.

**`MANIFEST.json` records:**
- input and output sha256 hashes;
- source URLs and release dates;
- HGNC download date and blacklist version;
- code commit and `rules_version`;
- counts of retained peaks and experiments.

Output A is immutable within a release. Changes to antibodies, ontologies or antigen mapping
produce a new metadata version.

## 9. Compute

- Runs on Argos, streaming:
  - `pigz` or `gzip` decompresses the archive;
  - an awk hash filter keeps in-scope experiment IDs;
  - Python adds annotations, validates rows and sweeps the blacklist;
  - `bgzip`, then `tabix`.
- Memory: a few GB (metadata dictionary plus blacklist).
- Disk: the archive is 21.4 GB gzip.
- bedtools and bedToBigBed are not installed; a bigBed output is deferred.
