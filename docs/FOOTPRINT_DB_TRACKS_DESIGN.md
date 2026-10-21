# Public footprint databases → per-source sample-count tracks (hg38)

User request (2026-10-21):
- Download the per-sample footprints from public footprint databases.
- Build one bigWig per source. The signal is the number of samples with a footprint at each base, in the same
  style as the ChIP-Atlas evidence tracks.
- For Vierstra 2020, take only the per-sample footprint BEDs and the consensus files. Use FPR 0.001 as the main
  track and FPR 0.01 as the looser version.

## Sources surveyed (2026-10-21)

| Source | Per-sample footprints | Build | Samples | Used |
|---|---|---|---|---|
| Vierstra et al. 2020 *Nature* (Altius, footprint-tools) | `per.dataset/<sample>/interval.all.fps.<FPR>.bed.gz`, FPR 1e-4 … 0.2 | hg38 | 243 DNase-seq | yes, at FPR 0.001 and 0.01 |
| Funk et al. 2020 *Cell Rep* (ENCODE DNase/FAIRE; HINT and Wellington) | FILER2 mirror `TF-footprint-atlas/<assay>/bed14/hg38/<ENCSR>.<tissue>_<method>_<seed>-footprint.bed.gz`. Rows are footprint × motif hits; footprint coordinates are in columns 7–8. The paper's NeMO link is dead. | hg38 | 155 DNase + 6 FAIRE experiments (163/6 files per method) | yes: DNase and FAIRE × HINT and Wellington, alignment seed 20 only (seed 16 is the same data with a different aligner seed) |
| Neph et al. 2012 *Nature* (UW ENCODE) | EBI `integration_data_jan2011/byDataType/footprints/jan2011/all.footprints.gz`: a single file with a cell-type column, FDR 1% | hg19 | 41 cell types | yes, lifted to hg38 with UCSC liftOver; unmapped count recorded |
| Boyle et al. 2011 *Genome Res* (Furey lab) | per-cell-line BED (`<line>_footprints_hg18.bed`) + `Combined_GM` + `All_footprints_hg18.tgz` | hg18 native (their hg19 = liftover) | 7 lines (GM12891, GM12892, H1 ES, HeLa-S3, HUVEC, K562, NHEK) | yes: hg18 → hg38 liftOver, track `boyle2011_hg18` (Combined_GM kept in raw, not counted) |
| footprintDB (Sebastian 2014 *Bioinformatics*) | — (motif/TF interface database) | — | — | no genomic footprints |
| PRINT / scPrinter (Hu 2025 *Nature*, Zenodo 15399859) | no footprint BEDs; 6 example PBMC TFBS-score bigWigs (Bcell/Monocyte/Tcell × 2) | (hg38 tutorial) | 6 tutorial pseudo-bulks | raw only (continuous TFBS score, not footprint calls; no count track) |
| GTRD | site not reachable on 2026-10-21 (timeouts) | — | — | not verified |
| TOBIAS | no precomputed human atlas (only mouse embryo results on figshare) | — | — | no |

## Track definition

- Unit: base pair, on chr1–22, X and Y.
- For each sample: take the unique footprint intervals, clipped to chromosome ends and merged within the sample,
  so each sample counts at most once per base.
- Signal = the number of samples whose footprints cover the base (`bedtools genomecov -bg` over the merged
  per-sample intervals).
- One track per source/variant, never mixed:
  - `vierstra2020_fpr0.001`, `vierstra2020_fpr0.01`;
  - `funk2020_{dnase,faire}_{hint,wellington}`;
  - `neph2012_fdr0.01`.
- Blacklist split as for the ChIP-Atlas tracks (`04a_chipatlas/10_mask_blacklist.py`).
- QC (`02_footprint_track_qc.py`):
  - sum(value × bp) equals total footprint bp;
  - 1 ≤ value ≤ number of samples;
  - the bedGraph is sorted and non-overlapping;
  - recount by tabix at 600 random positions;
  - plus a synthetic test with known answers.
- Interpretation: the signal is the number of samples in which some caller found a footprint. Different callers
  and thresholds are not on the same scale, so tracks from different sources are compared by pattern, not by
  value.

## Layout

- One dataset per source: `DATA/2.PROJECTS/PMA/footprint_{vierstra2020,funk2020,neph2012}/`.
  - `raw/2026-10-21/` holds the downloads with MD5SUMS.
  - `processed/tracks_v1/<variant>/` holds `footprints.bed.gz`, `samples.tsv`, `<variant>.samples.{bw,bedGraph.gz}`
    and `qc.json`, plus the blacklist splits.

## Integrated / consensus files (user, 2026-10-21: "没有per sample的就下载整合后的footprint bed文件，独立保存")

Kept as separate files and not merged into the count tracks. All are in hg38: files already in hg38 are kept as
they are, and the others are lifted with `03_lift_bed.sh`, keeping all columns and recording the unmapped
footprints.

| Source | File | Build → hg38 |
|---|---|---|
| Vierstra 2020 | `consensus.index/consensus_footprints_and_collapsed_motifs_hg38.bed.gz`, plus the other consensus files | native |
| Neph 2012 | `combined.fps.gz` (8.37 M combined footprints, 41 cell types) | hg19 → hg38 |
| Boyle 2011 | `Combined_GM_footprints_hg18.bed` | hg18 → hg38 |
