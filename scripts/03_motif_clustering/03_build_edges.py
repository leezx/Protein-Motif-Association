"""Step 3 §3.2: TOMTOM kept rows (q < 0.05) -> eligible edges with similarity s.

Directed eligibility = statistical_match_v0.1 (BH q < 0.01, overlap >= 60 %
of the shorter motif). An undirected edge needs both directions eligible.
s_dir = clip(mean column Pearson at TOMTOM's alignment, 0, 1) * overlap /
max(L_A, L_B); s = min(s_AB, s_BA). The overlap recomputed from TOMTOM's
offset must equal TOMTOM's Overlap (asserted for every row).

Within a partition -> edges.tsv.gz; composite <-> monomer pairs eligible in
either direction -> contains_component.tsv.gz (never equivalence edges).
"""
import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "02_motif_import"))
import pma_motif as pm  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parent))
import pma_cluster as pc  # noqa: E402

R = Path(os.environ["PMA_MOTIF_RESULT"]) / "step3_motif_clustering"
TT = R / "tomtom"
BLOCK = 2_000_000


def load_nodes():
    motifs = pm.read_meme(R / "nodes" / "nodes.meme")
    ids = [m[0] for m in motifs]
    part = [m[1] for m in motifs]
    U = [pc.column_unit(m[2]) for m in motifs]
    L = np.array([len(u) for u in U])
    start = np.r_[0, np.cumsum(L)[:-1]]
    fwd = np.vstack(U)
    rc = np.vstack([u[::-1, ::-1] for u in U])
    return ids, np.array(part), L, start, fwd, rc


def directed_r(df, L, start, fwd, rc):
    """Vectorised pc.directed_r over rows with integer node indices qi, ti."""
    lq, lt, off = L[df.qi], L[df.ti], df.offset.to_numpy()
    i0 = np.maximum(0, -off)
    i1 = np.minimum(lq, lt - off)
    n = np.maximum(i1 - i0, 0)
    assert (n == df.overlap.to_numpy()).all(), "recomputed overlap != TOMTOM Overlap"
    minus = df.orientation.to_numpy() == "-"
    rep = np.repeat(np.arange(len(df)), n)
    k = np.arange(n.sum()) - np.repeat(np.cumsum(n) - n, n)
    qcol = start[df.qi.to_numpy()][rep] + i0[rep] + k
    tcol = start[df.ti.to_numpy()][rep] + i0[rep] + off[rep] + k
    dots = np.where(minus[rep], (fwd[qcol] * rc[tcol]).sum(1), (fwd[qcol] * fwd[tcol]).sum(1))
    return np.bincount(rep, weights=dots, minlength=len(df)) / np.maximum(n, 1)


def main():
    ids, part, L, start, fwd, rc = load_nodes()
    idx = {n: i for i, n in enumerate(ids)}
    files = sorted((TT / "kept").glob("chunk_*.tsv.gz"))
    assert files, "no TOMTOM chunks"
    rows, n_rows = [], 0
    for f in files:
        t = pd.read_csv(f, sep="\t", dtype={"query": str, "target": str, "orientation": str})
        n_rows += len(t)
        t = t[t["query"] != t["target"]]
        t["qi"] = t["query"].map(idx).to_numpy()
        t["ti"] = t["target"].map(idx).to_numpy()
        assert t.qi.notna().all() and t.ti.notna().all(), f"{f}: unknown node"
        t["qi"], t["ti"] = t.qi.astype(int), t.ti.astype(int)
        elig = (t.q < pc.V01_Q) & (t.overlap >= pc.V01_OV * np.minimum(L[t.qi], L[t.ti]))
        rows.append(t[elig][["qi", "ti", "offset", "q", "overlap", "orientation"]])
    d = pd.concat(rows, ignore_index=True)
    r = np.concatenate([directed_r(d.iloc[i:i + BLOCK], L, start, fwd, rc) for i in range(0, len(d), BLOCK)])
    d["s_dir"] = np.clip(r, 0, 1) * d.overlap.to_numpy() / np.maximum(L[d.qi], L[d.ti])
    d["a"], d["b"] = np.minimum(d.qi, d.ti), np.maximum(d.qi, d.ti)
    d["fwd"] = d.qi == d.a
    ab = d[d.fwd].set_index(["a", "b"])[["s_dir", "q"]]
    ba = d[~d.fwd].set_index(["a", "b"])[["s_dir", "q"]]
    assert ab.index.is_unique and ba.index.is_unique
    both = ab.join(ba, how="inner", lsuffix="_ab", rsuffix="_ba").reset_index()
    either = ab.join(ba, how="outer", lsuffix="_ab", rsuffix="_ba").reset_index()
    both["s"] = np.minimum(both.s_dir_ab, both.s_dir_ba)
    same = part[both.a] == part[both.b]
    out = both[same].assign(a=lambda x: np.array(ids)[x.a], b=lambda x: np.array(ids)[x.b],
                            partition=part[both[same].a])
    out = out[["a", "b", "s", "s_dir_ab", "s_dir_ba", "q_ab", "q_ba", "partition"]].sort_values(["a", "b"])
    out.to_csv(R / "edges.tsv.gz", sep="\t", index=False, float_format="%.6g")
    # directed v0.1-eligible pairs (coverage in §8.3); q < 0.01 rows are a
    # subset of the kept q < 0.05 rows, so this set is exact
    pd.DataFrame({"query": np.array(ids)[d.qi], "target": np.array(ids)[d.ti], "s_dir": d.s_dir}).to_csv(
        R / "eligible_directed.tsv.gz", sep="\t", index=False, float_format="%.6g")
    cross = either[part[either.a] != part[either.b]].copy()
    comp_is_a = part[cross.a] == "composite"
    cc = pd.DataFrame({"composite_node": np.where(comp_is_a, np.array(ids)[cross.a], np.array(ids)[cross.b]),
                       "monomer_node": np.where(comp_is_a, np.array(ids)[cross.b], np.array(ids)[cross.a]),
                       "s_dir_ab": cross.s_dir_ab, "s_dir_ba": cross.s_dir_ba})
    cc.sort_values(["composite_node", "monomer_node"]).to_csv(R / "contains_component.tsv.gz", sep="\t",
                                                              index=False, float_format="%.6g")
    s = dict(chunks=len(files), kept_rows_q05=int(n_rows), eligible_directed=int(len(d)),
             pairs_either=int(len(either)), pairs_both=int(len(both)),
             edges_within_partition=int(len(out)), edges_by_partition=out.partition.value_counts().to_dict(),
             contains_component_pairs=int(len(cc)),
             s_quantiles={str(k): round(v, 3) for k, v in out.s.quantile([.05, .25, .5, .75, .95]).items()})
    (R / "edges_summary.json").write_text(json.dumps(s, indent=2) + "\n")
    print(json.dumps(s, indent=2))


if __name__ == "__main__":
    main()
