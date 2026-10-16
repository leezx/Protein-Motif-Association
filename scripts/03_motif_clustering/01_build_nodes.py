"""Step 3 §3.0: raw motifs -> exact-matrix nodes (orientation-free).

Node key = min(sha1(m), sha1(revcomp(m))) of the matrix as written in
PMA_motifs_raw.meme, so reverse-complement exact duplicates share a node
(F24; the Step 2 normalized_matrix_hash is orientation-specific). The
node matrix is the canonical orientation; each motif records whether it
is fwd or rc relative to it.

Outputs ($PMA_MOTIF_RESULT/step3_motif_clustering/nodes/):
  motif_nodes.tsv  pma_id, node_id, node_orientation, partition, unclusterable
  nodes.meme       one canonical matrix per clusterable node
  node_summary.json
"""
import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "02_motif_import"))
import pma_motif as pm  # noqa: E402

LAYER = os.environ.get("PMA_RAW_LAYER", "v0.2.1")
PROC = Path(os.environ["PMA_MOTIF_PROCESSED"]) / f"{LAYER}_raw_layer"
OUT = Path(os.environ["PMA_MOTIF_RESULT"]) / "step3_motif_clustering" / "nodes"


def node_key(m):
    """(key, orientation of m relative to the canonical node matrix)."""
    f, r = pm.sha1(m), pm.sha1(np.ascontiguousarray(pm.revcomp(m)))
    return (f, "fwd") if f <= r else (r, "rc")


def build(motifs, md):
    rows, canon = [], {}
    for mid, _, m in motifs:
        k, o = node_key(m)
        nid = "PMN_" + k[:12]
        if nid in canon:
            assert canon[nid][0] == k, f"node id prefix collision {nid}"
        else:
            canon[nid] = (k, m if o == "fwd" else np.ascontiguousarray(pm.revcomp(m)))
        rows.append((mid, nid, o))
    nodes = pd.DataFrame(rows, columns=["pma_id", "node_id", "node_orientation"])
    meta = md.set_index("pma_id").loc[nodes.pma_id]
    nodes["is_composite"] = meta.is_composite.astype(str).eq("True").to_numpy()
    nodes["short_lt5"] = meta.qc_flags.str.contains("short_lt5").to_numpy()
    g = nodes.groupby("node_id")
    comp = g.is_composite.agg(["all", "any"])
    # §3.0: composite partition only when every member is composite; a node
    # mixing composite and monomer records is put in the monomer partition
    # and counted (the matrix is identical, so the pattern is the same).
    part = np.where(comp["all"], "composite", "monomer")
    nodes["partition"] = nodes.node_id.map(dict(zip(comp.index, part)))
    nodes["unclusterable"] = nodes.node_id.map(g.short_lt5.all())
    assert (g.short_lt5.nunique() == 1).all(), "short_lt5 differs within a node"
    return nodes.drop(columns=["is_composite", "short_lt5"]), canon, int((comp["any"] & ~comp["all"]).sum())


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    md = pd.read_csv(PROC / "PMA_motif_metadata.tsv", sep="\t", keep_default_na=False, low_memory=False)
    motifs = pm.read_meme(PROC / "PMA_motifs_raw.meme")
    nodes, canon, mixed = build(motifs, md)
    assert nodes.pma_id.is_unique and len(nodes) == len(motifs)
    nodes.to_csv(OUT / "motif_nodes.tsv", sep="\t", index=False)
    first = nodes.drop_duplicates("node_id")
    keep = first[~first.unclusterable]
    pm.write_meme([(n, p, canon[n][1]) for n, p in zip(keep.node_id, keep.partition)], OUT / "nodes.meme")
    exact = md[md.pma_id.isin(nodes.pma_id)].normalized_matrix_hash.nunique()
    s = dict(layer=LAYER, motifs=len(nodes), nodes=int(nodes.node_id.nunique()),
             distinct_normalized_hash=int(exact),
             rc_only_duplicates=int(exact - nodes.node_id.nunique()),
             clusterable_nodes=len(keep), unclusterable_nodes=int(first.unclusterable.sum()),
             partition=keep.partition.value_counts().to_dict(), mixed_composite_monomer_nodes=mixed)
    (OUT / "node_summary.json").write_text(json.dumps(s, indent=2) + "\n")
    print(json.dumps(s, indent=2))


if __name__ == "__main__":
    main()
