"""Step 3b §16/§17: alignment graph among the unique motifs (t = 0.99 representatives).

usage: 15_unique_graph.py
Per partition: representative nodes of dedup/PMA_unique_motifs_t0.99.tsv; edges
from the exact all-vs-all run (align/exact_*.npz) with both ends representatives
and s >= 0.65 (weight s). Representatives with no such edge are isolated_at_s065
and form a separate, reported set (PI 2026-10-17: tiers are built on connected
motifs). Writes unique/graph_nodes_<part>.tsv (row = graph index; unique_id,
node_id, isolated) and unique/graph_edges_<part>.tsv (i, j, s; connected motifs
only, 0-based indices into the non-isolated rows) for 16_unique_louvain.R, plus
unique/tau_edges_<part>.npz (all representative pairs with s >= 0.825, indices into
graph_nodes rows) for hub coverage. Memory: streams the npz chunks.
"""
import glob
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd

R = Path(os.environ["PMA_MOTIF_RESULT"]) / "step3b_v03"
U = R / "unique"
S_EDGE, TAU = 0.65, 0.825


def main():
    U.mkdir(parents=True, exist_ok=True)
    u = pd.read_csv(R / "dedup" / "PMA_unique_motifs_t0.99.tsv", sep="\t", usecols=["unique_id", "partition",
                                                                                    "representative_node"])
    summ = {}
    for part in ("composite", "monomer"):
        ids = pd.read_csv(R / "pca" / f"nodes_{part}.tsv", sep="\t").node_id.to_numpy()
        idx = {n: i for i, n in enumerate(ids)}
        up = u[u.partition == part].sort_values("unique_id").reset_index(drop=True)
        node_row = np.full(len(ids), -1, dtype=np.int64)
        node_row[[idx[x] for x in up.representative_node]] = np.arange(len(up))
        Q, T, S = [], [], []
        for f in sorted(glob.glob(str(R / "align" / f"exact_{part}_*of*.npz"))):
            z = np.load(f)
            a, b, s = node_row[z["q"]], node_row[z["t"]], z["s"]
            k = (a >= 0) & (b >= 0) & (s >= S_EDGE)
            Q.append(a[k]); T.append(b[k]); S.append(s[k])
        q, t, s = np.concatenate(Q), np.concatenate(T), np.concatenate(S)
        deg = np.bincount(q, minlength=len(up)) + np.bincount(t, minlength=len(up))
        iso = deg == 0
        up["isolated"] = iso
        up.rename(columns={"representative_node": "node_id"}).to_csv(U / f"graph_nodes_{part}.tsv", sep="\t",
                                                                      index=False)
        conn = np.cumsum(~iso) - 1  # row -> index among connected rows
        pd.DataFrame({"i": conn[q], "j": conn[t], "s": s}).to_csv(U / f"graph_edges_{part}.tsv", sep="\t",
                                                                   index=False, float_format="%.4f")
        hi = s >= TAU
        np.savez_compressed(U / f"tau_edges_{part}.npz", q=q[hi], t=t[hi], s=s[hi])
        summ[part] = dict(unique=len(up), isolated=int(iso.sum()), connected=int((~iso).sum()),
                          edges_s065=int(len(q)), edges_tau=int(hi.sum()))
        print(part, summ[part], flush=True)
    (U / "graph_summary.json").write_text(json.dumps(summ, indent=2) + "\n")


if __name__ == "__main__":
    main()
