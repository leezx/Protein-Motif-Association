"""Step 4a §11: ChIP-Atlas Protein Occupancy Evidence Tracks (peak-derived; not read coverage).

usage: 05_occupancy_tracks.py <occupancy.bed.gz> <class_annotation.csv> <chrom.sizes> <out_dir> [workers] [region]
Definitions, per base x, from experiment-level peaks of Output A (v1); p = target label (HGNC symbol, else the
ChIP-Atlas antigen), class(p) from the annotation (labels without HGNC symbol: 'Non-gene label'):
  E(x)   = |{e : x in peaks(e)}|                          experiments.bw
  P(x)   = |{p : x in peaks(p)}|                          proteins.bw
  TF(x)  = |{p : class(p) = Sequence-specific TF, x in peaks(p)}|     tf.bw
  CAP(x) = |{p : class(p) in CAP, x in peaks(p)}|        cap.bw
  CAP = Histone writer/eraser, Histone reader, Chromatin remodeler, Architectural/cohesin.
  P_k(x) for every class k is computed for QC only (class_<k>.bedGraph, removed after QC).
QC on every bedGraph breakpoint (exact, all chromosomes): P = sum_k P_k; TF <= P; CAP <= P; P <= E; values > 0.
Streaming sweep per chromosome (input start-sorted; heap of active peak ends), workers in parallel.
Writes <out_dir>/{experiments,proteins,tf,cap}.bw (+ .bedGraph.gz), qc.json. [region] = chr:start-end test mode.
"""
import collections
import csv
import gzip
import heapq
import json
import multiprocessing as mp
import re
import subprocess
import sys
from pathlib import Path

CAP = {"Histone writer/eraser", "Histone reader", "Chromatin remodeler", "Architectural/cohesin"}
MAIN = ("experiments", "proteins", "tf", "cap")


def slug(c):
    return re.sub(r"[^A-Za-z0-9]+", "_", c).strip("_")


class Track:
    """Distinct-active-item count as a step function, written as merged bedGraph segments."""
    def __init__(self, chrom, out, lo, hi):
        self.chrom, self.out, self.lo, self.hi = chrom, out, lo, hi
        self.heap, self.active, self.n, self.last = [], collections.Counter(), 0, lo
        self.seg = None; self.nseg = 0

    def _emit(self, a, b):
        a, b = max(a, self.lo), min(b, self.hi)
        if a >= b or self.n == 0:
            return
        s = self.seg
        if s and s[1] == a and s[2] == self.n:
            s[1] = b
        else:
            if s:
                self.out.write(f"{self.chrom}\t{s[0]}\t{s[1]}\t{s[2]}\n"); self.nseg += 1
            self.seg = [a, b, self.n]

    def advance(self, pos):
        h = self.heap
        while h and h[0][0] <= pos:
            e, item = heapq.heappop(h)
            if e > self.last:
                self._emit(self.last, e); self.last = e
            self.active[item] -= 1
            if self.active[item] == 0:
                del self.active[item]; self.n -= 1
        if pos > self.last:
            self._emit(self.last, pos); self.last = pos

    def add(self, s, e, item):
        self.advance(s)
        if self.active[item] == 0:
            self.n += 1
        self.active[item] += 1
        heapq.heappush(self.heap, (e, item))

    def close(self):
        self.advance(1 << 62)
        if self.seg:
            self.out.write(f"{self.chrom}\t{self.seg[0]}\t{self.seg[1]}\t{self.seg[2]}\n"); self.nseg += 1


def run_chrom(args):
    bed, cls, classes, chrom, lo, hi, wdir = args
    names = list(MAIN) + [f"class_{slug(k)}" for k in classes]
    fh = {t: open(f"{wdir}/{t}.{chrom}.bedGraph", "w") for t in names}
    tr = {t: Track(chrom, fh[t], lo, hi) for t in names}
    q = chrom if lo == 0 and hi >= 1 << 40 else f"{chrom}:{lo + 1}-{hi}"
    p = subprocess.Popen(["tabix", bed, q], stdout=subprocess.PIPE, text=True, bufsize=1 << 20)
    rows = 0; prev = -1
    for line in p.stdout:
        f = line.split("\t", 9)
        s, e = int(f[1]), int(f[2])
        if s < prev:
            raise RuntimeError(f"{chrom}: input not start-sorted")
        prev = s; rows += 1
        t = "_".join((f[8] if f[8] != "." else f[7]).split())
        c = cls.get(f[8], "Non-gene label") if f[8] != "." else "Non-gene label"
        tr["experiments"].add(s, e, f[3])
        tr["proteins"].add(s, e, t)
        if c == "Sequence-specific TF":
            tr["tf"].add(s, e, t)
        elif c in CAP:
            tr["cap"].add(s, e, t)
        tr[f"class_{slug(c)}"].add(s, e, t)
    if p.wait() != 0:
        raise RuntimeError(f"tabix failed on {chrom}")
    for t in names:
        tr[t].close(); fh[t].close()
    qc = qc_chrom(wdir, chrom, names)
    qc.update(chrom=chrom, rows=rows, segments={t: tr[t].nseg for t in MAIN})
    return qc


def steps(path):
    """Yield (start, end, value) from a single-chrom bedGraph."""
    with open(path) as f:
        for line in f:
            _, a, b, v = line.split("\t")
            yield int(a), int(b), int(v)


def qc_chrom(wdir, chrom, names):
    """Exact check on the union of breakpoints of all tracks of one chromosome."""
    its = {t: steps(f"{wdir}/{t}.{chrom}.bedGraph") for t in names}
    cur = {t: next(its[t], None) for t in names}
    bad = collections.Counter(); ex = {}
    bp_checked = 0; maxv = collections.Counter()
    pos = min((c[0] for c in cur.values() if c), default=None)
    while pos is not None:
        val = {}
        nxt = []
        for t in names:
            c = cur[t]
            while c and c[1] <= pos:
                c = cur[t] = next(its[t], None)
            if c and c[0] <= pos < c[1]:
                val[t] = c[2]; nxt.append(c[1])
            else:
                val[t] = 0
                if c: nxt.append(c[0])
        if not nxt:
            break
        end = min(nxt)
        ksum = sum(v for t, v in val.items() if t.startswith("class_"))
        for name, ok in (("P_ne_sum_classes", val["proteins"] == ksum), ("TF_gt_P", val["tf"] <= val["proteins"]),
                         ("CAP_gt_P", val["cap"] <= val["proteins"]), ("P_gt_E", val["proteins"] <= val["experiments"]),
                         ("P_zero_E_pos", (val["proteins"] > 0) == (val["experiments"] > 0))):
            if not ok:
                bad[name] += 1; ex.setdefault(name, f"{chrom}:{pos}-{end} {val}")
        if val["experiments"] > 0:
            bp_checked += end - pos
        for t in MAIN:
            maxv[t] = max(maxv[t], val[t])
        pos = end
    return dict(qc_violations=dict(bad), qc_examples=ex, covered_bp=bp_checked, max=dict(maxv))


def spot_check(bed, cls, out_dir, n=300, seed=20261020):
    """Independent recount at random covered positions straight from tabix (different code path)."""
    import random
    rnd = random.Random(seed)
    lines = []
    with gzip.open(out_dir / "experiments.bedGraph.gz", "rt") as f:
        for i, line in enumerate(f):  # reservoir sample of segments
            if len(lines) < n:
                lines.append(line)
            else:
                j = rnd.randint(0, i)
                if j < n:
                    lines[j] = line
    tracks = {}
    for t in MAIN:
        tracks[t] = out_dir / f"{t}.bedGraph.gz"
    bad = []
    for line in lines:
        c, a, b, _ = line.split("\t"); x = rnd.randint(int(a), int(b) - 1)
        rows = subprocess.run(["tabix", str(bed), f"{c}:{x + 1}-{x + 1}"], capture_output=True, text=True,
                              check=True).stdout.splitlines()
        exps, prots, tf, cap = set(), set(), set(), set()
        for r in rows:
            f = r.split("\t")
            t = "_".join((f[8] if f[8] != "." else f[7]).split())
            k = cls.get(f[8], "Non-gene label") if f[8] != "." else "Non-gene label"
            exps.add(f[3]); prots.add(t)
            if k == "Sequence-specific TF": tf.add(t)
            elif k in CAP: cap.add(t)
        want = dict(experiments=len(exps), proteins=len(prots), tf=len(tf), cap=len(cap))
        got = {}
        for t in MAIN:
            q = subprocess.run(["tabix", str(tracks[t]), f"{c}:{x + 1}-{x + 1}"], capture_output=True, text=True,
                               check=True).stdout.split()
            got[t] = int(q[3]) if q else 0
        if got != want:
            bad.append(dict(pos=f"{c}:{x}", want=want, got=got))
    return dict(positions=len(lines), mismatches=len(bad), examples=bad[:5])


def main(bed, ann, sizes_path, out, workers=6, region=None):
    sizes = {l.split("\t")[0]: int(l.split("\t")[1]) for l in Path(sizes_path).read_text().splitlines() if l}
    cls = {r["gene"]: r["Class"] for r in csv.DictReader(open(ann, encoding="utf-8-sig"))}
    classes = sorted(set(cls.values()) | {"Non-gene label"})
    out = Path(out); wdir = out / "work"; wdir.mkdir(parents=True, exist_ok=True)
    if region:
        m = re.match(r"^([^:]+):([\d,]+)-([\d,]+)$", region)
        jobs = [(bed, cls, classes, m.group(1), int(m.group(2).replace(",", "")) - 1,
                 int(m.group(3).replace(",", "")), str(wdir))]
    else:
        chroms = subprocess.run(["tabix", "-l", bed], capture_output=True, text=True, check=True).stdout.split()
        chroms.sort(key=lambda c: -sizes.get(c, 0))  # big chromosomes first for load balance
        jobs = [(bed, cls, classes, c, 0, 1 << 41, str(wdir)) for c in chroms]
    with mp.Pool(workers) as pool:
        res = pool.map(run_chrom, jobs, chunksize=1)
    chroms_sorted = sorted(r["chrom"] for r in res)
    used = wdir / "chrom.sizes"
    used.write_text("".join(f"{c}\t{sizes[c]}\n" for c in chroms_sorted))
    for t in MAIN:
        bg = out / f"{t}.bedGraph"
        with open(bg, "w") as w:
            for c in chroms_sorted:
                with open(wdir / f"{t}.{c}.bedGraph") as r:
                    for line in r:
                        w.write(line)
        subprocess.run(["bedGraphToBigWig", str(bg), str(used), str(out / f"{t}.bw")], check=True)
        subprocess.run(["bgzip", "-f", "-@", str(workers), str(bg)], check=True)
        subprocess.run(["tabix", "-f", "-p", "bed", str(out / f"{t}.bedGraph.gz")], check=True)
    viol = collections.Counter(); ex = {}
    for r in res:
        viol.update(r["qc_violations"]); [ex.setdefault(k, v) for k, v in r["qc_examples"].items()]
    spot = spot_check(bed, cls, out)
    qc = dict(rows=sum(r["rows"] for r in res), chromosomes=len(res),
              covered_bp=sum(r["covered_bp"] for r in res),
              max={t: max(r["max"].get(t, 0) for r in res) for t in MAIN},
              segments={t: sum(r["segments"][t] for r in res) for t in MAIN},
              identity_violations=dict(viol), identity_examples=ex, spot_check=spot,
              status="PASS" if not viol and spot["mismatches"] == 0 else "FAIL")
    (out / "qc.json").write_text(json.dumps(qc, indent=1) + "\n")
    for f in wdir.iterdir():
        f.unlink()
    wdir.rmdir()
    print(json.dumps({k: v for k, v in qc.items() if k != "identity_examples"}))
    return 0 if qc["status"] == "PASS" else 1


if __name__ == "__main__":
    a = sys.argv[1:]
    sys.exit(main(*a[:4], workers=int(a[4]) if len(a) > 4 else 6, region=a[5] if len(a) > 5 else None))
