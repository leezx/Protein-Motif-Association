"""Step 2: descriptive benchmark tables under the §8 fallback.

No curator labels exist, so no threshold is selected and
statistical_match_v0.2 is not issued. Reported: statistical_match_v0.1
(per-query BH q < 0.01 over the whole raw layer, overlap >= 60 % of the
shorter motif) on P-high, P-provisional and N-challenge, by length bin,
with 95 % bootstrap CIs grouped by TFClass family (1,000 resamples).
The N-challenge link rate is not a false-positive rate.
"""
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd

B = Path(os.environ["PMA_MOTIF_RESULT"]) / "step2_motif_import" / "benchmark"
REPO = Path(__file__).resolve().parents[2] / "results" / "02_motif_import"
Q, OV, NBOOT, SEED = 0.01, 0.6, 1000, 20261015
LABELS = ["<=8", "9-10", "11-12", "13-15", ">15"]


def load():
    p = pd.read_csv(B / "benchmark_pairs.tsv", sep="\t", keep_default_na=False)
    t = pd.read_csv(B / "tomtom" / "benchmark_tomtom.tsv", sep="\t")
    d = t.set_index(["Query_ID", "Target_ID"])
    # every pair must have both directed rows
    for a, b in (("m1", "m2"), ("m2", "m1")):
        idx = pd.MultiIndex.from_arrays([p[a], p[b]])
        missing = ~idx.isin(d.index)
        assert not missing.any(), f"{missing.sum()} pairs lack {a}->{b} rows"
        r = d.loc[idx]
        tag = "12" if a == "m1" else "21"
        p[f"p_{tag}"] = r["p-value"].to_numpy()
        p[f"q_{tag}"] = r["bh_q"].to_numpy()
        p[f"ov_{tag}"] = r["Overlap"].to_numpy() / np.minimum(p.len1, p.len2)
    p["group"] = [";".join(sorted(x)) for x in zip(p.family1, p.family2)]
    return p


def match(p, q=Q, ov=OV):
    m12 = (p.q_12 < q) & (p.ov_12 >= ov)
    m21 = (p.q_21 < q) & (p.ov_21 >= ov)
    return m12 | m21, m12 & m21


def boot_ci(x, groups, rng):
    """Grouped bootstrap CI of the mean of a 0/1 vector."""
    x = np.asarray(x, float)
    if len(x) == 0:
        return np.nan, np.nan
    g = pd.Series(x).groupby(np.asarray(groups))
    sums, ns = g.sum().to_numpy(), g.size().to_numpy()
    k = len(sums)
    stats = []
    for _ in range(NBOOT):
        i = rng.integers(0, k, k)
        stats.append(sums[i].sum() / ns[i].sum())
    return tuple(np.percentile(stats, [2.5, 97.5]))


def rate_table(p, by, rng):
    rows = []
    for key, g in p.groupby(by, sort=False):
        key = key if isinstance(key, tuple) else (key,)
        e, b = match(g)
        for rule, v in (("either", e), ("both", b)):
            lo, hi = boot_ci(v, g.group, rng)
            rows.append(dict(zip(by, key), rule=rule, n=len(g), n_match=int(v.sum()),
                             rate=round(v.mean(), 3), ci_lo=round(lo, 3), ci_hi=round(hi, 3)))
    return pd.DataFrame(rows)


def main():
    rng = np.random.default_rng(SEED)
    p = load()
    p["len_bin"] = pd.Categorical(p.len_bin, LABELS, ordered=True)
    p = p.sort_values(["set", "len_bin", "pair_id"])
    t_bin = rate_table(p, ["set", "len_bin"], rng)
    t_all = rate_table(p, ["set"], rng)
    t_part = rate_table(p[p.set != "P_high"], ["set", "partition"], rng)
    t_src = rate_table(p[p.set == "P_provisional"].assign(
        src_pair=[" vs ".join(sorted(x)) for x in zip(p.src1, p.src2)]), ["src_pair"], rng)
    # cutoff sensitivity (descriptive only; not threshold selection)
    grid = []
    for q in (0.001, 0.01, 0.05):
        for s, g in p.groupby("set"):
            e, b = match(g, q=q)
            grid.append(dict(set=s, q=q, either=round(e.mean(), 3), both=round(b.mean(), 3), n=len(g)))
    pd.concat([t_all.assign(len_bin="all"), t_bin]).to_csv(REPO / "benchmark_v01_by_length.tsv",
                                                          sep="\t", index=False)
    t_part.to_csv(REPO / "benchmark_v01_by_partition.tsv", sep="\t", index=False)
    t_src.to_csv(REPO / "benchmark_v01_pprov_by_source_pair.tsv", sep="\t", index=False)
    pd.DataFrame(grid).to_csv(REPO / "benchmark_v01_q_grid.tsv", sep="\t", index=False)
    ph = p[p.set == "P_high"].copy()
    ph["match_either"], ph["match_both"] = match(ph)
    ph[["pair_id", "m1", "m2", "tf1", "len1", "len2", "len_bin", "p_12", "q_12", "ov_12",
        "p_21", "q_21", "ov_21", "match_either", "match_both"]].to_csv(
        REPO / "benchmark_p_high_pairs.tsv", sep="\t", index=False)
    s = dict(n_pairs=p.groupby("set").size().to_dict(),
             v01_either=t_all[t_all.rule == "either"].set_index("set").rate.to_dict(),
             v01_both=t_all[t_all.rule == "both"].set_index("set").rate.to_dict(),
             statistical_match_v02="not issued (no curator labels; design §8 fallback)")
    (REPO / "benchmark_summary.json").write_text(json.dumps(s, indent=2) + "\n")
    print(pd.concat([t_all.assign(len_bin="all"), t_bin]).to_string(index=False))
    print(json.dumps(s, indent=2))


if __name__ == "__main__":
    main()
