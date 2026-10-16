#!/bin/bash
# SGE array runner for Step 3 TOMTOM chunks (Argos all.q, x86 MEME build).
# Task t takes chunk NCHUNK - t (from the end), so it meets the standalone
# node runner (which goes from the start) in the middle; locks in
# tomtom_chunk.sh prevent double work.
# submit: qsub -t 1-560 -tc 40 -v W=<work_dir> 02b_tomtom_sge.sh
#$ -N pma_tomtom
#$ -q all.q
#$ -pe smp 1
#$ -cwd
#$ -j y
#$ -o logs_sge/
set -euo pipefail
: "${W:?}"
export MEME_BIN=/home/zz950/softwares/meme-5.5.9-x86/bin
export PYTHON=/mnt/storage/apps/anaconda3-2024.06-1/bin/python
n=$(ls "$W"/chunks/chunk_*.meme | wc -l)
i=$(( n - SGE_TASK_ID ))
c=$(printf "%s/chunks/chunk_%03d.meme" "$W" "$i")
"$W/tomtom_chunk.sh" "$W" "$c"
