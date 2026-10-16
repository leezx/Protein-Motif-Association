# Step 2 — Multi-source motif import, harmonisation and QC (design)

Status: revision 1, 2026-10-14, after ChatGPT pre-compute review (REQUEST
CHANGES, F1–F7). No Step 2 compute has been run.
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
| Factorbook | downloaded 2026-10-15 | HT-SELEX ZMotif catalog | 6,700 | Downloaded manually in a browser after factorbook.org returned HTTP 429 to scripts (amendment 2026-10-15). Motif IDs are ENA run accessions. TF, ligand and batch come from ENA run reports for PRJEB9797 (Yin 2017) and PRJEB3289 (Jolma 2013); all runs resolve. |

The v0.2 raw layer is a **snapshot of the sources available on
2026-10-14**. It is not a claim of a complete human motif collection.

Source-file caveats found during fetch:
- **CisBP species archive:** the archive's `PWMs_all_motifs` file
  interleaves matrices with server-side unzip log lines. The ID-to-matrix
  assignment is ambiguous, so this file is **not used**. Matrices come
  from `EntireDataset_PWMs.zip`, which has one file per motif ID (all
  7,434 human IDs present). At import, each file's name is checked
  against the motif ID it is loaded for. Totals alone are not trusted.
- **Codebook:** 4 PWMs contain all-zero spacer rows, set to uniform and
  counted (Step 1).

## 3. Motif identity (frozen)

- `pma_id` = `<SRC>_<source_motif_id>`, where SRC ∈ {CB26, JA26, JU26,
  HO14, CI310, FBC, FBS}. JU26 marks JASPAR UNVALIDATED; FBC marks
  Factorbook ChIP; FBS marks Factorbook HT-SELEX. The ID is stable across
  rebuilds of the same source version.
- **SELEX experiment key** (amendment 2026-10-15, implements §5):
  `SELEX:<publication>.<ligand>.<batch>` for Yin 2017 and Jolma 2013.
  It is derived from ENA sample aliases (Factorbook) and from HOCOMOCO
  `origin`, so motifs from the same SELEX experiment carry the same
  experiment ID across sources. All cycles of one experiment share a
  key.
- Each motif also stores `source_db`, `source_version`, `fetch_date`,
  `source_motif_id`, `source_file` and `source_status`.
- **Hash semantics:**
  - `raw_matrix_hash` is the sha1 of the source matrix exactly as
    parsed (source units: counts or probabilities). It checks source
    integrity.
  - `normalized_matrix_hash` is the sha1 of the row-normalised matrix.
    It identifies strict duplicates across sources.
  - **Serialisation (both hashes):** rows in motif order, columns
    A,C,G,T; little-endian IEEE-754 float64 (`numpy '<f8'`, C order);
    the byte string is prefixed with the length as uint32 little-endian.
    Gap rows are hashed as they were in the source (all zero) for
    `raw_matrix_hash`, and as uniform for `normalized_matrix_hash`.
    A unit test pins the hash of a fixed matrix.
  - `rounded_equiv_group` groups motifs whose normalised matrices agree
    at 4 decimals, in either orientation. It is not called an exact
    duplicate. Each member records `equiv_orientation` (`fwd`/`rc`).
    Members are flagged, never merged.
- **Gap rows:** `gap_mask` is the list of positions that were all-zero
  in the source. They are set to uniform for computation only. Rows that
  were genuinely uniform in the source are not in the mask.

## 4. Evidence model (frozen)

"Which protein's experiment produced the motif" is kept separate from
"does that protein directly recognise the sequence". The source database
name is never a quality proxy.

| Field | Values |
|---|---|
| `assay_class` | `in_vitro_selection` (HT-SELEX, Methyl-HT-SELEX, GHT-SELEX, SELEX, CAP-SELEX, SMiLE-seq, B1H, DAP-seq), `in_vitro_array` (PBM), `in_vivo_occupancy` (ChIP-seq, ChIP-exo, CUT&RUN), `literature_compiled` (Transfac, Misc, COMPILED), `unknown` |
| `assayed_target` | the protein, or the protein assembly for heterodimer experiments, whose experiment produced the motif. Empty if unknown. |
| `motif_tf_assignment` | the TF(s) the source assigns the motif to (source-native; may differ from `assayed_target`) |
| `assignment_basis` | `in_vitro_binding`, `occupancy_derived`, `homology_transfer`, `literature`, `unknown` |
| `direct_binding_evidence` | `supported` (in-vitro binding assay of this protein or assembly), `not_established` (occupancy-derived or literature-only), `transferred` (homology), `unknown` |
| `source_link_status` | source-native link evidence, kept verbatim (CisBP `TF_Status` D/I; Codebook Direct/Inferred). This is **not** used as `direct_binding_evidence`. |
| `species_basis` | `human`, `mouse_ortholog`, `other_vertebrate`, `unknown` |
| `source_quality` | source-native grade, kept verbatim (HOCOMOCO A–D; JASPAR CORE/UNVALIDATED) |
| `curation_label` | Codebook Supp. Table 13 expert label (`ok` / `plausible` / `no` and annotation) where the motif is listed; Supp. Table 16 artefact flag |

Examples:
- An EP300 ChIP-seq motif: `assayed_target = EP300`,
  `assignment_basis = occupancy_derived`,
  `direct_binding_evidence = not_established`.
- A SOX9 HT-SELEX motif: `assayed_target = SOX9`,
  `assignment_basis = in_vitro_binding`, `direct_binding_evidence = supported`.
- A heterodimer CAP-SELEX motif: direct binding is assigned to the
  assembly (`A::B`), not to each subunit.

Source-specific mapping:
- **HOCOMOCO datatype codes:** P = ChIP-seq, S = HT-SELEX, M = Methyl-HT-SELEX,
  G = GHT-SELEX, I = SMiLE-seq, B = PBM, H = inherited from v11.
- **CisBP `MSource_Type`:** mapped as in the table above. CisBP is one
  row per TF–motif link, stored in `PMA_motif_tf_links.tsv`.

## 5. Provenance and derived-from links (frozen)

- **Independent evidence unit = the original experiment (or experiment
  series), not a database record or motif ID.** Each motif stores the
  resolvable accessions in `experiment_ids`: GEO GSM/GSE, SRA, ENCODE
  ENCSR, GTRD PEAKS, Codebook experiment IDs, and publication + SELEX
  ligand ID for Jolma2013/Yin2017. Where none resolve,
  `experiment_identity = unknown`. Unknown is never counted as
  independent.

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

## 8. Similarity calibration (frozen before any cross-source TOMTOM)

Target: **sequence-pattern equivalence**, not TF-identity concordance.

**Label sets.** Labels come from metadata and expert curation, never
from similarity scores.

| Set | Definition | Role |
|---|---|---|
| **P-high** | (a) Codebook Supp. Table 13 PWMs labelled "consistent with codebook motif" with classification `ok`, each paired with the Codebook PWM of the same TF. (b) Pairs confirmed equivalent in the manual review (below). Each pair records `label_source` (`codebook_t13` / `manual_review`). | expert-curated positives; not an experimental gold standard |
| **P-provisional** | same HGNC TF; both `direct_binding_evidence = supported`; monomer; no shared `experiment_ids` | weak-label concordance, descriptive only; never used to pick thresholds |
| **N-high** | pairs confirmed as different patterns in the manual review | ground-truth negatives |
| **N-challenge** | different TFClass superclass, length within ±2 bp, sharing a ≥ 5-mer of the IUPAC consensus | challenge set; reports the cross-family link rate; not assumed negative |

**Manual review.** A stratified sample of ~200 pairs (balanced across
the five length bins), drawn from P-provisional and N-challenge, is
shown as aligned logo pairs on a review sheet. A human curator labels
each pair: same pattern / different pattern / partial-composite /
unsure. Only same/different labels enter P-high/N-high. Blinding: the
sheet shows logos and lengths only. TF names and TOMTOM scores are
hidden.

**Calibration vs evaluation.** Pairs are split **by TFClass family**
(HOCOMOCO masterlist), so no family appears in both partitions. The
split is enforced at the **motif** level: no motif appears in both
partitions. A pair whose two motifs fall in different partitions is
excluded from the primary calibration and evaluation and reported as a
separate cross-family challenge set, with its count.
- Thresholds are chosen on the calibration partition only.
- The evaluation partition is run **once**.
- If labels are too few for a held-out split (< 30 per length bin),
  grouped 5-fold CV by family is used and reported as *internal* CV.

**Pre-specified primary criterion.** Maximise sensitivity on P-high,
subject to specificity ≥ 0.95 on N-high, **in every length bin**.
Choose among a uniform BH q cutoff, a uniform best-alignment
Pearson-similarity cutoff and length-stratified q. Report per-bin
sensitivity, specificity and precision with bootstrap 95 % CIs (1,000
resamples, grouped by family). Min-bin F1 is reported as a secondary
measure only. Sensitivity is also reported stratified by P-high
`label_source`. Output: `statistical_match_v0.2`, with `v0.1` kept
alongside it.

**Fallback if no human curator is available (pre-specified).** P-high
is Table 13 only (35 pairs) and N-high is empty. Specificity then has
no ground truth, so no threshold is selected and `statistical_match_v0.2`
is **not issued**. `statistical_match_v0.1` (BH q < 0.01, overlap ≥ 60 %)
stays the operational rule. Step 2 reports, descriptively: P-high
sensitivity of v0.1 by length bin with grouped-bootstrap CIs, and the
N-challenge link rate by length bin. The Table 13 recall is not
generalised to all human motifs, and the N-challenge link rate is not
called a false-positive rate. Done criterion 3 is then met by these
descriptive tables. The calibration is reopened when manual
labels exist.

### 8.1 Benchmark implementation (amendment 2026-10-15, after import, before any TOMTOM)

The import showed that Table 13 resolves only partly to the raw layer.
Its 14 HOCOMOCO **v12** IDs do not exist in v14, so 21 of the 35
consistent/ok rows map: 17 Factorbook and 4 JASPAR. The rules below
were fixed before any benchmark similarity was computed.

- **Universe.** Targets are the whole v0.2 raw layer (all motifs in
  `PMA_motifs_raw.meme`). Every motif in a benchmark pair is a query,
  and BH is per query over all targets, with self-pairs inside the
  family (the Step 1 convention). Undirected pairs are reported under
  both rules, `either` and `both` directions.
- **Eligible motifs** for P-provisional and N-challenge are monomers
  with `direct_binding_evidence = supported`, `species_basis = human`,
  no `derived_from` record, and no QC flag other than `low_ic`.
- **P-provisional** pairs come from different source databases. They
  must not share an `exact_dup_group` or `rounded_equiv_group`, and must
  not share a recorded experiment ID. A pair where one side has no
  recorded experiment ID is allowed, since independence is then
  unverified rather than refuted.
- **N-challenge.** TFClass superclass comes from the HOCOMOCO v14
  masterlist via HGNC. The IUPAC consensus uses standard rules: a base
  with p ≥ 0.6; a two-base code when the pair sums to ≥ 0.75 and each is
  ≥ 0.25; otherwise N. A shared 5-mer has no N and is matched in either
  orientation.
- **Sampling.** The length bin is that of the shorter motif. P-high
  keeps every pair. P-provisional and N-challenge each draw up to 100
  pairs per length bin, at most 3 pairs per TF pair, with seed
  20261015.
- **Family partition.** A motif's family is the TFClass family of its
  first HGNC TF. A family goes to calibration if the last hex digit of
  `sha1(family)` is even, and to evaluation otherwise. A motif with no
  family goes to neither partition. Pairs whose motifs fall in
  different partitions form the cross-family challenge set.
- **Manual review sheet.** 20 pairs per length bin each from
  P-provisional and N-challenge, 200 in total. The pairs are shuffled
  and the sheet shows logos only, with both orientations of the second
  motif. The answer key is a separate file.

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

1. Every source in §2 is imported. Counts reconcile with the source
   manifests, and every exclusion has a flag.
2. 100 % of motifs have `pma_id`, `source_*`, `assay_class`,
   `motif_tf_assignment` and `species_basis`. The share with
   `discovery_dataset_known` is reported for ChIP-derived motifs.
3. The label sets are built, including the manual review sheet. The
   calibration/evaluation split is frozen, and `statistical_match_v0.2`
   is chosen on the calibration partition and evaluated once, with CIs.
   Without a curator, the §8 fallback tables replace this item.
4. The whole pipeline reruns from raw with one command and gives
   identical `raw_matrix_hash`, `normalized_matrix_hash` and metadata.

## 12. Amendment v0.2.1 (2026-10-16): HOCOMOCO H14INVITRO / H14INVIVO

Reason: the completeness check found that §2 named HOCOMOCO CORE + INVIVO +
INVITRO but v0.2 imported H14CORE only. The sub-collections hold
alternative-specificity variants that are not in CORE. Their matrices are
already in raw (`hocomoco_v14/2026-10-14/H14{INVITRO,INVIVO}_annotation.jsonl`,
field `pcm`); nothing new is fetched. HOCOMOCO v13 was assessed and not
imported (refits of v14 motifs, no new TFs; `raw/hocomoco_v13/README.md`).

Rules (revised after review F10/F11):
- An INVITRO/INVIVO entry is merged into an existing record only when its
  parsed count matrix is identical (either orientation) AND it comes from the
  same source experiment (same TF, `original_motif.origin` and
  `motif_datatype`). Otherwise it is its own record; identical matrices across
  records are flagged as exact duplicates, never merged (§3).
- Result on the data: all 2,334 matrix-identical entries share TF, origin and
  assay with the record they merge into (0 cross-TF or cross-experiment
  matches; 2 RXRG entries come from the same peak set PEAKS035283 with a
  different peak-calling score and are labelled
  `same_experiment_other_original_motif`). New records: 421 INVITRO + 422
  INVIVO entries; 3 are in both, so **840** records (asserted), of which
  `source_set` is INVITRO for 421 and INVIVO for 419.
- No provenance is dropped: `PMA_hocomoco_collection_memberships.tsv` has one
  row per HOCOMOCO entry (4,769: pma_id, collection, source motif name,
  original motif, TF, origin, assay, collection datatype, collection quality,
  match type). Collection-specific quality lives there, not in the record.
  Records also carry `hocomoco_collections` and `hocomoco_alt_names`.
- Fields, evidence model, TF mapping and QC flags are the same as H14CORE (§3–§7).
  Nothing in other sources changes.
- Output: `processed/v0.2.1_raw_layer/` (expected 30,781 records). v0.2 stays
  frozen as the layer the §8 benchmark was run on; `PMA_RAW_LAYER=v0.2`
  rebuilds it and must reproduce its checksums. The benchmark is not rerun:
  it is bound to v0.2 (benchmark_dataset_version = v0.2; 28,938 targets) and
  is not a v0.2.1 calibration. Step 3 uses v0.2.1 and recomputes its own
  similarity scores and per-query BH over the v0.2.1 universe (29,778
  targets); v0.2 q-values are never reused.
- Evidence counting (Step 3 acceptance condition): the 840 records are
  alternative profiles, not independent experiments. Several HOCOMOCO records
  (CORE/INVITRO/INVIVO) of one TF from one origin count as one experiment;
  unresolved experiment identity stays `independence_unresolved`.
- QC tables for v0.2.1 go to `results/02_motif_import/v0.2.1/`.

Done when: v0.2.1 builds with 840 extra HOCOMOCO records and no other change
in record set; v0.2 rebuild reproduces its checksums; a v0.2.1 rerun gives
identical checksums.
