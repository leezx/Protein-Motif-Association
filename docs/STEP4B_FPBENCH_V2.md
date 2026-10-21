# Step 4b — footprint caller benchmark v2 (K562, chr1–2)

Supersedes the HCT116 CTCF-degron protocol in `STEP4B_ATAC_FOOTPRINT_BENCHMARK_DESIGN.md` §4 for tool selection.
That protocol could not produce labels (one biological ChIP replicate per condition), so no caller was ever scored.
v2 uses the standard motif-site benchmark from the HINT-ATAC, TOBIAS and PRINT papers.

## Design (fixed before any caller score was read)

| Item | Choice |
|---|---|
| ATAC | ENCODE K562 `ENCSR868FGK`, BAM `ENCFF534DCE`; filtered MAPQ ≥ 30, proper pair, no dup/secondary/supplementary |
| Regions | `ENCFF993BAP` IDR peaks on chr1 + chr2 → summit ± 500 bp, non-overlapping (greedy by signalValue): 14,437 × 1 kb |
| Shared inputs | one filtered BAM (TOBIAS, HINT) and the fragments derived from it, Tn5-shifted +4/−5 (PRINT, TraceBIND, scPrinter) |
| Truth | ENCODE K562 TF ChIP-seq, GRCh38 conservative IDR peaks, ≥ 2 biological replicates, no ERROR/NOT_COMPLIANT file audit, JASPAR 2026 CORE motif with the same name: 208 TFs |
| Sites | MOODS p < 1e-4 in the windows, centre ≥ 100 bp from window edges; best hit per overlapping cluster. bound = overlaps that TF's peak, unbound = no overlap |
| TFs scored | ≥ 30 bound and ≥ 30 unbound sites: 146 TFs, 761,832 sites |
| Site score | max caller score over the motif ± 5 bp |
| Metrics | per-TF AUPR and AUROC; median over TFs; difference to the accessibility baseline on the same sites |
| Baselines | `access`: Tn5 insertions ± 100 bp of the site centre. `naive_fp`: −FOS from raw insertions (no bias model) |
| Compute | rcapps3 (x86_64, 72 cores, 1 TB), one caller at a time, 16 cores each; `measure.py` records wall, user+sys CPU and peak process-tree PSS |

Motifs only define evaluation sites. No caller sees motifs or ChIP.

Callers and scores:

| Caller | Version / mode | Score used |
|---|---|---|
| TOBIAS | 0.17.5, ATACorrect + FootprintScores | FootprintScores bigWig |
| HINT-ATAC | RGT 1.0.2, `--atac-seq --paired-end` | footprint BED score; 0 outside calls (thresholded caller) |
| PRINT | buenrostrolab/PRINT `8dad731`, upstream R functions unmodified, precomputed hg38 Tn5 bias | −log10 p, radius 10 (primary) and 20 |
| TraceBIND | 0.1.0, PRINT Tn5 CNN bias (no mtDNA fine-tuning / mito-FDR) | max −log10 BH p over footprint widths 10–40 bp |
| scPrinter | GitHub main `ed7cafba`, CPU, PRINT hg38 bias h5 | −log10 p, modes 10 and 20 |

## Results (2026-10-21)

All five callers finished on all 14,437 windows with exit code 0. Site coverage ≥ 98 % for every score.

### Accuracy, 146 TFs, 761,832 sites

| Method | median AUROC | median AUPR | AUROC within access quintiles | TFs > access (stratified) | median CV gain over access |
|---|---|---|---|---|---|
| access (baseline) | **0.806** | **0.341** | **0.591** | — | — |
| TOBIAS | 0.798 | 0.323 | 0.575 | 35 | −0.0007 |
| HINT-ATAC | 0.632 | 0.251 | 0.540 | 23 | +0.0005 |
| TraceBIND | 0.560 | 0.187 | 0.522 | 14 | −0.0002 |
| scPrinter r10 | 0.558 | — | 0.524 | 18 | −0.0002 |
| PRINT r10 | 0.537 | 0.125 | 0.522 | 17 | −0.0002 |
| scPrinter r20 | 0.522 | — | 0.515 | 19 | −0.0002 |
| PRINT r20 | 0.514 | 0.133 | 0.511 | 17 | −0.0002 |
| naive_fp (−FOS) | 0.492 | 0.126 | 0.503 | 11 | −0.0005 |

- Stratified AUROC: within-TF accessibility quintiles, weighted by bound × unbound per stratum (strata need ≥ 10 of each).
  Added after the first TOBIAS/access scores were seen; disclosed as post hoc.
- CV gain (`05_added_value.py`): per-TF 5-fold CV logistic regression AUROC of access + caller minus access alone,
  same folds, rank-normalised features. Also post hoc.
- No caller beats the accessibility baseline for the median TF, on any metric.
  TOBIAS tracks accessibility (per-TF Spearman with access 0.76); PRINT, scPrinter and TraceBIND do not (≤ 0.16), and
  PRINT and scPrinter agree with each other (ρ 0.94).
- Footprint signal beyond accessibility is real but confined to a few long-residence TFs:

| TF | access | TOBIAS | HINT | PRINT r20 | scPrinter r20 | TraceBIND |
|---|---|---|---|---|---|---|
| CTCF AUROC | 0.653 | 0.710 | 0.733 | 0.844 | **0.848** | 0.795 |
| CTCF stratified | 0.546 | 0.722 | 0.641 | 0.831 | **0.834** | 0.770 |
| CTCF CV gain | — | +0.119 | +0.108 | +0.199 | **+0.201** | +0.134 |
| NFIX CV gain | — | +0.010 | — | +0.087 | +0.078 | +0.057 |

  JUNB (+0.02–0.03) and MAFK (+0.015–0.025) are the only other TFs with a gain ≥ 0.01 shared across PRINT-family callers.

### Resources (rcapps3, 16 cores, one caller at a time)

| Caller | wall | CPU h | avg busy cores | peak PSS | full-genome wall at 16 cores (linear) |
|---|---|---|---|---|---|
| HINT-ATAC | 3.7 min | 0.57 ¹ | 9.4 | 2.6 GB | 0.33 h |
| scPrinter | 5.9 min ² | 0.85 ³ | 1.1 | 24.4 GB | 0.52 h |
| TOBIAS | 11.1 min | 2.23 ¹ | 12.1 | 2.3 GB | 0.98 h |
| PRINT | 23.8 min | 1.95 ⁴ | 4.9 | 38.4 GB | 2.10 h |
| TraceBIND | 363.7 min | 80.1 | 13.2 | 36.1 GB | 32.1 h |

1. rusage of reaped children (run before the per-process sampler); consistent with the busy-core average.
2. Excludes this benchmark's own bedgraph writer (2,553 s of Python formatting, harness code). scPrinter itself:
   fragment import 172 s, footprinting 126 s.
3. Includes the export step.
4. From the `print_cpu` rerun (same inputs, wall 23.7 min); the first run's rusage missed forked workers.

- Full genome = 76,558 windows (factor 5.30). Fixed costs (bias load, imports) make this an upper estimate.
- PRINT stages: bias 81 s, counts 286 s, radius 10 458 s, radius 20 463 s. Peak memory is the genome-wide bias load.
- TraceBIND stages: bias 3,683 s, counts 320 s, footprint 17,752 s. Its first hour overlapped short smoke tests and
  scoring on the same host.
- Speed gate from the v1 design (100 M fragments ≤ 4 h on 32 CPUs within 40 GiB), judged from the
  linear full-peak-set estimate at 16 cores (this run: 21.5 M fragments on chr1–2):
  HINT, TOBIAS, scPrinter pass; PRINT passes on time but sits at 34–38 GB; TraceBIND fails (~32 h at 16 cores).

### Conclusion

- On ChIP-labelled motif sites, accessibility alone is the best predictor of occupancy for 146 K562 TFs.
  TOBIAS reproduces it; the PRINT family and TraceBIND discard it by design and add almost nothing for the median TF.
- If a footprint caller is needed for CTCF-like TFs, scPrinter is the pick: best CTCF accuracy (= PRINT, ρ 0.94),
  ~4× faster than PRINT and ~60× faster than TraceBIND. A C port of PRINT is not justified by these data.

## Independent validation: GM12878 (2026-10-21)

Pre-specified replication: every step, threshold and metric is the one fixed on K562; only the fragment barcode
became a parameter. Driver `scripts/04b_fpbench/run_replicate_cell.sh`, comparison `06_compare_cells.py`.

- Input: ENCODE `ENCSR637XSC`, rep 1 filtered alignments `ENCFF981FXV` and IDR peaks `ENCFF914YHG` (md5 checked;
  Argos `raw/2026-10-21/encode_gm12878/ENCSR637XSC/`). chr1–2, 16.7 M fragments, 15,708 × 1 kb windows.
- Truth: 75 TFs with GM12878 ENCODE conservative IDR ChIP and a JASPAR motif; 63 pass the ≥ 30 bound / ≥ 30 unbound
  filter (258,642 sites, 40,802 bound). 43 TFs are scored in both cell lines.
- Results (`result/fpbench_gm12878_v1/eval/`; median over 63 TFs):

| method | AUROC K562 → GM12878 | stratified AUROC | median CV gain | CTCF CV gain K562 / GM12878 |
|---|---|---|---|---|
| access | 0.806 → 0.845 | 0.591 → 0.603 | — | — |
| TOBIAS | 0.798 → 0.837 | 0.575 → 0.593 | −0.001 / −0.001 | +0.119 / +0.169 |
| HINT-ATAC | 0.632 → 0.660 | 0.540 → 0.560 | 0.000 / −0.000 | +0.108 / +0.121 |
| TraceBIND | 0.560 → 0.562 | 0.522 → 0.536 | −0.000 / −0.001 | +0.134 / +0.216 |
| scPrinter r20 | 0.522 → 0.542 | 0.515 → 0.534 | −0.000 / −0.000 | +0.201 / +0.262 |
| PRINT r20 | 0.514 → 0.536 | 0.511 → 0.528 | −0.000 / −0.000 | +0.199 / +0.264 |
| naive FOS | 0.492 → 0.493 | 0.503 → 0.497 | −0.001 / −0.000 | +0.038 / +0.051 |

- The method ranking and the null median gain replicate; the CTCF gain replicates for every caller and is larger.
- Per-TF gains across the 43 shared TFs agree poorly (Spearman ρ −0.02 HINT to 0.53 TOBIAS; TraceBIND 0.30). Only CTCF
  (all callers) and REST (TOBIAS, HINT) gain ≥ 0.01 in both lines; the small gains of other TFs are noise.
- GM12878 runtimes are not resource data (TraceBIND ran alongside the other callers); resources come from K562 only.
- Figure and write-up: `PR/Protein–Motif-Association/Figures/Footprint_benchmark/` (panel f; `Fig_fpbench_k562.result.md` v0.3).

## Limits

- Two cell lines (K562 discovery, GM12878 replication), two chromosomes each. Runtime extrapolation to all 159,628 peaks is linear in windows and labelled as such.
- ChIP overlap is occupancy, not base-level footprint truth; indirect binding and motif-less peaks add label noise
  equally for every caller. Unbound sites may hold undetected binders.
- K562 ATAC `ENCSR868FGK` carries an ENCODE nucleosome-free-fraction warning.
- No naked-DNA specificity layer in this round.
- TraceBIND ran without mtDNA bias fine-tuning or its mito-FDR, so its native calls are not at full strength.
- The scores reward occupancy, which correlates with accessibility; a caller that removes accessibility on purpose
  is judged by the stratified AUROC and CV gain, not the raw AUROC.

Code: `scripts/04b_fpbench/` (`00`–`05`, `measure.py`, `run_*`). Tables: `eval/summary.tsv`, `per_tf_metrics.tsv`,
`added_value_*.tsv`, `resources.tsv`. Results (Argos): `DATA/2.PROJECTS/PMA/atac_footprint/result/fpbench_k562_v1/` and `fpbench_gm12878_v1/`.
