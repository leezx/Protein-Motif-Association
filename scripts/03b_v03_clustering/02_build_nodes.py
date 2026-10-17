"""Step 3b §4.2 + §5.2: raw layer v0.3 pool -> clustering nodes.

1. Exact: node key = min(sha1 fwd, sha1 rc) of the matrix as written in the
   v0.3 MEME (same key as Step 3, so v0.2.1 node IDs carry over).
2. Within-experiment near-duplicates (frozen): between nodes whose members
   all come from one experiment/model (ENCODE model annotation, Cistrome
   DCid, HDMA cell cluster, v0.2.1 accession experiment): mean column
   Pearson >= 0.98 with overlap >= 90 % of the longer profile, complete
   linkage. Kept node: most seqlets/hits, then node ID. Nodes shared by
   several experiments are never absorbed (experiments merge only by exact
   identity).
   Stop rule (zero errors): controls = curated alternative motifs of one TF
   (JASPAR different base IDs; HOCOMOCO H14CORE different subtypes) and
   composite vs component pairs (Step 3 contains_component). If any control
   pair meets the criterion, or there are < 50 controls, near-dedup is off.
3. Partition: composite when every member is composite (v0.2.1 is_composite
   or composite_status == composite); short_lt5 nodes are unclusterable.

usage: 02_build_nodes.py  (env PMA_MOTIF_PROCESSED, PMA_MOTIF_RESULT)
Outputs (result/step3b_v03/nodes/): motif_nodes.tsv, nodes.meme,
near_dedup_controls.tsv, near_dedup_groups.tsv, node_summary.json
"""
import json
import os
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import fcluster, linkage
from scipy.spatial.distance import squareform

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "02_motif_import"))
import pma_align as pa  # noqa: E402
import pma_motif as pm  # noqa: E402

R_MIN, FRAC_LONGER, MIN_CONTROLS = 0.98, 0.90, 50
LAYER = Path(os.environ["PMA_MOTIF_PROCESSED"]) / "v0.3_raw_layer"
RES = Path(os.environ["PMA_MOTIF_RESULT"])
OUT = RES / "step3b_v03" / "nodes"


def node_key(m):
    f, r = pm.sha1(m), pm.sha1(np.ascontiguousarray(pm.revcomp(m)))
    return (f, "fwd") if f <= r else (r, "rc")


def experiment_key(md):
    src = md.source_db.astype(str)
    return np.select(
        [src.str.startswith("ENCODE_"), src == "Cistrome_DB2", src == "HDMA",
         md.experiment_identity.fillna("") == "accession"],
        ["ENC:" + md.model_annotation.fillna("").astype(str), "CIS:" + md.source_identifier.astype(str),
         "HDMA:" + md.cell_cluster_id.fillna("").astype(str), "V021:" + md.experiment_ids.fillna("").astype(str)],
        "")


def controls(md, nodes, idx):
    """Distinct alternative-pattern pairs with independent evidence."""
    m = md.set_index("pma_id")
    node_of = dict(zip(nodes.pma_id, nodes.node_id))
    pairs = []
    ja = md[(md.source_db == "JASPAR") & md.motif_tf_assignment.fillna("").ne("")
            & ~md.motif_tf_assignment.fillna("").str.contains(";")]
    ja = ja.assign(base=ja.source_motif_id.str.split(".").str[0])
    ho = md[(md.source_db == "HOCOMOCO") & md.source_motif_id.astype(str).str.contains(r"\.H14CORE\.")]
    ho = ho.assign(base=ho.source_motif_id.str.extract(r"\.H14CORE\.(\d+)\.", expand=False))
    for kind, t in (("jaspar_alt_base", ja), ("hocomoco_subtype", ho)):
        for tf, g in t.groupby("motif_tf_assignment"):
            g = g.drop_duplicates("base")
            ids = g.pma_id.tolist()
            for i in range(len(ids)):
                for j in range(i + 1, len(ids)):
                    pairs.append((kind, tf, ids[i], ids[j]))
    cc = RES / "step3_motif_clustering" / "contains_component.tsv.gz"
    rows = [dict(kind=k, tf=tf, a=node_of.get(a), b=node_of.get(b)) for k, tf, a, b in pairs]
    if cc.exists():
        c = pd.read_csv(cc, sep="\t", usecols=["composite_node", "monomer_node"])
        rows += [dict(kind="composite_component", tf="", a=x, b=y) for x, y in zip(c.composite_node, c.monomer_node)]
    out = pd.DataFrame(rows).dropna()
    out = out[(out.a != out.b) & out.a.isin(idx) & out.b.isin(idx)].drop_duplicates(["a", "b"])
    return out, cc.exists()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    md = pd.read_csv(LAYER / "PMA_motif_metadata.tsv", sep="\t", low_memory=False)
    md = md[md.cluster_pool.astype(str) == "True"].copy()
    mats = {mid: m for mid, _, m in pm.read_meme(LAYER / "PMA_motifs_raw.meme")}
    md = md[md.pma_id.isin(mats)]
    rows, canon = [], {}
    for pid in md.pma_id:
        k, o = node_key(mats[pid])
        nid = "PMN_" + k[:12]
        if nid in canon:
            assert canon[nid][0] == k, f"node id prefix collision {nid}"
        else:
            canon[nid] = (k, mats[pid] if o == "fwd" else np.ascontiguousarray(pm.revcomp(mats[pid])))
        rows.append((pid, nid, o))
    nodes = pd.DataFrame(rows, columns=["pma_id", "exact_node", "node_orientation"])
    meta = md.set_index("pma_id").loc[nodes.pma_id]
    nodes["experiment"] = experiment_key(meta.reset_index())
    nodes["weight"] = pd.to_numeric(meta.n_seqlets, errors="coerce").fillna(
        pd.to_numeric(meta.cis_numhits, errors="coerce")).fillna(0).to_numpy()
    nodes["is_composite"] = (meta.is_composite.astype(str).eq("True") |
                             meta.composite_status.astype(str).eq("composite")).to_numpy()
    nodes["short_lt5"] = meta.qc_flags.fillna("").str.contains("short_lt5").to_numpy()

    ids = sorted(canon)
    idx = {n: i for i, n in enumerate(ids)}
    Z, Zrc, st, ln = pa.pack([canon[n][1] for n in ids])

    ctl, have_cc = controls(md, nodes.rename(columns={"exact_node": "node_id"}), idx)
    r = pa.near_dup_r(Z, Zrc, st, ln, ctl.a.map(idx).to_numpy(np.int64), ctl.b.map(idx).to_numpy(np.int64),
                      FRAC_LONGER) if len(ctl) else np.array([])
    ctl["r_near"] = r
    ctl["would_merge"] = r >= R_MIN
    ctl.to_csv(OUT / "near_dedup_controls.tsv", sep="\t", index=False, float_format="%.6g")
    near_on = bool(len(ctl) >= MIN_CONTROLS and not ctl.would_merge.any())

    absorbed = {}
    groups = []
    if near_on:
        n_exp = nodes.groupby("exact_node").experiment.nunique()
        single = nodes[(nodes.experiment != "") & nodes.exact_node.map(n_exp).eq(1)]
        w = single.groupby("exact_node").weight.max()
        for ex, g in single.groupby("experiment"):
            cand = sorted(g.exact_node.unique())
            if len(cand) < 2:
                continue
            ii = np.array([idx[c] for c in cand], dtype=np.int64)
            a, b = np.triu_indices(len(cand), 1)
            rr = pa.near_dup_r(Z, Zrc, st, ln, ii[a], ii[b], FRAC_LONGER)
            if not (rr >= R_MIN).any():
                continue
            d = np.ones((len(cand), len(cand)))
            d[a, b] = d[b, a] = np.where(rr >= R_MIN, 1 - rr, 1.0)
            np.fill_diagonal(d, 0)
            lab = fcluster(linkage(squareform(d, checks=False), "complete"), 1 - R_MIN, "distance")
            for c in np.unique(lab):
                mem = [cand[i] for i in np.flatnonzero(lab == c)]
                if len(mem) < 2:
                    continue
                keep = sorted(mem, key=lambda n: (-w.get(n, 0), n))[0]
                for n in mem:
                    if n != keep:
                        absorbed[n] = keep
                groups.append(dict(experiment=ex, kept=keep, absorbed=";".join(x for x in mem if x != keep)))
    pd.DataFrame(groups, columns=["experiment", "kept", "absorbed"]).to_csv(OUT / "near_dedup_groups.tsv",
                                                                           sep="\t", index=False)
    nodes["node_id"] = nodes.exact_node.map(lambda n: absorbed.get(n, n))
    nodes["near_dup_of"] = nodes.exact_node.map(lambda n: absorbed.get(n, ""))
    g = nodes.groupby("node_id")
    comp = g.is_composite.agg(["all", "any"])
    nodes["partition"] = nodes.node_id.map(dict(zip(comp.index, np.where(comp["all"], "composite", "monomer"))))
    nodes["unclusterable"] = nodes.node_id.map(g.short_lt5.all())
    nodes.drop(columns=["is_composite", "short_lt5", "weight"]).to_csv(OUT / "motif_nodes.tsv", sep="\t",
                                                                       index=False)
    first = nodes.drop_duplicates("node_id")
    keep = first[~first.unclusterable]
    pm.write_meme([(n, p, canon[n][1]) for n, p in zip(keep.node_id, keep.partition)], OUT / "nodes.meme")
    src = md.set_index("pma_id").source_db
    s = dict(pool_profiles=len(nodes), exact_nodes=len(canon), nodes=int(nodes.node_id.nunique()),
             clusterable_nodes=len(keep), partition=keep.partition.value_counts().to_dict(),
             near_dedup=dict(enabled=near_on, controls=len(ctl), controls_by_kind=ctl.kind.value_counts().to_dict(),
                             controls_would_merge=int(ctl.would_merge.sum()), contains_component_available=have_cc,
                             absorbed_nodes=len(absorbed), groups=len(groups)),
             profiles_by_source=nodes.pma_id.map(src).value_counts().to_dict(),
             nodes_by_first_source=keep.pma_id.map(src).value_counts().to_dict(),
             mixed_composite_nodes=int((comp["any"] & ~comp["all"]).sum()))
    (OUT / "node_summary.json").write_text(json.dumps(s, indent=2, default=int) + "\n")
    print(json.dumps(s, indent=2, default=int))


if __name__ == "__main__":
    main()
