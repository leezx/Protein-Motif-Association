#!/bin/bash
# Step 4a §7 pilot: run the full pipeline on a valid gzip prefix of the 05 archive and compare the
# 05 archive filtered at score >= 100 / >= 200 with the 10 / 20 archives inside a shared chr1 window.
# usage: 00_pilot.sh <raw_release_dir> <stage_dir> <prefix_gz_file>   (env: Argos r4p3 python, pigz, mawk, bgzip, tabix)
set -euo pipefail
RAW=$1; ST=$2; PRE=$3
HERE=$(cd "$(dirname "$0")" && pwd)
P=$ST/pilot; mkdir -p $P
B=https://chip-atlas.dbcls.jp/data/hg38/allPeaks_light
head -c 400000000 "$PRE" | gzip -dc 2>/dev/null | head -n -1 > $P/p05.bed || true
for t in 10 20; do curl -sS -r 0-150000000 $B/allPeaks_light.hg38.$t.bed.gz | gzip -dc 2>/dev/null | head -n -1 > $P/p$t.bed || true; done
wc -l $P/p05.bed $P/p10.bed $P/p20.bed
mawk -v ids=$ST/scope_ids.txt 'BEGIN{while((getline l < ids)>0) keep[l]=1} ($4 in keep)' $P/p05.bed \
  | python $HERE/02_peaks.py $P $RAW/reference > $P/pilot_occupancy.bed
cp $ST/annotation_suffix.tsv $P/ 2>/dev/null || true
bgzip -f -@ 4 $P/pilot_occupancy.bed && tabix -f -p bed $P/pilot_occupancy.bed.gz
echo "tabix chr1:1000000-1010000 rows: $(tabix $P/pilot_occupancy.bed.gz chr1:1000000-1010000 | wc -l)"
zcat $P/pilot_occupancy.bed.gz | head -3
python - "$P" <<'PY'
import sys, collections
P = sys.argv[1]
def load(f, minq=None):
    rows = []
    for line in open(f):
        c, s, e, i, q = line.rstrip("\n").split("\t")
        rows.append((c, int(s), int(e), i, float(q)))
    return rows
r05, r10, r20 = load(f"{P}/p05.bed"), load(f"{P}/p10.bed"), load(f"{P}/p20.bed")
assert all(r[0] == "chr1" for r in r05[:1000])
W = min(max(r[1] for r in rows if r[0] == "chr1") for rows in (r05, r10, r20)) - 100000
for t, rt in ((100, r10), (200, r20)):
    a = {r[:4] for r in r05 if r[0] == "chr1" and r[1] < W and r[4] >= t}
    b = {r[:4] for r in rt if r[0] == "chr1" and r[1] < W}
    print(f"q>={t}: window chr1:0-{W} | 05 filtered {len(a)} | archive {len(b)} | shared {len(a & b)} | only05 {len(a - b)} | only{t // 10} {len(b - a)}")
qs = [r[4] for r in r10 if r[1] < W]
print("min score in 10 archive window", min(qs), "| min score in 20 archive window", min(r[4] for r in r20 if r[1] < W))
PY
cat $P/peaks_summary.json
