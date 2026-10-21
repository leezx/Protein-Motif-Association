"""Collect SEA results of the hotspot motif enrichment (§18.3) into ranked tables and panels.

usage: 28_motif_enrichment_collect.py <prep_dir> <out_dir>
Reads <prep_dir>/manifest.tsv, runs/<comparison>/{sea_<library>.tsv,task.json,hb.info.txt}, motifs/motif_annotation.tsv.
Writes:
  all_results.tsv.gz              every motif × comparison × library (log10 p/q, enrichment ratio, TP%, FP%)
  ranked/<comparison>.<library>.tsv  motifs ranked by q-value, then enrichment ratio
  top_motifs.tsv                  top 20 per comparison × library
  runs_summary.tsv                target/control sizes and HOMER frequency difference per comparison
  Motif_A_<library>.png/.pdf      log2 enrichment heatmap of the top motifs across comparisons
Ranking is by significance (BH q over the library, recomputed from SEA p-values because SEA ran per motif chunk);
significant = q < 0.05 and enrichment ratio > 1.
"""
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

LN10 = np.log(10)
ORDER = ["G_protein_top20", "G_protein_top10", "G_protein_top5", "G_protein_top1",
         "A_protein_top20", "A_protein_top10", "A_protein_top5", "A_protein_top1",
         "S_protein_top5_promoter", "S_protein_top5_distal",
         "G_open_top20", "G_open_top10", "G_open_top5", "G_open_top1",
         "S_open_top5_promoter", "S_open_top5_distal"]
plt.rcParams.update({"font.size": 7})


def label(r):
    if r.library.startswith("JASPAR"):
        return str(r.label)
    fam = "" if pd.isna(r.tf_family) else str(r.tf_family)
    tfs = "" if pd.isna(r.candidate_tfs) or r.candidate_tfs == "NA" else ",".join(t.split(":")[0] for t in str(r.candidate_tfs).split(";")[:2])
    return f"{r.motif_id} {fam}{' (' + tfs + ')' if tfs else ''}"


def main(prep, out):
    prep, out = Path(prep), Path(out); (out / "ranked").mkdir(parents=True, exist_ok=True)
    man = pd.read_csv(prep / "manifest.tsv", sep="\t")
    ann = pd.read_csv(prep / "motifs" / "motif_annotation.tsv", sep="\t", dtype=str)
    rows, runs = [], []
    for c in man.comparison:
        d = prep / "runs" / c
        t = json.loads((d / "task.json").read_text()) if (d / "task.json").exists() else {"comparison": c, "status": "missing"}
        runs.append(t)
        if t.get("status") != "ok":
            continue
        for f in sorted(d.glob("sea_*.tsv")):
            lib = f.stem[4:]
            s = pd.read_csv(f, sep="\t", comment="#")
            s = s[s["ID"].notna()]
            s = s.assign(comparison=c, library=lib)
            rows.append(s)
    pd.DataFrame(runs).to_csv(out / "runs_summary.tsv", sep="\t", index=False)
    A = pd.concat(rows, ignore_index=True)
    A = A.rename(columns={"ID": "motif_id", "TP%": "TP_pct", "FP%": "FP_pct"})
    # SEA ran per motif chunk: recompute E (p × motifs in library) and BH q over the whole library, in log10.
    A["log10_p"] = A.LOG_PVALUE / LN10
    parts = []
    for _, g in A.groupby(["comparison", "library"], sort=False):
        g = g.sort_values("log10_p"); m = len(g); r = np.arange(1, m + 1)
        g = g.assign(log10_E=g.log10_p + np.log10(m),
                     log10_q=np.minimum(np.minimum.accumulate((g.log10_p + np.log10(m) - np.log10(r)).to_numpy()[::-1])[::-1], 0))
        parts.append(g)
    A = pd.concat(parts, ignore_index=True)
    A = A.merge(ann, on=["library", "motif_id"], how="left")
    A["motif_label"] = [label(r) for r in A.itertuples()]
    A["significant"] = (A.log10_q < np.log10(0.05)) & (A.ENR_RATIO > 1)
    A = A.sort_values(["comparison", "library", "log10_q", "ENR_RATIO"], ascending=[True, True, True, False])
    A["rank"] = A.groupby(["comparison", "library"]).cumcount() + 1
    cols = ["comparison", "library", "rank", "motif_id", "motif_label", "tf_family", "candidate_tfs", "annotation_status",
            "CONSENSUS", "TP", "TP_pct", "FP", "FP_pct", "ENR_RATIO", "log10_p", "log10_q", "log10_E", "significant"]
    A[cols].to_csv(out / "all_results.tsv.gz", sep="\t", index=False, float_format="%.4g")
    for (c, lib), g in A.groupby(["comparison", "library"]):
        g[cols].to_csv(out / "ranked" / f"{c}.{lib}.tsv", sep="\t", index=False, float_format="%.4g")
    A[A["rank"] <= 20][cols].to_csv(out / "top_motifs.tsv", sep="\t", index=False, float_format="%.4g")
    sig = A.groupby(["comparison", "library"]).agg(tested=("motif_id", "size"), significant=("significant", "sum")).reset_index()
    sig.to_csv(out / "significant_counts.tsv", sep="\t", index=False)

    # heatmaps: union of the top 8 motifs of each comparison (by q), log2 enrichment ratio, dot = not significant
    comps = [c for c in ORDER if c in set(A.comparison)]
    for lib, g in A.groupby("library"):
        top = g[(g["rank"] <= 8) & g.significant].drop_duplicates("motif_id").motif_id
        top = list(dict.fromkeys(top))
        if not top:
            continue
        M = g[g.motif_id.isin(top)].pivot_table(index="motif_id", columns="comparison", values="ENR_RATIO").reindex(columns=comps)
        S = g[g.motif_id.isin(top)].pivot_table(index="motif_id", columns="comparison", values="significant", aggfunc="max").reindex(columns=comps)
        L = np.log2(M.astype(float))
        order = L.mean(axis=1).sort_values(ascending=False).index
        L, S = L.loc[order], S.loc[order]
        labs = g.drop_duplicates("motif_id").set_index("motif_id").motif_label.reindex(order)
        fig, ax = plt.subplots(figsize=(0.42 * len(comps) + 4.5, 0.16 * len(order) + 1.8))
        v = np.nanmax(np.abs(L.values)); im = ax.imshow(L.values, aspect="auto", cmap="RdBu_r", vmin=-v, vmax=v)
        for i in range(L.shape[0]):
            for j in range(L.shape[1]):
                if S.values[i, j] is not True and S.values[i, j] != 1:
                    ax.text(j, i, "·", ha="center", va="center", fontsize=6, color="grey")
        ax.set_xticks(range(len(comps))); ax.set_xticklabels(comps, rotation=60, ha="right")
        ax.set_yticks(range(len(order))); ax.set_yticklabels([str(x)[:60] for x in labs], fontsize=5.5)
        cb = fig.colorbar(im, ax=ax, fraction=0.03); cb.set_label("log2 enrichment ratio (SEA)")
        ax.set_title(f"{lib}: top motifs per comparison (· = not significant, q ≥ 0.05)\n"
                     "G = GC/k-mer-matched genome control; A = + accessibility-matched; S = promoter / distal strata", fontsize=7)
        fig.tight_layout()
        fig.savefig(out / f"Motif_A_{lib}.png", dpi=200, bbox_inches="tight"); fig.savefig(out / f"Motif_A_{lib}.pdf", bbox_inches="tight")
        plt.close(fig)
    print(sig.pivot(index="comparison", columns="library", values="significant").reindex(comps).to_string())


if __name__ == "__main__":
    main(*sys.argv[1:])
