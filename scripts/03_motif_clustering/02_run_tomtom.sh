#!/usr/bin/env bash
# Step 3 §3.1: all-vs-all TOMTOM over the clusterable nodes, run on a
# compute node (Argos rcapps8; see computingResource.md). Every node is a
# query against the full node set; each chunk is reduced by
# tomtom_filter.py (per-query BH, completeness asserted, keep q < 0.05)
# and the full chunk output is deleted.
#
# usage: 02_run_tomtom.sh <work_dir>   (work_dir holds nodes.meme and the
#        scripts tomtom_filter.py, split_meme.py)
# env:   MEME_BIN (dir with tomtom), NJOBS (parallel, default 64),
#        NCHUNK (default 560), PYTHON (default python3)
set -euo pipefail
W="$1"
: "${MEME_BIN:?}"
NJOBS="${NJOBS:-64}"; NCHUNK="${NCHUNK:-560}"; PYTHON="${PYTHON:-python3}"
ARGS=(-no-ssc -dist pearson -min-overlap 5 -evalue -thresh 1e9 -text)
TARGET="$W/nodes.meme"
NT=$(grep -c '^MOTIF' "$TARGET")
mkdir -p "$W/chunks" "$W/kept" "$W/logs"
[[ -e "$W/chunks/chunk_000.meme" ]] || "$PYTHON" -I "$W/split_meme.py" "$TARGET" "$NCHUNK" "$W/chunks/chunk"

run_chunk() {  # skips chunks already done, so the run can be resumed
  local c="$1" b; b=$(basename "$c" .meme)
  [[ -s "$W/kept/$b.tsv.gz" ]] && return 0
  "$MEME_BIN/tomtom" "${ARGS[@]}" "$c" "$TARGET" > "$W/chunks/$b.tsv" 2> "$W/logs/$b.log"
  "$PYTHON" -I "$W/tomtom_filter.py" "$W/chunks/$b.tsv" "$NT" "$W/kept/$b.tmp.gz" >> "$W/logs/$b.log"
  mv "$W/kept/$b.tmp.gz" "$W/kept/$b.tsv.gz"
  rm "$W/chunks/$b.tsv"
}
export -f run_chunk; export W MEME_BIN TARGET NT PYTHON
export ARGS_STR="${ARGS[*]}"
ls "$W"/chunks/chunk_*.meme | xargs -P "$NJOBS" -I{} bash -c 'ARGS=($ARGS_STR); run_chunk "$@"' _ {}

n_meme=$(ls "$W"/chunks/chunk_*.meme | wc -l); n_kept=$(ls "$W"/kept/chunk_*.tsv.gz | wc -l)
[[ $n_kept -eq $n_meme ]] || { echo "only $n_kept/$n_meme chunks done" >&2; exit 1; }
{ echo -e "tomtom_version\t$("$MEME_BIN/tomtom" --version)"
  echo -e "args\t${ARGS[*]} (query chunks: $NCHUNK, parallel: $NJOBS)"
  echo -e "targets\t$NT"
  echo -e "host\t$(hostname) $(uname -m)"
  echo -e "finished\t$(date -u +%Y-%m-%dT%H:%M:%SZ)"; } > "$W/run_info.tsv"
( cd "$W/kept" && md5sum chunk_*.tsv.gz > ../kept_checksums.md5 )
echo done
