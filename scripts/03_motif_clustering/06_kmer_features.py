"""Step 3 §8.1: 8-mer affinity profiles per node (frozen representation).

usage: 06_kmer_features.py <nodes.meme> <out_dir>

For each node: probability floor 0.01 + renormalise, lo = log2(p / 0.25);
a(k) = best over positions and both strands of the mean per-position
log-odds of 8-mer k in an 8-column window (L < 8: the motif slides inside
the 8-mer and is averaged over its L columns). Features = the 32,896
reverse-complement-collapsed 8-mers. Each profile is centred and
L2-normalised, so the dot product of two profiles is their Pearson
correlation.

Writes: features.f32 (row-major, nodes x 32,896 float32), nodes.tsv
(node_id, partition, length, gc, ic, length_lt8), kmers.txt.
numpy only.
"""
import sys
from pathlib import Path

import numpy as np

K = 8
FLOOR = 0.01
BASES = "ACGT"


def read_meme(path):
    out, cur, mat = [], None, []
    for line in open(path):
        if line.startswith("MOTIF"):
            if cur:
                out.append((*cur, np.array(mat, float)))
            p = line.split()
            cur, mat = (p[1], p[2] if len(p) > 2 else ""), []
        elif cur and line.strip() and line.split()[0][0] in "0123456789." and len(line.split()) == 4:
            mat.append([float(x) for x in line.split()])
    if cur:
        out.append((*cur, np.array(mat, float)))
    return out


def kmer_tables(k=K):
    idx = np.arange(4 ** k)
    digits = (idx[:, None] // 4 ** np.arange(k - 1, -1, -1)) % 4  # first base most significant
    rc = ((3 - digits[:, ::-1]) * 4 ** np.arange(k - 1, -1, -1)).sum(1)
    canon = np.flatnonzero(idx <= rc)
    names = ["".join(BASES[d] for d in row) for row in digits[canon]]
    return canon, names


def log_odds(p):
    p = np.maximum(np.asarray(p, float), FLOOR)
    p = p / p.sum(1, keepdims=True)
    return np.log2(p / 0.25)


def strand_scores(lo, k=K):
    """Best mean per-position log-odds of every k-mer on one strand."""
    L = len(lo)
    best = np.full(4 ** k, -np.inf)
    if L >= k:
        for w in range(L - k + 1):
            s = lo[w]
            for i in range(1, k):
                s = (s[:, None] + lo[w + i][None, :]).ravel()
            best = np.maximum(best, s / k)
    else:
        zero = np.zeros(4)
        for j in range(k - L + 1):
            s = np.zeros(1)
            for pos in range(k):
                row = lo[pos - j] if j <= pos < j + L else zero
                s = (s[:, None] + row[None, :]).ravel()
            best = np.maximum(best, s / L)
    return best


def affinity(p, canon):
    lo = log_odds(p)
    a = np.maximum(strand_scores(lo), strand_scores(lo[::-1, ::-1]))[canon]
    a = a - a.mean()
    n = np.linalg.norm(a)
    return a / n if n > 0 else a


def main(meme, out_dir):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    canon, names = kmer_tables()
    motifs = read_meme(meme)
    (out / "kmers.txt").write_text("\n".join(names) + "\n")
    with open(out / "features.f32", "wb") as fh, open(out / "nodes.tsv", "w") as nt:
        nt.write("node_id\tpartition\tlength\tgc\tic\tlength_lt8\n")
        for n, (mid, part, p) in enumerate(motifs):
            fh.write(affinity(p, canon).astype("<f4").tobytes())
            q = np.maximum(p, 1e-9)
            ic = float((2 + (q * np.log2(q)).sum(1)).sum())
            gc = float(p[:, 1:3].sum(1).mean())
            nt.write(f"{mid}\t{part}\t{len(p)}\t{gc:.4f}\t{ic:.4f}\t{len(p) < K}\n")
            if n % 2000 == 0:
                print(n, flush=True)
    print(f"{len(motifs)} nodes x {len(canon)} k-mers")


if __name__ == "__main__":
    main(*sys.argv[1:])
