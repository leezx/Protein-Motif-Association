#!/usr/bin/env python3
"""Put the per-cell-line results side by side.

For each method and cell line: median AUROC, median access-stratified AUROC, median CV gain over access,
TFs with gain >= 0.01. For TFs scored in both cell lines: Spearman of per-TF CV gain between cell lines.

usage: 06_compare_cells.py <out.tsv> <name>=<result_root> [<name>=<result_root> ...]
"""
import sys

import pandas as pd
from scipy.stats import spearmanr


def main():
    out = sys.argv[1]
    cells = dict(a.split("=", 1) for a in sys.argv[2:])
    rows, gains = [], {}
    for cell, R in cells.items():
        s = pd.read_csv(f"{R}/eval/summary.tsv", sep="\t").set_index("method")
        a = pd.read_csv(f"{R}/eval/added_value_summary.tsv", sep="\t").set_index("method")
        gains[cell] = pd.read_csv(f"{R}/eval/added_value_per_tf.tsv", sep="\t")
        for m in s.index:
            rows.append({"cell": cell, "method": m, "n_tf": int(s.loc[m, "n_tf"]),
                         "median_auroc": s.loc[m, "median_auroc"],
                         "median_auroc_access_strat": s.loc[m, "median_auroc_access_strat"],
                         "median_cv_gain": a.loc[m, "median_gain"] if m in a.index else float("nan"),
                         "tf_gain_ge_0_01": int(a.loc[m, "tf_gain_ge_0_01"]) if m in a.index else 0})
    df = pd.DataFrame(rows)
    df.to_csv(out, sep="\t", index=False, float_format="%.4f")
    print(df.pivot(index="method", columns="cell", values=["median_auroc", "median_auroc_access_strat", "median_cv_gain"])
          .round(3).to_string())
    names = list(cells)
    if len(names) == 2:
        g = [gains[n].set_index(["tf", "method"]).gain for n in names]
        both = pd.concat(g, axis=1, keys=names, join="inner").reset_index()
        print(f"\nTFs scored in both: {both.tf.nunique()}")
        for m, h in both.groupby("method"):
            rho = spearmanr(h[names[0]], h[names[1]]).statistic
            top = h.assign(mn=h[names].min(axis=1)).nlargest(3, "mn")
            print(f"{m:14s} rho={rho:+.2f}  gain>=0.01 in both: {int(((h[names] >= 0.01).all(axis=1)).sum())}  "
                  + ", ".join(f"{t}({x:+.3f}/{y:+.3f})" for t, x, y in zip(top.tf, top[names[0]], top[names[1]])))


if __name__ == "__main__":
    main()
