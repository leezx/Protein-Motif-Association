"""Figure 1E–G panels for the three-level co-occupancy clustering (§13–§17), drawn from finished result tables.

usage: 22_figure1_clustering_panels.py <occupancy_chipatlas/result dir> <out_dir>
Writes Figure1E_protein_cooccupancy.png, Figure1F_experiment_clustering.png, Figure1G_region_classes.png (+ .pdf).
No recomputation: every number comes from cooccupancy_v1, experiment_clustering_v1, region_classes_v1,
validation_v1_1 and validation_v1_2.
"""
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

VARIANTS = [("b250_k05", "250 bp, 5%"), ("b500_k05", "500 bp, 5%"), ("b1000_k05", "1000 bp, 5%"),
            ("b500_k025", "500 bp, 2.5%"), ("b500_k10", "500 bp, 10%")]
NAMED_SHORT = {"CPX-5989": "Cohesin (STAG1)", "CPX-5991": "Cohesin (STAG2)", "CPX-4206": "GBAF", "CPX-6267": "NELF",
               "CPX-3323": "SIN3A", "CPX-2327": "PRC2.1", "CPX-880": "MBD2/NuRD", "CPX-922": "MBD3/NuRD",
               "CPX-9065": "CoREST", "CPX-915": "TFIID", "CPX-3227": "Mediator (3/13)"}
plt.rcParams.update({"font.size": 8, "axes.spines.top": False, "axes.spines.right": False})


def tag(ax, letter):
    ax.text(-0.12, 1.06, letter, transform=ax.transAxes, fontsize=12, fontweight="bold", va="bottom")


def image(ax, path, title):
    ax.imshow(plt.imread(path)); ax.axis("off"); ax.set_title(title, fontsize=8)


def save(fig, out, name):
    fig.savefig(out / f"{name}.png", dpi=200, bbox_inches="tight"); fig.savefig(out / f"{name}.pdf", bbox_inches="tight")
    plt.close(fig)


def fig_protein(R, out):
    S = {k: json.loads((R / "validation_v1_2/sensitivity" / k / "summary.json").read_text()) for k, _ in VARIANTS}
    base = S["b500_k05"]
    fig = plt.figure(figsize=(15, 10))
    gs = fig.add_gridspec(2, 3, wspace=0.5, hspace=0.4)
    ax = fig.add_subplot(gs[0, 0]); image(ax, R / "cooccupancy_v1/all/heatmap_jaccard.png",
                                          "Jaccard co-occupancy, 808 proteins (all contexts)"); tag(ax, "A")
    # B: AUROC forest
    ax = fig.add_subplot(gs[0, 1]); tag(ax, "B")
    rows = [(lab, S[k]["pair_metrics_nohot"]) for k, lab in VARIANTS]
    mu = base["matched_universe"]
    rows += [("K-562 (183 shared)", mu["K-562"]), ("Hep G2 (183 shared)", mu["Hep G2"])]
    for i, (lab, m) in enumerate(rows):
        lo, hi = m["auroc_ci95"]
        c = "#1f4e9b" if i < len(VARIANTS) else "#d1495b"
        ax.errorbar(m["auroc"], i, xerr=[[m["auroc"] - lo], [hi - m["auroc"]]], fmt="o", color=c, capsize=2)
        ax.text(0.93, i, f"PR-AUC {m['pr_auc']:.3f}\n(base {m['pr_auc_baseline']:.4f})", va="center", fontsize=6)
    ax.axvline(0.5, color="grey", ls=":"); ax.set_yticks(range(len(rows))); ax.set_yticklabels([r[0] for r in rows])
    ax.invert_yaxis(); ax.set_xlim(0.45, 1.05); ax.set_xlabel("AUROC, same-complex vs other pairs (protein-resampling 95% CI)")
    ax.set_title("Known-complex discrimination is stable across bin size and threshold")
    # C: HOT / null decomposition
    ax = fig.add_subplot(gs[0, 2]); tag(ax, "C")
    d = base["hot_null_decomposition"]
    keys = [("p_allbins_size", "All bins\nsize-matched"), ("p_nohot_size", "Non-HOT\nsize-matched"),
            ("p_nohot_breadth", "Non-HOT\nbreadth-matched")]
    x = np.arange(len(keys))
    a1 = [d[k]["fdr05_all"] for k, _ in keys]; a2 = [d[k]["distinct_fdr05_minrep"] for k, _ in keys]
    ax.bar(x - 0.2, a1, 0.4, label=f"all entries (n = {base['complexes']})", color="#7a9cc6")
    ax.bar(x + 0.2, a2, 0.4, label=f"distinct member sets (n = {d['p_nohot_breadth']['distinct_sets']})", color="#1f4e9b")
    for xi, v1, v2 in zip(x, a1, a2):
        ax.text(xi - 0.2, v1 + 2, v1, ha="center", fontsize=7); ax.text(xi + 0.2, v2 + 2, v2, ha="center", fontsize=7)
    ax.set_xticks(x); ax.set_xticklabels([k[1] for k in keys]); ax.set_ylabel("Complexes with BH-FDR ≤ 0.05")
    ax.legend(frameon=False, fontsize=7); ax.set_title("Complex recovery: HOT removal vs null model")
    # D: named complexes across variants
    ax = fig.add_subplot(gs[1, 0]); tag(ax, "D")
    names = list(NAMED_SHORT)
    M = np.array([[-np.log10(next(v["fdr"] for kk, v in S[k]["named"].items() if kk.split()[0] == c)) for k, _ in VARIANTS]
                  for c in names])
    im = ax.imshow(M, cmap="Blues", vmin=0, vmax=3, aspect="auto")
    for i in range(M.shape[0]):
        for j in range(M.shape[1]):
            f = 10 ** -M[i, j]
            ax.text(j, i, f"{f:.3f}", ha="center", va="center", fontsize=6, color="white" if M[i, j] > 2 else "black",
                    fontweight="bold" if f > 0.05 else "normal")
    ax.set_yticks(range(len(names))); ax.set_yticklabels([NAMED_SHORT[c] for c in names])
    ax.set_xticks(range(len(VARIANTS))); ax.set_xticklabels([v[1] for v in VARIANTS], rotation=30, ha="right")
    fig.colorbar(im, ax=ax, orientation="horizontal", fraction=0.05, pad=0.22, label="−log10 breadth-matched FDR")
    ax.set_title("Physical complexes (FDR; bold = FDR > 0.05)")
    # E: pair tiers
    ax = fig.add_subplot(gs[1, 1]); tag(ax, "E")
    t = pd.read_csv(R / "validation_v1_2/study/pair_tiers.tsv", sep="\t")
    t["cat"] = np.where((t.tier == "tier1_high") & t.context_replicated, "Tier 1 + same-context replication",
                        t.tier.map({"tier1_high": "Tier 1 (cross-study + LOSO)", "tier2_moderate": "Tier 2 (LOSO-sensitive)",
                                    "insufficient_coverage": "Insufficient coverage",
                                    "study_dependent": "Study-dependent"}))
    cats = ["Tier 1 + same-context replication", "Tier 1 (cross-study + LOSO)", "Tier 2 (LOSO-sensitive)",
            "Insufficient coverage", "Study-dependent"]
    cols = ["#1b5e20", "#66bb6a", "#c5e1a5", "#bdbdbd", "#e57373"]
    kinds = [("complex_portal", "Complex\nPortal pairs"), ("top_non_complex", "Top-300\nnon-complex")]
    for i, (k, lab) in enumerate(kinds):
        sub = t[t.kind == k]; left = 0
        for c, col in zip(cats, cols):
            n = int((sub.cat == c).sum())
            ax.barh(i, n, left=left, color=col, label=c if i == 0 else None)
            if n >= 15:
                ax.text(left + n / 2, i, n, ha="center", va="center", fontsize=7)
            left += n
    ax.set_yticks([0, 1]); ax.set_yticklabels([k[1] for k in kinds]); ax.invert_yaxis(); ax.set_xlabel("Protein pairs")
    ax.legend(frameon=False, fontsize=6.5, loc="upper center", bbox_to_anchor=(0.5, -0.18), ncol=2)
    ax.set_title("Study-level robustness of candidate pairs")
    # F: study influence
    ax = fig.add_subplot(gs[1, 2]); tag(ax, "F")
    inf = pd.read_csv(R / "validation_v1_2/study/protein_study_influence.tsv", sep="\t").dropna(subset=["max_influence"])
    jit = np.random.default_rng(0).uniform(-0.08, 0.08, len(inf))
    ax.scatter(inf.n_studies * np.exp(jit), inf.max_influence, s=6, alpha=0.4, color="#6c757d")
    for g, c in (("ESR1", "#d1495b"), ("HMGA1", "#e9a03b"), ("PPARA", "#e9a03b"), ("CTCF", "#1f4e9b"), ("SMARCA4", "#2a9d8f")):
        r = inf[inf.protein == g].iloc[0]
        off = {"HMGA1": (-10, -14), "PPARA": (6, -4)}.get(g, (4, 3))
        ax.scatter(r.n_studies, r.max_influence, s=25, color=c); ax.annotate(f"{g} ({r.top_study})", (r.n_studies, r.max_influence),
                                                                            fontsize=6.5, xytext=off, textcoords="offset points")
    ax.axhline(0.5, color="grey", ls=":"); ax.set_xscale("log"); ax.set_xlabel("Studies per protein")
    ax.set_ylabel("Max study influence\n1 − Jaccard(all, without one study)")
    ax.set_title("Single studies can dominate a protein's occupancy")
    fig.suptitle("Figure 1E. DBP co-occupancy recovers known complexes; candidate pairs require study-level validation",
                 fontsize=10, y=0.98)
    save(fig, out, "Figure1E_protein_cooccupancy")


def fig_experiment(R, out):
    e = pd.read_csv(R / "validation_v1_2/experiment/experiment_confounder_sensitivity.tsv", sep="\t")
    V = ["V0_raw", "V1_drop_comp1", "V2_same_peak_decile", "V3_other_study", "V4_same_decile_other_study"]
    VL = ["V0", "V1", "V2", "V3", "V4"]
    fig = plt.figure(figsize=(15, 5.2))
    gs = fig.add_gridspec(1, 3, width_ratios=[1.5, 1, 1.2], wspace=0.3)
    ax = fig.add_subplot(gs[0, 0]); image(ax, R / "experiment_clustering_v1/tsne.png", "t-SNE of 29,900 ChIP experiments"); tag(ax, "A")
    ax = fig.add_subplot(gs[0, 1]); tag(ax, "B")
    a = e[e.view == "all"]
    for f, c in (("protein", "#1f4e9b"), ("cell_type", "#d1495b"), ("protein_class", "#7a9cc6"), ("tissue", "#e9a03b")):
        y = [a[(a.variant == v) & (a.factor == f)].kappa.iloc[0] for v in V]
        ax.plot(range(5), y, "o-", color=c, label=f.replace("_", " ")); ax.text(4.1, y[-1], f"{y[-1]:.2f}", va="center", fontsize=7)
    ax.set_xticks(range(5)); ax.set_xticklabels(VL); ax.set_ylim(0, 0.7)
    ax.set_xlabel("V0 raw · V1 −SVD comp 1 · V2 same peak decile ·\nV3 other study · V4 = V2 + V3", fontsize=7); ax.set_ylabel("κ (conditional expectation)")
    ax.legend(frameon=False, fontsize=7); ax.set_title("10-NN label agreement under neighbour restrictions")
    ax = fig.add_subplot(gs[0, 2]); tag(ax, "C")
    views = [("cell_type=K-562", "protein", "K-562: protein"), ("cell_type=Hep G2", "protein", "Hep G2: protein"),
             ("cell_type=MCF-7", "protein", "MCF-7: protein"), ("protein=CTCF", "cell_type", "CTCF: cell type"),
             ("protein=AR", "cell_type", "AR: cell type"), ("protein=ESR1", "cell_type", "ESR1: cell type"),
             ("protein=FOXA1", "cell_type", "FOXA1: cell type")]
    for i, (vw, f, lab) in enumerate(views):
        g = e[(e.view == vw) & (e.factor == f)]
        k0 = g[g.variant == "V0_raw"].kappa.iloc[0]; r4 = g[g.variant == V[4]].iloc[0]
        col = "#d1495b" if r4.kappa < 0.05 else "#1f4e9b"
        ax.plot([k0, r4.kappa], [i, i], color=col, lw=1.5); ax.scatter([k0], [i], color="white", edgecolor=col, zorder=3)
        ax.scatter([r4.kappa], [i], color=col, zorder=3)
        ax.text(max(k0, r4.kappa) + 0.02, i, f"{k0:.2f} → {r4.kappa:.3f} (p {r4.p_perm:g})", va="center", fontsize=6.5)
    ax.set_yticks(range(len(views))); ax.set_yticklabels([v[2] for v in views]); ax.invert_yaxis()
    ax.set_xlim(-0.02, 0.95); ax.set_xlabel("κ: open = V0 raw, filled = V4 (same depth + other study)")
    ax.set_title("Within-context structure after control (red: κ < 0.05)")
    fig.suptitle("Figure 1F. About half of experiment-level structure reflects study and sequencing depth", fontsize=10, y=1.02)
    save(fig, out, "Figure1F_experiment_clustering")


def fig_region(R, out):
    c = pd.read_csv(R / "region_classes_v1/classes.tsv", sep="\t")
    s = pd.read_csv(R / "validation_v1_2/region/region_stability.tsv", sep="\t")
    summ = json.loads((R / "validation_v1_2/region/summary.json").read_text())
    inf = pd.read_csv(R / "validation_v1_2/study/protein_study_influence.tsv", sep="\t").set_index("protein")
    c["top"] = c.top_proteins.str.split(";").apply(lambda xs: [x.split("(")[0] for x in xs[:3]])
    c["top1_frac"] = c.top_proteins.str.split(";").apply(lambda xs: float(xs[0].split("(")[1].split(",")[0]))
    # single-study-driven: dominant protein (in-class fraction >= 0.9) whose occupancy one study changes >= 0.9
    c["single_study"] = [(f >= 0.9) and (inf.max_influence.get(t[0], 0) or 0) >= 0.9 for f, t in zip(c.top1_frac, c.top)]
    c = c.merge(s, on="cls", suffixes=("", "_s"))
    lab = [f"{r.cls} {'–'.join(r.top)}" for r in c.itertuples()]
    fig = plt.figure(figsize=(15, 7.5))
    gs = fig.add_gridspec(1, 3, width_ratios=[1.1, 1.3, 0.8], wspace=0.75)
    ax = fig.add_subplot(gs[0, 0]); tag(ax, "A")
    pcs = ["Sequence-specific TF", "Architectural/cohesin", "Chromatin remodeler", "Histone reader", "Histone writer/eraser",
           "Transcription machinery"]
    im = ax.imshow(c[pcs].to_numpy(), cmap="magma_r", vmin=0, vmax=0.8, aspect="auto")
    ax.set_yticks(range(len(c))); ax.set_yticklabels(lab, fontsize=6.5)
    ax.set_xticks(range(len(pcs))); ax.set_xticklabels([p.replace(" ", "\n", 1) for p in pcs], rotation=45, ha="right", fontsize=6.5)
    fig.colorbar(im, ax=ax, orientation="horizontal", fraction=0.04, pad=0.16, label="Share of occupancy calls in class")
    ax.set_title(f"20 region classes ({summ['bins']:,} bins with ≥ 3 proteins)")
    ax = fig.add_subplot(gs[0, 1]); tag(ax, "B")
    y = np.arange(len(c))
    for i, r in enumerate(c.itertuples()):
        col = "#e9a03b" if r.single_study else ("#d1495b" if r.median_best_match_reruns < 0.55 else "#1f4e9b")
        ax.plot([r.min_best_match_reruns, 1], [i, i], color="#eeeeee", lw=4, solid_capstyle="butt")
        ax.scatter(r.median_best_match_reruns, i, color=col, zorder=3, s=30)
        ax.scatter(r.min_best_match_reruns, i, color=col, marker="|", s=60, zorder=3)
        if r.single_study:
            ax.text(0.02, i - 0.35, "single-study driven", va="center", fontsize=6, color="#e9a03b")
    ax.set_yticks(y); ax.set_yticklabels(lab, fontsize=6.5); ax.invert_yaxis(); ax.set_xlim(0, 1)
    ax.set_xlabel("Best-match Jaccard across 11 reruns (dot = median, bar = minimum)")
    ax.set_title("Per-class stability (blue stable, red unstable, orange single-study)")
    ax = fig.add_subplot(gs[0, 2]); tag(ax, "C")
    rr = summ["reruns"]; cr = summ["cross_resolution"]
    groups = [("k 20 vs 30", [cr["20v30"]["ari"]]), ("k 10 vs 20", [cr["10v20"]["ari"]]),
              ("5 seeds", [rr[f"seed{i}"]["ari"] for i in range(1, 6)]),
              ("5 × 80 % subsample", [rr[f"sub80_{i}"]["ari"] for i in range(5)]), ("non-HOT", [rr["nohot"]["ari"]])]
    for i, (g, vals) in enumerate(groups):
        ax.scatter(vals, [i] * len(vals), color="#1f4e9b", s=20)
        ax.text(max(vals) + 0.02, i, f"{min(vals):.2f}–{max(vals):.2f}" if len(vals) > 1 else f"{vals[0]:.2f}", va="center", fontsize=7)
    ax.set_yticks(range(len(groups))); ax.set_yticklabels([g[0] for g in groups]); ax.invert_yaxis(); ax.set_xlim(0, 1)
    ax.set_xlabel("ARI vs base k = 20 solution"); ax.set_title("Global stability")
    fig.suptitle("Figure 1G. Region occupancy classes map to known programs; stability and study support vary by class",
                 fontsize=10, y=0.99)
    save(fig, out, "Figure1G_region_classes")
    return c[["cls", "single_study"]]


def main(R, out):
    R = Path(R); out = Path(out); out.mkdir(parents=True, exist_ok=True)
    fig_protein(R, out); fig_experiment(R, out); flags = fig_region(R, out)
    print("single-study classes:", flags[flags.single_study].cls.tolist())


if __name__ == "__main__":
    main(*sys.argv[1:3])
