"""Batch-matched cell-type comparison: same target, same ENCODE lab, HepG2 vs K562, at hotspot bins.

usage: 36_matched_celltype.py <occupancy.bed.gz> <experiments.tsv.gz> <class_annotation.csv> <bins500.npz>
                              <bins_annotation.npz> <out_dir>

Matched set: experiments whose title/attributes mark them as ENCODE (ENCODE|ENCSR|ENCLB|ENCBS), grouped by
(target, lab from the 'lab' attribute); a (target, lab) is kept when it has experiments in both 'Hep G2' and 'K-562'.
For each kept (target, lab) m and 500 bp bin b (grid of 23_hotspot_bins.py): n_c = experiments of m in cell c,
k_c = those with >= 1 peak overlapping b. Experiment pairs counted only when at least one has a peak:
  within  c:  C(k_c, 2) / (C(n_c, 2) - C(n_c - k_c, 2))          (n_c >= 2, k_c >= 1)
  between:    k_H k_K / (n_H n_K - (n_H - k_H)(n_K - k_K))       (k_H + k_K >= 1)
Unit = (b, m) with between defined and >= 1 within defined; within = mean of its defined cells. Reported as the
mean over units (unit) and as sum agree / sum pairs (pooled), by bin group (top1, b5, b20, low; top1 split by
PLS / pELS / dELS), target group (DBP = lambert2018_TF; cofactor; other) and condition: all bins, or bins active in
both cells (>= A matched targets with a peak in each cell; A = 5 and 10). If between ~ within, the cross-cell-type
difference seen with unmatched data was batch; if between << within, composition truly differs between the cells.
Also per target (top1, active in both, A = 5): within, between, presence in each cell. Writes matched_agreement.tsv,
matched_targets.tsv, matched_set.tsv, summary.json.
"""
import collections
import csv
import gzip
import json
import re
import subprocess
import sys
from pathlib import Path

import numpy as np

BIN = 500
CELLS = ("Hep G2", "K-562")
COFACTOR = {"Transcription machinery", "Histone writer/eraser", "Histone reader", "Chromatin remodeler",
            "Architectural/cohesin"}
CCRE = ["PLS", "pELS", "dELS", "CA-H3K4me3", "CA-CTCF", "CA-TF", "TF", "CA", "none"]


def c2(x):
    return x * (x - 1) / 2


def main(bed, exps, ann_csv, npz, ann_npz, out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    by = collections.defaultdict(list)
    with gzip.open(exps, "rt") as f:
        for r in csv.DictReader(f, delimiter="\t"):
            if r["cell_type"] not in CELLS or not re.search(r"ENCODE|ENCSR|ENCLB|ENCBS", r["title"] + r["attributes_raw"]):
                continue
            t = "_".join((r["antigen_hgnc_symbol"] if r["antigen_hgnc_symbol"] != "." else r["antigen_raw"]).split())
            try:
                lab = dict(json.loads(r["attributes_raw"])).get("lab", "?")
            except (ValueError, TypeError):
                lab = "?"
            by[(t, lab, r["cell_type"])].append(r["experiment_id"])
    sets = sorted({(t, l) for (t, l, c) in by if c == CELLS[0] and (t, l, CELLS[1]) in by})
    exp_ix = {}
    for t, l in sets:
        for c in CELLS:
            for e in by[(t, l, c)]:
                exp_ix[e] = len(exp_ix)
    dbp, cls = set(), {}
    with open(ann_csv) as f:
        for r in csv.DictReader(f):
            cls[r["gene"]] = r["Class"]
            if "lambert2018_TF" in r["functional_tags"].split(";"):
                dbp.add(r["gene"])
    grp = {t: ("DBP" if t in dbp else "cofactor" if cls.get(t) in COFACTOR else "other") for t, _ in sets}
    with open(out / "matched_set.tsv", "w") as f:
        f.write("target\tlab\tgroup\tn_hepg2\tn_k562\texperiments_hepg2\texperiments_k562\n")
        for t, l in sets:
            f.write(f"{t}\t{l}\t{grp[t]}\t{len(by[(t, l, CELLS[0])])}\t{len(by[(t, l, CELLS[1])])}\t"
                    f"{','.join(by[(t, l, CELLS[0])])}\t{','.join(by[(t, l, CELLS[1])])}\n")

    z, a = np.load(npz), np.load(ann_npz)
    chroms, offs = list(z["chrom"]), dict(zip(list(z["chrom"]), z["offset"].astype(np.int64)))
    nbin = dict(zip(list(z["chrom"]), z["n_bins"].astype(np.int64)))
    N = int(z["n_bins"].sum())
    hit_bins = [set() for _ in exp_ix]
    rows = 0
    for c in chroms:
        proc = subprocess.Popen(["tabix", bed, c], stdout=subprocess.PIPE, text=True, bufsize=1 << 20)
        o, n = offs[c], nbin[c]
        for line in proc.stdout:
            f = line.split("\t", 4)
            i = exp_ix.get(f[3])
            if i is None:
                continue
            rows += 1
            s, e = int(f[1]), int(f[2])
            hit_bins[i].update(o + k for k in range(s // BIN, min((e - 1) // BIN, n - 1) + 1))
        assert proc.wait() == 0
        print(c, rows, flush=True)

    P = z["proteins"].astype(np.int32)
    keep = a["keep"]
    cc = a["ccre"]
    groups = {"top1": keep & (P >= 244), "b5": keep & (P >= 70) & (P < 244), "b20": keep & (P >= 17) & (P < 36),
              "low": keep & (P >= 1) & (P < 17)}
    for k in ("PLS", "pELS", "dELS"):
        groups[f"top1_{k}"] = groups["top1"] & (cc == CCRE.index(k))
    K = {}
    for t, l in sets:
        for ci, c in enumerate(CELLS):
            k = np.zeros(N, np.int8)
            for e in by[(t, l, c)]:
                hb = np.fromiter(hit_bins[exp_ix[e]], np.int64)
                k[hb] += 1
            K[(t, l, ci)] = k
    act = [sum((K[(t, l, ci)] > 0).astype(np.int16) for t, l in sets) for ci in range(2)]

    acc = collections.defaultdict(lambda: np.zeros(7))  # sum within, sum between, units, w agree, w pairs, b agree, b pairs
    per_t = {}
    for t, l in sets:
        nH, nK = len(by[(t, l, CELLS[0])]), len(by[(t, l, CELLS[1])])
        kH, kK = K[(t, l, 0)].astype(np.float64), K[(t, l, 1)].astype(np.float64)
        wH_den = c2(nH) - c2(nH - kH)
        wK_den = c2(nK) - c2(nK - kK)
        wH = np.where((nH >= 2) & (wH_den > 0), c2(kH) / np.where(wH_den > 0, wH_den, 1), np.nan)
        wK = np.where((nK >= 2) & (wK_den > 0), c2(kK) / np.where(wK_den > 0, wK_den, 1), np.nan)
        b_den = nH * nK - (nH - kH) * (nK - kK)
        btw = np.where(b_den > 0, kH * kK / np.where(b_den > 0, b_den, 1), np.nan)
        with np.errstate(all="ignore"):
            w = np.nanmean(np.vstack([wH, wK]), axis=0)
        unit = ~np.isnan(btw) & ~np.isnan(w)
        for gname, gm in groups.items():
            for cond, cm in (("all", gm), ("active_both_5", gm & (act[0] >= 5) & (act[1] >= 5)),
                             ("active_both_10", gm & (act[0] >= 10) & (act[1] >= 10))):
                m = cm & unit
                v = acc[(gname, grp[t], cond)]
                v[0] += w[m].sum(); v[1] += btw[m].sum(); v[2] += m.sum()
                mm = cm & ~np.isnan(btw)
                v[3] += (c2(kH[mm & (nH >= 2)]).sum() + c2(kK[mm & (nK >= 2)]).sum())
                v[4] += (np.nan_to_num(wH_den[mm & (nH >= 2)]).sum() + np.nan_to_num(wK_den[mm & (nK >= 2)]).sum())
                v[5] += (kH[mm] * kK[mm]).sum(); v[6] += b_den[mm].sum()
        m = groups["top1"] & (act[0] >= 5) & (act[1] >= 5)
        nb = int(m.sum())
        per_t[(t, l)] = dict(units=int((m & unit).sum()), within=float(np.nanmean(w[m & unit])) if (m & unit).any() else
                             float("nan"), between=float(np.nanmean(btw[m & unit])) if (m & unit).any() else float("nan"),
                             pct_hepg2=float((kH[m] > 0).mean()), pct_k562=float((kK[m] > 0).mean()),
                             pct_both=float(((kH[m] > 0) & (kK[m] > 0)).mean()), bins=nb)
    with open(out / "matched_agreement.tsv", "w") as f:
        f.write("bins\ttarget_group\tcondition\tunits\twithin_unit\tbetween_unit\tratio_unit\twithin_pooled\t"
                "between_pooled\tratio_pooled\n")
        for (g, tg, cond), v in sorted(acc.items()):
            if v[2] == 0:
                continue
            wu, bu = v[0] / v[2], v[1] / v[2]
            wp, bp = v[3] / v[4], v[5] / v[6]
            f.write(f"{g}\t{tg}\t{cond}\t{int(v[2])}\t{wu:.4f}\t{bu:.4f}\t{bu / wu:.3f}\t{wp:.4f}\t{bp:.4f}\t{bp / wp:.3f}\n")
    with open(out / "matched_targets.tsv", "w") as f:
        f.write("target\tlab\tgroup\tbins\tunits\twithin\tbetween\tratio\tpct_hepg2\tpct_k562\tpct_both\n")
        for (t, l), d in sorted(per_t.items(), key=lambda x: x[1]["between"] / x[1]["within"]
                                if x[1]["within"] else 0):
            r = d["between"] / d["within"] if d["within"] else float("nan")
            f.write(f"{t}\t{l}\t{grp[t]}\t{d['bins']}\t{d['units']}\t{d['within']:.4f}\t{d['between']:.4f}\t{r:.3f}\t"
                    f"{d['pct_hepg2']:.4f}\t{d['pct_k562']:.4f}\t{d['pct_both']:.4f}\n")
    summ = dict(target_lab_sets=len(sets), targets=len({t for t, _ in sets}), experiments=len(exp_ix), peak_rows=rows,
                groups={g: collections.Counter(grp[t] for t, _ in sets)[g] for g in ("DBP", "cofactor", "other")},
                top1_bins=int(groups["top1"].sum()),
                top1_active_both_5=int((groups["top1"] & (act[0] >= 5) & (act[1] >= 5)).sum()),
                top1_active_both_10=int((groups["top1"] & (act[0] >= 10) & (act[1] >= 10)).sum()))
    (out / "summary.json").write_text(json.dumps(summ, indent=1))
    print(json.dumps(summ, indent=1))
    print(open(out / "matched_agreement.tsv").read())


if __name__ == "__main__":
    main(*sys.argv[1:7])
