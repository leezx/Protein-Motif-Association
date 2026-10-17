"""Step 3b §18: core-set alignment graph (PI 2026-10-17: core-set tiers).

usage: 19_core_graph.py
Core unique motif = any record with evidence v2 tier <= 2 OR >= 2 independent
experiments (17_unique_tiers.unique_meta). Writes unique_core/ in the layout of
unique/ (15_unique_graph.py): graph_nodes_<part>.tsv (core only, isolation
recomputed inside the core), graph_edges_<part>.tsv (s >= 0.65, 0-based indices
into connected core rows), tau_edges_<part>.npz (s >= tau, indices into
graph_nodes rows), plus core_definition.json.
"""
import importlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
ut = importlib.import_module("17_unique_tiers")
R = ut.R
U, C = R / "unique", R / "unique_core"


def main():
    C.mkdir(parents=True, exist_ok=True)
    _, _, meta = ut.unique_meta()
    core = meta.high.fillna(False) | (meta.n_exp.fillna(0) >= 2)
    summ = dict(definition="evidence_v2 tier <= 2 OR n_exp >= 2", parts={})
    for part in ut.PARTS:
        gn = pd.read_csv(U / f"graph_nodes_{part}.tsv", sep="\t")
        keep = core.reindex(gn.unique_id).fillna(False).to_numpy()
        new_row = np.full(len(gn), -1, dtype=np.int64)
        new_row[keep] = np.arange(keep.sum())
        # full-graph edges -> full graph rows -> core rows
        conn_rows = np.flatnonzero(~gn.isolated.to_numpy())
        ge = pd.read_csv(U / f"graph_edges_{part}.tsv", sep="\t")
        a, b = new_row[conn_rows[ge.i.to_numpy()]], new_row[conn_rows[ge.j.to_numpy()]]
        s = ge.s.to_numpy()
        del ge
        k = (a >= 0) & (b >= 0)
        a, b, s = a[k], b[k], s[k]
        cn = gn[keep].reset_index(drop=True)
        deg = np.bincount(a, minlength=len(cn)) + np.bincount(b, minlength=len(cn))
        cn["isolated"] = deg == 0
        cn.to_csv(C / f"graph_nodes_{part}.tsv", sep="\t", index=False)
        conn = np.cumsum(deg > 0) - 1
        pd.DataFrame({"i": conn[a], "j": conn[b], "s": s}).to_csv(C / f"graph_edges_{part}.tsv", sep="\t",
                                                                 index=False, float_format="%.4f")
        z = np.load(U / f"tau_edges_{part}.npz")
        ta, tb = new_row[z["q"]], new_row[z["t"]]
        k = (ta >= 0) & (tb >= 0)
        np.savez_compressed(C / f"tau_edges_{part}.npz", q=ta[k], t=tb[k], s=z["s"][k])
        summ["parts"][part] = dict(unique=len(gn), core=len(cn), core_isolated=int(cn.isolated.sum()),
                                   core_connected=int((~cn.isolated).sum()), edges_s065=int(len(s)),
                                   edges_tau=int(k.sum()))
        print(part, summ["parts"][part], flush=True)
    (C / "core_definition.json").write_text(json.dumps(summ, indent=2) + "\n")


if __name__ == "__main__":
    main()
