"""Step 4a §11: region -> protein -> experiment -> cellular context, from the v1 records (no summary inference).

usage: 07_region_query.py <occupancy.bed.gz> <class_annotation.csv> <chr:start-end> [out_prefix]
Coordinates are 1-based inclusive (IGV). Writes (or prints) two tables:
  <out_prefix>.proteins.tsv     target, class, n_experiments, n_peaks, n_cell_types, n_tissues, top cell types,
                                experiments; sorted by n_experiments
  <out_prefix>.experiments.tsv  one row per overlapping peak: experiment, target, class, cell type, tissue,
                                biosample type, antibody, GSM, peak coordinates, qscore, QC flags
and a summary line: distinct experiments, proteins, TFs, CAPs, cell types, and the share of the top 5 proteins.
"""
import collections
import csv
import subprocess
import sys

CAP = {"Histone writer/eraser", "Histone reader", "Chromatin remodeler", "Architectural/cohesin"}


def main(bed, ann, region, prefix=None):
    cls = {r["gene"]: r["Class"] for r in csv.DictReader(open(ann, encoding="utf-8-sig"))}
    rows = subprocess.run(["tabix", bed, region.replace(",", "")], capture_output=True, text=True,
                          check=True).stdout.splitlines()
    by_t = collections.defaultdict(lambda: dict(exps=set(), peaks=0, cells=collections.Counter(), tissues=set()))
    peaks = []
    for r in rows:
        f = r.split("\t")
        t = "_".join((f[8] if f[8] != "." else f[7]).split())
        k = cls.get(f[8], "Non-gene label") if f[8] != "." else "Non-gene label"
        d = by_t[t]; d["class"] = k
        if f[3] not in d["exps"]:
            d["cells"][f[13]] += 1
        d["exps"].add(f[3]); d["peaks"] += 1; d["tissues"].add(f[14])
        peaks.append([f[3], t, k, f[13], f[14], f[15], f[18] if f[18] != "." else f[19], f[21],
                      f"{f[0]}:{int(f[1]) + 1}-{f[2]}", f[6], f[23]])
    order = sorted(by_t, key=lambda t: (-len(by_t[t]["exps"]), t))
    prot = [["target", "class", "n_experiments", "n_peaks", "n_cell_types", "n_tissues", "top_cell_types",
             "experiments"]]
    for t in order:
        d = by_t[t]
        prot.append([t, d["class"], len(d["exps"]), d["peaks"], len(d["cells"]), len(d["tissues"]),
                     ";".join(f"{c}({n})" for c, n in d["cells"].most_common(5)), ",".join(sorted(d["exps"]))])
    exps_hdr = ["experiment", "target", "class", "cell_type", "tissue", "biosample_type", "antibody", "gsm",
                "peak", "qscore", "qc_flags"]
    n_exp = len({p[0] for p in peaks}); top5 = sum(len(by_t[t]["exps"]) for t in order[:5])
    summary = (f"{region}\texperiments={n_exp}\tproteins={len(by_t)}"
               f"\ttf={sum(1 for t in by_t if by_t[t]['class'] == 'Sequence-specific TF')}"
               f"\tcap={sum(1 for t in by_t if by_t[t]['class'] in CAP)}"
               f"\tcell_types={len({p[3] for p in peaks})}"
               f"\ttop5_protein_share_of_experiments={top5 / max(n_exp, 1):.3f}")
    if prefix:
        for name, tab in (("proteins", prot), ("experiments", [exps_hdr] + peaks)):
            with open(f"{prefix}.{name}.tsv", "w") as w:
                w.write(f"# {summary}\n")
                for r in tab:
                    w.write("\t".join(map(str, r)) + "\n")
    else:
        for r in prot[:30]:
            print("\t".join(map(str, r[:7])))
    print(summary)


if __name__ == "__main__":
    main(*sys.argv[1:5])
