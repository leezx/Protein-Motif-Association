"""Step 4a §11: split the occupancy evidence tracks at the ENCODE hg38 blacklist v2 (base-wise).

usage: 10_mask_blacklist.py <blacklist.bed.gz> <chrom.sizes> <in_dir> <out_noBlacklist_dir> <out_blacklistOnly_dir>
Every <in_dir>/*.bedGraph.gz is split into the part outside the blacklist (noBlacklist) and the part inside it
(blacklistOnly); values are copied unchanged. Writes <track>.bw, .bedGraph.gz (+ .tbi) to both directories and
mask_qc.json to the noBlacklist one. QC per track: no noBlacklist base inside and no blacklistOnly base outside the
blacklist (re-checked from the written files); sum(value*bp): input = noBlacklist + blacklistOnly.
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


def split(c, s, e, bl):
    """Pieces of [s, e) outside and inside the blacklist."""
    iv = bl.get(c)
    if not iv:
        return [(s, e)], []
    i = max(bisect.bisect_right(iv, [s, 1 << 62]) - 1, 0)
    outside, inside, cur = [], [], s
    while i < len(iv) and iv[i][0] < e:
        bs, be = iv[i]
        if be > cur:
            if bs > cur: outside.append((cur, min(bs, e)))
            inside.append((max(bs, cur), min(be, e)))
            cur = max(cur, be)
        i += 1
    if cur < e: outside.append((cur, e))
    return outside, inside


def subtract(c, s, e, bl):
    """Pieces of [s, e) outside the blacklist, and the masked bp."""
    o, i = split(c, s, e, bl)
    return o, sum(b - a for a, b in i)


def finish(o, sizes, t, d):
    subprocess.run(["bedGraphToBigWig", str(o), sizes, str(d / f"{t}.bw")], check=True)
    subprocess.run(["bgzip", "-f", str(o)], check=True)
    subprocess.run(["tabix", "-f", "-p", "bed", str(o) + ".gz"], check=True)


def main(blp, sizes, ind, out, out_bl):
    bl = load_bl(blp); ind, out, out_bl = Path(ind), Path(out), Path(out_bl)
    out.mkdir(parents=True, exist_ok=True); out_bl.mkdir(parents=True, exist_ok=True)
    qc = {}
    for bg in sorted(ind.glob("*.bedGraph.gz")):
        t = bg.name[:-len(".bedGraph.gz")]
        o, ob = out / f"{t}.bedGraph", out_bl / f"{t}.bedGraph"
        tot_in = tot_out = tot_bl = 0; bp_bl = 0
        with gzip.open(bg, "rt") as r, open(o, "w") as w, open(ob, "w") as wb:
            for l in r:
                c, s, e, v = l.split("\t"); s, e, v = int(s), int(e), int(v)
                tot_in += (e - s) * v
                outside, inside = split(c, s, e, bl)
                for a, b in outside:
                    w.write(f"{c}\t{a}\t{b}\t{v}\n"); tot_out += (b - a) * v
                for a, b in inside:
                    wb.write(f"{c}\t{a}\t{b}\t{v}\n"); tot_bl += (b - a) * v; bp_bl += b - a
        wrong_out = wrong_in = 0  # re-check from the written files
        with open(o) as r:
            for l in r:
                c, s, e, _ = l.split("\t"); wrong_out += sum(b - a for a, b in split(c, int(s), int(e), bl)[1])
        with open(ob) as r:
            for l in r:
                c, s, e, _ = l.split("\t"); wrong_in += sum(b - a for a, b in split(c, int(s), int(e), bl)[0])
        finish(o, sizes, t, out); finish(ob, sizes, t, out_bl)
        qc[t] = dict(signal_in=tot_in, signal_noBlacklist=tot_out, signal_blacklistOnly=tot_bl,
                     bp_with_signal_in_blacklist=bp_bl, noBlacklist_bp_inside_blacklist=wrong_out,
                     blacklistOnly_bp_outside_blacklist=wrong_in,
                     blacklist_signal_fraction=round(tot_bl / max(tot_in, 1), 4),
                     status="PASS" if wrong_out == 0 and wrong_in == 0 and tot_in == tot_out + tot_bl else "FAIL")
    res = dict(blacklist=str(blp), tracks=qc, status="PASS" if all(v["status"] == "PASS" for v in qc.values()) else "FAIL")
    (out / "mask_qc.json").write_text(json.dumps(res, indent=1) + "\n")
    print(json.dumps({k: (v["blacklist_signal_fraction"], v["status"]) for k, v in qc.items()}))
    return 0 if res["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:6]))
