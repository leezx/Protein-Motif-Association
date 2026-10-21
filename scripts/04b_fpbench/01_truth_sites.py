#!/usr/bin/env python3
"""Step 4b footprint benchmark v2: motif sites inside the benchmark windows, labelled by same-cell ChIP-seq.

Motifs are used only to define evaluation sites; no caller sees them.
  bound   = site overlaps a conservative IDR ChIP-seq peak of that TF
  unbound = site overlaps no peak of that TF
A site is kept only if its centre is >= MARGIN bp from both window edges, so every caller has flank context.
Overlapping hits of one motif are reduced to the best-scoring hit.

usage: 01_truth_sites.py <regions_1kb.bed> <genome.fa> <jaspar.meme> <chip_panel.tsv> <chip_dir> <outdir> <threads>
output: <outdir>/sites.tsv.gz  chrom start end tf strand moods_score bound
        <outdir>/site_summary.tsv
"""
import gzip, os, subprocess, sys
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pysam

MARGIN = 100
SEQS = []  # filled before the worker pool forks
PVAL = 1e-4


def read_meme(path, wanted):
    """JASPAR MEME -> {motif_id: (name, counts array 4 x L)} for wanted ids."""
    out, mid, rows = {}, None, None
    for line in open(path):
        if line.startswith("MOTIF"):
            parts = line.split()
            mid, name = parts[1], parts[2]
            rows = [] if mid in wanted else None
        elif rows is not None and line.strip() and line.strip()[0] in "0123456789." and mid in wanted:
            vals = [float(x) for x in line.split()]
            if len(vals) == 4:
                rows.append(vals)
                out[mid] = (name, np.array(rows).T)
    return out


def scan_one(args):
    import MOODS.scan, MOODS.tools
    mid, name, mat, bg = args
    seqs = SEQS
    m = (mat + 0.01) / (mat + 0.01).sum(axis=0)
    lo = MOODS.tools.log_odds([list(r) for r in m], bg, 1)
    rc = MOODS.tools.reverse_complement(lo)
    thr = MOODS.tools.threshold_from_p(lo, bg, PVAL)
    L = m.shape[1]
    hits = []
    for (chrom, ws), seq in seqs:
        for strand, mat_ in (("+", lo), ("-", rc)):
            for h in MOODS.scan.scan_dna(seq, [mat_], bg, [thr], 7)[0]:
                s = ws + h.pos
                c = s + L // 2
                if c - ws < MARGIN or ws + len(seq) - c < MARGIN:
                    continue
                hits.append((chrom, s, s + L, name, strand, h.score))
    # best hit per overlapping cluster
    hits.sort(key=lambda x: (x[0], x[1]))
    kept = []
    for h in hits:
        if kept and kept[-1][0] == h[0] and h[1] < kept[-1][2]:
            if h[5] > kept[-1][5]:
                kept[-1] = h
            continue
        kept.append(h)
    return name, kept


def main():
    regions, fa, meme, panel, chip_dir, out, threads = sys.argv[1:8]
    threads = int(threads)
    os.makedirs(out, exist_ok=True)
    panel_rows = [l.rstrip("\n").split("\t") for l in open(panel)][1:]
    wanted = {r[1]: r for r in panel_rows}
    motifs = read_meme(meme, wanted)
    genome = pysam.FastaFile(fa)
    seqs = SEQS
    for line in open(regions):
        c, s, e = line.split()[:3]
        seqs.append(((c, int(s)), genome.fetch(c, int(s), int(e)).upper()))
    gc = sum(q.count("G") + q.count("C") for _, q in seqs) / sum(len(q) for _, q in seqs)
    bg = [(1 - gc) / 2, gc / 2, gc / 2, (1 - gc) / 2]
    jobs = [(mid, motifs[mid][0], motifs[mid][1], bg) for mid in wanted if mid in motifs]
    tmp = os.path.join(out, "sites.unlabelled.bed")
    with open(tmp, "w") as o, ProcessPoolExecutor(threads) as ex:
        for name, kept in ex.map(scan_one, jobs):
            for h in kept:
                o.write("%s\t%d\t%d\t%s\t%s\t%.3f\n" % h)
    # label with each TF's own ChIP peaks
    peaks = os.path.join(out, "chip_peaks.bed")
    with open(peaks, "w") as o:
        for r in panel_rows:
            tf, acc = r[0], r[2]
            with gzip.open(os.path.join(chip_dir, acc + ".bed.gz"), "rt") as f:
                for line in f:
                    p = line.split("\t")
                    o.write(f"{p[0]}\t{p[1]}\t{p[2]}\t{tf}\n")
    # per-TF overlap with sorted interval arrays
    by_tf = {}
    for line in open(peaks):
        c, s, e, tf = line.split()
        by_tf.setdefault((tf, c), []).append((int(s), int(e)))
    idx = {}
    for k, v in by_tf.items():
        v.sort()
        a = np.array(v)
        idx[k] = (a[:, 0], np.maximum.accumulate(a[:, 1]))
    n = {}
    with open(tmp) as f, gzip.open(os.path.join(out, "sites.tsv.gz"), "wt") as o:
        o.write("chrom\tstart\tend\ttf\tstrand\tmoods_score\tbound\n")
        for line in f:
            c, s, e, tf, strand, sc = line.split()
            s, e = int(s), int(e)
            b = 0
            if (tf, c) in idx:
                starts, maxend = idx[(tf, c)]
                i = np.searchsorted(starts, e) - 1  # last peak starting before site end
                b = int(i >= 0 and maxend[i] > s)
            o.write(f"{c}\t{s}\t{e}\t{tf}\t{strand}\t{sc}\t{b}\n")
            k = n.setdefault(tf, [0, 0]); k[b] += 1
    with open(os.path.join(out, "site_summary.tsv"), "w") as o:
        o.write("tf\tunbound\tbound\n")
        for tf in sorted(n):
            o.write(f"{tf}\t{n[tf][0]}\t{n[tf][1]}\n")
    os.remove(tmp)


if __name__ == "__main__":
    main()
