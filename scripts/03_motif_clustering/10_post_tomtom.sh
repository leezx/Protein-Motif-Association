#!/bin/bash
# Step 3 after TOMTOM and Seurat finish, on Argos (rcapps3, x86):
# edges/similarity, then representatives + annotations + reference files.
# usage: bash 10_post_tomtom.sh   (run from the repo clone on Argos)
set -euo pipefail
cd "$(dirname "$0")"
M=/home/zz950/DATA/2.PROJECTS/PMA/motif_reference
export PMA_MOTIF_RAW=$M/raw PMA_MOTIF_PROCESSED=$M/processed PMA_MOTIF_RESULT=$M/result
PY=/mnt/storage/apps/anaconda3-2024.06-1/bin/python
S=$PMA_MOTIF_RESULT/step3_motif_clustering
bash "$S/tomtom/02_run_tomtom.sh" "$S/tomtom" finalize
"$PY" -I 03_build_edges.py
"$PY" -I 09_representatives.py
"$PY" -I 11_validate.py
