# Step 2 — Multi-source motif import, QC and calibration benchmark: results

Run 2026-10-15. The design is `docs/STEP2_MOTIF_IMPORT_DESIGN.md`
(revision 1 + F8–F11 + §8.1 amendment), approved by ChatGPT before
compute.

- Code: `scripts/02_motif_import/` (`run_import.sh`, then
  `03_build_benchmark.py`, `04_run_benchmark_tomtom.sh`,
  `05_benchmark_analysis.py`).
- Small tables: `results/02_motif_import/`.
- Data: `$BIO_DATA/2.PROJECTS/PMA/motif_reference/processed/v0.2_raw_layer/`
  and `result/step2_motif_import/benchmark/`.

No curator labels exist yet, so the pre-specified **§8 fallback**
applies. `statistical_match_v0.2` is **not issued**, and
`statistical_match_v0.1` stays the operational rule. Benchmark numbers
are descriptive.

## 1. Raw layer v0.2

| Source / set | Records | In MEME | HGNC TFs | Notes |
|---|---|---|---|---|
| Codebook 2026 representative | 1,685 | 1,685 | 1,418 | 180 inferred (`transferred`) |
| JASPAR 2026 CORE vert NR | 1,019 | 1,019 | 878 | 77 composites |
| JASPAR 2026 UNVALIDATED NR | 1,031 | 1,031 | 407 | 412 composites (mostly CAP-SELEX); 394 non-vertebrate |
| HOCOMOCO v14 H14CORE | 1,595 | 1,595 | 1,107 | 240 from mouse data |
| CisBP 3.10 human | 7,434 | 6,431 | 1,402 | 1,003 Transfac matrices withheld (`no_matrix_license`) |
| Factorbook ChIP-seq MEME | 10,477 | 10,477 | 1,030 | 563 from mm10 experiments |
| Factorbook HT-SELEX (ZMotif) | 6,700 | 6,700 | 613 | Yin 2017 + Jolma 2013 runs; 2,367 methyl-HT-SELEX; 268 mouse proteins |
| **Total** | **29,941** | **28,938** | **1,771** (union) | |

The Factorbook HT-SELEX catalog was downloaded manually on 2026-10-15
(scripts get HTTP 429). Its motif IDs are ENA run accessions. TF, ligand
and batch come from the ENA run reports of PRJEB9797 and PRJEB3289,
which resolve all 6,700 runs. The browser also re-saved two ChIP files;
both are byte-identical to the 2026-10-14 copies (see
`raw/factorbook/2026-10-14/README.source.md`).

Counts reconcile with every source manifest. No record failed the
format or normalisation checks.

QC flags:
- `low_ic` 832: CisBP 497, Factorbook SELEX 193, Codebook 118;
- `short_lt5` 26: Factorbook SELEX 19, JASPAR 7;
- `long_gt40` 3.

A rerun from raw, after the benchmark TOMTOM, reproduced identical metadata and MEME md5s (done
criterion 4). Tests: `tests/test_pma_motif.py` pins the hash
serialisation (F11), the gap mask, orientation-free rounding and the
evidence mapping.

### Evidence model (`results/02_motif_import/evidence_by_source.tsv`)

| Source | supported | not_established | transferred | unknown |
|---|---|---|---|---|
| Codebook | 950 | 554 | 180 | 1 |
| JASPAR CORE + UNVAL | 1,409 | 499 | 0 | 142 |
| HOCOMOCO | 836 | 750 | 0 | 9 |
| CisBP | 3,648 | 2,761 | 1,004 | 21 |
| Factorbook ChIP | 0 | 10,477 | 0 | 0 |
| Factorbook HT-SELEX | 6,700 | 0 | 0 | 0 |

- Every Factorbook ChIP motif is `occupancy_derived`, with
  `direct_binding_evidence = not_established`.
- 301 of Factorbook's 1,348 TFs (ChIP and SELEX combined) appear in no
  other source. Many are chromatin or non-sequence-specific ChIP targets
  (for example EP300, POLR2A). The §4 model records them as the target
  of an occupancy experiment, not as DNA-binding specificities.
- Restricted to human motifs with `supported` direct binding, the union
  is 929 TFs:
  - CisBP 912, Codebook 795, HOCOMOCO 659, Factorbook SELEX 605 and
    JASPAR 584;
  - 85 are unique to CisBP, 10 to JASPAR and 2 to Factorbook.
- The `unknown` assay cases are JASPAR records with no `type`
  annotation, CisBP records whose only stated source is JASPAR, and
  HOCOMOCO motifs inherited from v11.

### Provenance

- **Experiment identity.**
  - **Accession** (ENCODE ENCSR, GTRD peaks, a Codebook experiment ID,
    an ENA run, or the SELEX key `publication.ligand.batch`): all of
    Factorbook and 1,492 HOCOMOCO motifs.
  - **Publication record** (publication plus source record ID):
    4,098 CisBP, 1,257 Codebook and 94 HOCOMOCO motifs.
  - **The SELEX key links sources.** Factorbook SELEX motifs cover
    1,716 SELEX experiments. 416 of them are also the source experiment
    of a HOCOMOCO motif, so the two motifs are one piece of evidence,
    not two. CisBP and Codebook records of the same Yin 2017 / Jolma 2013
    experiments carry only a TF-level record ID, so that link cannot be
    made from their metadata.
  - **Unknown:** every JASPAR record (JASPAR gives a PMID, not an
    experiment accession), 3,336 CisBP and 428 Codebook motifs.
  - Unknown is never counted as independent evidence.
- **`derived_from`.** Recorded for 3,781 records, where the source names
  another motif collection: CisBP 3,336, Codebook 251, HOCOMOCO 177
  (built from Codebook/MEX data) and JASPAR 17.
- **Discovery dataset of occupancy-derived motifs.** Known for every
  Factorbook (10,477) and HOCOMOCO ChIP (750) motif. Known for
  222 / 495 JASPAR motifs. Unknown for every CisBP (1,099) and Codebook
  (408) occupancy motif. Those cannot be used for strict independent
  validation later.

### Duplicates (flag only, never merged)

- **Exact normalised-matrix duplicates:** 1,500 records in 734 groups.
  Most are one of two kinds:
  - Factorbook-internal (355 groups). In 354 of them all members come
    from one ENCODE experiment with several peak files. The other is a
    CTCF motif found identically in two experiments.
  - CisBP + Codebook (263 groups): Codebook PWMs carried over from
    Lambert 2018/CisBP.
- **Rounded (4 dp, either orientation):** 4,519 records in 2,184 groups.
  The largest cross-source groups are CisBP + Codebook (1,347) and
  CisBP + JASPAR (309).

These groups are copies of one matrix across databases, not
independent agreement.

### Curation labels

- **Codebook Supp. Table 13.** 442 of 484 rows map to raw-layer motifs:
  431 Factorbook rows, by ENCSR + consensus, and 11 JASPAR rows, by base
  ID.
  - The 32 HOCOMOCO **v12** rows do not map, because v12 IDs do not
    exist in v14.
  - Of the 35 `consistent with codebook motif` / `ok` rows, 21 map.
- **Codebook Supp. Table 16** (37 artefact motif IDs, given as MEX IDs).
  None matches a HOCOMOCO H14CORE source motif. HOCOMOCO is the only
  imported source that uses MEX IDs, so no record carries an artefact
  flag. A similarity-based screen against these matrices is left to
  Step 3.

## 2. Calibration benchmark (§8, §8.1)

**Set-up (§8.1, fixed before TOMTOM).**
- 11,433 eligible motifs: monomers with supported direct binding, human,
  no `derived_from`, and no QC flag except `low_ic`.
- Pairs: P-high 19, P-provisional 500 and N-challenge 500. The
  P-provisional and N-challenge sets have 100 pairs per length bin. A
  pair's length bin is set by its shorter motif.
- 1,740 query motifs, each compared with all 28,938 raw-layer motifs
  (TOMTOM 5.5.9, Step 1 arguments). BH is applied per query over the full
  universe. `bh_extract.py` asserts 28,938 distinct targets per query (the
  MEME file has 28,938 unique IDs). `05_benchmark_analysis.py` asserts
  that the TOMTOM query set equals `benchmark_queries.txt` and that the
  output holds exactly 2 × 1,019 distinct directed rows. All checks pass.
  The distinct-target assertion was added after the run; it follows from
  the asserted per-query count, no duplicates, and unique target IDs.
- Rule `statistical_match_v0.1`: q < 0.01 and overlap ≥ 60 % of the
  shorter motif. "Either" means at least one direction passes; "both"
  means both directions pass.
- 95 % CIs: bootstrap clustered by family pair (1,000 resamples, seed
  20261015). They describe this sampled benchmark only (100 pairs per
  length bin, ≤ 3 per TF pair), not the population of all motif pairs.
  They do not capture dependence through TFs or motifs shared across
  family pairs. Groups with n < 5 get no CI.

### v0.1 link rates (`results/02_motif_import/benchmark_v01_by_length.tsv`)

| Set | n | Either | 95 % CI | Both | 95 % CI |
|---|---|---|---|---|---|
| P-high (Codebook Table 13 consistent/ok) | 19 | 0.737 | 0.33–1.00 | 0.579 | 0.00–0.73 |
| P-provisional (same TF, different sources; independence mostly unresolved) | 500 | 0.708 | 0.64–0.77 | 0.648 | 0.56–0.72 |
| N-challenge (different superclass, shared 5-mer) | 500 | 0.048 | 0.02–0.08 | 0.024 | 0.01–0.05 |

By length bin (either direction):

| Shorter motif | P-provisional | N-challenge |
|---|---|---|
| ≤ 8 | 0.56 (0.47–0.64) | 0.15 (0.07–0.22) |
| 9–10 | 0.67 (0.55–0.77) | 0.01 (0.00–0.03) |
| 11–12 | 0.72 (0.58–0.85) | 0.06 (0.00–0.14) |
| 13–15 | 0.77 (0.61–0.87) | 0.01 (0.00–0.03) |
| > 15 | 0.82 (0.74–0.89) | 0.01 (0.00–0.03) |

- **Short motifs drive both weaknesses.** At ≤ 8 bp, v0.1 links 15 % of
  N-challenge pairs and misses 44 % of P-provisional pairs. From 9 bp up,
  the N-challenge rate is ≤ 6 %.
- **Partitions agree.** P-provisional either-rate: calibration 0.72,
  evaluation 0.68. N-challenge: calibration 0.03, evaluation 0.04,
  cross-family 0.06 (`benchmark_v01_by_partition.tsv`).
- **Cutoff sensitivity** (descriptive; no threshold is selected), in
  `benchmark_v01_q_grid.tsv`:

  | q cutoff | P-provisional (either) | N-challenge (either) |
  |---|---|---|
  | 0.001 | 0.58 | 0.002 |
  | 0.01 | 0.71 | 0.048 |
  | 0.05 | 0.82 | 0.114 |

- **By source pair (F10).** The P-provisional either-rate ranges from
  0.56 (CisBP vs JASPAR, n = 18) to 0.84 (Factorbook vs HOCOMOCO,
  n = 43). CisBP vs Factorbook has the most pairs (n = 252, 0.66). Some
  of those may be the same Yin 2017 experiment (see below). See
  `benchmark_v01_pprov_by_source_pair.tsv`.

### Experiment independence of P-provisional pairs (results review F1)

Pair selection excluded only pairs with a *known* shared experiment, so
"different source records" does not mean "independent experiments".
Each pair now carries an `independence_status`
(`benchmark_pair_independence.tsv`):
- `confirmed_distinct` when both motifs carry an experiment-level SELEX
  key (`publication.ligand.batch`) and the keys differ;
- `known_shared` when an experiment ID is shared (0 pairs; excluded by
  construction);
- `independence_unresolved` otherwise, i.e. when either motif has an
  unknown or only TF-level identity.

Most P-provisional pairs are Yin 2017 / Jolma 2013 HT-SELEX motifs
re-derived by several databases, so independence is rarely resolvable.
See `benchmark_v01_pprov_by_independence.tsv`.

| Status | Publications | n | Either | 95 % CI |
|---|---|---|---|---|
| confirmed_distinct | all | 36 | 0.83 | 0.69–0.95 |
| independence_unresolved | all | 464 | 0.70 | 0.63–0.76 |
| independence_unresolved | same publication | 241 | 0.76 | 0.67–0.83 |
| independence_unresolved | different publications | 153 | 0.60 | 0.51–0.67 |
| independence_unresolved | publication unknown | 70 | 0.71 | 0.59–0.81 |

- The 36 confirmed-distinct pairs are all Factorbook SELEX vs HOCOMOCO
  pairs with different SELEX experiments.
- Among unresolved pairs, those from the same publication link more
  often than those from different publications (0.76 vs 0.60). This is
  consistent with shared underlying experiments inflating the rate, but
  is not proof of it.
- The P-provisional rate therefore measures same-TF agreement between
  database records. It is not independent cross-experiment
  reproducibility, and the unresolved pairs must not be used as
  independent replication in later evidence grading.

### What the N-challenge links are

In this sampled challenge set, v0.1 links 24 of 500 pairs. By manual
reading, not verification, 21 of the 24 look like plausible shared
sequence patterns across superclasses:
- CAGGTG E-boxes: SNAI1/2/3 against TCF4 and FIGLA (6).
- MyoD-family CAGCTG sites against the TGACAG(CTGTCA) sites of the TALE
  homeodomains MEIS2, PKNOX1 and TGIF1 (4).
- MGA, which carries a T-box domain as well as its bHLH-ZIP, against
  EOMES (1).
- TAATTA homeobox sites against SKOR1/2 (9). SKOR has no TFClass
  DNA-binding annotation.
- OVOL2 against MYBL2, both of which bind CCGTTA-like sites (1).

The other 3 are RFX3 vs NFATC4, ETV2 vs ZNF140 and E2F2 vs SOX10.

Some of these share only a short core (for example, CAGCTG within the
longer TALE site), so a match is not full motif equivalence. The
observed link rate describes similarity detected by the v0.1 rule
within this sampled challenge set. It is neither a false-positive rate
nor a specificity, and it is not a bound for cross-superclass pairs in
general: it depends on length matching, the shared-5-mer requirement,
sampling and v0.1's own misses. Only curator labels can separate true
from false links.

### P-high (`benchmark_p_high_pairs.tsv`)

- 14 of 19 pairs link (either direction). This is a small sanity
  check, not v0.1's sensitivity. Most length bins hold 1–7 pairs; bins
  with n < 5 get no CI.
- All 7 pairs with a shorter motif > 15 bp link.
- The 5 non-links:
  - two ZXDB pairs and one DACH1 pair (p ≥ 9e-5; the Factorbook ChIP
    motif differs);
  - ZBTB8A against a 5 bp Codebook motif (q = 0.043);
  - ZBTB40 (q = 0.035).
- All 19 are Codebook vs Factorbook/JASPAR pairs. 17 are zinc-finger
  TFs; DACH1 and ZBTB8A have no family annotation. The set does not
  represent other TF families.

### Status under the §8 fallback

- `statistical_match_v0.2` is **not issued**, and v0.1 remains the
  operational rule for Step 3.
- None of these rates is reported as sensitivity or FPR, and the
  Table 13 agreement is not generalised beyond its 19 pairs.
- The 200-pair review sheet
  (`result/step2_motif_import/benchmark/review_sheet.html`) is ready for
  a curator. Labels would allow a v0.2 threshold to be selected on the
  calibration partition and tested on the evaluation partition.

### Limitations

- 464 of 500 P-provisional pairs have unresolved independence (see
  above). CisBP and Codebook give only TF-level record IDs, so their
  copies of Yin 2017 / Jolma 2013 experiments cannot be matched by
  SELEX key.
- P-high is small (19 pairs), so its CIs span most of [0, 1].
- CIs are clustered by family pair only (see Set-up).
- Reproducibility is shown only for the frozen raw inputs in the same
  environment: identical md5s on rerun and 9 passing tests. It is not
  shown across operating systems, library versions or re-downloads. A
  release will record input checksums, software versions and an
  environment lock (Step 4).
