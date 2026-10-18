"""Step 4b-1: common event adapter for score-track callers (PRINT track, TOBIAS FootprintScores).

usage: events_from_track.py <track.tsv.gz|bigwig> <regions.bed> <out.bed> <half_width> [min_score=0]
Greedy non-maximum suppression per region: repeatedly take the highest-scoring position with score >= min_score,
emit [pos - half_width, pos + half_width + 1), then mask positions within 2*half_width. Events keep their score so
thresholds can be swept later. Identical rule for every track-based caller.
"""
import gzip
import sys
from collections import defaultdict

import numpy as np

src, bed, out, hw = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4])
mins = float(sys.argv[5]) if len(sys.argv) > 5 else 0.0
regions = [(l.split("\t")[0], int(l.split("\t")[1]), int(l.split("\t")[2])) for l in open(bed)]
if src.endswith((".bw", ".bigwig")):
    import pyBigWig
    bw = pyBigWig.open(src)
    get = lambda c, s, e: np.nan_to_num(np.array(bw.values(c, s, e), dtype=float))
else:
    tr = defaultdict(dict)
    with gzip.open(src, "rt") as f:
        next(f)
        for line in f:
            c, p, v = line.rstrip("\n").split("\t")
            tr[c][int(p)] = float(v)
    get = lambda c, s, e: np.array([tr[c].get(p, 0.0) for p in range(s, e)])
n = 0
with open(out, "w") as w:
    for c, s, e in regions:
        x = get(c, s, e).copy()
        while x.size and x.max() >= mins and x.max() > 0:
            i = int(x.argmax())
            w.write(f"{c}\t{s + i - hw}\t{s + i + hw + 1}\t{x[i]:.4f}\n")
            n += 1
            x[max(0, i - 2 * hw): i + 2 * hw + 1] = -np.inf
print(out, n, "events")
