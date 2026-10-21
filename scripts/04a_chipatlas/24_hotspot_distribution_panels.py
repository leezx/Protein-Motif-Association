"""Distribution panels and threshold tables for hotspot / open-region definition (§18), from 23_hotspot_bins.py.

usage: 24_hotspot_distribution_panels.py <bins500.npz> <out_dir> [atac_n=18651] [dnase_n=2086] [atac_ct=N] [dnase_ct=N]
Writes Hotspot_A_protein_distribution.{png,pdf}, Hotspot_B_open_distribution.{png,pdf},
thresholds_<track>.tsv, quantiles.tsv, joint_protein_open.tsv. Light (numpy on ~6 M bins); runs locally.
"""
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

plt.rcParams.update({"font.size": 8, "axes.spines.top": False, "axes.spines.right": False})
BIN = 500
QS = [0.5, 0.75, 0.9, 0.95, 0.99, 0.999]
P_THR = [1, 2, 3, 5, 10, 20, 30, 50, 75, 100, 150, 200, 300, 500, 1000]
F_THR = [0.0005, 0.001, 0.002, 0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.3, 0.5]
C_ATAC, C_DNASE, C_PROT = "#1b7837", "#762a83", "#2166ac"


def tag(ax, letter):
    ax.text(-0.14, 1.05, letter, transform=ax.transAxes, fontsize=12, fontweight="bold", va="bottom")


def save(fig, out, name):
    fig.savefig(out / f"{name}.png", dpi=200, bbox_inches="tight"); fig.savefig(out / f"{name}.pdf", bbox_inches="tight")
    plt.close(fig)


def survival(v):
    """x (sorted unique values) and number of bins with value >= x."""
    u, c = np.unique(v, return_counts=True)
    return u, np.cumsum(c[::-1])[::-1]


def thr_table(v, thrs, n_all, denom=None):
    nz = (v > 0).sum(); rows = []
    for t in thrs:
        k = int((v >= (t * denom if denom else t)).sum()) if denom else int((v >= t).sum())
        rows.append({"threshold": t, **({"threshold_count": int(np.ceil(t * denom))} if denom else {}),
                     "bins": k, "Mb": k * BIN / 1e6, "pct_of_nonzero_bins": 100 * k / nz, "pct_of_genome_bins": 100 * k / n_all})
    return pd.DataFrame(rows)


def main(npz, out, *opts):
    o = dict(a.split("=") for a in opts)
    N = {"atac_experiments": int(o.get("atac_n", 18651)), "dnase_experiments": int(o.get("dnase_n", 2086))}
    out = Path(out); out.mkdir(parents=True, exist_ok=True)
    z = np.load(npz); n_all = int(z["n_bins"].sum())
    P = z["proteins"].astype(np.int64)
    A = z["atac_experiments"] / N["atac_experiments"]; D = z["dnase_experiments"] / N["dnase_experiments"]

    # tables
    q = []
    for name, v in (("proteins", P), ("atac_experiments", z["atac_experiments"]), ("dnase_experiments", z["dnase_experiments"]),
                    ("atac_celltypes", z["atac_celltypes"]), ("dnase_celltypes", z["dnase_celltypes"])):
        nz = v[v > 0]
        q.append({"track": name, "bins_nonzero": int(nz.size), "pct_genome_bins": 100 * nz.size / n_all, "max": int(nz.max()),
                  "mean_nonzero": float(nz.mean()), **{f"q{int(x * 1000) / 10:g}": float(np.quantile(nz, x)) for x in QS}})
    pd.DataFrame(q).to_csv(out / "quantiles.tsv", sep="\t", index=False, float_format="%.4g")
    thr_table(P, P_THR, n_all).to_csv(out / "thresholds_proteins.tsv", sep="\t", index=False, float_format="%.4g")
    for name, v in (("atac_experiments", z["atac_experiments"]), ("dnase_experiments", z["dnase_experiments"])):
        thr_table(v, F_THR, n_all, denom=N[name]).rename(columns={"threshold": "threshold_fraction"}).to_csv(
            out / f"thresholds_{name}.tsv", sep="\t", index=False, float_format="%.4g")
    edges = np.array([1, 2, 3, 5, 10, 20, 30, 50, 75, 100, 150, 200, 300, 500, 2000])
    pb = np.digitize(P, edges) - 1  # -1 = no protein
    jr = []
    for i in range(-1, len(edges) - 1):
        m = pb == i
        lab = "0" if i < 0 else (f"{edges[i]}" if edges[i + 1] - edges[i] == 1 else f"{edges[i]}-{edges[i + 1] - 1}")
        jr.append({"proteins": lab, "bins": int(m.sum()),
                   **{f"{k}_{s}": float(f(v[m])) for k, v in (("atac_frac", A), ("dnase_frac", D))
                      for s, f in (("q25", lambda x: np.quantile(x, .25)), ("median", np.median), ("q75", lambda x: np.quantile(x, .75)),
                                   ("pct_open", lambda x: 100 * (x > 0).mean()))}})
    J = pd.DataFrame(jr); J.to_csv(out / "joint_protein_open.tsv", sep="\t", index=False, float_format="%.4g")

    # Figure A: proteins
    nzP = P[P > 0]
    fig, ax = plt.subplots(1, 3, figsize=(13, 3.8))
    lb = np.unique(np.round(np.logspace(0, np.log10(nzP.max() + 1), 60)).astype(int))
    ax[0].hist(nzP, bins=lb, color=C_PROT); ax[0].set_xscale("log"); ax[0].set_yscale("log")
    ax[0].set_xlabel("distinct proteins in bin (max over bin)"); ax[0].set_ylabel("500 bp bins")
    ax[0].set_title(f"{nzP.size:,} bound bins ({100 * nzP.size / n_all:.1f}% of genome bins)"); tag(ax[0], "A")
    x, s = survival(nzP)
    ax[1].plot(x, s, color=C_PROT); ax[1].set_xscale("log"); ax[1].set_yscale("log")
    ax[1].set_xlabel("threshold: ≥ x proteins"); ax[1].set_ylabel("bins passing"); tag(ax[1], "B")
    sec = ax[1].secondary_yaxis("right", functions=(lambda b: b * BIN / 1e6, lambda m: m * 1e6 / BIN)); sec.set_ylabel("Mb")
    for qq, ls in ((0.9, ":"), (0.95, "--"), (0.99, "-."), (0.999, "-")):
        t = np.quantile(nzP, qq); ax[1].axvline(t, color="grey", ls=ls, lw=0.8)
        ax[1].text(t, s[0], f" {qq * 100:g}%: ≥{t:.0f}", rotation=90, va="top", fontsize=6)
    ax[1].set_title("survival: bins with ≥ x proteins")
    T = thr_table(P, P_THR, n_all)
    ax[2].axis("off"); tag(ax[2], "C")
    tb = ax[2].table(cellText=[[f"≥{r.threshold}", f"{r.bins:,}", f"{r.Mb:.1f}", f"{r.pct_of_nonzero_bins:.2f}"] for r in T.itertuples()],
                     colLabels=["proteins", "bins", "Mb", "% of bound"], loc="center", cellLoc="right")
    tb.auto_set_font_size(False); tb.set_fontsize(7); tb.scale(1, 1.15)
    ax[2].set_title("candidate hotspot thresholds")
    fig.suptitle("ChIP-Atlas hg38 protein ChIP-seq (histone excluded), blacklist-masked: distinct proteins per 500 bp bin", fontsize=9)
    fig.tight_layout(); save(fig, out, "Hotspot_A_protein_distribution")

    # Figure B: open chromatin
    fig, ax = plt.subplots(2, 2, figsize=(11, 8)); ax = ax.ravel()
    for v, n, c, lab in ((z["atac_experiments"], N["atac_experiments"], C_ATAC, "ATAC"), (z["dnase_experiments"], N["dnase_experiments"], C_DNASE, "DNase")):
        nz = v[v > 0]
        lb = np.unique(np.round(np.logspace(0, np.log10(nz.max() + 1), 60)).astype(int))
        ax[0].hist(nz / n, bins=lb / n, histtype="step", color=c, lw=1.2, label=f"{lab}: {nz.size:,} bins ({100 * nz.size / n_all:.1f}% genome), n={n:,} expts")
        x, s = survival(nz); ax[1].plot(x / n, s, color=c, label=lab)
        for qq, ls in ((0.9, ":"), (0.99, "-.")):
            ax[1].axvline(np.quantile(nz, qq) / n, color=c, ls=ls, lw=0.7)
    for a in ax[:2]:
        a.set_xscale("log"); a.set_yscale("log"); a.set_xlabel("fraction of experiments with a peak in the bin")
    ax[0].set_ylabel("500 bp bins"); ax[0].legend(fontsize=6, frameon=False); ax[0].set_title("open bins: experiment fraction"); tag(ax[0], "A")
    ax[1].set_ylabel("bins passing (≥ x)"); ax[1].legend(fontsize=7, frameon=False)
    ax[1].set_title("survival (dotted 90%, dash-dot 99% of open bins)"); tag(ax[1], "B")
    sec = ax[1].secondary_yaxis("right", functions=(lambda b: b * BIN / 1e6, lambda m: m * 1e6 / BIN)); sec.set_ylabel("Mb")
    xi = np.arange(len(J))
    for k, c, lab, dx in (("atac_frac", C_ATAC, "ATAC", -0.12), ("dnase_frac", C_DNASE, "DNase", 0.12)):
        ax[2].errorbar(xi + dx, J[f"{k}_median"], yerr=[J[f"{k}_median"] - J[f"{k}_q25"], J[f"{k}_q75"] - J[f"{k}_median"]],
                       fmt="o", ms=3, color=c, lw=0.8, label=f"{lab} median (IQR)")
        ax[3].plot(xi, J[f"{k}_pct_open"], "o-", ms=3, color=c, label=lab)
    for a in ax[2:]:
        a.set_xticks(xi); a.set_xticklabels(J.proteins, rotation=45, ha="right"); a.set_xlabel("distinct proteins in bin")
    ax[2].set_yscale("symlog", linthresh=1e-3); ax[2].set_ylim(0, 1.5); ax[2].set_ylabel("fraction of experiments open"); ax[2].legend(fontsize=7, frameon=False)
    ax[2].set_title("openness vs protein count"); tag(ax[2], "C")
    ax[3].set_ylabel("% of bins with ≥1 open experiment"); ax[3].legend(fontsize=7, frameon=False)
    ax[3].set_title("any openness vs protein count"); tag(ax[3], "D")
    fig.suptitle("ATAC-seq / DNase-seq evidence per 500 bp bin (filtered experiments, blacklist-masked)", fontsize=9)
    fig.tight_layout(); save(fig, out, "Hotspot_B_open_distribution")


if __name__ == "__main__":
    main(*sys.argv[1:])
