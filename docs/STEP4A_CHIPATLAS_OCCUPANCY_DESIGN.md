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

## 10. Light per-target BED for browsing (user request 2026-10-20)

**Why.** The experiment-level Output A (443 M rows) and the coordinate-unique BED6 (1.02 G rows with histone)
are too large to open in IGV. Exact-coordinate dedup removes only ~4 % of rows, because peak boundaries
from different experiments almost never coincide. Measured on v1 chr21: 6.15 M rows → 5.87 M coordinate-unique
→ 0.99 M per-target merged → 36 k all-target clusters. The user chose per-target merging, with histone marks in
a separate file.

**Rule.** For each target, overlapping or book-ended peaks (start ≤ open end) are chained across all experiments
of that target, as `bedtools merge` per name.
- Target: the HGNC symbol (Output A column 9); otherwise the curated ChIP-Atlas antigen (column 8) with
  whitespace replaced by `_`.
- Histone marks always use the ChIP-Atlas antigen (`PMA_LIGHT_TARGET=antigen`, e.g. `H3K27ac`, `H2A.Z`). HGNC
  mapping of histone antigens is unreliable: `H2B` → H2BC21, `H2A` → H2AC20, `H3.6` → the pseudogene H3P16.
- No peak is filtered. Blacklist overlap is counted per region, not removed.

**Inputs.**
- Proteins: the verified v1 Output A and its experiment table.
- Histone: the same Step 4a pipeline (§3–§6 rules, blacklist flag) run with `PMA_OCC_CLASSES=Histone`
  (`01_experiments.py` + `02_peaks.py`), giving a histone BED6+18 and `experiments_stage1.tsv.gz`.

**Outputs** (`04_light_bed.py`, one release directory per file set):

| File | Content |
|---|---|
| `<prefix>.bb`, `<prefix>.bed.gz` (+ `.tbi`) | BED6: chrom, start, end, target, score = min(1000, n experiments), `.` |
| `<prefix>.detail.tsv.gz` (+ `.tbi`) | chrom, start, end, target, n_experiments, n_peaks, max_qscore, n_peaks_blacklist, experiments |
| `<prefix>.experiments.tsv.gz` | experiment context (cell type, tissue, antibody, GSM, QC flags) |
| `<prefix>.targets.tsv`, `<prefix>.qc.json`, `MANIFEST.json` | per-target counts, QC, hashes |

Join key: BED row → detail row by (chrom, start, end, target), unique by construction; detail → context by
experiment ID.

**Acceptance.**
- Every input peak lies in exactly one region (Σ n_peaks = rows in).
- No duplicate keys; regions of one target are disjoint.
- score = min(1000, n_experiments).
- Width distribution and maximum width are reported, because chaining can join long stretches for broad targets.

**Limits.** Merged regions lose individual peak boundaries; they come back through the detail table and Output A.
Chained regions of broad or high-coverage targets (Pol II, histone marks) can be wide. This file is for browsing
and region lookup, not for motif-level analysis.

## 11. ChIP-Atlas Protein Occupancy Evidence Tracks (v1 scope, frozen 2026-10-20)

These are peak-derived evidence summaries across experiments. They are not read coverage, binding affinity or
co-binding in one cell. "Binding intensity" is not used as a name.

**Definitions.** Per base x, using the experiment-level peaks of v1 Output A (TF + Pol, q < 1e-5, no filtering).
p is a target label: the HGNC symbol, otherwise the ChIP-Atlas antigen. class(p) comes from
`PMA_chipatlas_hg38_protein_class_annotation.v1_1.csv`; labels without an HGNC symbol get class `Non-gene label`.

| Track | Definition |
|---|---|
| `experiments.bw` | E(x) = \|{e : x ∈ peaks(e)}\| |
| `proteins.bw` | P(x) = \|{p : x ∈ peaks(p)}\| (includes non-gene labels such as Epitope_tags, Pol II) |
| `tf.bw` | TF(x) = \|{p : class(p) = Sequence-specific TF, x ∈ peaks(p)}\| |
| `cap.bw` | CAP(x) = \|{p : class(p) ∈ {Histone writer/eraser, Histone reader, Chromatin remodeler, Architectural/cohesin}, x ∈ peaks(p)}\| |

Further rules:
- No binning or smoothing: exact base-pair step functions.
- An experiment or label counts once per base, whatever the number of overlapping peaks.
- Transcription machinery and Other/ambiguous count in E and P only.
- CTCF has primary class Architectural/cohesin, so it counts in CAP, not TF.

**Histone labels.** `08_histone_labels.py` assigns each of the 144 ChIP-Atlas Histone-class labels to exactly one
category (deterministic rules, `PMA_chipatlas_hg38_histone_label_annotation.tsv`):

| Category | Labels | Experiments |
|---|---|---|
| `histone_modification` (one histone, one residue, one defined modification) | 89 | 36,009 |
| `histone_variant_or_core` (H3, H3.3, H2A.Z, CENPA, H1.x, macroH2A, oncohistone H3K27M) | 31 | 959 |
| `pan_or_ambiguous` (Pan_*, H3ac, H4ac, H3K27me / H3K4me without degree, multi-site antibodies, H2Aub without site, nonstandard H4K4me3 / H3K14me3 / H3K4ox / H3K9acS10ph) | 22 | 505 |
| `non_histone_target` (CENPB, HINFP) | 2 | 8 |

- `canonical_label` merges spelling variants of one modification only: H2BK120ub1 → H2BK120ub, Ub → ub.
- Ambiguous labels are never assigned to a specific degree or site.

**Histone tracks** (`PMA_TRACK_MODE=histone`, from the histone BED6+18 of §10). Universe: experiments whose label is a
`histone_modification`; m is the canonical modification label.

| Track | Definition |
|---|---|
| `histone_experiments.bw` | H(x) = \|{e ∈ universe : x ∈ peaks(e)}\| |
| `histone_modifications.bw` | M(x) = \|{m : x ∈ peaks(m)}\| (distinct validated modification labels) |
| `histone_<m>.bw` | H_m(x) = \|{e : mark(e) = m, x ∈ peaks(e)}\| for the six core marks |

The six core marks fall into four functional groups, which are never summed into one signal:
- active regulatory: H3K27ac, H3K4me3;
- enhancer-associated (active or poised): H3K4me1;
- repressive: H3K27me3, H3K9me3;
- transcription elongation (gene bodies): H3K36me3.

Interpretation limits:
- Raw counts measure evidence quantity. Experiment numbers differ by mark (H3K27ac 12,010 vs H3K36me3 1,690), so
  counts are not comparable across marks.
- The per-mark recurrence fraction R_m(x) = H_m(x) / N_m is deferred.
- In IGV every track autoscales on its own axis (`09_igv_session.py`); heights are not compared across tracks.

Histone QC (both directions of the M–H identity hold because M and H share one universe):
- M ≤ H;
- M > 0 ⇔ H > 0;
- H_m ≤ H and Σ_core H_m ≤ H;
- the 300-position tabix recount, which also reports positions where one experiment has several overlapping peaks
  (counted once by construction).

**Blacklist split** (`10_mask_blacklist.py`; `tracks*_noBlacklist/` and `tracks*_blacklistOnly/`; one IGV session
each).
- Every track is split base-wise at the ENCODE hg38 blacklist v2 into the part outside and the part inside.
- Peaks are not dropped, because many peaks overlap the blacklist only in part. Values are unchanged; the raw tracks
  stay the reference.
- noBlacklist is the recommended browsing set. blacklistOnly shows what is removed.
- Reason: 57 % of bases with E ≥ 10,000 lie in the blacklist. The maximum, at chr1:125.17 Mb in the "High Signal
  Region" chr1:125,130,200–143,562,200, is near-universal artefactual peak calling.
- QC per track:
  - no noBlacklist base inside and no blacklistOnly base outside the blacklist, re-read from the written files;
  - Σ(value·bp): raw = noBlacklist + blacklistOnly.

**Class annotation v1.1.** The user's file is kept unchanged; v1.1 is a separate file.
- 168 genes were `Other/ambiguous` with basis `conservative_unresolved` and are in the Lambert 2018 human TF list.
  v1.1 sets them to Sequence-specific TF (basis `lambert2018_TF_list`).
- Lambert TFs with a more specific primary class keep it and get the tag `lambert2018_TF` (60 genes, e.g. CTCF,
  KMT2A, TBP).
- 9 TF-classed genes outside Lambert are flagged for manual review: ZFP36, NR0B2, BCL3, SMAD2 and others.
- `functional_tags` holds non-exclusive tags; `Class` is the single primary class.

**QC (automated, release-blocking).**
- Identities on every breakpoint of every chromosome:
  - P = Σ_k P_k over the mutually exclusive classes;
  - TF ≤ P and CAP ≤ P;
  - P ≤ E;
  - P > 0 ⇔ E > 0.
- Independent recount at 300 random covered positions directly from Output A with tabix (separate code path).

**Provenance.** `07_region_query.py chr:start-end` answers region → protein → experiment → cell context from the
Output A records. It reports per-protein experiment counts, cell types and tissues, and the share of experiments
contributed by the top 5 proteins, which flags hotspots dominated by a few proteins. Example:
chr4:16,001,000–16,002,000 has 3,336 experiments and 248 proteins, but CTCF alone has 1,815 experiments and the
top 5 proteins (CTCF and cohesin) have 73.5 %.

**Deferred (not v1):**
- protein-normalized peak support S(x) = Σ_p R_p(x);
- context-specific tracks;
- hotspot clustering;
- a comparison with ChIP-Atlas and ReMap functions (P1, desk review).

## 12. RNA polymerase and chromatin accessibility tracks (user request 2026-10-20)

**RNA polymerase.** All 4,448 ChIP-Atlas 'RNA polymerase' experiments carry two labels:
RNA polymerase II (4,352) and RNA polymerase III (96).
- Neither has an HGNC symbol, so they count in E and P only, each as one label in P, and in neither TF nor CAP.
- Separate tracks, `tracks_rnapol/`:
  - `rnapol2_experiments.bw`: Pol_II(x) = |{e : antigen(e) = RNA polymerase II, x ∈ peaks(e)}|;
  - `rnapol3_experiments.bw`: the same for Pol III.
- The protein tracks are unchanged.

**Accessibility.** The ChIP-Atlas hg38 archive also holds ATAC-Seq (48,776 experiments, 772 M peaks) and DNase-seq
(4,604 experiments, 130 M peaks).
- Each assay gets an experiment-level BED6+18 from the same Step 4a pipeline (`PMA_OCC_CLASSES`), in
  `atac_v1/` and `dnase_v1/`.
- Two tracks per assay, assays not merged:
  - `<assay>_experiments.bw`: A(x) = |{e : x ∈ peaks(e)}|;
  - `<assay>_celltypes.bw`: C(x) = |{ChIP-Atlas cell type of e : x ∈ peaks(e)}|. This damps cell types with many
    replicate experiments.
- QC:
  - C ≤ A;
  - C > 0 ⇔ A > 0;
  - the 300-position recount;
  - blacklist split as in §11.

Other ChIP-Atlas classes are not used:
- Input control: controls.
- Unclassified and No description: no usable target label.
- Bisulfite-Seq: methylation, not in the peak archive.
- Annotation tracks: not experiments.

**Experiment filter** (user decision 2026-10-20; `11_experiment_filter.py`,
`light_v1/PMA_chipatlas_hg38_experiment_filter.tsv`). Applies to the accessibility tracks and the histone tracks;
protein and Pol tracks are unchanged, because their single-cell keyword hits were false positives such as
"VP16(10x)" and "SC" for Santa Cruz.

Exclusion rules:
- `single_cell`: the experiment metadata mention single-cell / single-nucleus, sc/snATAC, sci-ATAC, 10x / Chromium,
  multiome, SHARE/SNARE-seq or scCUT&Tag. Study-level wording also counts, so this rule is conservative.
- `non_accessibility` (ATAC/DNase only): the title core names another assay or a control. Examples:
  - RNA-seq or ChIP-seq mislabelled as ATAC;
  - histone marks;
  - IgG or input;
  - KAS-seq / KAS-ATAC;
  - deproteinized-DNA DNase background.
- `low_peaks` (ATAC/DNase only): fewer than 10,000 peaks in the q < 1e-5 archive.

Why 10,000 rather than 100,000:
- This archive uses q < 1e-5 MACS2 calls. ATAC has a median of 3,427 peaks per experiment and only 644 of 48,776
  experiments reach 100,000.
- A 100,000 floor would keep 10 % of ATAC peaks; 10,000 keeps 92 %.

| Class | Experiments | Included | Peaks included |
|---|---|---|---|
| ATAC-Seq | 48,776 | 18,651 | 92.1 % |
| DNase-seq | 4,604 | 2,086 | 99.1 % |
| Histone | 40,444 | 37,762 | 2,682 single-cell iCELL8 CUT&Tag removed, ~2,700 peaks |

The pre-filter tracks are kept under `light_v1/preFilter/` for comparison.

## 13. Protein-level co-occupancy (DBP modules), v1 discovery scan (user request 2026-10-20)

**Question.** Does genome-wide ChIP-seq co-occupancy recover known protein complexes after control for peak density,
hotspots and cell context? Only after that check may unannotated DBP modules be considered. Outputs are called
*DBP co-occupancy modules*, never protein complexes. Pooled co-occupancy across cell types is not co-binding in
one cell.

**Region universe.**
- Fixed 500-bp genome bins, so overlap chaining is impossible.
- ENCODE v2 blacklist bins are removed.
- The universe is the bins occupied by at least one selected protein.

**Proteins.**
- HGNC-symbol targets of v1 Output A in the classes Sequence-specific TF, Architectural/cohesin, Chromatin remodeler,
  Histone reader, Histone writer/eraser and Transcription machinery (annotation v1.1).
- At least 3 experiments in the analysed context.
- Other/ambiguous and non-gene labels are excluded.

**Occupancy.**
- Protein p occupies bin b if b overlaps peaks of at least k_p distinct experiments of p.
- k_p = max(2, ⌈0.05 · n_exp(p)⌉), a reproducibility floor that scales with how often p was profiled.
- Proteins with fewer than 500 occupied bins are dropped.

**Similarity**, for every protein pair with bin sets A and B:
- J = |A∩B| / |A∪B| (baseline);
- O/E = |A∩B| · N / (|A| · |B|), with N the universe size; log2 O/E corrects for occupancy breadth.

**Hotspot control.** The analysis is repeated without HOT bins, defined as the top 1 % of bins by number of
occupying proteins.

**Cell-context control.** The analysis is repeated within K-562 and within Hep G2 (experiments of that ChIP-Atlas
cell type only, k_p = max(1, ⌈0.05 · n⌉), at least 2 experiments).

**Clustering.** Average-linkage hierarchical clustering on 1 − J and on −log2 O/E. The heatmap carries a
protein-class colour bar.

**Benchmark** (independent reference: Complex Portal human, 2026-10-21, UniProt → HGNC).
- Pairs of selected proteins that share a complex versus all other pairs:
  - AUROC of J and of log2 O/E;
  - the median within-complex similarity against 1,000 size-matched random sets, tested on both Jaccard and log2 O/E.
  - Jaccard is the primary metric. log2 O/E penalises broadly occupied proteins: CTCF and cohesin have the highest
    Jaccard (0.585) but no O/E excess. Genome-wide AUROC is Jaccard 0.76 (0.81 without HOT bins) against O/E 0.59
    (0.78).
- Named checks, which are expectations to test, not results:
  - cohesin (RAD21, SMC1A, SMC3, STAG1/2) and CTCF;
  - BAF (SMARCA4, SMARCC1/2, SMARCB1, ARID1A/B);
  - Mediator (MED*);
  - PRC2 (EZH2, SUZ12, EED);
  - NuRD (CHD4, HDAC1/2, MTA1/2).

**Outputs:** `result/cooccupancy_v1/<context>/`
- `proteins.tsv`, `pair_similarity.tsv.gz`, `linkage.tsv`;
- `heatmap_jaccard.png`, `heatmap_log2oe.png`;
- `benchmark.json`, `complex_recovery.tsv`.

## 14. Experiment-level clustering (user request 2026-10-20)

**Question.** Is variation in genome-wide DBP binding patterns driven mainly by protein identity, by cell context or
by technical factors? Large experiment clusters are not interpreted biologically until this is answered.

**Data.**
- v1 protein experiments (TF + Pol) with at least 1,000 peaks.
- Features: 500-bp non-blacklist bins occupied by at least 20 experiments. A fixed random 500,000 of them (seed
  20261021) keeps the matrix tractable while preserving pairwise structure.
- An experiment occupies a bin if any of its peaks overlaps it.

**Representation.**
- TF-IDF on the binary experiments × bins matrix, then truncated SVD (50 components).
- The correlation of each component with log10 peak count is reported. Components with |r| > 0.7 are dropped as
  depth axes.
- Rows are L2-normalised.

**Attribution.** In the 10-nearest-neighbour graph (cosine), for each factor:
- the observed fraction of neighbours sharing the label, against the expectation Σ p_label²;
- AMI between 50 k-means clusters and the label.

Factors:
- protein (HGNC symbol, else antigen);
- protein class;
- cell type;
- tissue;
- peak-count decile (technical);
- antibody status (technical).

**Controlled views.**
- Within K-562 and within Hep G2: does protein identity or class organise the experiments?
- Within CTCF and within the next most profiled HGNC proteins: does cell type or tissue organise them?

**Outputs:** `result/experiment_clustering_v1/`
- `attribution.tsv`, `clusters.tsv` (experiment → cluster plus metadata);
- `svd_depth_correlation.tsv`;
- `tsne.png`, coloured by class and by the top cell types;
- `controlled.tsv`.

## 15. Region-level occupancy classes (user request 2026-10-20)

**Question.** Which combinations of DBPs recur at the same genomic regions (occupancy grammar)? Classes are
descriptive. They depend on which proteins were profiled.

**Data.** The protein × bin occupancy of §13 (context `all`: same proteins, k_p rule and blacklist removal). Regions
are 500-bp bins occupied by at least 3 selected proteins.

**Method.**
- TF-IDF on bins × proteins, truncated SVD (30 components), L2-normalise.
- MiniBatch k-means for k = 10, 20 and 30; the silhouette on a 50,000-bin sample is reported, and k = 20 is used
  unless the silhouette clearly prefers another k.

**Per class:**
- number of bins and median proteins per bin;
- the HOT fraction (top 1 % of bins by protein count);
- protein-class composition;
- the 15 most enriched proteins (in-class occupancy ÷ overall occupancy, at least 10 % in-class occupancy).

**Outputs:** `result/region_classes_v1/`
- `classes.tsv`, `class_proteins.tsv`, `silhouette.tsv`;
- `region_classes.bed.gz` (+ `.tbi`, `.bb`; name = class) for IGV.

## 16. v1.1 validation gate (GPT review of §13–§15, 2026-10-20: REVISE)

Scope is limited to the four L1 items. No new features. Novel-module nomination waits for this gate.

**L1-a Study provenance** (`study_provenance.tsv`).
- Source: the ENA portal API (`read_experiment`). It gives the SRA study for every hg38 ChIP-Atlas experiment of
  class TF / Pol / Histone / ATAC / DNase: `secondary_study_accession` (SRP/ERP/DRP) and `study_accession` (PRJ).
- The study unit is the SRA study, which normally maps one-to-one to a GEO series.
- Experiments without an ENA record become their own singleton study and are flagged.
- Limitation: reuse of the same raw reads under different studies cannot be detected from these fields.

**L1-b Complex recovery validation** (`complex_recovery_validation.tsv`, `benchmark_validation.json`). All on the
non-HOT Jaccard.
- Breadth-matched null. Each complex member is replaced by a random protein from the same occupancy-breadth decile
  (|occupied bins|), 10,000 draws, giving p = (1 + #null ≥ obs) / (1 + n). BH-FDR is applied over all complexes and
  separately over distinct member sets. The unadjusted size-matched p of v1 is kept.
- Pair-level metrics: AUROC and PR-AUC (average precision), each with a 95 % CI from a protein-level bootstrap
  (1,000 resamples of proteins). Pairs are not independent, so proteins are resampled.
- Matched universe: K-562 and Hep G2 are recomputed on the proteins present in both contexts.
- Per-complex coverage:
  - members in Complex Portal (HGNC-mapped) versus members in the PMA set;
  - experiments and studies per member.
- Physical versus functional. Cohesin core (RAD21, SMC1A, SMC3, STAG1, STAG2) is a physical complex. CTCF–cohesin
  pairs are scored separately as a known functional association.

**L1-c Study-level leave-one-out** (`pair_study_validation.tsv`).
- Candidate pairs:
  - all Complex Portal same-complex pairs;
  - the top 300 non-Complex-Portal pairs by non-HOT Jaccard in context `all`.
- For each pair:
  - studies per protein and studies shared by both;
  - LOSO Jaccard: remove every experiment of one study at a time, recompute both occupancies, and report the
    minimum;
  - cross-study Jaccard: A's experiments from studies that did not profile B, against B's experiments from studies
    that did not profile A.
- Thresholds are recomputed on each subset: k = max(min(2, n), ⌈0.05 n⌉).
- Status:
  - `insufficient_independent_evidence` if either protein comes from a single study or the cross-study sets are
    empty;
  - `study_robust` if the cross-study Jaccard is at least half of the full Jaccard and at least the 95th percentile
    of all pairs' non-HOT Jaccard;
  - otherwise `study_dependent`.

**L1-d Experiment-level confounder sensitivity** (`experiment_confounder_sensitivity.tsv`). The same TF-IDF/SVD
embedding as §14 is evaluated under five variants:
- V0 raw;
- V1 without SVD component 1;
- V2 neighbours restricted to the same peak-count decile;
- V3 neighbours restricted to other studies;
- V4 = V2 + V3.

For protein, cell type, protein class and tissue, each variant reports the observed and expected same-label
fraction, the fold enrichment, and κ = (obs − exp) / (1 − exp). κ is used to compare factors, because fold
enrichment is not comparable across label sets with different numbers and frequencies of levels. Within-cell-type
and within-protein views are repeated under V4.

**Provenance note.** The Complex Portal file sits in `raw/2026-10-21/` because the directory was named after the UTC
date. It was downloaded on 2026-10-20 at 21:30 EDT (2026-10-21 01:30 UTC). Raw stays append-only, so this is recorded
in a provenance note rather than by renaming. The seed value 20261021 is an arbitrary fixed constant.

**Addendum after the run (2026-10-21; post hoc, declared as such).** The cross-study criterion only excludes studies
that profiled both proteins. It misses a single study that dominates one protein's occupancy. For example, SRP158854
(58 ESR1 experiments, no CTCF) supplies half of ESR1's occupied bins, and dropping it lowers the CTCF–ESR1 Jaccard
from 0.366 to 0.025 (`18_pair_loso_diagnostic.py`). The strict tier `study_robust_loso` therefore also requires
LOSO-min Jaccard ≥ 0.5 × the full Jaccard. It is a filter on `pair_study_validation.tsv`, not a recomputation. The
pre-registered `study_robust` counts are still reported.

## 17. v1.2: v1.1 revisions and core L2 sensitivity (GPT review of v1.1, 2026-10-21: REVISE, L2 approved)

Scope: the four items GPT asked for. High-confidence novel-module nomination stays closed. No data are deleted:
SRP158854 and the Hep G2 BAF experiments are flagged, not removed.

**A. Study independence** (`20_study_influence.py`).
- Provenance coverage is reported for the protein input itself. All 39,099 protein experiments are mapped; 8 are
  singleton studies.
- Robustness tiers per candidate pair, from `pair_study_validation.tsv`:
  - `tier1_high`: cross-study robust (§16) and LOSO-min ≥ 0.5 × full;
  - `tier2_moderate`: cross-study robust, but sensitive to one study;
  - `insufficient_coverage`;
  - `study_dependent`.
- Context replication, a separate dimension from study robustness. For each cell type with experiments for both
  proteins, recompute the cross-study Jaccard inside that cell type: A from studies that did not profile B in that
  cell type, and vice versa. Thresholds use the within-context floor of 1 (§13). The pair is `context_replicated`
  if, in at least one cell type, this Jaccard is ≥ 0.5 × the full Jaccard and ≥ the 95th percentile of all pairs.
- Study influence per protein. For every protein with ≥ 2 studies and every one of its studies s, recompute the
  occupied bins without s (threshold recomputed on n − n_s). Report:
  - `influence = 1 − Jaccard(occ_full, occ_without_s)`;
  - the most influential study and the change in the number of occupied bins.

  Proteins with maximum influence ≥ 0.5 are flagged. This is provenance QC, not a filter.
- Targeted QC, metadata only, no deletion:
  - SRP158854: per-experiment cell type, antibody, peak count and title;
  - Hep G2 BAF (SMARCA4, SMARCC2, SMARCE1): experiments, studies, peak counts, occupied bins and pairwise
    experiment-level Jaccard, against K-562.

**B. Statistical additions.**
- Complex recovery (`19_protein_sensitivity.py`):
  - The representative of each distinct member set is now its minimum-p entry. v1.1 used the first entry in
    Complex Portal order; both are reported. BH is then rerun over the distinct sets.
  - HOT/null decomposition on the same complexes:
    - all bins + size-matched null;
    - non-HOT + size-matched null;
    - non-HOT + breadth-matched null.
  - The CI is labelled "protein-resampling CI". The FDR is labelled "breadth-matched empirical FDR".
- Matched universe (K-562 / Hep G2): precision at the top 20 and top 50 pairs, and the overlap of the top-50 pair
  sets between the two cell types.
- Experiment level (`17_experiment_sensitivity.py` v1.2):
  - Expected same-label fraction conditioned on each anchor's eligible-neighbour set. V0/V1 use all other
    experiments; V2 the same peak decile; V3 other studies; V4 both. The expectation is averaged over anchors, and
    κ is recomputed from it.
  - Empirical p from 200 label permutations within peak-decile strata, with the neighbour graphs fixed.
  - For each view, the number of anchors with a full set of 10 eligible neighbours.

**C. Core L2 sensitivity.**
- Bin size and threshold (`19_protein_sensitivity.py`, `PMA_BIN`, `PMA_KFRAC`). Context `all` is rerun at:
  - 250 / 500 / 1000 bp with k = 5 %;
  - 500 bp with k = 2.5 % and 10 %.

  Each variant reports AUROC and PR-AUC (protein-resampling CI), FDR counts, and the named physical complexes.
  A conclusion is stable if the AUROC CI overlaps the 500-bp/5 % CI and the named complexes keep FDR ≤ 0.05.
- Region classes (`21_region_stability.py`, on the §15 matrix):
  - cross-resolution agreement for k = 10/20/30 (ARI, NMI and best-match overlap per k = 20 class);
  - 5 seeds at k = 20 (ARI against seed 20261021);
  - 5 × 80 % bin subsamples (ARI on shared bins);
  - non-HOT re-clustering (ARI on shared bins);
  - per-class stability as the median best-match Jaccard across reruns.

  C07 (HMGA1) and C09 (PPARA) are checked against the study-influence table.

Compute: SGE `all.q`, 8 slots, h_vmem = 48G, chained with `-hold_jid` where outputs are shared. Outputs go to
`result/validation_v1_2/{protein,sensitivity/<variant>,experiment,region,study}`.

## 18. Hotspot and open-region thresholds, then motif enrichment (user request 2026-10-21)

**Request.** Which motifs are enriched in the hotspot regions, ranked by significance. Before that, show the
per-region distributions of (a) distinct ChIP-seq proteins (histone excluded) and (b) ATAC and DNase open-chromatin
evidence, so that the user can set the thresholds that define "hotspot binding" and "open" regions.

**Step 1 — distributions (this round).**
- Unit: 500 bp genome bins (chr1–22, X, Y), the same bin as §13–§15.
- Inputs: the blacklist-masked evidence tracks (`tracks_noBlacklist/proteins`, `tracks_atac_noBlacklist/atac_{experiments,celltypes}`,
  `tracks_dnase_noBlacklist/dnase_{experiments,celltypes}`), i.e. after the §12 experiment filter
  (ATAC 18,651, DNase 2,086 experiments).
- Per-bin value = maximum of the track inside the bin (`23_hotspot_bins.py`). Proteins = distinct protein labels
  (TF, CAP, Pol and other non-histone targets).
- Outputs: histograms and survival curves (bins ≥ x), quantile and threshold tables, and the joint relation of
  protein count with ATAC/DNase fraction (`24_hotspot_distribution_panels.py`).
- QC: chr21 brute-force check on 300 non-zero and 300 zero bins per track; per-track max equals the bedGraph max.

**Step 2 — motif enrichment (after the user fixes the thresholds; not run yet).** Hotspot set = bins at or
above the protein threshold, merged; background = bound or open bins below the threshold, matched for GC and
open-chromatin level, so that the enrichment is not driven by promoter GC or accessibility alone. Motifs from
`motif_reference` (Step 3 clustered set); test with a standard enrichment tool (e.g. SEA/HOMER), ranked by
adjusted p. The exact design is fixed once the thresholds are chosen.

### 18.1 Frozen hotspot definition (user decision 2026-10-21, after GPT review)

The distributions are continuous with no natural cut, so the thresholds are operational, pre-specified quantiles
(not significance levels: top 5% ≠ p < 0.05). They are frozen before any motif analysis.
- Two tiers, nested: **high** = top 5%, **extreme** = top 1%. Each quantile is computed among bins with value > 0 in
  that track.
- **Protein binding hotspot:** P_b = max distinct non-histone proteins in the bin ≥ Q(P | P > 0).
- **Open-chromatin hotspot:** the ATAC tier and the DNase tier are computed separately, and a bin must pass both
  (cross-assay concordance). The per-assay sets are kept in `per_assay/`.
- Adjacent passing bins on a chromosome are merged into regions. These are annotation units, not independent
  motif sites.
- Record the absolute thresholds with the data version; they will shift when ChIP-Atlas grows.
- Code: `25_hotspot_beds.py`. The result is in `result/hotspot_regions_v1/` (4 BEDs + bigBed + summary.json).
- Names: "ChIP-derived protein occupancy hotspot" and "cross-experiment accessibility hotspot". They are not a
  measure of binding strength, of co-binding in one cell, or of function.
- Sensitivity checks to follow:
  - motif results under both tiers;
  - promoter versus distal strata;
  - GC/CpG- and accessibility-matched backgrounds;
  - dominance of single studies or cell types.

### 18.2 v2: four tiers (user request 2026-10-21)

The user asked for two looser tiers. Tiers are now named by percentile and are nested:
top1 ⊂ top5 ⊂ top10 ⊂ top20, i.e. Q0.99 / Q0.95 / Q0.90 / Q0.80 among positive bins.

All other rules are unchanged from §18.1. v1 `high` and `extreme` equal v2 `top5` and `top1`.

The `tier` column now holds the strictest tier that any bin of the region reaches.

Output goes to `result/hotspot_regions_v2/`. v1 is kept unchanged.

### 18.3 Motif enrichment in hotspot regions (user request 2026-10-21)

**Question.** Which known motifs are enriched in each hotspot set, ranked by significance?

**Sequence units.**
- One 500 bp sequence per hotspot region: the region's summit bin.
  - Protein hotspots: the bin with the most proteins.
  - Open-chromatin hotspots: the bin with the highest mean ATAC/DNase rank.
- This avoids counting long merged regions more than once.
- Regions are sampled at random (seed 1) down to at most 50,000 per set. This bounds run time; the effect sizes
  are already precise at that size.

**Controls.** Built with HOMER 5.1 `homer2 bg`, at the user's suggestion. It selects genomic sequences that match
the targets in GC content and k-mer composition.
- **G (genome-matched):** sampled from blacklist-free bins outside the top20 hotspot set of the same class. All
  8 sets (2 classes × 4 tiers) get this control.
- **A (accessibility-matched, protein hotspots only):**
  - Candidate bins come from outside the same-tier protein set. A chr21 test showed that bins outside protein top20 are
    almost never as open as the targets (pool shortfall 60–90%), so the control for tier t is bins with fewer
    proteins than tier t at matched openness.
  - They are stratified on the mean ATAC/DNase rank into 20 strata, defined by the target's quantiles, with 5
    candidates per target bin in each stratum.
  - `homer2 bg -bg` then picks the GC/k-mer-matched subset.
  - Control size = min(targets, pool / 2). How well the matching succeeds (shortfall, median open score) is reported.
  - This answers which motifs mark protein hotspots beyond what openness alone explains.
- **S (promoter / distal strata):** for top5 of both classes, target and control are split into promoter (TSS
  ±1 kb, GENCODE v32 transcripts from the 10x GRCh38-2020-A genes.gtf) and distal sets, each with a G control
  drawn from the same stratum.
- Control size = min(2 × targets, 100,000).
- Implementation note (first run): `homer2 bg -bgr` over the whole eligible genome needed about 40 GB and
  failed with bad_alloc. G controls therefore use explicit candidates: up to 500,000 random eligible 500 bp bins
  per class/stratum (separate RNG), passed with `-bg`, the same mode as A.

**Motif libraries.**
1. JASPAR 2026 CORE vertebrates non-redundant: 1,019 motifs, from the PMA v0.3 raw layer.
2. The PMA Step 3B consensus representatives at three tiers: HIGH (2,059 clusters), MEDIUM (995) and LOW (542).
   The three tiers are clustering resolutions, not quality grades.

**Test.** MEME 5.5.9 SEA with the HOMER control (`--n`), reporting all motifs. Motifs are ranked by SEA q-value
(log scale), with the enrichment ratio, TP% and FP% reported alongside.

**Reading the results.**
- Motif enrichment is a property of the sequences: it shows which motif classes these regions carry.
- It does not show which protein binds there.
- Promoter-associated GC-rich motifs are expected to dominate control G. Controls A and S are the checks on that.

**Run 1 → run 2 revision (2026-10-21, before any result was read).**
- *Problem.* HOMER `homer2 bg` sorts targets into 10 GC/CpG bins and trims every bin to the bin with the fewest
  matches. Run 1 drew G candidates only from outside top20, which removes nearly all CpG islands. The CpG-rich
  bin then found almost no matches, and the controls collapsed to 40 (protein top1), 920 (protein top5) and
  220 (protein top5 promoter) sequences. A controls had the same problem in milder form, at 2,800–9,700.
- *Fix.*
  - The G pool for tier t excludes only the tier-t set of the same class.
  - It includes every eligible promoter bin, plus 500,000 random eligible distal bins.
  - The promoter and distal strata draw from those parts only.
  - A pools take 20 candidates per target in each stratum.
  - Targets are capped at 10,000 per set and controls are 2 × targets. SEA run time scales with sequence length
    × motifs, and 50,000 × 500 bp per set was far beyond what the question needs.
- *Check.* `runs_summary.tsv` flags any comparison whose control is under half the requested size as
  SMALL_CONTROL.

## 19. Mouse mm10 build (user request 2026-10-30)

**Request.** Build the mouse (mm10) atlas from ChIP-Atlas with the same method as hg38. User decisions 2026-10-30:
- scope = core Output A/B (§3–§8) + light per-target BEDs (§10) + evidence tracks (§11–§12, incl. blacklist split);
  co-occupancy, clustering, hotspots and motif enrichment (§13–§18) are out of scope for this build;
- gene nomenclature = MGI only (no human orthology layer).

**19.1 Code.** One code path for both genomes. `PMA_GENOME = hg38 (default) | mm10` selects
`scripts/04a_chipatlas/genome_config.py` (raw release, archive and reference file names, gene namespace, release
name, tabix checks). With the default, hg38 outputs are byte-identical to the pre-change code (checked on the full
experimentList for `01`, and on synthetic chr1 rows for `02`). Output names: `PMA_chipatlas_mm10_*`.
Column names follow the namespace: `antigen_mgi_symbol`, `antigen_mgi_id` take the place of the HGNC columns at the
same positions (BED6+18 column 9–10), so downstream scripts, which use column positions, need no change.

**19.2 Data.** Separate dataset `DATA/2.PROJECTS/PMA/occupancy_chipatlas_mm10/` (`config/pma_env.sh` switches
`PMA_OCC*` on `PMA_GENOME`). Raw release `raw/2026-10-30/`:

| File | Release | Note |
|---|---|---|
| `experimentList.tab` (+ file/antigen/celltype lists) | 2026-10-14 | same metadata snapshot as hg38 v1 |
| `allPeaks_light.mm10.05.bed.gz` | 2026-09-26 | 15,427,670,963 bytes, MACS2 q < 1e-5 |
| `reference/MRK_List1.rpt` | MGI, downloaded 2026-10-30 | markers incl. withdrawn (previous symbols) |
| `reference/mgi.gaf.gz`, `go-basic.obo` | GO Consortium | GO annotations of MGI genes; ontology |
| `reference/mm10-blacklist.v2.bed.gz` | Boyle-Lab v2 | |
| `reference/mm10.chrom.sizes` | UCSC | UCSC contig names, as in the ChIP-Atlas peaks |

Release name `PMA_ChIPAtlas_mm10_20260926peaks_20261014meta_v1`.

**19.3 Mouse-specific rules (rules_version stays 4a.v1; antibody/context/QC rules unchanged).**
- *Antigen → MGI.* Same priority as §5.1 on MGI genes (Marker Type `Gene`): exact approved symbol > manual exception
  (`config/chipatlas_antigen_exceptions.mm10.tsv`) > unique previous (withdrawn → current) > unique synonym.
  Metadata check (28,085 in-scope experiments: 24,555 TFs and others + 3,530 RNA polymerase): approved_exact 21,544,
  complex_or_family 3,532, tag_only 2,363, non_gene_target 427, previous_symbol 196, manual_curated 20, unmapped 3
  (`Fo`). Upper-case spellings (INO80, CEBPA, RAF1) are manual exceptions, not a new status. `RFP` is a tag, not the
  unrelated withdrawn MGI symbol.
- *TF set and `target_category`.* No Lambert-equivalent list from MGI; the TF set is MGI genes annotated to
  GO:0003700 (DNA-binding transcription factor activity) or a descendant; NOT-qualified and ND annotations excluded.
  The chromatin-regulator test (§5.1) runs on the names of the matched GO rule terms in place of HGNC gene groups.
- *Protein class annotation for tf/cap tracks and the class split.* hg38 uses the curated v1.1 table. For mm10,
  `29_go_class_annotation.py` writes `PMA_chipatlas_mm10_protein_class_annotation.go_v1.csv` (same columns): first
  matching GO rule in the order TF (GO:0003700) > histone writer/eraser > transcription machinery > histone reader >
  chromatin remodeler > architectural/cohesin; CTCF/CTCFL by symbol rule (as hg38 v1.1); else Other/ambiguous.
  Rule terms are checked against the ontology; a missing or obsolete term stops the run. The order was chosen on the
  685 genes shared with hg38 v1.1 (upper-cased symbol, a calibration check only): 559 agree (81.6 %). Draft class
  counts (897 genes): TF 429, writer/eraser 65, machinery 51, reader 41, remodeler 36, architectural 14, other 261.
  **The mouse tf/cap tracks are GO-rule classes, not curated classes**; say so wherever they are used.
- *Histone labels.* `08_histone_labels.py` unchanged, fed from the light histone targets (`run_tracks.sh labels`).

**19.4 Fix found by the mm10 smoke test (applies to both genomes).** `experimentList.tab` has one row per
(experiment, genome); 411,513 IDs appear more than once (e.g. mm10 and mm9). `03_finalize.py` kept the last row per
ID, so archive experiments were mis-counted as `other_genome` in the reconciliation report. Categories now use the
row of the build genome. Peak inclusion was never affected (`01` filters on genome). The hg38 v1 report would change
only in this category split if rebuilt.

**19.5 Run (Argos, SGE all.q).** Job chain, each step with `/usr/bin/time -v` and a status file:
1. `run_4a.sh` (core);
2. after 1: `run_light.sh protein`, `run_tracks.sh classes`, `protein`, `pol`, `mask_protein`, `mask_pol`;
3. after 1: `run_tracks.sh filter`, `run_light.sh histone`, `labels`, `histone`, `mask_histone`;
4. after 3: `atac`, `mask_atac`; `dnase`, `mask_dnase`;
5. after 2–4: IGV sessions (`09_igv_session.py`, raw / noBlacklist / blacklistOnly).
hg38 peak RSS was ≤ 3.2 GB per step; mm10 is smaller (15.4 vs 21.4 GB archive).

**19.6 Checks before use.** Same gates as hg38: reconciliation `rows_accounted`, zero sort violations, tabix
retrieval, per-step QC JSON PASS (light BED, tracks, mask), and a review of the GO-rule class table.
