"""Step 3b §15b: exact all-vs-all alignment similarity s within a partition.

usage: 12_exact_neighbors.py <part> <chunk> <n_chunks>
For every query node in this chunk (query rows i with i % n_chunks == chunk):
s against every node of the partition; keep the top-200 partners with s >= 0.65
and every partner with s >= 0.825 (capped at 2,000, highest s first).
Writes align/exact_<part>_<chunk>of<n>.npz (q, t, s) and the per-query counts of
partners at s >= 0.65 and >= 0.825 (uncapped). Node index = row of pca/nodes_<part>.tsv.
"""
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "02_motif_import"))
import pma_align as pa  # noqa: E402
import pma_motif as pm  # noqa: E402

TOP, S_EDGE, TAU, CAP = 200, 0.65, 0.825, 2000
R = Path(os.environ["PMA_MOTIF_RESULT"]) / "step3b_v03"


def main(part, chunk, nch):
    ids = pd.read_csv(R / "pca" / f"nodes_{part}.tsv", sep="\t").node_id.to_numpy()
    mats = {n: m for n, p, m in pm.read_meme(R / "nodes" / "nodes.meme") if p == part}
    Z, Zrc, st, ln = pa.pack([mats[n] for n in ids])
    allt = np.arange(len(ids), dtype=np.int64)
    qs, ts, ss, n65, n825 = [], [], [], [], []
    mine = allt[allt % nch == chunk]
    for k, i in enumerate(mine):
        s = pa.s_one_vs_all(Z, Zrc, st, ln, np.int64(i), allt)
        s[i] = -1.0
        hi = np.flatnonzero(s >= S_EDGE)
        n65.append(len(hi))
        n825.append(int((s[hi] >= TAU).sum()))
        o = hi[np.argsort(-s[hi], kind="stable")]
        keep = np.union1d(o[:TOP], o[s[o] >= TAU][:CAP])
        qs.append(np.full(len(keep), i, dtype=np.int32))
        ts.append(keep.astype(np.int32))
        ss.append(s[keep].astype(np.float32))
        if k % 5000 == 0:
            print(part, chunk, k, len(mine), flush=True)
    np.savez_compressed(R / "align" / f"exact_{part}_{chunk}of{nch}.npz", q=np.concatenate(qs), t=np.concatenate(ts),
                        s=np.concatenate(ss), query=mine.astype(np.int32), n65=np.array(n65), n825=np.array(n825))
    print("done", part, chunk, flush=True)


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]), int(sys.argv[3]))
