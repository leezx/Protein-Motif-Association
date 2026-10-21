#!/usr/bin/env bash
# PMA footprint atlas: one ChIP-Atlas experiment (SRX) from raw reads to a HINT footprint BED, built for speed.
#   ENA FASTQ via aria2c (ftp, https fallback; 2 files x 8 connections; md5 checked; SRA prefetch + fasterq-dump only when ENA has none)
#   -> chromap on all runs of the experiment at once (ATAC paired: adapter trim; MAPQ >= 30; PCR duplicates removed;
#      fragments <= 2 kb) streamed into a level-1 sorted BAM
#   -> regions: ChIP-Atlas peaks of the same SRX (bed05, MACS2 q < 1e-5), minus ENCODE blacklist and chrM;
#      MACS3 (q < 0.01) on our own alignment when ChIP-Atlas peaks are missing or fail the identity checks
# Identity checks (raw data and ChIP-Atlas peaks must come from the same experiment):
#   R1 runs: live ENA read_run for this SRX = the run list we download, and sum(ENA read_count) = ChIP-Atlas reads.
#      Fails -> stop (exit 4): the accession table and ENA disagree, nothing is aligned.
#   R2 reads: chromap input reads within 98-100% of sum(ENA read_count) (x2 for paired). Fails -> stop (exit 4).
#   P1 peak file: every peak name starts with "<SRX>.05_peak_" and the count equals ChIP-Atlas n_peaks.
#   P2 signal: our reads in those peaks >= 3x our reads in the same peaks shifted by 100 kb.
#      P1 or P2 fails -> ChIP-Atlas peaks are discarded and MACS3 is run on our alignment (logged in qc.tsv).
#   -> HINT footprints inside the regions, regions split across all threads
#      ATAC : --atac-seq [--paired-end]   (Tn5 bias table; HINT applies the Tn5 shift itself)
#      DNase: --dnase-seq --bias-correction --bias-type <SH|DH>
# All intermediates live in a per-job scratch directory on node-local disk, deleted on exit (success or failure).
# Kept: <outdir>/<SRX>.hint_fp.bed.gz (chrom, start, end, SRX, HINT score, strand) and one row in <outdir>/qc.tsv.
#
# usage: fp_sample.sh <ATAC|DNase> <SRX> <runs.tsv> <outdir> <threads> [dnase_bias_type=DH]
set -euo pipefail
ASSAY=$1; SRX=$2; RUNS=$3; OUT=$4; T=$5; BIAS=${6:-DH}
: "${FPATLAS_ENV:?}" "${FPATLAS_PMAFP:?}" "${FPATLAS_HINT:?}" "${FPATLAS_REF:?}"
E=$FPATLAS_ENV; P=$FPATLAS_PMAFP; H=$FPATLAS_HINT; REF=$FPATLAS_REF
FA=$REF/hg38_primary.fa; IDX=$REF/hg38_primary.chromap.index; BL=$REF/hg38-blacklist.v2.bed
mkdir -p "$OUT"
SCR=$(mktemp -d "${FPATLAS_SCRATCH:-${TMPDIR:-/tmp}}/fp_${SRX}_XXXX")
# on failure, print the tails of the tool logs (stderr goes to the persistent job log) before scratch is removed
mon=
# on failure, print the tails of the tool logs (stderr goes to the persistent job log) before scratch is removed
trap 'rc=$?; [ -n "$mon" ] && kill "$mon" 2>/dev/null; if [ $rc -ne 0 ]; then for l in aria.log chromap.log macs.log; do [ -s "$SCR/$l" ] && { echo "--- $l" >&2; tail -n 30 "$SCR/$l" >&2; }; done; fi; rm -rf "$SCR"' EXIT
# If the SGE job shell (FPATLAS_PARENT) disappears (h_vmem kill, qdel), kill this whole process group and clear scratch:
# on Argos those kills do not reach every child, which otherwise keep downloading or aligning.
if [ -n "${FPATLAS_PARENT:-}" ]; then
  ( while kill -0 "$FPATLAS_PARENT" 2>/dev/null; do sleep 10; done; rm -rf "$SCR"; kill -9 0 ) &
  mon=$!
fi
cd "$SCR"
declare -A TM; t0=$(date +%s)
tick() {  # stage time; the log line also records scratch use at the end of the stage
  local n; n=$(date +%s); TM[$1]=$((n - t0)); t0=$n
  echo "[$(date -Is)] $1 ${TM[$1]} s, scratch $(du -sh "$SCR" | cut -f1)"
}

# 1. runs of this experiment: run, layout, fastq_ftp, fastq_md5
awk -F'\t' -v x="$SRX" 'NR > 1 && $2 == x {print $3 "\t" $16 "\t" $21 "\t" $22}' "$RUNS" > runs.txt
[ -s runs.txt ] || { echo "no runs for $SRX" >&2; exit 2; }
read -r CA_READS CA_PEAKS < <(awk -F'\t' -v x="$SRX" 'NR > 1 && $2 == x {print $12, $15; exit}' "$RUNS")

# R1: run membership and read count, against live ENA
curl -sf --retry 5 "https://www.ebi.ac.uk/ena/portal/api/filereport?accession=$SRX&result=read_run&fields=run_accession,read_count&format=tsv" \
  | awk -F'\t' 'NR > 1' | sort > ena_runs.txt || { echo "ENA query failed" >&2; exit 4; }
if ! diff -q <(cut -f1 ena_runs.txt) <(cut -f1 runs.txt | sort) > /dev/null; then
  echo "R1 FAIL: ENA runs for $SRX differ from the accession table" >&2; exit 4; fi
ENA_READS=$(awk -F'\t' '{s += $2} END {print s}' ena_runs.txt)
[ "$ENA_READS" = "$CA_READS" ] || { echo "R1 FAIL: ENA reads $ENA_READS != ChIP-Atlas reads $CA_READS" >&2; exit 4; }
LAYOUT=$(cut -f2 runs.txt | sort -u)
[ "$(echo "$LAYOUT" | wc -l)" -eq 1 ] || { echo "mixed layouts in $SRX" >&2; exit 2; }
case $LAYOUT in PAIRED) PE=1 ;; SINGLE) PE=0 ;; *) echo "layout $LAYOUT" >&2; exit 2 ;; esac

# 2. download. ENA lists <run>.fastq.gz (unpaired leftovers) next to _1/_2 for paired runs: skipped.
#    ChIP-Atlas peaks are fetched in the same batch.
mkdir -p fq
: > aria.txt; : > aria_https.txt
sra=()
while IFS=$'\t' read -r run lay urls md5s; do
  if [ -z "$urls" ]; then sra+=("$run"); continue; fi
  IFS=';' read -r -a U <<< "$urls"; IFS=';' read -r -a M <<< "$md5s"
  for k in "${!U[@]}"; do
    f=$(basename "${U[$k]}")
    if [ $PE -eq 1 ] && [[ $f != *_1.fastq.gz && $f != *_2.fastq.gz ]]; then continue; fi
    u=${U[$k]#*://}
    printf 'ftp://%s\n  out=fq/%s\n  checksum=md5=%s\n' "$u" "$f" "${M[$k]}" >> aria.txt
    printf 'https://%s\n  out=fq/%s\n  checksum=md5=%s\n' "$u" "$f" "${M[$k]}" >> aria_https.txt
  done
done < runs.txt
printf '%s\n  out=ca_peaks.bed\n' "https://chip-atlas.dbcls.jp/data/hg38/eachData/bed05/$SRX.05.bed" > aria_peaks.txt
"$E/aria2c" -q -i aria_peaks.txt --allow-overwrite=true --max-tries=5 || rm -f ca_peaks.bed &
pk=$!
# ENA ftp first (faster on Argos), https as fallback; aria2 resumes partial files and re-verifies md5.
# ENA limits connections per client IP, so concurrency stays modest: 2 files x 8 connections.
ARIA=(-j 2 -x 8 -s 8 -k 8M -c --max-tries=10 --retry-wait=15 --file-allocation=none --check-integrity=true
      --auto-file-renaming=false --show-console-readout=false --summary-interval=0 --console-log-level=error
      --download-result=full)
if [ -s aria.txt ]; then
  if ! "$E/aria2c" -i aria.txt "${ARIA[@]}" > aria.log 2>&1; then
    echo "ftp download incomplete, retrying over https" >&2; grep -E "ERR|error" aria.log | head -n 10 >&2
    "$E/aria2c" -i aria_https.txt "${ARIA[@]}" > aria.log 2>&1 || exit 5
  fi
  echo "fastq $(du -sb fq | cut -f1) bytes"
fi
for run in ${sra[@]+"${sra[@]}"}; do  # SRA fallback
  "$E/prefetch" -q -O sra "$run"
  "$E/fasterq-dump" -q -e "$T" -t "$SCR" -O fq --split-files "sra/$run"; rm -rf "sra/$run"
done
wait $pk || true
tick download

# 3. align all runs in one chromap call (comma-separated lists keep mate order), stream to sorted BAM
if [ $PE -eq 1 ]; then
  R1=$(ls fq/*_1.fastq* | paste -sd,); R2=$(ls fq/*_2.fastq* | paste -sd,)
  READS=(-1 "$R1" -2 "$R2")
else
  READS=(-1 "$(ls fq/*.fastq* | paste -sd,)")
fi
TRIM=(); [ "$ASSAY" = ATAC ] && [ $PE -eq 1 ] && TRIM=(--trim-adapters)
# --low-mem writes <output>.temp files, so the output must be a path in scratch: a FIFO read by samtools sort
mkfifo aln.sam
"$E/samtools" sort -@ 8 -m 3G -l 1 -T sorttmp -o aln.bam aln.sam &
sp=$!
"$E/chromap" -x "$IDX" -r "$FA" "${READS[@]}" ${TRIM[@]+"${TRIM[@]}"} --remove-pcr-duplicates -q 30 -l 2000 \
  --low-mem --SAM -t "$T" -o aln.sam 2> chromap.log
wait $sp
rm -f aln.sam
rm -rf fq
"$E/samtools" index -@ "$T" aln.bam
n_in=$(grep -m1 -oE 'Number of reads: [0-9]+' chromap.log | grep -oE '[0-9]+' || true)
[ -n "$n_in" ] || { echo "R2 FAIL: input read count not found in chromap.log" >&2; tail -n 30 chromap.log >&2; exit 4; }
# chromap counted 0.4% fewer reads than 2x ENA for SRX4978105 (reads it skips at load), so allow up to 2% below;
# file identity is already fixed by the ENA md5 check in step 2
exp_in=$((ENA_READS * (PE + 1)))
if [ "$n_in" -gt "$exp_in" ] || [ $((n_in * 100)) -lt $((exp_in * 98)) ]; then
  echo "R2 FAIL: chromap read $n_in reads, ENA lists $exp_in" >&2; exit 4; fi
echo "R2: chromap read $n_in of $exp_in ENA reads"
tick align

# 4. regions
# P1 + P2 on the ChIP-Atlas peaks
SRC=macs3; why=no_chipatlas_file
if [ -s ca_peaks.bed ]; then
  bad=$(awk -F'\t' -v p="$SRX.05_peak_" 'index($4, p) != 1' ca_peaks.bed | wc -l)
  n_ca=$(wc -l < ca_peaks.bed)
  if [ "$bad" -ne 0 ] || [ "$n_ca" != "$CA_PEAKS" ]; then why="P1_fail(bad=$bad,n=$n_ca,expected=$CA_PEAKS)"
  else
    cut -f1-3 ca_peaks.bed | awk '$1 ~ /^chr([0-9]+|X|Y)$/' | sort -k1,1 -k2,2n | "$P/bedtools" merge -i - > p2_in.bed
    "$P/bedtools" shift -i p2_in.bed -g "$REF/hg38_primary.chrom.sizes" -s 100000 | sort -k1,1 -k2,2n \
      | "$P/bedtools" merge -i - > p2_out.bed
    c_in=$("$E/samtools" view -c -@ "$T" -L p2_in.bed aln.bam)
    c_out=$("$E/samtools" view -c -@ "$T" -L p2_out.bed aln.bam)
    if [ "$c_in" -ge $((3 * c_out)) ] && [ "$c_in" -gt 0 ]; then SRC=chipatlas; why="P2_ratio=$((c_in / (c_out + 1)))"
    else why="P2_fail(in=$c_in,shifted=$c_out)"; fi
  fi
fi
echo "regions: $SRC ($why)"
if [ $SRC = macs3 ]; then
  if [ $PE -eq 1 ]; then MF=(-f BAMPE)
  elif [ "$ASSAY" = ATAC ]; then MF=(-f BAM --nomodel --shift -100 --extsize 200)
  else MF=(-f BAM --nomodel --shift -75 --extsize 150); fi
  "$P/macs3" callpeak -t aln.bam "${MF[@]}" -g hs -q 0.01 --keep-dup all -n p --outdir peaks > macs.log 2>&1
  cp peaks/p_peaks.narrowPeak ca_peaks.bed
fi
cut -f1-3 ca_peaks.bed | awk '$1 ~ /^chr([0-9]+|X|Y)$/' | sort -k1,1 -k2,2n \
  | "$P/bedtools" intersect -v -a - -b "$BL" | "$P/bedtools" merge -i - > peaks.bed
n_peaks=$(wc -l < peaks.bed)
tick peaks

# 5. HINT (single-threaded; regions split into T chunks run in parallel)
if [ "$ASSAY" = ATAC ]; then HOPT=(--atac-seq); [ $PE -eq 1 ] && HOPT+=(--paired-end)
else HOPT=(--dnase-seq --bias-correction "--bias-type=$BIAS"); fi
mkdir -p hint && split -n l/"$T" -d -a 3 peaks.bed hint/r_
pids=()
for f in hint/r_*; do
  mkdir -p "$f.o"  # --dnase-seq does not create the output folder
  "$H/rgt-hint" footprinting "${HOPT[@]}" --organism=hg38 --output-location="$f.o" --output-prefix=fp aln.bam "$f" \
    > "$f.log" 2>&1 & pids+=("$!")
done
for p in "${pids[@]}"; do wait "$p" || { tail -n 20 hint/*.log >&2; exit 3; }; done
cat hint/r_*.o/fp.bed | awk -v s="$SRX" 'BEGIN{OFS="\t"} {print $1, $2, $3, s, $5, $6}' | sort -k1,1 -k2,2n \
  | "$E/pigz" -p 4 > "$OUT/$SRX.hint_fp.bed.gz.tmp"
mv "$OUT/$SRX.hint_fp.bed.gz.tmp" "$OUT/$SRX.hint_fp.bed.gz"
n_fp=$("$E/pigz" -dc "$OUT/$SRX.hint_fp.bed.gz" | wc -l)
tick hint

# 6. one QC row (depth is needed later for depth-aware aggregation); the trap removes everything else
n_map=$(grep -m1 -oE 'Number of mapped reads: [0-9]+' chromap.log | grep -oE '[0-9]+' || echo NA)
n_out=$(grep -m1 -oE 'Number of output mappings \(passed filters\): [0-9]+' chromap.log | grep -oE '[0-9]+$' || echo NA)
row=$(printf '%s\t' "$SRX" "$ASSAY" "$LAYOUT" "$(wc -l < runs.txt)" "$n_in" "$n_map" "$n_out" "$SRC" "$why" "$n_peaks" "$n_fp" \
  "${TM[download]}" "${TM[align]}" "${TM[peaks]}" "${TM[hint]}" "$(hostname)" "$(date -Is)")
(
  flock 9
  [ -s "$OUT/qc.tsv" ] || printf 'srx\tassay\tlayout\tn_runs\treads_in\treads_mapped\tmappings_kept\tregion_source\tregion_check\tregions\tfootprints\tt_download_s\tt_align_s\tt_regions_s\tt_hint_s\thost\tfinished\n' > "$OUT/qc.tsv"
  echo "${row%$'\t'}" >> "$OUT/qc.tsv"
) 9> "$OUT/.qc.lock"
echo "done $SRX: $n_fp footprints"
