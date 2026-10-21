#!/bin/bash
# Public footprint databases -> one hg38 sample-count track per source/variant (design: docs/FOOTPRINT_DB_TRACKS_DESIGN.md).
# usage: 01_footprint_tracks.sh <variant> <raw_dir> <chrom.sizes> <out_dir> [liftOver] [chain]
#   variant: vierstra2020_fpr0.001 | vierstra2020_fpr0.01 |
#            funk2020_dnase_hint | funk2020_dnase_wellington | funk2020_faire_hint | funk2020_faire_wellington |
#            neph2012_fdr0.01_liftedFromHg19 | boyle2011_liftedFromHg18   (need liftOver + chain)
# Lifted variants carry 'liftedFrom<build>' in every output name and get LIFTOVER_NOTICE.txt (user rule 2026-10-21:
# lifted files must be labelled so they are never mistaken for native hg38).
# Writes <out_dir>/<variant>/: <variant>.footprints.bed.gz (chrom start end sample; unique, merged within sample, sorted),
#   samples.tsv, <variant>.samples.bedGraph.gz(+.tbi), <variant>.samples.bw, then qc.json via 02_footprint_track_qc.py.
# Signal = number of samples with a footprint covering the base. Needs bedtools, bgzip, tabix, bedGraphToBigWig, python.
set -euo pipefail
V=$1; RAW=$2; SIZES=$3; OUT=$4/$1; LIFT=${5:-}; CHAIN=${6:-}
HERE=$(cd "$(dirname "$0")" && pwd)
NP=${NSLOTS:-4}; export LC_ALL=C OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
mkdir -p "$OUT/tmp"; cd "$OUT"
CHR='^chr([0-9]+|X|Y)\t'
SORT="sort -S 8G --parallel=$NP -T $OUT/tmp"

lift() {  # tmp/src.bed (name = sample|id) -> stdout hg38 chrom start end sample; liftover.json records losses
  "$LIFT" tmp/src.bed "$CHAIN" tmp/hg38.bed tmp/unmapped.bed 2> tmp/liftover.log
  echo "{\"source_footprints\": $(wc -l < tmp/src.bed), \"lifted\": $(wc -l < tmp/hg38.bed), \"unmapped\": $(grep -vc '^#' tmp/unmapped.bed || true), \"chain\": \"$(basename "$CHAIN")\"}" > liftover.json
  awk 'BEGIN{OFS="\t"}{split($4,a,"|"); print $1,$2,$3,a[1]}' tmp/hg38.bed
}

emit() {  # -> stdout: chrom start end sample (unsorted, may contain duplicates)
  case $V in
    vierstra2020_fpr*)
      t=${V#vierstra2020_fpr}
      for f in "$RAW"/per.dataset/*.fps.$t.bed.gz; do
        s=$(basename "$f" .fps.$t.bed.gz); zcat "$f" | awk -v s="$s" 'BEGIN{OFS="\t"}{print $1,$2,$3,s}'
      done ;;
    funk2020_*)
      a=${V#funk2020_}; m=${a#*_}; a=${a%%_*}; d=$([ "$a" = dnase ] && echo DNase-seq || echo FAIRE-seq)
      for f in "$RAW"/$d/*_${m}_20-footprint.bed.gz; do
        s=$(basename "$f" -footprint.bed.gz); s=${s%_${m}_20}
        zcat "$f" | awk -v s="$s" 'BEGIN{OFS="\t"} !/^#/ {print $1,$7,$8,s}'
      done ;;
    neph2012_fdr0.01_liftedFromHg19)
      zcat "$RAW"/jan2011_all.footprints.gz | awk 'BEGIN{OFS="\t"}{print $1,$2,$3,$4"|"NR}' > tmp/src.bed
      lift ;;
    boyle2011_liftedFromHg18)  # Furey lab per-cell-line footprints, native hg18 (their hg19 files are liftovers); Combined_GM excluded
      for f in "$RAW"/*_footprints_hg18.bed; do
        s=$(basename "$f" _footprints_hg18.bed); [ "$s" = Combined_GM ] && continue
        awk -v s="$s" 'BEGIN{OFS="\t"} !/^(track|browser|#)/ {print $1,$2,$3,s"|"NR}' "$f"
      done > tmp/src.bed
      lift ;;
    *) echo "unknown variant $V" >&2; exit 2 ;;
  esac
}

# 1. unique footprints on chr1-22,X,Y, clipped to chromosome ends, merged within each sample
emit | grep -P "$CHR" | awk 'BEGIN{OFS="\t"} NR==FNR{L[$1]=$2; next} ($1 in L) && $3>$2 {if($3>L[$1])$3=L[$1]; if($2<$3) print}' "$SIZES" - \
  | $SORT -k4,4 -k1,1 -k2,2n \
  | awk 'BEGIN{OFS="\t"} {if($4==s && $1==c && $2<=e){if($3>e)e=$3; next} if(c!="")print c,b,e,s; c=$1;b=$2;e=$3;s=$4} END{if(c!="")print c,b,e,s}' \
  | $SORT -k1,1 -k2,2n > tmp/fp.bed
awk 'BEGIN{OFS="\t"}{n[$4]++; bp[$4]+=$3-$2} END{print "sample","footprints","bp"; for(s in n) print s,n[s],bp[s]}' tmp/fp.bed | (read h; echo "$h"; sort) > samples.tsv
bgzip -@ "$NP" -c tmp/fp.bed > "$V.footprints.bed.gz" && tabix -f -p bed "$V.footprints.bed.gz"

# 2. per-base number of samples (each sample's footprints are disjoint after the merge)
bedtools genomecov -bg -i tmp/fp.bed -g <(grep -P "$CHR" "$SIZES" | sort -k1,1) > tmp/samples.bedGraph
bedGraphToBigWig tmp/samples.bedGraph <(grep -P "$CHR" "$SIZES") "$V.samples.bw"
bgzip -@ "$NP" -c tmp/samples.bedGraph > "$V.samples.bedGraph.gz" && tabix -f -p bed "$V.samples.bedGraph.gz"

# 3. QC: conservation identity, max <= samples, random-position recount
python -I "$HERE/02_footprint_track_qc.py" "$V.footprints.bed.gz" "$V.samples.bedGraph.gz" samples.tsv qc.json
rm -rf tmp
if [[ $V == *liftedFrom* ]]; then
  printf "LIFTED OVER, NOT NATIVE hg38.\nSource build: %s\nChain: %s\nliftOver stats: %s\nAll coordinates here were converted with UCSC liftOver (default minMatch 0.95); unmapped footprints are dropped.\n" \
    "${V##*liftedFrom}" "$(basename "$CHAIN")" "$(cat liftover.json)" > LIFTOVER_NOTICE.txt
fi
md5sum "$V".footprints.bed.gz* "$V".samples.* samples.tsv qc.json $(ls liftover.json LIFTOVER_NOTICE.txt 2>/dev/null) > MD5SUMS
cat qc.json
