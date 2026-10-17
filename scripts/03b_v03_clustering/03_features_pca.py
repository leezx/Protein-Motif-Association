"""Step 3b §5.1-5.2: 8-mer affinity features, balanced PCA basis, projection.

Representation = Step 3 §8.1 (06_kmer_features.affinity: floor 0.01,
log-odds, 32,896 RC-collapsed 8-mers, per-profile centred + L2-normalised).
Per partition:
- basis: <= 50,000 nodes; strata = source family x evidence type of the
  node's majority member; equal caps, unused quota redistributed in
  proportion to the remaining available nodes; seed 20261016. A partition
  with <= 50,000 nodes uses all of them.
- PCA: feature-wise centring on the basis (no per-8-mer scaling, as
  ScaleData do.scale = FALSE), randomized SVD, 51 PCs.
- projection: every node (basis included) = (x - mean) @ V.T -> PC scores.
Features are cached as float16 (row order = nodes_<part>.tsv) for the
medoid step (§6.2). Feature blocks are computed with a process pool.

usage: 03_features_pca.py <n_workers>  (env PMA_MOTIF_PROCESSED, PMA_MOTIF_RESULT)
Outputs (result/step3b_v03/pca/): pca_<part>.tsv.gz, nodes_<part>.tsv,
features_<part>.f16, basis_<part>.tsv, pca_summary.json
"""
import json
import os
import sys
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.utils.extmath import randomized_svd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "03_motif_clustering"))
sys.path.insert(0, str(HERE.parent / "02_motif_import"))
import importlib  # noqa: E402

kf = importlib.import_module("06_kmer_features")
import pma_motif as pm  # noqa: E402

SEED, CAP, NPC, BLOCK = 20261016, 50_000, 51, 4096
LAYER = Path(os.environ["PMA_MOTIF_PROCESSED"]) / "v0.3_raw_layer"
RES = Path(os.environ["PMA_MOTIF_RESULT"]) / "step3b_v03"
OUT = RES / "pca"
CANON = kf.kmer_tables()[0]


def feats(mats):
    return np.vstack([kf.affinity(m, CANON) for m in mats]).astype(np.float32)


def blocks(mats, pool):
    chunks = [mats[i:i + 256] for i in range(0, len(mats), 256)]
    for x in pool.imap(feats, chunks):
        yield x


def balanced_basis(strata, rng):
    """Frozen §5.2: cap CAP / n_strata each; under-full strata give all
    their nodes; the unused quota goes to the other strata in proportion to
    their remaining available nodes (floor, then +1 to the largest
    remainders, ties by stratum name)."""
    n = len(strata)
    if n <= CAP:
        return np.arange(n)
    names = sorted(set(strata))
    groups = {s: rng.permutation(np.flatnonzero(strata == s)) for s in names}
    size = np.array([len(groups[s]) for s in names])
    take = np.minimum(size, CAP // len(names))
    rem = size - take
    unused = CAP - take.sum()
    extra = np.floor(unused * rem / rem.sum()).astype(int)
    short = unused - extra.sum()
    frac = unused * rem / rem.sum() - extra
    for i in sorted(range(len(names)), key=lambda i: (-frac[i], names[i]))[:short]:
        extra[i] += 1
    take = take + np.minimum(extra, rem)
    return np.sort(np.concatenate([groups[s][:k] for s, k in zip(names, take)]))


def main(nw):
    OUT.mkdir(parents=True, exist_ok=True)
    nodes = pd.read_csv(RES / "nodes" / "motif_nodes.tsv", sep="\t")
    md = pd.read_csv(LAYER / "PMA_motif_metadata.tsv", sep="\t", low_memory=False,
                     usecols=["pma_id", "source_db", "evidence_type", "assay_class"])
    x = nodes[~nodes.unclusterable.astype(bool)].merge(md, on="pma_id")
    x["stratum"] = x.source_db + "|" + x.evidence_type.fillna("").where(x.evidence_type.fillna("") != "",
                                                                        x.assay_class.fillna("na"))
    stratum = x.groupby("node_id").stratum.agg(lambda s: s.value_counts().sort_index().idxmax())
    motifs = pm.read_meme(RES / "nodes" / "nodes.meme")
    summ = {}
    with Pool(nw) as pool:
        for part in ("composite", "monomer"):
            sel = [(n, m) for n, p, m in motifs if p == part]
            ids = [n for n, _ in sel]
            mats = [m for _, m in sel]
            st = stratum.reindex(ids).fillna("unknown").to_numpy()
            rng = np.random.default_rng(SEED)
            basis = balanced_basis(st, rng)
            ff = np.lib.format.open_memmap(OUT / f"features_{part}.f16", mode="w+", dtype=np.float16,
                                           shape=(len(ids), len(CANON)))
            i = 0
            for blk in blocks(mats, pool):
                ff[i:i + len(blk)] = blk
                i += len(blk)
            ff.flush()
            B = np.asarray(ff[basis], dtype=np.float32)
            mu = B.mean(0)
            B -= mu
            _, sv, V = randomized_svd(B, n_components=NPC, n_iter=7, random_state=SEED)
            tot = float((B.astype(np.float64) ** 2).sum())
            del B
            pcs = np.empty((len(ids), NPC), dtype=np.float32)
            for a in range(0, len(ids), BLOCK):
                pcs[a:a + BLOCK] = (np.asarray(ff[a:a + BLOCK], dtype=np.float32) - mu) @ V.T
            df = pd.DataFrame(pcs, columns=[f"PC_{k + 1}" for k in range(NPC)])
            df.insert(0, "node_id", ids)
            df.to_csv(OUT / f"pca_{part}.tsv.gz", sep="\t", index=False, float_format="%.6g")
            pd.DataFrame({"node_id": ids, "stratum": st}).to_csv(OUT / f"nodes_{part}.tsv", sep="\t", index=False)
            pd.DataFrame({"node_id": np.array(ids)[basis], "stratum": st[basis]}).to_csv(
                OUT / f"basis_{part}.tsv", sep="\t", index=False)
            summ[part] = dict(nodes=len(ids), basis=int(len(basis)),
                              basis_by_stratum=pd.Series(st[basis]).value_counts().to_dict(),
                              var_explained=(sv ** 2 / tot).round(5).tolist())
            print(part, summ[part]["nodes"], summ[part]["basis"], flush=True)
    (OUT / "pca_summary.json").write_text(json.dumps(summ, indent=1) + "\n")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 32)
