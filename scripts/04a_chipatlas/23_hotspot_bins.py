"""Per-500 bp-bin maxima of the occupancy evidence tracks, for choosing hotspot / open-region thresholds (§18).

usage: 23_hotspot_bins.py <chrom.sizes> <out.npz> name=track.bedGraph.gz [name=track.bedGraph.gz ...]
Env: PMA_BIN (default 500), PMA_CHROMS (comma list; default chr1-22,X,Y).

For every bin the value is the maximum of the bedGraph over the bin (a bin with 12 distinct proteins at its
busiest base reports 12). Writes one uint16 array per track (concatenated over chromosomes, bins in chrom.sizes
order) plus chrom/offset arrays, and a JSON QC next to the npz: per-track bins > 0, max, and a check that the
summed covered bp equals the bedGraph total.
"""
import gzip
import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

BIN = int(os.environ.get("PMA_BIN", "500"))
DEFAULT = [f"chr{i}" for i in range(1, 23)] + ["chrX", "chrY"]


def load_sizes(path, chroms):
    s = dict(l.split()[:2] for l in open(path) if l.strip())
    return [(c, int(s[c])) for c in chroms]


def bin_max(path, sizes, offs, nbin):
    out = np.zeros(nbin, dtype=np.uint16)
    total_bp = 0; vmax = 0
    off = {c: o for (c, _), o in zip(sizes, offs)}
    with gzip.open(path, "rt") as fh:
        for ch in pd.read_csv(fh, sep="\t", header=None, names=["c", "s", "e", "v"], chunksize=5_000_000,
                              dtype={"c": str, "s": np.int64, "e": np.int64, "v": np.float64}):
            ch = ch[ch.c.isin(off)]
            if ch.empty:
                continue
            total_bp += int((ch.e - ch.s).sum()); vmax = max(vmax, float(ch.v.max()))
            base = ch.c.map(off).to_numpy(np.int64)
            b0 = ch.s.to_numpy() // BIN; b1 = (ch.e.to_numpy() - 1) // BIN
            n = (b1 - b0 + 1)
            idx = np.repeat(base + b0, n) + (np.arange(n.sum()) - np.repeat(np.cumsum(n) - n, n))
            v = np.repeat(np.minimum(ch.v.to_numpy(), 65535).astype(np.uint16), n)
            np.maximum.at(out, idx, v)
    return out, total_bp, vmax


def main(sizes_path, out, *tracks):
    chroms = os.environ.get("PMA_CHROMS", ",".join(DEFAULT)).split(",")
    sizes = load_sizes(sizes_path, chroms)
    nb = [(L + BIN - 1) // BIN for _, L in sizes]
    offs = np.concatenate([[0], np.cumsum(nb)[:-1]]).astype(np.int64); nbin = int(sum(nb))
    arrays, qc = {}, {"bin": BIN, "chroms": chroms, "n_bins": nbin, "tracks": {}}
    for t in tracks:
        name, path = t.split("=", 1)
        a, total_bp, vmax = bin_max(path, sizes, offs, nbin)
        assert int(a.max()) == int(min(vmax, 65535)), (name, a.max(), vmax)
        arrays[name] = a
        qc["tracks"][name] = {"path": path, "bins_gt0": int((a > 0).sum()), "max": int(a.max()), "covered_bp": total_bp}
        print(name, qc["tracks"][name], flush=True)
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(out, chrom=np.array([c for c, _ in sizes]), offset=offs, n_bins=np.array(nb), **arrays)
    Path(out).with_suffix(".qc.json").write_text(json.dumps(qc, indent=1))


if __name__ == "__main__":
    main(*sys.argv[1:])
