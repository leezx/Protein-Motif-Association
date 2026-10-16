#!/bin/bash
# Step 3 on the Argos standalone node rcapps3 (x86_64): all.q was fully
# booked. Two independent pipelines in parallel:
#   A) 8-mer features -> Seurat clustering (r4p3 env, R_LIBS_USER=R_lib_4)
#   B) x86 MEME 5.5.9 build -> extra TOMTOM workers sharing the locked chunks
# usage: S=<step3_dir> setsid nohup bash 08_run_rcapps3.sh &
set -uo pipefail
: "${S:?}"
PY=/mnt/storage/apps/anaconda3-2024.06-1/bin/python
RS=/home/zz950/softwares/miniconda3/envs/r4p3/bin/Rscript
mkdir -p "$S/logs_rcapps3"
(
  "$PY" -I "$S/scripts/06_kmer_features.py" "$S/tomtom/nodes.meme" "$S/kmer" > "$S/logs_rcapps3/kmer.log" 2>&1 &&
  R_LIBS_USER=/home/zz950/softwares/R_lib_4 OMP_NUM_THREADS=8 "$RS" "$S/scripts/07_seurat_cluster.R" "$S/kmer" "$S/seurat" \
    > "$S/logs_rcapps3/seurat.log" 2>&1
  echo "A exit $?" >> "$S/logs_rcapps3/status"
) &
(
  B=/home/zz950/softwares/meme-5.5.9-src/x86
  if [[ ! -x /home/zz950/softwares/meme-5.5.9-x86/bin/tomtom ]]; then
    rm -rf "$B" && mkdir -p "$B" && cd "$B" && tar xzf ../meme-5.5.9.tar.gz && cd meme-5.5.9 &&
    ./configure --prefix=/home/zz950/softwares/meme-5.5.9-x86 --enable-build-libxml2 --enable-build-libxslt > ../configure.log 2>&1 &&
    make -j 16 > ../make.log 2>&1 && make install > ../install.log 2>&1
  fi
  MEME_BIN=/home/zz950/softwares/meme-5.5.9-x86/bin PYTHON="$PY" NJOBS=40 \
    "$S/tomtom/02_run_tomtom.sh" "$S/tomtom" node > "$S/logs_rcapps3/tomtom.log" 2>&1
  echo "B exit $?" >> "$S/logs_rcapps3/status"
) &
wait
