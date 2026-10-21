#!/usr/bin/env bash
# TraceBIND wrapper: writes regionSeqs.txt from the indexed FASTA (BSgenome hg38 is not installed), then runs R.
# usage: run_tracebind.sh <regions.bed> <frags.tsv.gz> <genome.fa> <model_dir> <outdir> <cores>
set -euo pipefail
BED=$1; FRAGS=$2; FA=$3; MODEL=$4; O=$5; N=$6
E=/home/zz950/softwares/miniforge3/envs/pmafp
RP=/home/zz950/softwares/miniconda3/envs/r4p3
mkdir -p "$O/tb_work"
# TraceBIND get_bias(): 1-based [start, end] regions, all widened to the max width, +-50 bp sequence context.
"$E/bin/python" - "$BED" "$FA" "$O/tb_work/regionSeqs.txt" <<'PY'
import sys, pysam
bed, fa, out = sys.argv[1:4]
g = pysam.FastaFile(fa)
rows = [l.split()[:3] for l in open(bed)]
w = max(int(e) - int(s) for _, s, e in rows)
with open(out, "w") as o:
    for c, s, e in rows:
        s1 = int(s) + 1
        o.write(g.fetch(c, s1 - 1 - 50, s1 - 1 + w + 50).upper() + "\n")
PY
export R_LIBS=/home/zz950/softwares/R_lib_tracebind:/home/zz950/softwares/R_lib_4
export RETICULATE_PYTHON="$E/bin/python" PYTHONPATH=/home/zz950/PMA_fetch/pma_trace_python_overlay_v1
export R_ENVIRON_USER=/home/zz950/PMA_fetch/pma_bg_pr8_20261019/Renviron.tracebind
export CONDA_PREFIX="$RP" PATH="$RP/bin:$PATH" LD_LIBRARY_PATH="$E/lib:$RP/lib:${LD_LIBRARY_PATH:-}"
"$RP/bin/Rscript" "$(dirname "$0")/run_tracebind.R" "$E/bin/python" "$MODEL" "$BED" "$FRAGS" "$O" "$N"
