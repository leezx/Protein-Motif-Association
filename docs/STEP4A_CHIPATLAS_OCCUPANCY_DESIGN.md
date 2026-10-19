# Step 4a — ChIP-Atlas hg38 protein occupancy atlas: design

## PI target revision — coordinate-unique BED6 (2026-10-18; design gate)

The previously approved v1 below remains a valid **TF/RNA-polymerase subset** and must not be
described as all human ChIP-seq. The PI's final target is a coordinate-unique, losslessly
traceable hg38 reference of all eligible ChIP-Atlas ChIP-seq peak records. This revision is a
proposed build contract; no new Argos processing is authorized until this contract and its
implementation have passed the current-HEAD review gate.

### Scope

- Use the already staged `allPeaks_light.hg38.05.bed.gz` archive and matching metadata snapshot;
  do not redownload or overwrite raw inputs.
- Include metadata `genome=hg38` experiments whose exact `antigen class` is `TFs and others`,
  `RNA polymerase`, or `Histone`.
- Exclude `Input control`, `ATAC-Seq`, `DNase-seq`, and `Bisulfite-Seq`. Also exclude
  `Unclassified`, `No description`, annotation/aggregate tracks, and any unrecognized class from
  the primary reference; report each class and row count separately. Missing metadata is a
  separate quarantine category, not an inferred inclusion.
- The deliverable is specifically **all eligible hg38 ChIP-seq peaks**. It does not silently
  include hg19 or liftover coordinates. Report that assembly boundary in the manifest.
- ChIP-Atlas exposes hg38 and hg19 as separate human reference assemblies and classifies tracks
  by experiment class; the exact class strings and available assemblies must be checked against
  the pinned metadata snapshot, with the official [ChIP-Atlas Peak Browser](https://chip-atlas.org/peak_browser)
  and [Agent Guide](https://chip-atlas.org/agents) as reference sources.
- Preserve the source q < 1e-5 call set. Do not apply a new q threshold, blacklist filter,
  canonical-chromosome filter, or biological-quality filter during this aggregation.

### Primary output and identity

`PMA_chipatlas_hg38_unique_regions.bed.gz` is exactly BED6, 0-based half-open, with no header:

| Column | Contract |
|---|---|
| chrom, start, end | Exact source coordinates; coordinate key is `(hg38, chrom, start, end)`. |
| name | Stable `region_id = PMA_hg38_<full SHA-256>`. Hash the UTF-8 serialization of `PMA-region-v1`, `hg38`, source `chrom`, decimal `start`, and decimal `end`, joined by literal U+0009 TAB bytes with no spaces or trailing newline. Preserve source `chrom` spelling. Verify no hash collision. ID must not depend on input order or experiment membership. |
| score | `min(1000, number of distinct supporting experiment IDs)` for BED compatibility; exact uncapped count is in the region summary. This is support count, not binding strength or biological replicate count. |
| strand | `.`; the source intervals are unstranded. |

Only exact `(chrom,start,end)` duplicates collapse. Overlapping, nested, or nearby intervals with
different boundaries remain separate records; do not merge intervals or recenter summits.
Duplicate source rows from one experiment contribute one region–experiment pair, while every
source row remains represented in provenance.

### External linkage outputs

All large outputs remain outside this repository under the PMA external data workspace:

1. `region_experiment.tsv.gz`: unique `(region_id, experiment_id)` many-to-many links.
2. `peak_provenance.tsv.gz`: one row per included source peak row, including stable source-record
   identity (archive SHA-256 plus source row ordinal), `region_id`, `experiment_id`, and original
   peak fields. This preserves duplicate source rows without duplicating BED6 regions.
3. `region_summary.tsv.gz`: `region_id`, exact coordinates, distinct supporting experiment count,
   and source peak-row count.
4. `experiment_metadata.tsv.gz`: included experiment IDs and source metadata needed to interpret
   antigen, class, cell type, assay, genome, and source release.
5. Reconciliation/QC reports for included, excluded-by-class, other-genome, missing-metadata,
   malformed/rejected, and metadata-without-peaks records.

### Required acceptance checks before declaring the target complete

- Every source archive row is assigned exactly once to a documented mutually exclusive status;
  no unexplained loss. The old v1 arithmetic reconciliation is not proof that the revised class
  selection or provenance is correct.
- Included rows join to a unique metadata record with `genome=hg38` and one of the three included
  classes. Report class-level experiments, source rows, and resulting unique regions.
- BED6 has exactly six columns, valid hg38 half-open coordinates, no duplicate coordinate keys,
  and one unique `region_id` per coordinate. Its row count equals the number of unique included
  coordinate keys.
- The number of distinct `(region_id, experiment_id)` pairs in linkage equals the independently
  computed cardinality; every included source row maps to exactly one region and experiment, with
  no orphan links or omitted provenance.
- Deterministic chromosome-order sorting, bgzip/tabix indexing, and random interval queries agree
  with the unindexed sorted source output.
- Record immutable input hashes, metadata release, code commit, rules/schema versions, command,
  and output hashes. A repeat build from the same inputs and code must reproduce normalized
  content hashes.

The precise class inventory and all counts must be read from the pinned metadata and archive
during the later, separately approved Argos run. The previously reported 1,843,573,973
`out_of_scope_class` rows are **not** assumed to be all Histone; class-level counts remain
unverified until that run.

### Implementation-stage contract clarification (2026-10-19)

- Mutually exclusive source-row `primary_status` precedence is: `MALFORMED_SOURCE_ROW`,
  `INVALID_COORDINATE`, `UNSUPPORTED_CHROM`, `MISSING_METADATA`, `AMBIGUOUS_METADATA`,
  `OUT_OF_SCOPE_GENOME`, `OUT_OF_SCOPE_CLASS`, then `INCLUDED_PAIR_FIRST` or
  `INCLUDED_PAIR_ADDITIONAL`. The two included-pair states are assigned after coordinate/experiment
  grouping; duplicate source rows remain in provenance.
- A region's 3-bit membership mask records which of the three included experiment classes support
  it. The seven possible nonzero masks are mutually exclusive; their counts must sum to the global
  unique-region count. Also report overlapping class-specific unique-region counts.
- Keep the approved two external sorts in the core build: coordinate/experiment/source-row grouping,
  then source-row ordering for provenance. The builder records collision QC as `NOT_RUN` and the
  negligible-assumed SHA-256 risk honestly. Run a separate release-level third sort over one compact
  `(region_id, chrom, start, end)` record per unique region once for the formal release. Adjacent
  full-ID comparison must verify zero duplicate IDs and zero different-coordinate SHA-256
  collisions. This QC does not reread or reorder the raw archive or provenance table.
- The approved builder launcher must place Python and every child process in a cgroup with a hard
  44 GiB memory cap and swap disabled; GNU sort starts at `-S 4G --parallel=2`. `sort -S` alone is
  not a process-memory limit. If the cgroup cannot be created, fail closed. The actual disk peak is
  unknown until a read-only Argos preflight estimates scratch/output needs from the pinned inputs;
  do not infer disk feasibility from the memory cap or start the full build without adequate space.
- The builder writes 48 deterministic random 1 kb BED0 windows and compares each indexed `tabix`
  result byte-for-byte with the streaming unindexed BED6 rows captured during construction. The
  separate release-ID QC also verifies BED6 sort order, coordinate validity, and stable-ID hashes.

These are implementation-stage proposals, not tested behavior or resource measurements. No Argos
data or environment was accessed while adding them.

Historical v1 status: **contract approved** (ChatGPT, 2026-10-17: APPROVE WITH REVISIONS; the revisions are
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
