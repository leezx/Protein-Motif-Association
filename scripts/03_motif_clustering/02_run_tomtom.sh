#!/usr/bin/env bash
# Step 3 §3.1: all-vs-all TOMTOM over the clusterable nodes on Argos
# (never on the Mac mini). Work is split into NCHUNK query chunks that
# tomtom_chunk.sh claims with locks, so several runners can share them:
#   split     split nodes.meme into chunks (once)
#   node      run chunks in parallel on a standalone node (rcapps8: aarch64)
#   finalize  check all chunks done; write run_info.tsv and checksums
# The SGE array runner is 02b_tomtom_sge.sh (all.q, x86).
#
# usage: 02_run_tomtom.sh <work_dir> split|node|finalize
# env:   MEME_BIN, PYTHON (numpy), NJOBS (node mode, default 64), NCHUNK (560)
set -euo pipefail
W="$1"; MODE="$2"
NCHUNK="${NCHUNK:-560}"; PYTHON="${PYTHON:-python3}"
case "$MODE" in
  split)
    mkdir -p "$W/chunks"
    [[ -e "$W/chunks/chunk_000.meme" ]] || "$PYTHON" -I "$W/split_meme.py" "$W/nodes.meme" "$NCHUNK" "$W/chunks/chunk"
    ls "$W"/chunks/chunk_*.meme | wc -l ;;
  node)
    : "${MEME_BIN:?}"; export MEME_BIN PYTHON
    ls "$W"/chunks/chunk_*.meme | xargs -P "${NJOBS:-64}" -I{} "$W/tomtom_chunk.sh" "$W" {} ;;
  finalize)
    n_meme=$(ls "$W"/chunks/chunk_*.meme | wc -l); n_kept=$(ls "$W"/kept/chunk_*.tsv.gz | wc -l)
    [[ $n_kept -eq $n_meme ]] || { echo "only $n_kept/$n_meme chunks done" >&2; exit 1; }
    { echo -e "tomtom_version\t5.5.9 (aarch64 build on rcapps8; x86 build on all.q)"
      echo -e "args\t-no-ssc -dist pearson -min-overlap 5 -evalue -thresh 1e9 -text (query chunks: $n_meme)"
      echo -e "targets\t$(grep -c '^MOTIF' "$W/nodes.meme")"
      echo -e "hosts\t$(grep -h '^host' "$W"/logs/chunk_*.log | cut -d' ' -f2 | cut -d. -f1 | sort | uniq -c | tr '\n' ' ')"
      echo -e "finished\t$(date -u +%Y-%m-%dT%H:%M:%SZ)"; } > "$W/run_info.tsv"
    ( cd "$W/kept" && md5sum chunk_*.tsv.gz > ../kept_checksums.md5 )
    cat "$W/run_info.tsv" ;;
  *) echo "unknown mode $MODE" >&2; exit 2 ;;
esac
