# Step 4b — Genome-wide, motif-free ATAC-seq footprinting: benchmark design

## Current operative plan — PRINT on the complete same-sample peak set (2026-10-19 23:05 EDT)

This is the sole immediate execution scope. The user now wants one practical **PRINT-only** runtime
measurement over the sample's own complete ATAC peak intervals, not a four-tool comparison and not
base-by-base scanning of hg38. PRINT's native footprint calculation is motif-independent; motifs
and ChIP are outside this run. This is a two-scale operational run, not the full 99-scale spectrum.
Do not score accuracy, discover motifs, optimize/port code, change samples, or work on ChIP BED6/PR #7.

1. **Frozen sample and complete peak input.** Use the same-sample K562 `ENCSR868FGK` ATAC BAM
   `ENCFF534DCE.bam` and original ENCODE IDR peak file `ENCFF993BAP.bed.gz`. The fixed PMA
   conversation approved metadata-only checks and a streaming aggregate over its first three BED
   columns. Verified peak input: 3,651,342 compressed bytes; SHA-256
   `c0c1d0b5350a962b9d7a7f1d2edef1ca98005029c79f07979533f3a14cb40945`; 159,628 records; sum of
   interval widths 150,359,120 bp; union coverage after merging overlaps 55,114,693 bp. These are
   all original peak intervals; do not filter, summit-trim, merge, or pad them to reach the user's
   estimate of 200–400k. The verified count is 159,628. Report interval-width sum separately from
   unique covered bp because the original peaks overlap. K562 is timing-only due to ENCODE's
   nucleosome-free-fraction warning.

2. **PRINT scales and outputs.** Use the existing runner's radius list `10,20` (two fixed scales),
   after its radius/model meaning and exact parameters are recorded in this PR. The official paper
   describes PRINT footprints across 4–200 bp windows; the 99 local dispersion files at radii
   2–100 bp do not justify running all 99 or selecting scales after seeing output. This run must be
   labelled “PRINT radii 10 and 20 only,” not a complete 99-scale atlas. Existing
   `scripts/04b_footprint/run_print.R` outputs one per-position score track per radius, PRINT native
   event BED per radius, and a stage timing TSV; it does not emit BigWig. Keep the original peak
   intervals and preserve native output/count/hash evidence. Any derived input must retain all
   records and may not silently substitute the old 77,668 1-kb speed windows.

3. **Resources and exact gate.** The user has now directed direct use of the documented standalone
   nodes if SGE is unavailable; this supersedes the earlier “do not use standalone” preference for
   this bounded run. `computingResource.md` identifies `rcapps3` (x86_64, 72 CPU cores, 1 TB RAM)
   and `rcapps8` (aarch64, 128 cores, 1 TB RAM). A live read-only check at 2026-10-19 22:59 EDT
   found `rcapps8` had 453 GiB available, but the shared R4.3.2 `Rscript` binary is x86-64 and
   fails there with `Exec format error`; system R 4.1.2 lacks `cladoRcpp` and `rhdf5`. It is not a
   launch candidate without unapproved environment work. `rcapps3` is x86_64-compatible and had
   917 GiB available, 72 CPUs, and load average 51.7; choose it only after a fresh preflight confirms
   sufficient available CPU/memory. Its cgroup/job-wide memory enforcement has not been established.
   Run PRINT at 16 workers, CPU-only, with a fail-closed 100-GiB aggregate-PSS watchdog over the
   dedicated process group; stop if group enumeration or PSS sampling fails. Do not claim it covers
   descendants that detach from that group. Keep GNU-time and watchdog samples separate. Preserve
   the existing per-process 44-GiB `RLIMIT_AS` gate without describing
   it as a task-wide cap. Maximum wall time is 24 h. No administrator contact, package install,
   environment change, optimization, accuracy scoring, motif discovery, or other caller is in scope.
   Exact sync path, output directory, command, and fail-closed preflight are in the dated handoff;
   obtain exact-head review in the fixed PMA conversation before executing the caller.

4. **Timing record and stop rule.** After exact-head review, run PRINT once on `rcapps3` via the
   directly logged-in standalone path. Record gate task ID/exit state; caller wall, user/system CPU,
   `/usr/bin/time -v` maximum RSS (label its process scope), watchdog aggregate process-group PSS
   samples/peak/stop reason; worker count; input/runner/model hashes; peak count and covered bases;
   per-scale track/event row counts and hashes; and caller wall time separately. The fragment file
   is precomputed, so BAM-to-fragment preparation is outside this caller timing.
   Existing BAM-to-fragment conversion time may be reported only with exact input/output hashes
   verified. The 100-GiB PSS watchdog threshold is sampled and may be exceeded between samples or
   during TERM grace; it is not a hard memory cap. No QSUB job ID or scheduler memory value applies.
   This run reports computation time/resources and native output statistics only. No accuracy claim,
   cross-tool rank, motif finding, retry, algorithm change, C/C++ optimization, or merge.

**Current status (2026-10-19 23:19 EDT; PR #8 HEAD to refresh after this update).** The fixed PMA conversation approved the PRINT-on-all-original-peaks task definition and the read-only input aggregates. The user selected direct-login standalone compute if SGE is unavailable. `rcapps8` is unsuitable due to its aarch64/x86 R mismatch. `rcapps3` had 917 GiB available, R 4.2.2 and required packages present; PRINT repo commit and sourced module hashes are pinned. After one exact-head review returned three concrete supervisor findings, the launcher was repaired: it records `/proc` sampling errors, checks `smaps_rollup` before launch, cleans the monitored group on signal/timeout/exception and waits for the main child, and requires non-header score rows plus all timing stages. The sampled 100-GiB PSS threshold is not a hard memory limit; monitoring covers only the dedicated process group. Exact-head execution review is pending. No PRINT caller has run; the prior 77,668-window proposal remains superseded.

**Status.** The earlier benchmark design was approved by ChatGPT on 2026-10-17 with revisions.
That approval does not cover material Section 4 revisions. The current read-only qualification is
documented in `docs/CODEX_HANDOFF.md` and the dated handoff. No caller is selected, and no C/C++ port
is approved.

**Existing same-pilot resource observation (2026-10-20).** The fixed PMA conversation approved
read-only extraction on exact HEAD `e44334e3b13e00ea53a67871b69f13f224172dfa`. The existing
HCT116 ctrl 2,000-window jobs recorded: HINT 2:02.64 wall / 81.82 s user+system CPU / 224,548 KB
max RSS; PRINT 17:46.01 / 231.41 s / 37,524,900 KB; TOBIAS 15:16.06 / 867.82 s / 411,100 KB;
TraceBIND PRINT-bias reduced mode 2:28:53 / 33,396.85 s / 14,415,888 KB. Each task record/GNU-time summary and wrapper completion marker recorded success. TraceBIND used four R workers; the other wrappers used different execution shapes, and
PRINT/TraceBIND preparation was outside the caller timer. These are descriptive pilot observations,
not comparable speed/resource ranks. The RSS is GNU-time's recorded maximum, not asserted as
process-tree aggregate. Accuracy is still `cannot rank` because the selected labels and shared-score
gates fail; the table cannot nominate an accuracy winner or authorize a cancer-wide run.

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
   consensus peaks from the matched degron experiment. A qualifying peak file must be the ENCODE
   IDR-thresholded narrowPeak set with IDR ≤ 0.05 from at least two independent biological
   replicates; technical replicates do not count. Freeze accession, biosample/clone, treatment,
   biological-replicate mapping, matched input, genome, file IDs, audits, MD5/SHA-256, pipeline
   version and blacklist in the candidate manifest. Read summit from narrowPeak column 10 (offset
   from BED start) and strength from column 7 (`signalValue`). Merge overlapping ±50-bp summit
   windows by connected component; retain the summit with greatest `signalValue`, ties by the
   frozen hg38 `chrom.sizes` order, lowest summit coordinate, then file ID and 1-based source row.
   Keep one control-ChIP summit per component. The same fixed summit and 100-bp window are used
   for every caller and both ATAC conditions. Freeze one caller-independent common ATAC callable
   mask as the union of the two matched-condition ENCODE IDR-thresholded ATAC narrowPeak sets
   (IDR ≤ 0.05), minus the frozen hg38 blacklist; retain only candidate windows fully inside this
   mask. If those exact consensus files are unavailable, stop until an equally fixed peak pipeline
   is reviewed; do not choose a caller's peak set. Caller events, STREME and TOMTOM do not create or
   remove candidates. Freeze the candidate manifest before reading caller scores. If exact
   provenance, independent biological replicates, matched input or peak QC are unavailable, stop:
   do not generate inferential occupancy labels.
2. **Treatment labels.** Require at least three matched independent biological-replicate pairs,
   each with control and auxin CTCF IP plus matched input, all with provenance and assay QC. Technical
   replicates are merged within each biological replicate before counting. Count deduplicated
   fragments in each IP/input BAM over the frozen candidate windows. A spike-in exposure is usable
   only when a fixed amount of exogenous chromatin was added at a documented stage, its read count
   represents recovery/sequencing exposure relevant to the target assay, and the spike does not vary
   with target condition or cell amount. Document spike species, amount, addition stage, mapping
   filters, IP/input handling and per-library counts. IP and matched-input aliquots require separately
   interpretable exposure factors; never reuse an IP factor for its input. If these conditions hold,
   define each DESeq2 size factor as its uniquely mapped exogenous spike-fragment count divided by
   the geometric mean of those counts across libraries. Do not add target-genome total-count, TMM or
   another library-size normalization on top. Spike added after IP calibrates only later stages; it
   cannot correct earlier IP/recovery differences. If timing or interpretation is unknown, fail closed
   rather than treating raw spike counts as valid exposure.

   Use an unshrunk DESeq2 negative-binomial interaction model with design
   `~ replicate_pair + condition + assay + condition:assay`, where `condition` is control/auxin and
   `assay` is matched input/IP. The estimand is the auxin-vs-control IP change minus the corresponding
   input change. Freeze factor levels, design-matrix columns, contrast direction, DESeq2 version,
   size factors, dispersion/fit settings and the complete tested-locus universe before assigning
   labels; require a full-rank design and record diagnostics. Require at least three matched,
   independent biological-replicate pairs. A locus is coverage-eligible only if both IP and matched
   input counts are ≥10 in at least two pairs in each condition. Test directional depletion
   (`lfcThreshold=0.5`, `altHypothesis="less"`, so interaction <−0.5) and equivalence
   (`lfcThreshold=0.5`, `altHypothesis="lessAbs"`, so |interaction|<0.5) on the same eligible
   universe with `independentFiltering=FALSE`. Apply BH separately to the complete eligible universe
   for each hypothesis; unavailable/Cook's-outlier p-values stay ambiguous and count conservatively
   in the multiplicity denominator. A `depleted` locus must be control-ChIP-bound, have interaction
   estimate ≤−1, depletion-test BH q≤0.05, and an unshrunk 95% Wald interval with upper bound <−0.5.
   A `retained` locus must have treatment replicate-supported IDR evidence, equivalence-test BH
   q≤0.05, and an unshrunk 90% Wald interval wholly within [−0.5,+0.5]. These are model-based
   asymptotic intervals, not exact or finite-sample guarantees; per-site interval coverage is nominal
   and does not itself control error in the selected label set. All other, low-coverage, discordant,
   outlier or missing-provenance loci are `ambiguous` and excluded. A missing peak alone is never a
   negative. If biological pairs, matched inputs, interpretable spike exposures, or model diagnostics
   are absent/failed, stop; do not substitute technical replicates or uncalibrated normalization.
   These are conservative eligibility gates for this HCT116 benchmark, not universal standards. The
   available handoff currently reports technical rather than biological replication, so these labels
   are not presently eligible to generate.
3. **Score mapping and primary endpoint.** Evaluate the treated ATAC caller score at each frozen
   control-ChIP summit using the maximum threshold-free, continuous score in the same ±50-bp
   interval. Before labels are joined, the adapter manifest must freeze each tool's exact source
   commit/package build, command parameters, model/resource hashes, score field, units, direction,
   scale, file checksum and mapped genome interval. The current `events_from_track.py` event
   converter is not an AP adapter: it replaces missing bigWig values with zero for event output,
   so it must not be reused to build AP inputs. AP extraction must preserve the common mask and
   represent invalid coverage separately:

   | Caller | Current wrapper's primary candidate signal | Direction / current status |
   |---|---|---|
   | PRINT | `run_print.R` `.r10.track.tsv.gz`, column `score` (`aggregateScores`; radius 10 only; do not select a radius after seeing labels) | Higher `−log10(p)` is stronger; continuous track. Exact `print_repo` commit and dispersion/bias resource hashes are not yet frozen; no AP until recorded. |
   | TOBIAS | `run_tobias.sh` `footprints.bw`, TOBIAS 0.17.5 default FootprintScores/ScoreBigwig (`score=footprint`) value | Higher score indicates stronger footprint evidence and includes local accessibility. Freeze all score parameters and input hashes. |
   | HINT | `run_hint.sh` `events.bed`, RGT 1.0.2 | Thresholded intervals only in the current wrapper; unscorable for primary AP unless a documented, threshold-free per-base signal is added and frozen. BED score, if present, is not assumed continuous. |
   | TraceBIND | `run_tracebind.R` `.events.bed`, column 5 `−log10` BH-adjusted p, emitted only after `p_threshold=0.05` | Threshold-truncated events only in the current wrapper; package commit and model-resource hashes are not frozen; unscorable for primary AP. Do not treat the surviving event score as a full continuous track. |

   The fixed candidate window must be fully covered by the same predeclared callable mask for every
   caller. A finite observed score below a caller's event threshold remains a valid continuous
   score; it is not a no-call. A thresholded caller's absent event is not zero. Missing track
   coverage is `unscorable`, a failed caller/run invalidates that run (never silently drops loci),
   and a valid observed numeric zero remains zero only where the pinned tool's documentation defines
   that value. Report per-tool coverage and the exact common-site count. Four-way AP is allowed only
   if all four frozen adapters score every site in the same common mask; otherwise report only
   pairwise/subset comparisons on explicitly named shared sites and declare no four-tool winner.
   Compute pooled out-of-fold average precision (AP; non-interpolated area under the PR curve) for
   `retained` versus `depleted` loci. Do not use ChIP summit coordinates differently by class.
4. **Held-out split and inference.** Assign non-overlapping 1-Mb genomic blocks to five folds by
   `int(SHA256("PMA-4b-20261019|" + chromosome + ":" + block_start)[0:8], 16) % 5`, where
   `block_start` is the zero-based coordinate of the block's first base and chromosome order comes
   from the exact hg38 `chrom.sizes` file frozen with the candidate manifest. All paired conditions,
   replicates and loci in a block stay together. For each outer fold, every data-dependent fit or
   selection (sample-specific bias adaptation, normalization, scale selection and threshold tuning)
   must use training blocks only; pre-trained parameters are allowed only with a frozen
   external version/resource hash. An adaptation that consumes held-out reads, sequence-derived
   counts or test-fold score distributions is transductive and cannot support the primary held-out
   AP claim. Freeze each caller's maximum score-context radius from its pinned source/command and
   adapter. At a fold boundary, use a symmetric embargo `E=max(50 kb, 50 bp + C_j)`, where `C_j` is
   that verified context radius; remove embargo-overlapping read/sequence evidence from training and
   adaptation, and exclude scoring windows whose full dependency interval intersects the embargo. If
   a tool's context or fold-excluded execution cannot be verified, strict AP for it is ineligible. If
   a caller cannot produce fold-excluded scores, mark it ineligible for strict AP and report any
   all-sample score comparison separately as exploratory. Map each held-out raw score to
   its caller-specific training-fold empirical percentile (mid-rank; values outside the training
   range map to 0 or 1) before pooling out-of-fold AP, so fold-specific score scales are not pooled
   raw. The symmetric boundary embargo is defined above; also exclude scoring windows crossing a
   fold boundary. Select the operating
   threshold only in the four training folds: choose the highest score cutoff whose inclusive
   tie rule yields at least 80% retained-site recall; apply it unchanged to the held-out fold. If
   a training fold has fewer than 20 retained or 20 depleted eligible loci, its operating threshold
   is unestimable and matched-recall/B1 selection is unavailable for that fold. Also report
   predeclared 50%, 70% and 90% recall cutoffs as secondary results. Pool one out-of-fold score per
   locus for AP. For uncertainty, draw at least 100,000 paired bootstrap replicates of 1-Mb blocks,
   resampling identical blocks for all callers with seed `PMA-4b-bootstrap-20261019`; preserve all
   loci and labels within each sampled block. Do not use score-vector swaps: AP equality does not
   imply exchangeability. Discard draws without both labels and continue the seeded stream; if over
   5% of attempted draws are invalid, inferential AP is unavailable. Run two predeclared batches of
   50,000 valid draws. If any of the six pairwise AP-difference interval endpoints differ by more
   than 0.005 AP between batches, add batches of 100,000 valid draws until all endpoints are within
   0.005 of the pooled estimate or 1,000,000 valid draws; if stability is not reached, ranking is
   unavailable. For six comparisons, report Bonferroni simultaneous 99.1667% percentile intervals
   (1−0.05/6). These are approximate bootstrap intervals, not finite-sample guarantees. Inference is
   conditional on the fixed candidate universe, labels, blocks and already-fitted out-of-fold scores;
   it excludes refitting variability and does not establish cross-experiment generalization. Treating
   1-Mb blocks as independent is an approximation; long-range dependence and shared training models
   remain. If a caller has an invalid run, report its pairwise estimands unavailable instead of
   changing the frozen universe. A local AP leader requires the candidate's three pairwise AP-difference
   intervals against the other three callers to have lower bounds above zero. All six pairwise
   comparisons remain in the Bonferroni family.
5. **B1–B4 and selection.** B1 naked gDNA is specificity evidence only: apply the same training-fold
   cutoff and one frozen event adapter (21-bp event width, peak at local maximum, greedy NMS with
   minimum center distance 21 bp) to report naked-DNA false-event density per callable Mb and per
   million usable aligned fragment ends after matching depth. Naked-DNA runs can contain Tn5 insertions
   and cut sites, but they lack protein-protection footprint truth; report this as false-event density,
   not conventional binary FPR. If inferred insertion endpoints are additionally reported, freeze the
   fragment-to-insertion coordinate transform (including any +4/−4 shift) and its denominator.
   Freeze chromosome order and score ties: score descending, then frozen `chrom.sizes` order,
   coordinate ascending and stable event ID; a plateau's representative local maximum is its leftmost
   base. Apply an inclusive raw-score cutoff (`score >= cutoff`). Greedy NMS keeps centers at exactly
   21 bp apart (`distance >= 21 bp`). Run NMS once over each complete fold's callable territory after
   mask/embargo exclusions and before assigning events to candidate windows; an event counts only if
   its full 21-bp interval lies within that territory and mask. Missing coverage, failed calls and
   nonfinite scores invalidate the fold/run rather than being zero-filled or silently dropped.
   Apply each caller's unchanged, fold-specific HCT116 training cutoff to the corresponding B1
   genomic fold using the same frozen score field, model and resources; do not fit, adapt or recalibrate
   on naked-DNA reads. For each eligible B1 library `i`, let `E_i` be its usable fragment-end count,
   `C_i` its callable bases, `r_min = min_i(E_i/C_i)`, and `T_i = floor(r_min*C_i)`. Sort eligible
   paired fragments by ascending SHA-256 of `PMA-4b-B1-depth-20261019|<QNAME>`, breaking hash ties
   by QNAME byte order. Retain the longest prefix whose cumulative usable ends do not exceed `T_i`
   (do not split pairs); report `T_i`, the attained count and any residual. Count only ends passing
   the frozen usability predicate. Report usable ends,
   callable bases, raw cutoff, per-fold rate and pooled `sum(events)/sum(callable Mb)`. B1 is not
   positive truth. Report the
   corresponding held-out HCT116
   retained-site recall separately. B2 tests the paired ctrl→aux score change at ChIP-depleted
   versus retained loci; it reuses the primary labels and is not independent validation. B3 uses
   occupancy data independent of this benchmark and
   caller development; if none is available, state that generalization is unvalidated. The
   TraceBIND developers' HCT116 degron set is an author-benchmark reanalysis, not independent
   validation. B4 replicate reproducibility and motif-family recovery are supporting evidence only.
   Declare a **local HCT116 CTCF AP leader** only when one caller's held-out AP exceeds every other
   caller in the four-way common mask and the candidate's three simultaneous pairwise AP-difference
   intervals have lower bounds above zero. Otherwise
   report no AP leader or only the supported pairwise subset. Report B1 specificity and B2 direction
   separately; if either materially conflicts with the AP result, say evidence is mixed and do not
   name an overall best tool. Do not add post-hoc weights. This benchmark cannot establish a
   universal or pan-cancer winner. Accuracy
   selects the candidate first; speed is compared separately, and C/C++ work is considered only
   after profiling a validated accuracy candidate.

## 5. Speed gate

**Measured unit.** One sample of 100 M uniquely mapped paired-end fragments, on Argos CPUs.

| Limit | Value |
|---|---|
| CPU threads | 32 |
| Resource gate for the current one-shot assessment | 44-GiB `RLIMIT_AS`; never exceed the PMA per-task ≤50-GB hard cap. Record peak RSS separately because it is not the same quantity. |
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
