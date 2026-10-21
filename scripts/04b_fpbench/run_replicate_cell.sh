#!/usr/bin/env bash
# Replicate the benchmark in a second cell line: download ENCODE inputs, prep, truth, all callers, scoring.
# Accuracy replication only: TraceBIND runs alongside the other callers, so these timings are not benchmark timings
# (the resource benchmark is the K562 run, one caller at a time).
# usage: run_replicate_cell.sh <raw_dir> <result_root> <sample> <bam_acc> <bam_md5> <peaks_acc> <peaks_md5> <chip_panel.tsv>
set -uo pipefail
RAW=$1; R=$2; SAMPLE=$3; BAM=$4; BAM_MD5=$5; PK=$6; PK_MD5=$7; PANEL=$8
C=$(cd "$(dirname "$0")" && pwd)
E=/home/zz950/softwares/miniforge3/envs/pmafp/bin
FA=/home/zz950/DATA/2.PROJECTS/PMA/atac_footprint/raw/2026-10-17/reference/hg38.fa
MEME=/home/zz950/DATA/2.PROJECTS/PMA/atac_footprint/result/fpbench_k562_v1/truth/JASPAR2026_CORE_vertebrates_non-redundant_pfms_meme.txt
N=16
mkdir -p "$RAW" "$R/logs" "$R/truth/chip"
log() { echo "[$(date -Is)] $*"; }
dl() { [ -s "$2" ] || curl -sL --retry 3 --max-time 7200 -o "$2" "https://www.encodeproject.org/files/$1/@@download/$(basename "$2")"; }

log download ATAC
dl "$BAM" "$RAW/$BAM.bam"; dl "$PK" "$RAW/$PK.bed.gz"
printf '%s  %s\n%s  %s\n' "$BAM_MD5" "$BAM.bam" "$PK_MD5" "$PK.bed.gz" > "$RAW/md5.txt"
(cd "$RAW" && md5sum -c md5.txt) || { log md5 FAIL; exit 1; }
[ -s "$RAW/$BAM.bam.bai" ] || "$E/samtools" index -@ $N "$RAW/$BAM.bam"

log download ChIP
cp "$PANEL" "$R/truth/chip_panel.tsv"
tail -n +2 "$R/truth/chip_panel.tsv" | cut -f3,6 | while read -r a m; do
  dl "$a" "$R/truth/chip/$a.bed.gz"; echo "$m  $a.bed.gz"; done > "$R/truth/chip.md5"
(cd "$R/truth/chip" && md5sum -c ../chip.md5 > ../chip.md5.check) || { log ChIP md5 FAIL; exit 1; }

log prep
bash "$C/00_prep_inputs.sh" "$E" "$RAW/$BAM.bam" "$RAW/$PK.bed.gz" "$R/inputs" $N chr1,chr2 "$SAMPLE" > "$R/logs/00_prep.log" 2>&1 || { log prep FAIL; exit 1; }
log truth
"$E/python" "$C/01_truth_sites.py" "$R/inputs/regions_1kb.bed" "$FA" "$MEME" "$R/truth/chip_panel.tsv" "$R/truth/chip" "$R/truth" $N > "$R/logs/01_truth.log" 2>&1 || { log truth FAIL; exit 1; }

log callers
# scPrinter Tn5 bias bigWig is genome-wide and sample-independent: reuse the one built for K562
[ -e "$R/scprinter_ref" ] || ln -s "$(dirname "$MEME")/../scprinter_ref" "$R/scprinter_ref"
bash "$C/02_run_callers.sh" "$R" $N tracebind > "$R/logs/02_tracebind.log" 2>&1 &
TB=$!
bash "$C/02_run_callers.sh" "$R" $N tobias,hint,print,scprinter > "$R/logs/02_callers.log" 2>&1
wait $TB
log score
"$E/python" "$C/03_score_sites.py" "$R" > "$R/logs/03_score.log" 2>&1 || { log score FAIL; exit 1; }
"$E/python" "$C/05_added_value.py" "$R" > "$R/logs/05_added_value.log" 2>&1 || { log added_value FAIL; exit 1; }
log DONE
