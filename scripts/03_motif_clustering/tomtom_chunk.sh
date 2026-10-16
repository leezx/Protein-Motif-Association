#!/usr/bin/env bash
# One TOMTOM query chunk vs all nodes, then tomtom_filter.py (design §3.1).
# Safe to run from several hosts/jobs at once: a chunk is claimed with an
# atomic mkdir lock, temp files are host/PID-unique, and finished chunks
# (kept/<chunk>.tsv.gz) are skipped. A failed run releases its lock.
#
# usage: tomtom_chunk.sh <work_dir> <chunk.meme>
# env:   MEME_BIN (dir with tomtom), PYTHON (numpy available)
set -euo pipefail
W="$1"; c="$2"; b=$(basename "$c" .meme)
: "${MEME_BIN:?}"; PYTHON="${PYTHON:-python3}"
ARGS=(-no-ssc -dist pearson -min-overlap 5 -evalue -thresh 1e9 -text)
TARGET="$W/nodes.meme"
NT=$(grep -c '^MOTIF' "$TARGET")
mkdir -p "$W/kept" "$W/logs" "$W/locks"
[[ -s "$W/kept/$b.tsv.gz" ]] && exit 0
mkdir "$W/locks/$b" 2>/dev/null || exit 0
tag="$(hostname -s).$$"
tmp="$W/chunks/$b.$tag.tsv"
trap 'rm -f "$tmp" "$W/kept/$b.$tag.gz"; rmdir "$W/locks/$b" 2>/dev/null || true' EXIT
echo "host $tag start $(date -u +%FT%TZ)" > "$W/logs/$b.log"
"$MEME_BIN/tomtom" "${ARGS[@]}" "$c" "$TARGET" > "$tmp" 2>> "$W/logs/$b.log"
"$PYTHON" -I "$W/tomtom_filter.py" "$tmp" "$NT" "$W/kept/$b.$tag.gz" >> "$W/logs/$b.log"
mv "$W/kept/$b.$tag.gz" "$W/kept/$b.tsv.gz"
echo "end $(date -u +%FT%TZ)" >> "$W/logs/$b.log"
