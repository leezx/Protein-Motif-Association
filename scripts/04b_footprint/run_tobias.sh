#!/bin/bash
# Step 4b-1: TOBIAS ATACorrect + FootprintScores (motif-free score track) + common event adapter. CPU, --cores.
# usage: run_tobias.sh <env_bin> <bam> <regions.bed> <genome.fa> <blacklist.bed> <outdir> <cores>
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
B=$1; BAM=$2; BED=$3; FA=$4; BL=$5; O=$6; N=$7
mkdir -p $O
s=$(date +%s)
$B/TOBIAS ATACorrect --bam $BAM --genome $FA --peaks $BED --blacklist $BL --outdir $O --prefix x --cores $N > $O/atacorrect.log 2>&1
m=$(date +%s)
$B/TOBIAS FootprintScores --signal $O/x_corrected.bw --regions $BED --output $O/footprints.bw --cores $N > $O/fpscores.log 2>&1
e=$(date +%s)
$B/python $HERE/events_from_track.py $O/footprints.bw $BED $O/events.bed 10
f=$(date +%s)
printf "stage\tseconds\natacorrect\t%d\nfootprintscores\t%d\nevents\t%d\n" $((m-s)) $((e-m)) $((f-e)) > $O/timing.tsv
