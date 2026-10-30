"""Genomic annotation of 500 bp bins and protein hotspots, and occupancy after covariate stratification.

usage: 31_hotspot_annotation.py <bins500.npz> <tss.bed> <cCREs.bed> <cpgIslandExt.txt.gz> <genome.fa> <blacklist.bed.gz>
                                <hotspot_dir> <out_dir>

Unit = the 500 bp bins of 23_hotspot_bins.py (P = max distinct proteins in the bin, ATAC / DNase = max experiments open),
so region length plays no role. Per bin:
  tss_dist  |bin centre - nearest refGene TSS|; tss_class promoter (<= 1 kb), proximal (1-5 kb), distal (> 5 kb)
  ccre      highest-priority ENCODE V4 cCRE overlapping the bin (>= 1 bp):
            PLS > pELS > dELS > CA-H3K4me3 > CA-CTCF > CA-TF > TF > CA > none
  cpg       overlaps a UCSC CpG island; gc = G+C / non-N bases; nfrac = N bases / 500; blacklist = overlaps ENCODE v2
Bins with nfrac > 0.5 or blacklist are excluded from every table. Occupancy band (exclusive) from P with the hotspot
thresholds (17, 36, 70, 244): none (0), low (1-16), b20 (17-35), b10 (36-69), b5 (70-243), b1 (>= 244); nested tiers
top1..top20 = P >= threshold.
Stratified occupancy (bins with P > 0): stratum = tss_class x ccre x cpg x GC decile x ATAC-fraction class x DNase-fraction
class (open fraction 0, else decile among open bins). Within each stratum with >= 100 bins, r = mid-rank percentile of
P. Reports R^2 of log1p(P) on stratum means (share of occupancy variance the covariates explain) and how many top1 bins
remain in the top 1% of their own stratum ("residual hotspots"); writes them as BED.
Outputs: bins_annotation.npz, composition_band.tsv, composition_tier.tsv, occupancy_by_class.tsv, residual.tsv,
residual_top1.bed, region_annotation_<tier>.tsv.gz, summary.json.
"""
import gzip
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from pyfaidx import Fasta

BIN = 500
CCRE = ["PLS", "pELS", "dELS", "CA-H3K4me3", "CA-CTCF", "CA-TF", "TF", "CA", "none"]
THR = {"top1": 244, "top5": 70, "top10": 36, "top20": 17}
BANDS = ["none", "low", "b20", "b10", "b5", "b1"]
TSS_CLASS = ["promoter", "proximal", "distal"]


def mark_intervals(arr, offset, n, starts, ends, value, fn):
    """Apply fn(arr[bin], value) to every bin an interval overlaps; intervals are 0-based half-open."""
    b0 = starts // BIN
    b1 = (ends - 1) // BIN
    for k in range(int((b1 - b0).max()) + 1 if len(b0) else 0):
        sel = (b0 + k <= b1) & (b0 + k < n)
        fn(arr, offset + b0[sel] + k, value if np.isscalar(value) else value[sel])


def main(npz, tss_bed, ccre_bed, cpg_gz, fasta, blacklist, hot_dir, out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    z = np.load(npz)
    chroms, offs, nb = list(z["chrom"]), z["offset"], z["n_bins"]
    N = int(nb.sum())
    P = z["proteins"].astype(np.int32)
    atac = z["atac_experiments"] / 18651.0
    dnase = z["dnase_experiments"] / 2086.0

    tss = pd.read_csv(tss_bed, sep="\t", header=None, usecols=[0, 1])
    ccre = pd.read_csv(ccre_bed, sep="\t", header=None, usecols=[0, 1, 2, 5])
    cpg = pd.read_csv(cpg_gz, sep="\t", header=None, usecols=[1, 2, 3])
    cpg.columns = [0, 1, 2]
    bl = pd.read_csv(blacklist, sep="\t", header=None, usecols=[0, 1, 2])
    prio = {c: i for i, c in enumerate(CCRE)}
    ccre["p"] = ccre[5].map(prio).astype(np.int8)

    tss_dist = np.full(N, 2 ** 30, np.int64)
    cc = np.full(N, prio["none"], np.int8)
    cpg_b = np.zeros(N, bool)
    blk = np.zeros(N, bool)
    gc = np.full(N, np.nan, np.float32)
    nfrac = np.ones(N, np.float32)
    fa = Fasta(fasta, as_raw=True, sequence_always_upper=True)
    for c, o, n in zip(chroms, offs, nb):
        o, n = int(o), int(n)
        centre = np.arange(n, dtype=np.int64) * BIN + BIN // 2
        t = np.sort(tss.loc[tss[0] == c, 1].to_numpy(np.int64))
        if len(t):
            i = np.searchsorted(t, centre)
            left = np.abs(centre - t[np.clip(i - 1, 0, len(t) - 1)])
            right = np.abs(t[np.clip(i, 0, len(t) - 1)] - centre)
            tss_dist[o:o + n] = np.minimum(left, right)
        x = ccre[ccre[0] == c]
        mark_intervals(cc, o, n, x[1].to_numpy(np.int64), x[2].to_numpy(np.int64), x["p"].to_numpy(np.int8),
                       np.minimum.at)
        x = cpg[cpg[0] == c]
        mark_intervals(cpg_b, o, n, x[1].to_numpy(np.int64), x[2].to_numpy(np.int64), True,
                       lambda a, i, v: a.__setitem__(i, v))
        x = bl[bl[0] == c]
        mark_intervals(blk, o, n, x[1].to_numpy(np.int64), x[2].to_numpy(np.int64), True,
                       lambda a, i, v: a.__setitem__(i, v))
        seq = np.frombuffer(str(fa[c][:]).encode(), np.uint8)
        assert len(seq) <= n * BIN, f"{c}: fasta longer than bins"
        pad = n * BIN - len(seq)
        seq = np.concatenate([seq, np.full(pad, ord("N"), np.uint8)]).reshape(n, BIN)
        g = ((seq == ord("G")) | (seq == ord("C"))).sum(1)
        nn = (seq == ord("N")).sum(1)
        nfrac[o:o + n] = nn / BIN
        with np.errstate(invalid="ignore", divide="ignore"):
            gc[o:o + n] = np.where(nn < BIN, g / (BIN - nn), np.nan)
        print(c, flush=True)

    tcls = np.where(tss_dist <= 1000, 0, np.where(tss_dist <= 5000, 1, 2)).astype(np.int8)
    keep = (nfrac <= 0.5) & ~blk
    band = np.select([P == 0, P < 17, P < 36, P < 70, P < 244], [0, 1, 2, 3, 4], 5).astype(np.int8)
    np.savez_compressed(out / "bins_annotation.npz", chrom=z["chrom"], offset=offs, n_bins=nb, tss_dist=tss_dist,
                        tss_class=tcls, ccre=cc, cpg=cpg_b, gc=gc, nfrac=nfrac, blacklist=blk, keep=keep)

    df = pd.DataFrame(dict(P=P, band=band, tss=tcls, ccre=cc, cpg=cpg_b, gc=gc, atac=atac, dnase=dnase))[keep]

    def compose(groups):
        rows = []
        for name, m in groups:
            d = df[m]
            r = dict(group=name, bins=len(d), median_P=float(d.P.median()), gc_median=float(d.gc.median()),
                     cpg=float(d.cpg.mean()), atac_open=float((d.atac > 0).mean()),
                     atac_frac_median=float(d.atac.median()), dnase_frac_median=float(d.dnase.median()))
            for i, c in enumerate(TSS_CLASS):
                r[f"tss_{c}"] = float((d.tss == i).mean())
            for i, c in enumerate(CCRE):
                r[f"ccre_{c}"] = float((d.ccre == i).mean())
            rows.append(r)
        return pd.DataFrame(rows)

    compose([("all", np.ones(len(df), bool))] + [(b, (df.band == i).to_numpy()) for i, b in enumerate(BANDS)]) \
        .to_csv(out / "composition_band.tsv", sep="\t", index=False)
    compose([("all", np.ones(len(df), bool)), ("occupied", (df.P > 0).to_numpy())]
            + [(t, (df.P >= v).to_numpy()) for t, v in THR.items()]).to_csv(out / "composition_tier.tsv", sep="\t",
                                                                             index=False)
    rows = []
    for col, labels in (("tss", TSS_CLASS), ("ccre", CCRE)):
        for i, lab in enumerate(labels):
            d = df[df[col] == i]
            q = d.P.quantile([0.5, 0.9, 0.99]).to_list()
            rows.append(dict(variable=col, cls=lab, bins=len(d), occupied=float((d.P > 0).mean()), P_median=q[0],
                             P_q90=q[1], P_q99=q[2], **{f"pct_{t}": float((d.P >= v).mean()) for t, v in THR.items()},
                             share_of_top1=float((d.P >= 244).sum() / (df.P >= 244).sum())))
    pd.DataFrame(rows).to_csv(out / "occupancy_by_class.tsv", sep="\t", index=False)

    # stratified occupancy among occupied bins
    o = df[df.P > 0].copy()
    o["gcd"] = pd.qcut(o.gc, 10, labels=False, duplicates="drop")
    for a in ("atac", "dnase"):
        dec = pd.qcut(o.loc[o[a] > 0, a], 10, labels=False, duplicates="drop") + 1
        o[a + "c"] = 0
        o.loc[o[a] > 0, a + "c"] = dec
    keys = ["tss", "ccre", "cpg", "gcd", "atacc", "dnasec"]
    o["y"] = np.log1p(o.P)
    g = o.groupby(keys, observed=True)
    o["n_s"] = g.y.transform("size")
    o["mu"] = g.y.transform("mean")
    o["r"] = g.P.rank(pct=True, method="average")
    ok = o.n_s >= 100
    ss_tot = float(((o.y - o.y.mean()) ** 2).sum())
    r2 = 1 - float(((o.y - o.mu) ** 2).sum()) / ss_tot
    r2_sub = {}
    for name, ks in (("accessibility", ["atacc", "dnasec"]), ("promoter_ccre", ["tss", "ccre"]),
                     ("gc_cpg", ["gcd", "cpg"])):
        mu = o.groupby(ks, observed=True).y.transform("mean")
        r2_sub[name] = 1 - float(((o.y - mu) ** 2).sum()) / ss_tot
    t1 = o[(o.P >= 244) & ok]
    res = []
    for lab, m in (("top1", o.P >= 244), ("top5", o.P >= 70), ("top20", o.P >= 17), ("occupied", o.P > 0)):
        d = o[m & ok]
        res.append(dict(group=lab, bins=int(m.sum()), bins_in_strata_ge100=len(d),
                        r_median=float(d.r.median()), pct_r_ge99=float((d.r >= 0.99).mean()),
                        pct_r_ge95=float((d.r >= 0.95).mean()), pct_r_lt50=float((d.r < 0.5).mean())))
    pd.DataFrame(res).to_csv(out / "residual.tsv", sep="\t", index=False)
    rt = t1[t1.r >= 0.99]
    cidx = np.searchsorted(offs, rt.index.to_numpy(), side="right") - 1
    with open(out / "residual_top1.bed", "w") as f:
        for i, ci in zip(rt.index.to_numpy(), cidx):
            s = (i - offs[ci]) * BIN
            f.write(f"{chroms[ci]}\t{s}\t{s + BIN}\tP={P[i]};r={rt.r[i]:.4f}\t{int(1000 * rt.r[i])}\t.\n")
    rt_comp = {c: float((rt.ccre == i).mean()) for i, c in enumerate(CCRE)}
    rt_comp.update({f"tss_{c}": float((rt.tss == i).mean()) for i, c in enumerate(TSS_CLASS)})

    # hotspot regions: promoter overlap and best cCRE over their bins
    starts = {c: int(o_) for c, o_ in zip(chroms, offs)}
    for t in THR:
        reg = pd.read_csv(Path(hot_dir) / f"PMA_hotspot_protein_{t}.bed", sep="\t", header=None,
                          usecols=[0, 1, 2, 3, 6, 7])
        reg.columns = ["chrom", "start", "end", "name", "n_bins", "max_proteins"]
        b0 = reg.chrom.map(starts).to_numpy() + reg.start.to_numpy() // BIN
        nbins = ((reg.end - reg.start) // BIN).to_numpy()
        best_c = np.full(len(reg), 99, np.int8)
        best_t = np.full(len(reg), 2 ** 30, np.int64)
        anycpg = np.zeros(len(reg), bool)
        for k in range(int(nbins.max())):
            sel = k < nbins
            idx = b0[sel] + k
            best_c[sel] = np.minimum(best_c[sel], cc[idx])
            best_t[sel] = np.minimum(best_t[sel], tss_dist[idx])
            anycpg[sel] |= cpg_b[idx]
        reg["ccre"] = [CCRE[i] for i in best_c]
        reg["tss_dist"] = best_t
        reg["cpg"] = anycpg.astype(int)
        reg.to_csv(out / f"region_annotation_{t}.tsv.gz", sep="\t", index=False)

    summ = dict(bins_total=N, bins_kept=int(keep.sum()), bins_occupied=int(len(o)),
                strata=int(g.ngroups), strata_ge100=int((g.size() >= 100).sum()),
                bins_in_strata_ge100=float(ok.mean()), r2_all_covariates=r2, r2_single_blocks=r2_sub,
                top1_bins=int((o.P >= 244).sum()), residual_top1_bins=len(rt), residual_top1_composition=rt_comp)
    (out / "summary.json").write_text(json.dumps(summ, indent=1))
    print(json.dumps(summ, indent=1))


if __name__ == "__main__":
    main(*sys.argv[1:9])
