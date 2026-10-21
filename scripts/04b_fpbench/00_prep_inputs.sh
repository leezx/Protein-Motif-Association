#!/usr/bin/env bash
# Step 4b footprint benchmark v2: shared inputs for every caller.
# - filtered BAM (MAPQ>=30, proper pair, no dup/secondary/supplementary/unmapped) on the benchmark chromosomes
# - Tn5-shifted fragments (+4/-5) from that same BAM, bgzip + tabix
# - non-overlapping fixed 1-kb windows around IDR peak summits (greedy by signalValue), on the same chromosomes
# usage: 00_prep_inputs.sh <env_bin> <atac.bam> <idr_peaks.narrowPeak.gz> <outdir> <threads> <chrom,chrom,...> [sample]
#   sample is the fragment barcode (one pseudobulk), default K562
set -euo pipefail
B=$1; BAM=$2; PEAKS=$3; O=$4; T=$5; CHROMS=$6; SAMPLE=${7:-K562}
mkdir -p "$O"
export PATH="$B:$PATH"
IFS=, read -r -a CH <<< "$CHROMS"

samtools view -H "$BAM" | grep -E '^@PG' | cut -c1-300 > "$O/bam_header_pg.txt" || true
samtools view -@ "$T" -b -q 30 -f 2 -F 0xF0C "$BAM" "${CH[@]}" -o "$O/atac.filt.bam"
samtools index -@ "$T" "$O/atac.filt.bam"
samtools flagstat -@ "$T" "$O/atac.filt.bam" > "$O/atac.filt.flagstat.txt"

# Fragments: one row per properly paired fragment, taken from the leftmost mate (TLEN > 0).
samtools view -@ "$T" "$O/atac.filt.bam" \
  | awk -v smp="$SAMPLE" 'BEGIN{OFS="\t"} $9 > 0 {s = $4 - 1 + 4; e = $4 - 1 + $9 - 5; if (e > s) print $3, s, e, smp, 1}' \
  | sort -k1,1 -k2,2n -S 8G --parallel="$T" \
  | bgzip -@ "$T" > "$O/atac.frags.tsv.gz"
tabix -p bed "$O/atac.frags.tsv.gz"

# 1-kb windows: summit = start + col10; keep strongest summits first, drop any window overlapping a kept one.
zcat "$PEAKS" | awk -v chroms="$CHROMS" 'BEGIN{OFS="\t"; n = split(chroms, c, ","); for (i = 1; i <= n; i++) keep[c[i]] = 1}
  ($1 in keep) {s = $2 + $10; ws = s - 500; if (ws < 0) next; print $1, ws, s + 500, $7}' \
  | sort -k4,4gr -k1,1 -k2,2n \
  | python3 -c '
import sys
kept = {}
for line in sys.stdin:
    c, s, e, v = line.split("\t"); s, e = int(s), int(e)
    iv = kept.setdefault(c, [])
    # windows are all 1 kb, so overlap means |start difference| < 1000
    if any(abs(s - t) < 1000 for t in iv):
        continue
    iv.append(s)
for c in kept:
    for s in sorted(kept[c]):
        print(f"{c}\t{s}\t{s + 1000}\t{c}:{s}-{s + 1000}")
' | sort -k1,1 -k2,2n > "$O/regions_1kb.bed"

{
  echo -e "item\tvalue"
  echo -e "chromosomes\t$CHROMS"
  echo -e "filtered_bam_records\t$(samtools view -c -@ "$T" "$O/atac.filt.bam")"
  echo -e "fragments\t$(zcat "$O/atac.frags.tsv.gz" | wc -l)"
  echo -e "regions_1kb\t$(wc -l < "$O/regions_1kb.bed")"
  echo -e "idr_peaks_on_chroms\t$(zcat "$PEAKS" | awk -v chroms="$CHROMS" 'BEGIN{n=split(chroms,c,",");for(i=1;i<=n;i++)k[c[i]]=1} $1 in k' | wc -l)"
} > "$O/prep_summary.tsv"
sha256sum "$BAM" "$PEAKS" "$O/atac.filt.bam" "$O/atac.frags.tsv.gz" "$O/regions_1kb.bed" > "$O/SHA256SUMS"
cat "$O/prep_summary.tsv"
