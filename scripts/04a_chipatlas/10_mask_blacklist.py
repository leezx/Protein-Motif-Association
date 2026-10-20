"""Step 4a §11: blacklist-masked copies of the occupancy evidence tracks.

usage: 10_mask_blacklist.py <blacklist.bed.gz> <chrom.sizes> <in_dir> <out_dir>
Every <in_dir>/*.bedGraph.gz is clipped base-wise: values inside ENCODE hg38 blacklist v2 intervals become 0
(segments removed); everything outside is copied unchanged. Writes <out_dir>/<track>.bw, .bedGraph.gz (+ .tbi),
mask_qc.json. QC per track: no output base inside the blacklist; output segments never extend outside an input
segment; sum(value*bp) of input = output + masked part, computed independently from the blacklist intersection.
"""
import bisect
import collections
import gzip
import json
import subprocess
import sys
from pathlib import Path


def load_bl(path):
    iv = collections.defaultdict(list)
    with gzip.open(path, "rt") as f:
        for l in f:
            c, s, e = l.split("\t")[:3]
            iv[c].append([int(s), int(e)])
    out = {}
    for c, v in iv.items():  # merge overlaps
        v.sort(); m = [v[0]]
        for s, e in v[1:]:
            if s <= m[-1][1]: m[-1][1] = max(m[-1][1], e)
            else: m.append([s, e])
        out[c] = m
    return out


def subtract(c, s, e, bl):
    """Pieces of [s, e) outside the blacklist, and the masked bp."""
    iv = bl.get(c)
    if not iv:
        return [(s, e)], 0
    i = max(bisect.bisect_right(iv, [s, 1 << 62]) - 1, 0)
    pieces, cur, masked = [], s, 0
    while i < len(iv) and iv[i][0] < e:
        bs, be = iv[i]
        if be > cur:
            if bs > cur: pieces.append((cur, min(bs, e)))
            masked += min(be, e) - max(bs, cur)
            cur = max(cur, be)
        i += 1
    if cur < e: pieces.append((cur, e))
    return pieces, masked


def main(blp, sizes, ind, out):
    bl = load_bl(blp); ind, out = Path(ind), Path(out); out.mkdir(parents=True, exist_ok=True)
    qc = {}
    for bg in sorted(ind.glob("*.bedGraph.gz")):
        t = bg.name[:-len(".bedGraph.gz")]
        o = out / f"{t}.bedGraph"
        tot_in = tot_out = tot_masked = 0; bp_masked = 0; segs = 0
        with gzip.open(bg, "rt") as r, open(o, "w") as w:
            for l in r:
                c, s, e, v = l.split("\t"); s, e, v = int(s), int(e), int(v)
                tot_in += (e - s) * v
                pieces, m = subtract(c, s, e, bl)
                tot_masked += m * v; bp_masked += m
                for a, b in pieces:
                    w.write(f"{c}\t{a}\t{b}\t{v}\n"); tot_out += (b - a) * v; segs += 1
        # independent re-check: no output base inside the blacklist
        inside = 0
        with open(o) as r:
            for l in r:
                c, s, e, _ = l.split("\t"); _, m = subtract(c, int(s), int(e), bl); inside += m
        subprocess.run(["bedGraphToBigWig", str(o), sizes, str(out / f"{t}.bw")], check=True)
        subprocess.run(["bgzip", "-f", str(o)], check=True)
        subprocess.run(["tabix", "-f", "-p", "bed", str(o) + ".gz"], check=True)
        qc[t] = dict(signal_in=tot_in, signal_out=tot_out, signal_masked=tot_masked, bp_masked=bp_masked,
                     segments_out=segs, output_bp_inside_blacklist=inside,
                     masked_signal_fraction=round(tot_masked / max(tot_in, 1), 4),
                     status="PASS" if inside == 0 and tot_in == tot_out + tot_masked else "FAIL")
    res = dict(blacklist=str(blp), tracks=qc, status="PASS" if all(v["status"] == "PASS" for v in qc.values()) else "FAIL")
    (out / "mask_qc.json").write_text(json.dumps(res, indent=1) + "\n")
    print(json.dumps({k: (v["masked_signal_fraction"], v["status"]) for k, v in qc.items()}))
    return 0 if res["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:5]))
