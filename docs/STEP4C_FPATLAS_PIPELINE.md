# Step 4c — footprint atlas: per-sample pipeline and pilot (2026-10-21)

Goal: motif-free footprints for every ChIP-Atlas hg38 ATAC-seq and DNase-seq experiment, merged later into a
ChIP-Atlas-style reference (layer 1: HINT discrete footprints, per-sample BED + sample-count bigWig; layer 2: TOBIAS
continuous scores with an explicit normalisation, not started). This document covers the per-sample pipeline and
its two-sample pilot only. **No full-scale run has been started** (user instruction: hold after the pilot).

Tool choice follows the Step 4b benchmark (`STEP4B_FPBENCH_V2.md`): HINT is the fastest caller with discrete calls
(3.7 min / 14k peaks, 2.6 GB) and is the second-best footprint score after TOBIAS on the median TF.

## Inputs

- Run tables (Argos, md5 checked): `DATA/2.PROJECTS/PMA/occupancy_chipatlas/processed/light_v1/raw_accessions/
  PMA_chipatlas_hg38_{ATAC,DNase}_included_runs.tsv` — 18,651 ATAC / 2,086 DNase experiments (SRX) with their runs,
  ENA FASTQ URLs and md5, ChIP-Atlas read counts and peak counts. Columns used: 2 experiment, 3 run, 12 ChIP-Atlas
  reads, 15 ChIP-Atlas peaks, 16 layout, 21 fastq_ftp, 22 fastq_md5.
- Reference (`atac_footprint/processed/fpatlas_ref/`, built by `setup_fpatlas.sh`): hg38 primary assembly
  (chr1–22, X, Y, M) extracted from `atac_footprint/raw/2026-10-17/reference/hg38.fa`, chromap index (build 4.3 min, 26.5 GB RAM, 12.3 GB file),
  chrom sizes, ENCODE blacklist v2, md5 and an explicit conda environment list.

## Pipeline (`scripts/04c_fpatlas/fp_sample.sh`, one SRX per call)

| step | what | tools / parameters |
|---|---|---|
| 1 runs | runs of the SRX from the table; **R1** check | ENA portal `filereport` (`read_run`, `run_accession,read_count`) |
| 2 download | FASTQ of all runs; ChIP-Atlas peaks in parallel | aria2c 1.37: ftp first, https fallback; `-j 2 -x 8 -s 8`, md5 verified per file; paired runs keep only `_1`/`_2`; SRA `prefetch` + `fasterq-dump` only if ENA has no FASTQ. Peaks: `chip-atlas.dbcls.jp/data/hg38/eachData/bed05/<SRX>.05.bed` |
| 3 align | all runs in one call, streamed to a sorted BAM; **R2** check | chromap 0.2.6 `--remove-pcr-duplicates -q 30 -l 2000 --low-mem --SAM` (+ `--trim-adapters` for paired ATAC) → FIFO → samtools 1.21 `sort -m 3G -l 1` |
| 4 regions | ChIP-Atlas peaks of the same SRX after **P1** + **P2**; else MACS3 | chr1–22, X, Y; minus blacklist; merged. MACS3 fallback `-q 0.01 --keep-dup all` (BAMPE; SE ATAC `--nomodel --shift -100 --extsize 200`; SE DNase `--shift -75 --extsize 150`) |
| 5 footprints | HINT in the regions, regions split into one chunk per thread | RGT 1.0.2 `rgt-hint footprinting --organism=hg38`; ATAC `--atac-seq [--paired-end]`; DNase `--dnase-seq --bias-correction --bias-type=DH` (default DH = double-hit; SH selectable) |
| 6 QC | one row per SRX in `<assay>/qc.tsv` (flock) | reads in/mapped/kept, region source and check, n regions, n footprints, stage times, host |

Identity checks — raw data and ChIP-Atlas peaks must come from the same experiment:

- **R1** the live ENA run list for the SRX equals the table's run list, and the summed ENA `read_count` equals the
  ChIP-Atlas read count (verified exact for SRX4978105: 79,102,909 = 43,308,782 + 35,794,127). Fail → stop.
- File identity: every FASTQ md5 = ENA md5 (aria2 `--check-integrity`).
- **R2** chromap input reads within 98–100 % of the ENA count (×2 for paired). chromap counted 0.4 % fewer than
  2 × ENA for SRX4978105, so exact equality is not usable. Fail → stop.
- **P1** every peak name starts with `<SRX>.05_peak_` and the peak count equals ChIP-Atlas `n_peaks`.
- **P2** our reads inside the peaks ≥ 3 × our reads in the same peaks shifted by 100 kb.
- P1 or P2 fails → ChIP-Atlas peaks are discarded and MACS3 runs on our own alignment; recorded in `qc.tsv`.

Kept output per SRX: `<outdir>/<assay>/<SRX>.hint_fp.bed.gz` (chrom, start, end, SRX, HINT score, strand) and the QC
row. All intermediates (FASTQ, BAM, peaks, HINT chunks) live in a per-job directory on node-local disk
(`$TMPDIR` = `/ncache0/<job>`) and are deleted on exit, success or failure. A monitor inside the pipeline's process
group kills the group and clears scratch if the SGE job shell dies (qdel and h_vmem kills on Argos do not reach
every child).

SGE wrapper `qsub_fp.sh`: `all.q`, `-pe smp 16`, `h_vmem=100G` (per-process ulimit on Argos), `m_mem_free=4G` per
slot; task list `<ATAC|DNase>\t<SRX>`; per-task `resources/<SRX>.{json,log,scratch_peak_bytes}` from `measure.py`
(1 s process-tree CPU and PSS) and a 15 s `du` of scratch; failures appended to `failed.tsv`.
Submit: `qsub -t 1-<n> -tc <k> -v LIST=<tasks.tsv>,OUT=<root>,FPATLAS_CODE=<code dir> qsub_fp.sh`.

## Pilot results (`atac_footprint/result/fpatlas_pilot_v1/`, job 3660361, 16 slots each, run one after the other)

| | ATAC SRX4978105 | DNase SRX2370598 |
|---|---|---|
| input | 2 runs, PE, 79.1 M pairs, 9.5 GB FASTQ | 2 runs, PE, 87.1 M pairs, 4.3 GB FASTQ |
| R1 / R2 | pass / 157,555,936 of 158,205,818 reads (99.6 %) | pass / 174,113,576 of 174,113,576 |
| mapped / kept after MAPQ + dedup | 145.0 M / 112.4 M | 132.7 M / 100.5 M |
| regions | ChIP-Atlas, P2 ratio 10 → 34,191 merged | ChIP-Atlas, P2 ratio 18 → 56,553 merged |
| footprints | 153,770 (1.3 MB BED.gz) | 35,406 (0.35 MB BED.gz) |
| wall total | 59.7 min | 41.8 min |
| download / align / regions / HINT | 33.6 / 22.6 / 0.4 / 3.1 min | 23.6 / 12.3 / 0.3 / 5.6 min |
| CPU | 3.4 CPU h (avg 3.5 cores busy) | 2.3 CPU h (avg 3.3 cores busy) |
| peak memory | PSS 38.1 GB; SGE maxvmem 42.3 GB; chromap alone 28.1 GB | PSS 27.4 GB; maxvmem 38.6 GB; chromap 19.5 GB |
| peak node-local scratch | 57.0 GB | 25.1 GB |
| host | argos6 | argos4 |

- Compute per sample is small (2–3.5 CPU h); ENA download is the largest stage and the scaling limit. Observed
  per-file speed 1–8 MB/s; ENA refuses or throttles parallel connections from the cluster's address (rounds 3–4
  saw `CN:1` and connection refused). All ATAC + DNase FASTQ is ~100 TB: ~230 days at 5 MB/s, ~23 days at 50 MB/s.
- DNase SRX2370598 gave 4× fewer footprints than ATAC from 1.7× more regions; not investigated yet (DH bias model,
  HINT DNase thresholds or sample quality).

## Debug history (rounds 1–4, logs in `fpatlas_pilot_v1/attempt{1..4}/`)

1. chromap without `--low-mem` held all mappings for dedup (53–64 GB) → killed by h_vmem. Fix: `--low-mem`.
2. `--low-mem` with `-o /dev/stdout` aborts (writes `<output>.temp`) → exit 134. Fix: output to a FIFO in scratch.
   Orphaned aria2c/chromap/samtools after qdel → in-group monitor (`FPATLAS_PARENT`).
3. Two concurrent jobs: ENA ftp `CN:1`, ~1 MB/s, aria2 gave up (exit 5). Fix: 2 × 8 connections, https fallback,
   `-tc 1`.
4. Both reached alignment; ATAC stopped on exact R2 equality (fixed to 98–100 %), DNase HINT crashed because
   `--dnase-seq` does not create its output folder (fixed with `mkdir`).
5. Both PASS (table above).

## Open decisions before any scale-up

- Subset: all 20.7k experiments vs a depth / cell-type subset (ATAC PE ≥ 50 M reads: 2,296 experiments, 23.7 TB;
  DNase PE ≥ 50 M: 444, 5.5 TB).
- Download route: capped concurrency against ENA vs the AWS SRA mirror (`s3://sra-pub-run-odp`).
- Atlas definitions: per-sample denominators (fraction tracks), depth downsampling, ATAC and DNase as separate
  tracks, TOBIAS within-sample percentile normalisation for layer 2.

Code: `scripts/04c_fpatlas/` (`fp_sample.sh`, `qsub_fp.sh`, `setup_fpatlas.sh`, `measure.py`), branch
`task_20261020_fpbench_v2`.
