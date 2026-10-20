"""Step 4a §11: peak-derived occupancy summary tracks and class-split light BEDs.

usage: 05_occupancy_tracks.py <occupancy.bed.gz> <class_annotation.csv> <protein_nr.bed.gz> <chrom.sizes> <out_dir>
                              <region|chrom>[,...]
Per base, from experiment-level peaks (Output A, v1), counts of distinct items whose peak covers the base:
  experiments       distinct experiments                         (all protein experiments)
  proteins          distinct target labels                       (HGNC symbol, else ChIP-Atlas antigen)
  tf                distinct targets of class 'Sequence-specific TF'
  cap               distinct targets of classes Histone writer/eraser, Histone reader, Chromatin remodeler,
                    Architectural/cohesin
Writes <out_dir>/<track>.bedGraph and .bw (bedGraphToBigWig), and the light protein BED split by class
(<out_dir>/bed/<class>.bed). These are peak-overlap summaries, not read coverage.
"""
import collections
import csv
import os
import re
import subprocess
import sys
from pathlib import Path

CAP = {"Histone writer/eraser", "Histone reader", "Chromatin remodeler", "Architectural/cohesin"}
TRACKS = ("experiments", "proteins", "tf", "cap")


def target_of(f):
    return "_".join((f[8] if f[8] != "." else f[7]).split())


def parse_region(r, sizes):
    m = re.match(r"^([^:]+)(?::([\d,]+)-([\d,]+))?$", r)
    c = m.group(1)
    if m.group(2):  # 1-based inclusive (IGV/tabix) -> 0-based half-open
        return c, int(m.group(2).replace(",", "")) - 1, int(m.group(3).replace(",", ""))
    return c, 0, sizes[c]


def sweep(chrom, events, lo, hi, out):
    """events: (pos, delta, item); write bedGraph segments of the distinct-active-item count, clipped to [lo, hi)."""
    events.sort(key=lambda x: (x[0], x[1]))
    active = collections.Counter()
    n = 0; last = lo; segs = []
    def seg(a, b, v):
        a, b = max(a, lo), min(b, hi)
        if a < b and v > 0:
            if segs and segs[-1][1] == a and segs[-1][2] == v:
                segs[-1][1] = b
            else:
                segs.append([a, b, v])
    i = 0
    while i < len(events):
        pos = events[i][0]
        seg(last, pos, n)
        while i < len(events) and events[i][0] == pos:
            _, d, item = events[i]
            before = active[item]
            active[item] += d
            if before == 0 and active[item] > 0:
                n += 1
            elif before > 0 and active[item] == 0:
                n -= 1
                del active[item]
            i += 1
        last = pos
    seg(last, hi, n)
    for a, b, v in segs:
        out.write(f"{chrom}\t{a}\t{b}\t{v}\n")
    return len(segs)


def main(bed, ann, nr_bed, sizes_path, out, regions):
    sizes = {l.split("\t")[0]: int(l.split("\t")[1]) for l in Path(sizes_path).read_text().splitlines() if l}
    cls = {r["gene"]: r["Class"] for r in csv.DictReader(open(ann, encoding="utf-8-sig"))}
    out = Path(out); (out / "bed").mkdir(parents=True, exist_ok=True)
    bg = {t: open(out / f"{t}.bedGraph", "w") for t in TRACKS}
    bed_out = {}
    stats = collections.Counter()
    for reg in regions.split(","):
        chrom, lo, hi = parse_region(reg, sizes)
        ev = {t: [] for t in TRACKS}
        q = f"{chrom}:{lo + 1}-{hi}"
        p = subprocess.Popen(["tabix", bed, q], stdout=subprocess.PIPE, text=True)
        for line in p.stdout:
            f = line.rstrip("\n").split("\t")
            s, e = int(f[1]), int(f[2]); t = target_of(f); c = cls.get(f[8], "Non-gene label")
            stats["peaks"] += 1
            for track, item in (("experiments", f[3]), ("proteins", t),
                                ("tf", t if c == "Sequence-specific TF" else None),
                                ("cap", t if c in CAP else None)):
                if item is not None:
                    ev[track] += [(s, 1, item), (e, -1, item)]
        assert p.wait() == 0
        for t in TRACKS:
            stats[f"segments_{t}"] += sweep(chrom, ev[t], lo, hi, bg[t])
        p = subprocess.Popen(["tabix", nr_bed, q], stdout=subprocess.PIPE, text=True)
        for line in p.stdout:
            f = line.rstrip("\n").split("\t")
            c = cls.get(f[3], "Non-gene label")
            k = re.sub(r"[^A-Za-z0-9]+", "_", c).strip("_")
            if k not in bed_out:
                bed_out[k] = open(out / "bed" / f"{k}.bed", "w")
            bed_out[k].write(line); stats[f"bed_{k}"] += 1
        assert p.wait() == 0
    for h in list(bg.values()) + list(bed_out.values()):
        h.close()
    used = out / "chrom.sizes"
    used.write_text("".join(f"{c}\t{n}\n" for c, n in sizes.items()))
    for t in TRACKS:
        subprocess.run(["bedGraphToBigWig", str(out / f"{t}.bedGraph"), str(used), str(out / f"{t}.bw")], check=True)
    used.unlink()
    for k, v in sorted(stats.items()):
        print(f"{k}\t{v}")


if __name__ == "__main__":
    main(*sys.argv[1:7])
