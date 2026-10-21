#!/usr/bin/env python3
"""Does a caller add information beyond accessibility? Per-TF cross-validated logistic regression.

For each scored TF: 5-fold stratified CV AUROC of  bound ~ access  vs  bound ~ access + caller.
Features are within-TF rank-normalised (scale-free, robust to heavy tails). Gain = AUROC(access+caller) - AUROC(access).
Folds are the same for both models, so the gain is paired.

usage: 05_added_value.py <result_root>
output: <result_root>/eval/added_value_per_tf.tsv, added_value_summary.tsv
"""
import sys

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedKFold

MIN_SITES = 30
BASE = {"chrom", "start", "end", "tf", "strand", "moods_score", "bound", "access"}


def cv_auc(X, y, folds):
    p = np.zeros(len(y))
    for tr, te in folds:
        p[te] = LogisticRegression(max_iter=1000).fit(X[tr], y[tr]).decision_function(X[te])
    return roc_auc_score(y, p)


def main():
    R = sys.argv[1]
    s = pd.read_csv(f"{R}/eval/site_scores.tsv.gz", sep="\t")
    callers = [c for c in s.columns if c not in BASE]
    rows = []
    for tf, g in s.groupby("tf"):
        y = g.bound.values
        if y.sum() < MIN_SITES or (y == 0).sum() < MIN_SITES:
            continue
        rk = lambda v: (pd.Series(v).rank().values / len(v))[:, None]
        a = rk(g.access.values)
        folds = list(StratifiedKFold(5, shuffle=True, random_state=0).split(a, y))
        base = cv_auc(a, y, folds)
        for c in callers:
            both = cv_auc(np.hstack([a, rk(g[c].values)]), y, folds)
            rows.append({"tf": tf, "method": c, "auroc_access_cv": base, "auroc_access_plus_cv": both,
                         "gain": both - base})
    m = pd.DataFrame(rows)
    m.to_csv(f"{R}/eval/added_value_per_tf.tsv", sep="\t", index=False)
    summ = m.groupby("method").agg(
        n_tf=("tf", "size"),
        median_gain=("gain", "median"),
        mean_gain=("gain", "mean"),
        tf_gain_ge_0_01=("gain", lambda x: int((x >= 0.01).sum())),
        tf_gain_ge_0_05=("gain", lambda x: int((x >= 0.05).sum())),
        max_gain=("gain", "max"),
    ).reset_index().sort_values("median_gain", ascending=False)
    summ.to_csv(f"{R}/eval/added_value_summary.tsv", sep="\t", index=False)
    print(summ.to_string(index=False, float_format=lambda x: f"{x:.4f}"))
    for c in callers:
        top = m[m.method == c].nlargest(5, "gain")
        print(c, ", ".join(f"{t}:+{v:.3f}" for t, v in zip(top.tf, top.gain)))


if __name__ == "__main__":
    main()
