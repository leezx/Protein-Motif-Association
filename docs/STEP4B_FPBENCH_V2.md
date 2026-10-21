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
| scPrinter | GitHub main, CPU | −log10 p, modes 10 and 20 |

## Limits

- One cell line, two chromosomes. Runtime extrapolation to all 159,628 peaks is linear in windows and labelled as such.
- ChIP overlap is occupancy, not base-level footprint truth; indirect binding and motif-less peaks add label noise
  equally for every caller. Unbound sites may hold undetected binders.
- K562 ATAC `ENCSR868FGK` carries an ENCODE nucleosome-free-fraction warning.
- No naked-DNA specificity layer in this round.

Code: `scripts/04b_fpbench/`. Results (Argos): `DATA/2.PROJECTS/PMA/atac_footprint/result/fpbench_k562_v1/`.
