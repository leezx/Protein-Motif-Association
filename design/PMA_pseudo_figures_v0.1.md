# PMA — Protein–Motif Association
## Pseudo-figures and manuscript concept v0.1

**Status:** Conceptual manuscript blueprint; no results have been generated. All findings below are *hypotheses or planned analyses*, not established results.  
**Primary deliverable:** A versioned human protein–DNA occupancy reference with a statistically calibrated, context-aware protein–motif association catalog and peak-level annotations.  
**Scope:** Human; public ChIP-seq and CUT&RUN (other assays only after compatibility assessment); DNA-binding and chromatin-associated proteins.  
**Positioning:** Resource/database paper, not a new motif representation or a claim of causal protein–DNA recognition.

## Working title
**PMA: a comprehensive human protein–DNA occupancy reference with statistically calibrated protein–motif associations**

Alternative: **PMA maps motif associations across the human chromatin-associated proteome** (use only if actual coverage justifies it).

## Abstract (prospective; no invented results)

Sequence motifs are commonly linked to sequence-specific transcription factors, yet genomic occupancy profiles of transcriptional regulators and chromatin-associated proteins frequently contain motifs that are not assigned to the profiled protein. These associations may reflect direct recognition, protein assemblies, co-occupancy, chromatin context, or technical confounding. We propose PMA (Protein–Motif Association), a human reference integrating a quality-controlled motif repertoire with harmonized public protein–DNA occupancy profiles from ChIP-seq and CUT&RUN. PMA will test whether motifs are spatially associated with each protein's reproducible binding regions using matched genomic backgrounds, summit-centered analyses, effect-size estimates, uncertainty intervals, and cross-dataset replication. Associations will retain assay, cell context, motif-family ambiguity, and evidence provenance rather than equating co-localization with physical interaction. The resource will also provide a standardized human occupancy reference and peak-level motif annotations. We will assess whether PMA recovers known direct associations, identifies reproducible noncanonical associations, and improves interpretation of held-out occupancy datasets over direct-motif-only baselines. The resulting resource is intended to support hypothesis generation and transparent evaluation of protein–motif relationships, including for chromatin-associated proteins without known intrinsic DNA sequence specificity.

## Introduction — argument outline

**Paragraph 1 — Established foundation.** DNA sequence motifs are an effective abstraction of TF binding preferences. Databases such as JASPAR and HOCOMOCO and occupancy resources such as ReMap/ENCODE provide complementary views of sequence specificity and genomic binding. PWM is retained as a core representation, while motif families and non-PWM models may be tracked as optional metadata.

**Paragraph 2 — Gap.** In vivo occupancy is not equivalent to intrinsic DNA recognition. ChIP-seq/CUT&RUN peaks can contain motifs of partners or unrelated accessible-region motifs; non-sequence-specific chromatin proteins may show reproducible motif enrichments without direct DNA binding. Existing annotations often conflate direct specificity, co-occupancy and context association.

**Paragraph 3 — Statistical gap.** Simple motif enrichment against poorly matched backgrounds and binary peak–motif overlaps can overstate associations. Sequence composition, promoter/enhancer composition, accessibility, peak width, summit location, motif redundancy, assay and cell state all influence apparent enrichment. A calibrated effect-size and replication framework is required.

**Paragraph 4 — Contribution.** PMA assembles (i) a deduplicated high-quality motif reference, (ii) a harmonized human protein–DNA occupancy reference, and (iii) statistically evaluated protein–motif associations with context and peak-level annotations. PMA is a resource, not a claim to reconstruct protein complexes or causal regulatory networks.

**Paragraph 5 — Validation and utility.** Benchmark against direct motif catalogs and established co-binding resources, using held-out experiments and explicit negative controls. RARB is one predeclared interpretability case study, not evidence of success by itself.

## Figures (pseudo-figures; expected analyses, not results)

### Figure 1 | Architecture, scope and evidence provenance of PMA
**Question:** What does PMA contain, and how are source data transformed into auditable associations?

- **1a — Schematic:** Two inputs: motif catalog (JASPAR/HOCOMOCO/CIS-BP/validated de novo motifs) and occupancy datasets (ENCODE/ReMap/GTRD/Cistrome and CUT&RUN repositories, subject to license and duplication review). Protein ID normalization → QC → motif clustering → occupancy harmonization → statistical association → reference/API.
- **1b — Coverage matrix:** Proteins × assay × cell/tissue context, distinguishing sequence-specific TFs, cofactors, remodelers, writers/erasers/readers, and other chromatin proteins. Show missingness explicitly.
- **1c — Data quality:** Assay-specific QC distributions, reproducibility, peak numbers, blacklist removal, and retained/excluded datasets.
- **1d — Evidence schema:** Protein–motif-family–context–dataset edges with effect size, uncertainty, replicate support, provenance, and mechanism status (`direct established`, `complex supported`, `co-occupancy supported`, `association only`, `unresolved`). Mechanistic labels require independent evidence.

**Minimum claim:** A traceable and quality-controlled integrated reference exists; avoid claiming 'most comprehensive' without a dated competitor comparison.

### Figure 2 | Building a nonredundant, evidence-graded human motif repertoire
**Question:** How much usable motif diversity remains after family-aware deduplication and quality control?

- **2a — Motif acquisition:** Curated in vitro/in vivo motifs, provenance, species, experimental technology, and optional de novo discovery on *training datasets only*.
- **2b — Similarity graph:** Cluster redundant PWMs into motif families; preserve original motif IDs, alternative motifs, and orientation/length metadata. Do not merge biologically distinct profiles solely because of similarity.
- **2c — Quality tiers:** Independent in vitro support, held-out ChIP/CUT&RUN enrichment, motif centrality, and cross-dataset replication; report missing evidence rather than penalizing it as failure.
- **2d — Benchmark:** Motif-family recovery and false-positive rates under matched null sequences; compare curated-only versus expanded catalog at fixed false discovery rate.

**Minimum claim:** An auditable, nonredundant motif reference; do not assert that ChIP-derived motifs establish direct DNA specificity.

### Figure 3 | Statistical calibration of protein–motif genomic association (core analysis)
**Question:** Does a motif occur near a protein's reproducible occupancy sites more often—and more centrally—than expected under appropriate null models?

- **3a — Unit of inference:** One protein × one motif family × one biological context × one independent experiment. Peaks are nested observations, **not independent biological replicates**.
- **3b — Occupancy statistic:** Scan both strands using pre-specified motif thresholds or continuous scores; measure summit-centered motif occurrence/strength, spatial enrichment profile, and proportion of peaks with motif hits. Report motif family ambiguity.
- **3c — Matched controls:** Sample non-overlapping genomic intervals matched for GC, dinucleotide composition where feasible, mappability, length, chromosome, TSS distance, promoter/enhancer class, and accessibility **when matched ATAC exists**. Distinguish primary background (genomic sequence preference) from accessibility-conditioned background (association beyond accessible chromatin). Do not condition on variables that erase the effect of interest without reporting both estimands.
- **3d — Effect sizes and uncertainty:** Observed-to-expected enrichment, absolute excess occurrence, summit centrality, confidence intervals from block/region resampling; empirical null from matched permutations. Multiple-testing correction across motif families per protein/context, with hierarchical correction for atlas-wide claims.
- **3e — Reproducibility:** Meta-analyze independent experiments at dataset level with heterogeneity estimates; leave-one-study-out checks. Require minimum independent studies for a replicated tier; otherwise label single-study evidence.
- **3f — Null checks:** Shuffled motifs preserving composition, matched genomic negatives, motif-family decoys, promoter-only and distal-only strata, high-frequency ubiquitous motifs, and assay/batch sensitivity.

**Primary outputs:** calibrated association strength, confidence interval, q-value, spatial enrichment, replication grade, context heterogeneity, and evidence tier. **Never interpret a significant association as proof of direct binding or protein complex membership.**

### Figure 4 | Human protein–motif association landscape
**Question:** Which associations are widespread, protein-specific, or context-dependent?

- **4a — Bipartite network:** Protein families/classes × motif families, edges weighted by replicated association effect size; direct-recognition edges separately marked.
- **4b — Protein-level repertoire:** Number of supported motif families per protein, adjusted for study count and available contexts; display coverage bias.
- **4c — Context stability:** Same-protein associations across cell types using within-protein effect-size contrasts; show heterogeneity and assay confounding, not binary 'context specificity' without replication.
- **4d — Chromatin proteins:** Examples lacking canonical intrinsic motifs (e.g., HDAC1, BRD4, SMARCA4) with association-only evidence and candidate partner annotations where independently supported.

**Minimum claim:** PMA catalogs reproducible associations beyond canonical TF motif assignments, with explicit uncertainty.

### Figure 5 | Independent validation and competitive benchmarks
**Question:** Does PMA add reproducible information rather than merely increase motif coverage?

- **5a — Holdout design:** Split by study/laboratory and context where feasible, not random peaks; no motif discovery or edge selection on test data.
- **5b — Baselines:** Direct protein-assigned motifs (JASPAR/HOCOMOCO), motif-family-expanded baselines, and available co-binding/ChIP-motif resources (e.g., Factorbook/MethMotif/COBIND, contingent on comparable exports).
- **5c — Outcomes:** Held-out motif association replication, calibration, protein-specific precision against matched other-protein controls, and performance at equal motif count/FDR. Distinguish recovery of known direct binding from prediction of indirect associations.
- **5d — Robustness:** Background strategy, assay, peak caller, summit window, motif threshold, promoter/distal strata, study-count downsampling.

**Success criterion (pre-register thresholds after pilot):** Meaningful held-out gains over strongest fair baseline at controlled false-positive rate, including noncanonical associations; otherwise downgrade to curated reference without novel mapping claim.

### Figure 6 | PMA use case: interpreting RARB occupancy and peak annotations
**Question:** Can PMA clarify why a particular RARB ChIP-seq dataset lacks significant enrichment of its canonical assigned motif?

- **6a — Diagnose before explaining:** Check antibody/peak QC, motif identifiers and family similarity, background choice, peak width, summit centering, motif thresholds, assay conditions and cell context. Absence of enrichment is dataset- and null-dependent.
- **6b — RARB motif landscape:** Canonical RAR/RXR-like families versus other enriched families, with matched-null effects, centrality, and replication. Do not infer RARB–RXR from motif labels alone.
- **6c — Evidence paths:** Candidate RARB–motif edges with independent co-occupancy/PPI/complex evidence where available; distinguish supported mechanism from unresolved association.
- **6d — Peak annotation browser:** For each RARB peak: genomic coordinates, summit, reproducibility, motif hits/scores/offsets, motif-family ambiguity, peak class, linked dataset/context and association evidence. Optional peak-to-gene annotations must be labeled predictive and are **not** a core claim.
- **6e — Holdout:** Show whether training-derived associations predict motif enrichment in independent RARB datasets, with matched negative proteins.

**Possible outcomes:** (i) canonical motif was missed due to technical/annotation choices; (ii) alternative motifs replicate with independent support; (iii) association remains unresolved. All three are reportable; only (ii) supports expanded association utility.

## Methods — high-level plan

### 1. Scope, identifiers and provenance
Build a human protein universe from HGNC/UniProt and chromatin-related catalogs. Harmonize target antibodies, aliases, complex names, genome builds and biosample metadata. Record original accessions, dates, licenses, processing versions, and study IDs. Remove duplicate reprocessed datasets before counting independent replication.

### 2. Occupancy reference
Aggregate public ChIP-seq and CUT&RUN experiments. Prioritize uniformly processed raw reads when practical; otherwise record pipeline differences and stratify analyses. Apply assay-specific QC, genome blacklist, replicate concordance and summit/peak-quality criteria. Avoid pooling incompatible assays into one unqualified estimate.

### 3. Motif reference
Import experimentally supported PWMs with provenance; harmonize orientation, background frequencies and identifiers. Cluster by motif similarity into families, preserving individual PWMs. Discover de novo motifs only in training partitions; distinguish newly discovered motifs from independently validated direct specificity. Do not use ATAC footprints as definitive TF identity evidence.

### 4. Protein–motif association testing
For each dataset and motif family, scan summit-centered peaks and matched controls. Estimate occurrence, score and spatial enrichment effects. Generate empirical nulls using covariate-matched intervals/permutations; quantify uncertainty and correct for multiple comparisons. Analyze promoter and distal regions separately and compare unconditional versus accessibility-conditioned estimands. Aggregate at the independent experiment/study level, reporting heterogeneity and context.

### 5. Evidence grading
Keep independent dimensions rather than one opaque score: (a) motif sequence-quality tier, (b) protein occupancy quality, (c) genomic association statistics, (d) independent replication, (e) mechanistic support. Do not call a protein–motif edge 'direct' from ChIP/ATAC co-localization alone. Footprints support local occupancy patterns but rarely identify a unique protein.

### 6. Peak-level annotation
Release a queryable table and browser/API with protein, assay, biosample, peak coordinates, summit, reproducibility, motif family and motif hits, relative position, association effect, context, evidence paths and provenance. Distinguish *motif present in peak* from *protein occupies that motif*.

### 7. Benchmarking and reproducibility
Use study-level holdouts, motif-count-matched baselines, matched negative proteins, data-leakage checks, null calibration and robustness analyses. Provide code, versioned datasets, metadata, documented filters and frozen benchmark splits.

## Claims and limitations to state explicitly

- **Can claim if validated:** a comprehensive *collected* occupancy reference; calibrated, reproducible protein–motif **genomic associations**; a useful peak annotation resource.
- **Cannot infer from co-localization alone:** physical protein complexes, direct protein–DNA contacts, causal recruitment, CRE–gene regulation or therapeutic consequences.
- **ATAC footprints:** helpful orthogonal context but not a protein-specific gold standard; accessibility-conditioned backgrounds answer a different statistical question.
- **Completeness:** 'most comprehensive' must be established against a dated snapshot of competitor coverage, with consistent protein/study definitions.
- **Context:** retain cell/tissue metadata from v0.1; formal context-specific association claims require matched or sufficiently replicated comparisons.

## MVP and go/no-go gates

**MVP:** One frozen motif collection; uniformly documented occupancy datasets for a feasible human protein subset; a calibrated association test; peak annotations; one RARB use case; independent benchmark. The *long-term scope remains all human chromatin-associated proteins*, but v0.1 does not pretend to cover everything.

**Gate 1 — Data feasibility:** Adequate independent occupancy datasets and metadata for a representative pilot including sequence-specific TFs and non-sequence-specific chromatin proteins.

**Gate 2 — Statistical validity:** Empirical null is calibrated; results are robust to reasonable background and motif-family choices; replicate consistency exceeds negative controls.

**Gate 3 — Incremental value:** Expanded associations improve held-out interpretation over direct-motif and motif-count-matched baselines without unacceptable false positives.

**Stop/pivot:** If Gate 2 fails, do not scale. If Gate 3 fails, release a harmonized occupancy/motif reference with association results labeled exploratory, rather than claiming a new mapping paradigm.

## Parking lot (not core v0.1)

- Peak-to-gene causal assignment and enhancer regulatory networks.
- Protein complex reconstruction from co-localization alone.
- Pan-cancer patient atlas, DepMap dependencies, ADC/vaccine translation.
- New motif representation or new foundation model.
- Formal cell-state specificity claims without appropriate replication.

## Immediate next action

Run a **small pre-registered pilot** with RARB, RXRA, one canonical TF control and one chromatin cofactor, using a fixed motif catalog, two matched-null strategies and independent study holdouts. Inspect whether the association statistic is calibrated and whether any noncanonical protein–motif edges replicate **before** scaling to the human reference.
