"""Step 3b §15b: exact all-vs-all alignment similarity s within a partition.

usage: 12_exact_neighbors.py <part> <chunk> <n_chunks>
For every query row i in this chunk (i % n_chunks == chunk): s against every
node j > i (upper triangle, so each unordered pair is computed exactly once);
keep EVERY pair with s >= 0.65 (no truncation). Writes
align/exact_<part>_<chunk>of<n>.npz (q, t, s; q < t) plus the number of pairs
computed (completeness assertion). Node index = row of pca/nodes_<part>.tsv.
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

S_EDGE = 0.65
R = Path(os.environ["PMA_MOTIF_RESULT"]) / "step3b_v03"


def main(part, chunk, nch):
    ids = pd.read_csv(R / "pca" / f"nodes_{part}.tsv", sep="\t").node_id.to_numpy()
    mats = {n: m for n, p, m in pm.read_meme(R / "nodes" / "nodes.meme") if p == part}
    Z, Zrc, st, ln = pa.pack([mats[n] for n in ids])
    allt = np.arange(len(ids), dtype=np.int64)
    qs, ts, ss = [], [], []
    mine = allt[allt % nch == chunk]
    computed = 0
    for k, i in enumerate(mine):
        tgt = allt[i + 1:]
        if len(tgt) == 0:
            continue
        s = pa.s_one_vs_all(Z, Zrc, st, ln, np.int64(i), tgt)
        computed += len(tgt)
        hi = np.flatnonzero(s >= S_EDGE)
        qs.append(np.full(len(hi), i, dtype=np.int32))
        ts.append(tgt[hi].astype(np.int32))
        ss.append(s[hi].astype(np.float32))
        if k % 5000 == 0:
            print(part, chunk, k, len(mine), flush=True)
    np.savez_compressed(R / "align" / f"exact_{part}_{chunk}of{nch}.npz", q=np.concatenate(qs), t=np.concatenate(ts),
                        s=np.concatenate(ss), computed=np.int64(computed))
    print("done", part, chunk, flush=True)


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]), int(sys.argv[3]))
