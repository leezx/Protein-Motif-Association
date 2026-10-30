"""PMA cross-context evidence for the HT29 consensus ATAC regions of 45_ht29_dtag_counts.py (Context Query v0.1).

usage: 46_ht29_pma_evidence.py chrom <regions.bed> <occupancy.bed.gz> <out_dir> <chrom>
       46_ht29_pma_evidence.py annotate <regions.bed> <bins500.npz> <bins_annotation.npz> <motifs.meme> <motif_id>
                               <genome.fa> <out_dir> [p=1e-4]

chrom mode: streams the v1 Output A rows of one chromosome (tabix; protein + RNA polymerase experiments, the proteins.bw
universe). Target key = HGNC symbol, else the ChIP-Atlas antigen (whitespace -> _), as in 29_hotspot_protein_support.py.
For region R and target p, S(R, p) = experiments of p with >= 1 peak overlapping R. Writes parts/<chrom>.pairs.tsv:
region, target, n_exp, n_celltypes, n_exp_gut (cell type class 'Digestive tract'), n_exp_ht29 (cell type HT-29).
annotate mode: per region, the 500 bp bins it overlaps (23_hotspot_bins.py): P_max (distinct ChIP-Atlas proteins),
max ChIP-Atlas ATAC experiments open, blacklist (any bin); at the bin of the region midpoint: cCRE class, TSS distance
and class, CpG island, GC (31_hotspot_annotation.py). Motif: log-odds PWM (uniform background, pseudocount 0.01) on
both strands; n hits with P < p (exact null by score-distribution convolution) and the best score. Then collects the
chrom parts into pairs.tsv.gz and writes annotation.tsv.gz.
"""
import bisect
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pysam

CCRE = ["PLS", "pELS", "dELS", "CA-H3K4me3", "CA-CTCF", "CA-TF", "TF", "CA", "none"]
BIN = 500


def load_regions(path, chrom=None):
    r = pd.read_csv(path, sep="\t", header=None, names=["chrom", "start", "end", "region", "n_samples"])
    return r[r.chrom == chrom].reset_index(drop=True) if chrom else r


def run_chrom(regions_bed, bed, out_dir, chrom):
    reg = load_regions(regions_bed, chrom)
    st, en, name = reg.start.tolist(), reg.end.tolist(), reg.region.tolist()
    parts = Path(out_dir) / "parts"
    parts.mkdir(parents=True, exist_ok=True)
    fo = open(parts / f"{chrom}.pairs.tsv.tmp", "w")
    acc, nxt = {}, 0

    def flush(upto):
        nonlocal nxt
        while nxt < len(reg) and en[nxt] <= upto:
            for p, ex in acc.pop(nxt, {}).items():
                v = list(ex.values())
                fo.write(f"{name[nxt]}\t{p}\t{len(ex)}\t{len({c for c, _ in v})}\t"
                         f"{sum(k == 'Digestive tract' for _, k in v)}\t{sum(c == 'HT-29' for c, _ in v)}\n")
            nxt += 1

    proc = subprocess.Popen(["tabix", bed, chrom], stdout=subprocess.PIPE, text=True, bufsize=1 << 20)
    last, rows = -1, 0
    for line in proc.stdout:
        f = line.rstrip("\n").split("\t")
        s, e = int(f[1]), int(f[2])
        assert s >= last, "input not start-sorted"
        last = s
        rows += 1
        flush(s)
        i = bisect.bisect_right(en, s)
        while i < len(reg) and st[i] < e:
            p = "_".join((f[8] if f[8] != "." else f[7]).split())
            acc.setdefault(i, {}).setdefault(p, {})[f[3]] = (f[13], f[12])
            i += 1
    assert proc.wait() == 0, "tabix failed"
    flush(1 << 62)
    assert nxt == len(reg)
    fo.close()
    (parts / f"{chrom}.pairs.tsv.tmp").rename(parts / f"{chrom}.pairs.tsv")
    print(chrom, "rows", rows, "regions", len(reg))


def read_meme(path, mid):
    m, on = [], False
    for line in open(path):
        if line.startswith("MOTIF"):
            on = line.split()[1] == mid
            continue
        if on:
            x = line.split()
            if len(x) == 4 and all(_isnum(v) for v in x):
                m.append([float(v) for v in x])
            elif m and not line.strip():
                break
    assert m, f"motif {mid} not found"
    return np.array(m)


def _isnum(v):
    try:
        float(v)
        return True
    except ValueError:
        return False


def score_threshold(lo, p, step=0.01):
    """Smallest score s with P(score >= s) < p for i.i.d. uniform bases (scores rounded to step)."""
    q = np.round(lo / step).astype(int)
    off = q.min(axis=1)
    dist = np.array([1.0])
    for row, o in zip(q, off):
        k = row - o
        add = np.zeros(k.max() + 1)
        for v in k:
            add[v] += 0.25
        dist = np.convolve(dist, add)
    sf = np.cumsum(dist[::-1])[::-1]  # P(score >= index)
    idx = int(np.argmax(sf < p))
    return (idx + off.sum()) * step


def motif_scan(reg, fasta, pwm, p):
    lo = np.log2((pwm + 0.01) / (1 + 0.04) / 0.25)
    thr = score_threshold(lo, p)
    rc = lo[::-1, ::-1]
    w = len(lo)
    lut = np.full(256, 4, np.int8)
    for i, b in enumerate("ACGT"):
        lut[ord(b)] = i
        lut[ord(b.lower())] = i
    pad = np.vstack([lo.T, np.full(w, -99)]).T  # N -> -99
    padr = np.vstack([rc.T, np.full(w, -99)]).T
    n_hit, best = np.zeros(len(reg), np.int32), np.full(len(reg), -99.0)
    with pysam.FastaFile(fasta) as fa:
        for i, (c, s, e) in enumerate(zip(reg.chrom, reg.start, reg.end)):
            x = lut[np.frombuffer(fa.fetch(c, int(s), int(e)).encode(), np.uint8)]
            if len(x) < w:
                continue
            L = len(x) - w + 1
            sf = np.zeros(L)
            sr = np.zeros(L)
            for j in range(w):
                sf += pad[j, x[j:j + L]]
                sr += padr[j, x[j:j + L]]
            sc = np.maximum(sf, sr)
            n_hit[i] = int((sc >= thr).sum())
            best[i] = sc.max()
    return n_hit, best, thr


def annotate(regions_bed, npz, ann, meme, mid, fasta, out_dir, p=1e-4):
    out = Path(out_dir)
    reg = load_regions(regions_bed)
    z, a = np.load(npz), np.load(ann)
    offs = dict(zip(list(z["chrom"]), z["offset"].astype(np.int64)))
    nb = dict(zip(list(z["chrom"]), z["n_bins"].astype(np.int64)))
    o, n = reg.chrom.map(offs).to_numpy(), reg.chrom.map(nb).to_numpy()
    b0 = o + reg.start.to_numpy() // BIN
    b1 = o + np.minimum((reg.end.to_numpy() - 1) // BIN, n - 1)
    P, A, blk = z["proteins"].astype(np.int32), z["atac_experiments"].astype(np.int32), a["blacklist"]
    pmax, amax, bl = np.zeros(len(reg), np.int32), np.zeros(len(reg), np.int32), np.zeros(len(reg), bool)
    for k in range(int((b1 - b0).max()) + 1):
        m = b0 + k <= b1
        idx = b0[m] + k
        pmax[m] = np.maximum(pmax[m], P[idx])
        amax[m] = np.maximum(amax[m], A[idx])
        bl[m] |= blk[idx]
    mb = o + np.minimum(((reg.start + reg.end) // 2).to_numpy() // BIN, n - 1)
    d = reg.copy()
    d["P_max"], d["chipatlas_atac_frac"], d["blacklist"] = pmax, amax / 18651.0, bl
    d["ccre"] = np.array(CCRE)[a["ccre"][mb]]
    d["tss_dist"], d["tss_class"], d["cpg"], d["gc"] = a["tss_dist"][mb], a["tss_class"][mb], a["cpg"][mb], a["gc"][mb]
    n_hit, best, thr = motif_scan(reg, fasta, read_meme(meme, mid), p)
    d["sox9_motif_hits"], d["sox9_motif_best"] = n_hit, best
    d.to_csv(out / "annotation.tsv.gz", sep="\t", index=False)
    print(f"motif {mid} threshold {thr:.2f} bits (P<{p}); regions with >=1 hit: {(n_hit > 0).mean():.3f}")
    parts = sorted((out / "parts").glob("*.pairs.tsv"))
    pr = pd.concat([pd.read_csv(f, sep="\t", header=None, names=["region", "target", "n_exp", "n_celltypes",
                                                                  "n_exp_gut", "n_exp_ht29"]) for f in parts])
    assert set(pr.region) <= set(reg.region)
    pr.to_csv(out / "pairs.tsv.gz", sep="\t", index=False)
    print(f"pairs {len(pr)}; regions with any target {pr.region.nunique()} / {len(reg)}; chrom parts {len(parts)}")


if __name__ == "__main__":
    if sys.argv[1] == "chrom":
        run_chrom(*sys.argv[2:6])
    else:
        annotate(*sys.argv[2:9], *(float(x) for x in sys.argv[9:10]))
