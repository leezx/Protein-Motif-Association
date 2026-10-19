# Step 4b — Genome-wide, motif-free ATAC-seq footprinting: benchmark design

**Status.** The earlier benchmark design was approved by ChatGPT on 2026-10-17 with revisions.
Section 4 was materially revised on 2026-10-19 after exact-head review feedback and is pending
review of the revised PR HEAD; the earlier approval does not cover these changes. No caller is
selected, and no C/C++ port is approved. Both decisions wait for a measured benchmark (§6).

**PI direction.**
- Read Hu et al. 2025 *Nature* ("Multiscale footprints reveal the organization of cis-regulatory
  elements", PRINT / seq2PRINT).
- Compare its ATAC footprinting with other tools and pick the most accurate method for genome-wide,
  motif-free footprinting: find footprints first, then discover motifs de novo; never start from
  known motifs.
- Speed is a hard requirement. A tool that is too slow is dropped, unless it is clearly the most
  accurate; then its core computation is re-implemented in C/C++ (or Python with a C core).

**Positioning.** Step 4b is a protein-agnostic ATAC footprint atlas. Step 4a is the protein-labelled
ChIP occupancy atlas. The two meet later through genomic colocalisation and de novo motif
attribution.

## 1. Candidate methods

| Method | Motif-free detection | Native output | Role |
|---|---|---|---|
| TraceBIND (Lin…Zhang, *Nat Commun* 2026; R + Python) | yes | significant footprint intervals, p / q, effect size | primary candidate |
| PRINT / scPrinter (Hu…Buenrostro, *Nature* 2025; Python, R) | yes | multiscale per-bp scores (needs an event-calling adapter) | primary comparator |
| HINT-ATAC (Li…Costa, *Genome Biol* 2019; RGT) | yes | footprint BED intervals | classical comparator |
| TOBIAS FootprintScores (Bentsen, *Nat Commun* 2020) | the score track only | continuous bigwig (needs event calling) | optional baseline |
| ChromBPNet + TF-MoDISco | no known motifs used, but not an insertion-protection caller | attributions, de novo patterns | orthogonal discovery reference; not ranked with callers |
| seq2PRINT | sequence→footprint model | predicted footprints | orthogonal; not ranked with callers |
| footprint-tools, Wellington (DNase) | yes, but built for DNase | — | not in the main benchmark |

**Excluded.** Methods that need known motifs to call binding: CENTIPEDE, PIQ, BaGFoot,
msCentipede, TAMC and TOBIAS BINDetect.

**PRINT in brief.**
- **Tn5 bias.** A CNN over a ±50 bp one-hot sequence, trained on Tn5 insertions into BAC naked
  DNA. It reaches R = 0.94 on BAC DNA and 0.92 on human gDNA.
- **Footprint test.** Per bp and per scale (windows about 4–200 bp), the test compares the
  centre/(centre + flank) insertion ratio with a background mean/SD predicted by a small NN from
  centre bias, flank bias and coverage.
- **P value.** Lower-tailed z-tests against the left and right flank; the larger P is kept, and
  −log10 P is smoothed.

**TraceBIND additions to PRINT.**
- Per-sample fine-tuning of the bias CNN on mitochondrial reads.
- A negative-binomial centre/flank test with dynamic flank width.
- Left/right conservative P values, combined with the Cauchy method.
- BH/BY adjustment.
- Coverage-stratified empirical FDR, then the final non-overlapping events.

## 2. Search space ("genome-wide")

**Callable regions.**
- The callable regions are all accessible regions from the sample's own ATAC peak calling.
- Fixed-width off-peak regions are added as negative controls.
- The genome is processed in blocks.
- Positions are never pre-selected by known motifs, TF identity or ChIP sites.

**Allowed inputs to the caller:**
- insertion counts;
- the sequence-dependent Tn5 bias;
- the method's own statistical model.

**Pipeline.**
1. ATAC fragments → Tn5 insertions (+4 / −4 shift), with read preprocessing identical for all
   methods.
2. Motif-free calling.
3. TF-scale events: DNA at the footprint centre ±25 bp.
4. De novo discovery with one fixed engine (STREME is primary), against a background matched for GC,
   length and accessibility.

**Afterwards only:** the discovered motifs are annotated against PMA v0.3 and a frozen curated
in-vitro subset.
- PMA v0.3 never takes part in calling.
- A match to PMA is not independent truth, because PMA contains ENCODE de novo motifs.

## 3. Validation layers

| Layer | Data | Primary metrics |
|---|---|---|
| B1 biochemical specificity | human naked gDNA (GSE280532); BAC naked DNA (GSE216403, auxiliary because it is PRINT bias training data) | false footprint calls per callable Mb; empirical FDR, stratified by GC and coverage |
| B2 direct perturbation | in vitro MYC/MAX, CEBPA concentration series and no-TF controls (GSE280479); HCT116 CTCF degron ATAC, untreated ENCSR328JGW vs auxin ENCSR260SWI | direction and size of the footprint change at affected sites |
| B3 orthogonal occupancy | K562 deep bulk ATAC (held-out primary benchmark) with ChIP-exo (GSE151287), CUT&RUN and reliable ChIP from the same biosample; independent DNase footprints | sensitivity and locus-level PR-AUC against matched negatives (same peaks; similar accessibility, GC, mappability and summit distance); localisation error; for ChIP-seq, distance to summit only |
| B4 motif discovery | STREME on the called footprints | motif family recovery, reproducibility, enrichment over matched background |

ChIP peaks are not footprints, and an accessible region may hold undetected binders. "Not ChIP" is
therefore never treated as a clean negative. Where reliable negatives do not exist, enrichment and
positive-set recall are reported instead of an absolute precision.

## 4. Accuracy-ranking protocol (frozen before caller-score inspection)

This replaces the earlier B1-first / post-hoc median-AUPRC selection rule. It is a local
HCT116 CTCF-degron benchmark, not a universal caller ranking and not a genome-wide estimate of
motif-free event precision.

1. **Primary candidate universe.** Use the union of high-confidence untreated HCT116 CTCF ChIP
   consensus peaks from the matched degron experiment. Merge overlapping ±50-bp summit windows
   deterministically, retaining the summit of the strongest control peak (ties: chromosome order
   in the exact hg38 `chrom.sizes` file, then lowest summit coordinate, then stable peak ID); keep
   one control-ChIP summit per locus. The same fixed summit and
   100-bp window are used for every caller and both ATAC conditions. Caller events, STREME and
   TOMTOM do not create or remove candidates. Freeze the candidate manifest before reading caller
   scores. If ENCODE provenance, replicate relationships, assay controls or peak QC do not support
   a reliable consensus, stop and do not create these labels.
2. **Treatment labels.** Among control-bound candidate loci, call `depleted` only when the
   input-normalized auxin/control ChIP log2 fold-change is ≤ −1 and differential-test FDR ≤ 0.05
   with adequate coverage in the contributing replicates. Call `retained` only when the treated
   ChIP peak is replicate-supported and log2 fold-change is > −0.5. All other, low-coverage,
   discordant or missing-provenance loci are `ambiguous` and excluded. A missing peak alone is
   never a negative label. Confirm the matching biological sample, treatment time and replicate
   structure before applying these criteria; technical replicates do not count as independent
   biological replicates.
3. **Score mapping and primary endpoint.** Evaluate the treated ATAC caller score at each frozen
   control-ChIP summit using the maximum threshold-free, continuous score in the same ±50-bp
   interval. Fix each tool's score field and direction from its documented output before looking
   at labels. Compute pooled out-of-fold average precision (AP; the non-interpolated area under
   the precision-recall curve) for distinguishing `retained` from `depleted` loci. Do not
   substitute a ChIP summit-derived candidate coordinate asymmetrically between classes. If a
   caller only provides thresholded events and no continuous pre-threshold score, mark it
   `unscorable for primary AP`; do not fill missing scores with zero or rank it with an
   undocumented proxy. Report thresholded sensitivity separately.
4. **Held-out split and inference.** Assign non-overlapping 1-Mb genomic blocks to five folds by
   `int(SHA256("PMA-4b-20261019|" + chromosome + ":" + block_start)[0:8], 16) % 5`, where
   `block_start` is the zero-based coordinate of the block's first base and chromosome order comes
   from the exact hg38 `chrom.sizes` file frozen with the candidate manifest. All paired conditions,
   replicates and loci in a block stay together. At each boundary between adjacent blocks assigned
   to different folds, apply a 50-kb embargo on both sides; exclude any locus whose scoring window
   intersects that embargo. Also exclude windows crossing a fold boundary. Select the operating
   threshold only in the four training folds to reach 80%
   retained-site recall; apply it unchanged to the held-out fold. Also report predeclared 50%,
   70% and 90% recall operating points as secondary results. Pool the out-of-fold scores for AP.
   Compute 2,000 paired bootstrap resamples of 1-Mb blocks with seed `PMA-4b-bootstrap-20261019`;
   each resample uses the same blocks for all callers. Correct the six pairwise caller comparisons
   with Holm's method.
5. **B1–B4 and selection.** B1 naked gDNA is specificity evidence only: at each training-selected
   threshold report held-out observed recall, false calls per callable Mb and per million usable
   cuts after matching depth; it is not positive truth. B2 tests the paired ctrl→aux score change
   at ChIP-depleted versus retained loci. B3 uses occupancy data independent of this benchmark and
   caller development; if none is available, state that generalization is unvalidated. The
   TraceBIND developers' HCT116 degron set is an author-benchmark reanalysis, not independent
   validation. B4 replicate reproducibility and motif-family recovery are supporting evidence only.
   Declare a **local HCT116 CTCF candidate** only when one caller's held-out AP exceeds each other
   scorable caller under the six Holm-adjusted paired block comparisons and B1/B2 do not contradict
   it. If AP uncertainty overlaps or AP and specificity trade off, report a tie/Pareto set; do not
   add post-hoc weights. This benchmark cannot establish a universal or pan-cancer winner. Accuracy
   selects the candidate first; speed is compared separately, and C/C++ work is considered only
   after profiling a validated accuracy candidate.

## 5. Speed gate

**Measured unit.** One sample of 100 M uniquely mapped paired-end fragments, on Argos CPUs.

| Limit | Value |
|---|---|
| CPU threads | 32 |
| RAM | ≤ 40 GiB (Argos cap is about 50 GB) |
| Wall time | ≤ 4 h |

- The clock starts from aligned, indexed BAM or fragment files. It includes:
  - cut-site generation;
  - bias prediction or sample adaptation;
  - footprint computation;
  - multiple testing;
  - event calling;
  - output writing.
- Alignment is timed separately.
- Also reported: CPU-core-hours, peak memory, runtime per M callable bases, and I/O time.

**Gate decisions.**
- ≤ 4 h: pass.
- > 4 h: rejected by default.
  - The only exception: in at least two biological settings the tool keeps recall within 5
    percentage points and cuts false-positive density by at least 50 %. Only then may it be
    optimised or ported.
  - The ported version must pass the same 4 h gate before production use.

**Compute.** Argos has 72 cores and Tesla K80 GPUs, which current PyTorch builds do not support. All
methods are therefore benchmarked on CPU.

## 6. Phases

| Phase | Work | Go / no-go |
|---|---|---|
| 4b-1 reproduction and benchmark | Run TraceBIND, PRINT/scPrinter and HINT-ATAC (TOBIAS optional) natively on the same frozen fragments, peaks, strata, truth labels and versions. | comparable outputs on the same callable regions, with measured accuracy and runtime |
| 4b-2 selection | Combine the B1–B4 results with the speed gate. | one primary caller; when performance is similar, the faster and more maintainable one |
| 4b-3 optimisation (conditional) | Only if the accuracy winner fails the speed gate: profile it, then port the statistical kernel to C++. | the port is near-equivalent to the native tool and passes the gate |

**Port acceptance (4b-3), on 1–5 Mb test regions with identical inputs:**
- −log10 p within 0.01 for non-extreme values;
- reciprocal-overlap event F1 ≥ 0.99, with median boundary difference ≤ 1 bp;
- reproducible coverage-stratified FDR thresholds with fixed seeds;
- no systematic loss on the held-out benchmark.

**What a faithful TraceBIND port must keep:**
- the +4/−4 cut sites;
- the PRINT / mtDNA fine-tuned bias, which can be precomputed as arrays;
- the NB centre/flank test with dynamic windows;
- the left/right conservative P and the Cauchy combination;
- BH/BY;
- the empirical, coverage-stratified FDR;
- the non-overlapping event logic.

Approximating P values, reducing scales or dropping the empirical FDR makes it a new method that
must be validated separately.

**mtDNA eligibility.** `mt_bias_eligible` is a QC flag. When it fails, the PRINT-bias fallback is
labelled `PRINT-bias mode`. Mitochondrial reads must not be removed during preprocessing.

## 7. Outputs (after selection)

- `PMA_ATAC_footprints_hg38.bed.gz`: one row per motif-free footprint event, with chrom, start, end,
  sample_id, width/scale, score, p, q, effect size, bias-model version and caller version. It holds
  no TF names or motif IDs.
- Per-bp, per-scale tracks, with only the needed BigWig views exported.
- `PMA_ATAC_footprint_samples.tsv`.
- Benchmark metrics, runtime profile and `MANIFEST.json`.
- Separate de novo motif discovery results.

## 8. Data (raw, append-only; Argos `DATA/2.PROJECTS/PMA/atac_footprint/raw/2026-10-17/`)

| Set | Accession | Size |
|---|---|---|
| human naked gDNA fragments | GSE280532 (GSM8599883–7) | 2.13 GB |
| BAC naked DNA fragments + selected BACs | GSE216403 | 0.55 GB |
| in vitro MYC/MAX / CEBPA / no-TF | GSE280479 (GSM8598620–3) | 21 MB |
| HCT116 CTCF degron ATAC, filtered BAMs | ENCSR328JGW: ENCFF784ATG, ENCFF794FUH; ENCSR260SWI: ENCFF877LRY, ENCFF745WLX | about 10 GB |
| K562 deep ATAC + ChIP-exo / ChIP | to be selected after B1–B2 | — |
