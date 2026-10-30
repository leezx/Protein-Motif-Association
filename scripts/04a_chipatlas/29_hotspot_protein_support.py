"""Per-hotspot protein counts under an independent-experiment support rule (Figure 1, hotspot protein support).

usage: 29_hotspot_protein_support.py chrom <occupancy.bed.gz> <hotspot_dir> <class_annotation.csv> <out_dir> <chrom>
       29_hotspot_protein_support.py collect <out_dir> <light_nr.bed.gz> [n_check]

Input: v1 Output A (experiment-level BED6+18, protein + RNA polymerase rows, the same universe as proteins.bw) and the
protein hotspot regions PMA_hotspot_protein_<tier>.bed of 25_hotspot_beds.py. Target key p = HGNC symbol, else the
ChIP-Atlas antigen (whitespace -> _), exactly as in 05_occupancy_tracks.py. For hotspot region R and target p:
  S(R, p) = {experiments e of p with >= 1 peak overlapping R by >= 1 bp};  C(R, p) = distinct cell types (col 14) of S
Per region, the number of targets with
  n_ge1      |S| >= 1                       (any peak; the rule behind the hotspot P track)
  n_ge2exp   |S| >= 2                       (primary: >= 2 independent ChIP-seq experiments)
  n_ge2ct    |S| >= 2 and |C| >= 2          (sensitivity: support from >= 2 distinct cell types)
plus n_ge2exp split by protein class (annotation v1.1; targets without HGNC symbol -> 'Non-gene label'), and the
same three counts restricted to direct DNA-binding proteins (DBP = functional tag lambert2018_TF, Lambert et al. 2018
human TF list; dbp_ge1, dbp_ge2exp, dbp_ge2ct) and to class 'Sequence-specific TF' (seqtf_*, sensitivity).
chrom mode: one chromosome, streaming over start-sorted rows; a region is written once rows start at or past its end.
  Writes <out_dir>/parts/<tier>.<chrom>.regions.tsv and, for top1, <tier>.<chrom>.pairs.tsv (region, target, class,
  is_dbp, n_exp, n_celltypes).
collect mode: concatenates parts into <tier>.regions.tsv.gz, top1.pairs.tsv.gz, summary.json. QC: every region found;
  n_ge1 >= max_proteins (union over the region vs per-bin max); n_ge1 == targets of the light BED overlapping R for
  n_check random top1 regions (a merged light interval overlaps R iff one of its peaks does).
"""
import bisect
import collections
import csv
import glob
import gzip
import json
import random
import subprocess
import sys
from pathlib import Path

TIERS = ("top1", "top5", "top10", "top20")
CLASSES = ("Sequence-specific TF", "Transcription machinery", "Histone writer/eraser", "Histone reader",
           "Chromatin remodeler", "Architectural/cohesin", "Other/ambiguous", "Non-gene label")
PAIR_TIERS = ("top1",)


def slug(c):
    return "".join(ch if ch.isalnum() else "_" for ch in c).strip("_")


def load_regions(hot_dir, chrom):
    out = {}
    for t in TIERS:
        rows = []
        with open(Path(hot_dir) / f"PMA_hotspot_protein_{t}.bed") as f:
            for line in f:
                c = line.rstrip("\n").split("\t")
                if c[0] == chrom:
                    rows.append((int(c[1]), int(c[2]), c[3], int(c[6]), int(c[7])))
        rows.sort()
        assert all(a[1] <= b[0] for a, b in zip(rows, rows[1:])), f"{t} {chrom}: overlapping regions"
        out[t] = rows
    return out


def run_chrom(bed, hot_dir, ann, out_dir, chrom):
    cls, dbp = {}, set()
    with open(ann) as f:
        for r in csv.DictReader(f):
            cls[r["gene"]] = r["Class"]
            if "lambert2018_TF" in r["functional_tags"].split(";"):
                dbp.add(r["gene"])
    regions = load_regions(hot_dir, chrom)
    ends = {t: [r[1] for r in regions[t]] for t in TIERS}
    nxt = {t: 0 for t in TIERS}  # next region not yet written
    acc = {t: {} for t in TIERS}  # region index -> target -> {experiment: cell type}
    tcls, tdbp = {}, {}
    parts = Path(out_dir) / "parts"
    parts.mkdir(parents=True, exist_ok=True)
    fo = {t: open(parts / f"{t}.{chrom}.regions.tsv", "w") for t in TIERS}
    fp = {t: open(parts / f"{t}.{chrom}.pairs.tsv", "w") for t in PAIR_TIERS}

    def flush(t, upto):
        while nxt[t] < len(regions[t]) and regions[t][nxt[t]][1] <= upto:
            i = nxt[t]
            s, e, name, n_bins, maxp = regions[t][i]
            tg = acc[t].pop(i, {})
            n1 = len(tg)
            n2 = n2ct = n_exp = 0
            by = collections.Counter()
            sub = {g: [0, 0, 0] for g in ("dbp", "seqtf")}
            for p, ex in tg.items():
                n_exp += len(ex)
                k = len(ex)
                nct = len(set(ex.values()))
                hits = [g for g, ok in (("dbp", tdbp[p]), ("seqtf", tcls[p] == "Sequence-specific TF")) if ok]
                for g in hits:
                    sub[g][0] += 1
                if k >= 2:
                    n2 += 1
                    by[tcls[p]] += 1
                    for g in hits:
                        sub[g][1] += 1
                    if nct >= 2:
                        n2ct += 1
                        for g in hits:
                            sub[g][2] += 1
                if t in fp:
                    fp[t].write(f"{name}\t{p}\t{tcls[p]}\t{int(tdbp[p])}\t{k}\t{nct}\n")
            fo[t].write("\t".join(map(str, [chrom, s, e, name, n_bins, maxp, n1, n2, n2ct, n_exp]
                                      + [by[c] for c in CLASSES] + sub["dbp"] + sub["seqtf"])) + "\n")
            nxt[t] += 1

    rows = 0
    proc = subprocess.Popen(["tabix", bed, chrom], stdout=subprocess.PIPE, text=True, bufsize=1 << 20)
    last = -1
    for line in proc.stdout:
        f = line.rstrip("\n").split("\t")
        s, e = int(f[1]), int(f[2])
        assert s >= last, "input not start-sorted"
        last = s
        rows += 1
        p = "_".join((f[8] if f[8] != "." else f[7]).split())
        if p not in tcls:
            tcls[p] = cls.get(f[8], "Other/ambiguous") if f[8] != "." else "Non-gene label"
            tdbp[p] = f[8] in dbp
        for t in TIERS:
            flush(t, s)
            reg = regions[t]
            i = bisect.bisect_right(ends[t], s)  # first region with end > s
            while i < len(reg) and reg[i][0] < e:
                acc[t].setdefault(i, {}).setdefault(p, {})[f[3]] = f[13]
                i += 1
    assert proc.wait() == 0, "tabix failed"
    for t in TIERS:
        flush(t, 1 << 62)
        assert nxt[t] == len(regions[t])
        fo[t].close()
    for h in fp.values():
        h.close()
    (parts / f"{chrom}.done.json").write_text(json.dumps(
        dict(chrom=chrom, rows=rows, regions={t: len(regions[t]) for t in TIERS})))


def collect(out_dir, light, n_check=200):
    out = Path(out_dir)
    hdr = ["chrom", "start", "end", "name", "n_bins", "max_proteins", "n_ge1", "n_ge2exp", "n_ge2ct",
           "n_experiments"] + [f"ge2exp_{slug(c)}" for c in CLASSES] \
        + [f"{g}_{k}" for g in ("dbp", "seqtf") for k in ("ge1", "ge2exp", "ge2ct")]
    done = [json.loads(Path(p).read_text()) for p in sorted(glob.glob(str(out / "parts/*.done.json")))]
    summ = dict(chromosomes=len(done), rows=sum(d["rows"] for d in done), tiers={}, qc={})
    top1 = []
    for t in TIERS:
        recs = []
        for p in sorted(glob.glob(str(out / f"parts/{t}.*.regions.tsv"))):
            with open(p) as f:
                recs += [l.rstrip("\n").split("\t") for l in f]
        assert len(recs) == sum(d["regions"][t] for d in done)
        with gzip.open(out / f"{t}.regions.tsv.gz", "wt") as f:
            f.write("\t".join(hdr) + "\n")
            for r in recs:
                f.write("\t".join(r) + "\n")
        bad = sum(int(r[6]) < int(r[5]) for r in recs)
        summ["qc"][f"{t}_n_ge1_lt_max_proteins"] = bad
        col = {h: [int(r[i]) for r in recs] for i, h in enumerate(hdr) if h.startswith(("n_", "ge2exp_", "dbp_", "seqtf_"))}
        summ["tiers"][t] = dict(regions=len(recs), **{
            h: dict(sum=sum(v), median=sorted(v)[len(v) // 2], max=max(v), n_regions_ge1=sum(x >= 1 for x in v))
            for h, v in col.items()})
        summ["qc"][f"{t}_dbp_gt_all"] = sum(int(r[hdr.index(f"dbp_{k}")]) > int(r[hdr.index(n)])
                                            for r in recs for k, n in (("ge1", "n_ge1"), ("ge2exp", "n_ge2exp"),
                                                                       ("ge2ct", "n_ge2ct")))
        if t == "top1":
            top1 = recs
    with gzip.open(out / "top1.pairs.tsv.gz", "wt") as f:
        f.write("name\ttarget\tclass\tis_dbp\tn_experiments\tn_celltypes\n")
        for p in sorted(glob.glob(str(out / "parts/top1.*.pairs.tsv"))):
            with open(p) as g:
                for l in g:
                    f.write(l)
    rng = random.Random(20261030)
    mism = []
    for r in rng.sample(top1, min(n_check, len(top1))):
        res = subprocess.run(["tabix", light, f"{r[0]}:{int(r[1]) + 1}-{r[2]}"], capture_output=True, text=True,
                             check=True).stdout
        n = len({l.split("\t")[3] for l in res.splitlines() if l})
        if n != int(r[6]):
            mism.append([r[3], n, int(r[6])])
    summ["qc"]["light_bed_recount"] = dict(checked=min(n_check, len(top1)), mismatches=len(mism), examples=mism[:10])
    summ["status"] = "PASS" if not mism and not any(v for k, v in summ["qc"].items()
                                                    if k.endswith(("max_proteins", "gt_all"))) else "FAIL"
    (out / "summary.json").write_text(json.dumps(summ, indent=1))
    print(json.dumps(summ["qc"]), summ["status"])


if __name__ == "__main__":
    if sys.argv[1] == "chrom":
        run_chrom(*sys.argv[2:7])
    else:
        collect(sys.argv[2], sys.argv[3], *(int(x) for x in sys.argv[4:5]))
