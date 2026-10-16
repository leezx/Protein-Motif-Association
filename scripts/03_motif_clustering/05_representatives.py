"""Step 3 §3.4–3.5 (+F26, F27): representatives, CORE/EXTENDED tiers, scan sets,
and the v0.3 reference files, at the cuts chosen in cut_selection.json.

Tiers are per fine cluster from all qualifying members. Within each
archetype, each tier's fine clusters get one scanning representative
(ranked over their fine representatives) plus `archetype_extra` for any
fine cluster whose representative has s < 0.50 to it. A tier's scan set
only uses PWMs from fine clusters of that tier (F27).
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "02_motif_import"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import pma_motif as pm  # noqa: E402
import pma_cluster as pc  # noqa: E402

LAYER = os.environ.get("PMA_RAW_LAYER", "v0.2.1")
PROC = Path(os.environ["PMA_MOTIF_PROCESSED"]) / f"{LAYER}_raw_layer"
R = Path(os.environ["PMA_MOTIF_RESULT"]) / "step3_motif_clustering"
MASTER = Path(os.environ["PMA_MOTIF_RAW"]) / "hocomoco_v14" / "2026-10-14" / "tf_masterlist.tsv"
OUT = Path(os.environ["PMA_MOTIF_PROCESSED"]) / "v0.3_reference"
EXTRA_S = 0.50
NOT_EXPERIMENT_NS = {"ENA"}  # run-level IDs (SELEX cycles), not experiments
QUALITY = {"A": 0, "B": 1, "C": 2, "D": 3, "CORE": 0, "UNVALIDATED": 1}
TIERS = ("CORE_sequence", "CORE_occupancy", "EXTENDED")


def accessions(row):
    if row.experiment_identity != "accession":
        return []
    return [a for a in row.experiment_ids.split(";") if a and a.split(":", 1)[0] not in NOT_EXPERIMENT_NS]


def load():
    md = pd.read_csv(PROC / "PMA_motif_metadata.tsv", sep="\t", keep_default_na=False, low_memory=False)
    links = pd.read_csv(PROC / "PMA_motif_tf_links.tsv", sep="\t", keep_default_na=False)
    mem = pd.read_csv(PROC / "PMA_hocomoco_collection_memberships.tsv", sep="\t", keep_default_na=False)
    mn = pd.read_csv(R / "nodes" / "motif_nodes.tsv", sep="\t", keep_default_na=False)
    mn["unclusterable"] = mn.unclusterable.astype(str).eq("True")
    sel = json.loads((R / "clustering" / "cut_selection.json").read_text())
    key = f"{sel['c_fine']:.2f}_{sel['c_arch']:.2f}"
    grid = pd.read_csv(R / "clustering" / "node_clusters_grid.tsv.gz", sep="\t",
                       usecols=["node_id", f"fine_{key}", f"arch_{key}"])
    grid.columns = ["node_id", "fine", "arch"]
    edges = pd.read_csv(R / "edges.tsv.gz", sep="\t", usecols=["a", "b", "s"])
    ml = pd.read_csv(MASTER, sep="\t", keep_default_na=False)
    return md, links, mem, mn, sel, grid, edges, ml


def main():
    md, links, mem, mn, sel, grid, edges, ml = load()
    OUT.mkdir(parents=True, exist_ok=True)
    tclass = pc.target_class(md, links, ml)
    hq = mem.assign(r=mem.quality.map(QUALITY)).groupby("pma_id").r.min()
    rec = mn.merge(md, on="pma_id", how="left", validate="1:1")
    rec["target_class"] = rec.pma_id.map(tclass)
    rec["acc"] = [accessions(r) for r in rec.itertuples()]
    rec["quality_rank"] = np.where(rec.source_db == "HOCOMOCO", rec.pma_id.map(hq),
                                   rec.source_quality.map(QUALITY)).astype(float)
    rec["quality_rank"] = rec.quality_rank.fillna(9)
    rec = rec.merge(grid, on="node_id", how="left")
    assert rec[~rec.unclusterable].fine.notna().all(), "clusterable motif without fine cluster"

    # node similarity lookup (non-edges 0)
    S = {}
    for a, b, s in edges.itertuples(index=False):
        S[(a, b)] = S[(b, a)] = s

    def sim(x, y):
        return 1.0 if x == y else S.get((x, y), 0.0)

    cl = rec[~rec.unclusterable].copy()
    cl["fine"], cl["arch"] = cl.fine.astype(int), cl.arch.astype(int)
    # stable public IDs: order clusters by their smallest pma_id
    fid = cl.groupby("fine").pma_id.min().sort_values()
    fmap = {f: f"PMA_FC{i + 1:05d}" for i, f in enumerate(fid.index)}
    aid = cl.groupby("arch").pma_id.min().sort_values()
    amap = {a: f"PMA_AR{i + 1:05d}" for i, a in enumerate(aid.index)}
    cl["fine_cluster"], cl["archetype"] = cl.fine.map(fmap), cl.arch.map(amap)

    # ---- tiers per fine cluster (§3.5, F26) --------------------------------
    def tier(g):
        seq = g[(g.direct_binding_evidence == "supported") & (g.species_basis == "human")
                & (g.qc_flags == "") & (g.target_class == "sequence_specific_TF")]
        if len(seq):
            return "CORE_sequence", 0
        occ = g[(g.assay_class == "in_vivo_occupancy") & (g.target_class == "sequence_specific_TF")]
        n = pc.n_independent_experiments([a for x in occ.acc for a in x])
        return ("CORE_occupancy" if n >= 2 else "EXTENDED"), n

    tiers = {f: tier(g) for f, g in cl.groupby("fine_cluster")}
    cl["tier"] = cl.fine_cluster.map(lambda f: tiers[f][0])

    # ---- fine representatives (§3.4) ---------------------------------------
    def candidates(g, unit_col, unit_mean):
        all_low = (g.qc_flags == "low_ic").all()
        any_tf = (g.target_class == "sequence_specific_TF").any()
        med = g.length.astype(float).median()
        out = []
        for r in g.itertuples():
            ok = (r.qc_flags == "" or (all_low and r.qc_flags == "low_ic")) and \
                 (r.target_class == "sequence_specific_TF" or not any_tf)
            out.append(dict(pma_id=r.pma_id, eligible=ok, mean_s=unit_mean[getattr(r, unit_col)],
                            evidence=r.direct_binding_evidence, source_db=r.source_db,
                            quality_rank=r.quality_rank, n_experiments=r.n_exp,
                            length_dev=abs(float(r.length) - med)))
        return out

    node_acc = cl.groupby("node_id").acc.apply(lambda s: pc.n_independent_experiments([a for x in s for a in x]))
    cl["n_exp"] = cl.node_id.map(node_acc)
    fine_rep, fine_rows = {}, []
    for f, g in cl.groupby("fine_cluster"):
        nodes = g.node_id.unique()
        mean = {n: (np.mean([sim(n, m) for m in nodes if m != n]) if len(nodes) > 1 else 1.0) for n in nodes}
        rep = pc.rank_representative(candidates(g, "node_id", mean))
        fine_rep[f] = rep
        fine_rows.append(dict(level="fine_cluster", cluster_id=f, archetype=g.archetype.iloc[0],
                              tier=tiers[f][0], n_occupancy_experiments=tiers[f][1], representative=rep,
                              rep_node=g.set_index("pma_id").node_id[rep], n_motifs=len(g), n_nodes=len(nodes),
                              rep_mean_s=round(mean[g.set_index("pma_id").node_id[rep]], 4)))
    fr = pd.DataFrame(fine_rows)
    node_of = cl.set_index("pma_id").node_id

    # ---- archetype scan representatives per tier (F27) ---------------------
    scan_rows = []
    by_pma = cl.set_index("pma_id")
    for a, g in fr.groupby("archetype"):
        reps = g.representative.tolist()
        units = by_pma.loc[reps].assign(fine_cluster=g.cluster_id.to_numpy(), n_exp=0)
        for f, n in zip(g.cluster_id, g.n_occupancy_experiments):
            units.loc[fine_rep[f], "n_exp"] = cl[cl.fine_cluster == f].acc.pipe(
                lambda s: pc.n_independent_experiments([x for y in s for x in y]))
        units = units.reset_index()

        def pick(sub):
            nodes = [node_of[p] for p in sub.pma_id]
            mean = {p: (np.mean([sim(node_of[p], m) for m in nodes if m != node_of[p]]) if len(nodes) > 1 else 1.0)
                    for p in sub.pma_id}
            sub = sub.assign(unit=sub.pma_id)
            return pc.rank_representative(candidates(sub, "unit", mean)), mean

        medoid, _ = pick(units)
        scan_rows.append(dict(archetype=a, role="archetype_medoid", tier="", pma_id=medoid, fine_cluster=""))
        for t in TIERS:
            sub = units[units.fine_cluster.map(lambda f: tiers[f][0]) == t]
            if sub.empty:
                continue
            top, _ = pick(sub)
            scan_rows.append(dict(archetype=a, role="tier_scan_representative", tier=t, pma_id=top,
                                  fine_cluster=sub.set_index("pma_id").fine_cluster[top]))
            for p, f in zip(sub.pma_id, sub.fine_cluster):
                s = sim(node_of[p], node_of[top])
                if p != top and s < EXTRA_S:
                    scan_rows.append(dict(archetype=a, role="archetype_extra", tier=t, pma_id=p, fine_cluster=f,
                                          s_to_tier_rep=round(s, 4)))
    sr = pd.DataFrame(scan_rows)

    # ---- outputs -----------------------------------------------------------
    allrec = rec[["pma_id", "node_id", "node_orientation", "partition", "unclusterable"]].merge(
        cl[["pma_id", "fine_cluster", "archetype", "tier"]], on="pma_id", how="left").fillna("")
    assert allrec.pma_id.is_unique and len(allrec) == len(mn)
    allrec.to_csv(OUT / "PMA_motif_clusters.tsv", sep="\t", index=False)
    fr.to_csv(OUT / "PMA_motif_representatives.tsv", sep="\t", index=False)
    sr.to_csv(OUT / "PMA_motif_scan_sets.tsv", sep="\t", index=False)
    mats = {m: (m, a, x) for m, a, x in pm.read_meme(PROC / "PMA_motifs_raw.meme")}
    scan = sr[sr.role != "archetype_medoid"]
    files = {}
    for t, fn in zip(TIERS, ("PMA_motifs_core.meme", "PMA_motifs_core_occupancy.meme", "PMA_motifs_extended.meme")):
        ids = sorted(scan[scan.tier == t].pma_id.unique())
        pm.write_meme([mats[i] for i in ids], OUT / fn)
        files[t] = len(ids)
    ev = cl.groupby("fine_cluster").agg(
        n_motifs=("pma_id", "size"), n_tfs=("motif_tf_assignment", "nunique"),
        sources=("source_db", lambda s: ";".join(sorted(set(s)))),
        n_supported=("direct_binding_evidence", lambda s: int((s == "supported").sum())),
        tfs=("motif_tf_assignment", lambda s: ";".join(sorted(set(s)))[:2000])).reset_index()
    ev["tier"] = ev.fine_cluster.map(lambda f: tiers[f][0])
    ev["n_occupancy_experiments"] = ev.fine_cluster.map(lambda f: tiers[f][1])
    ev.to_csv(OUT / "PMA_motif_evidence.tsv", sep="\t", index=False)
    edges.to_csv(OUT / "PMA_motif_edges.tsv.gz", sep="\t", index=False, float_format="%.6g")
    s = dict(layer=LAYER, cuts=dict(c_fine=sel["c_fine"], c_arch=sel["c_arch"]),
             motifs=len(allrec), unclusterable=int(allrec.unclusterable.astype(str).eq("True").sum()),
             fine_clusters=int(cl.fine_cluster.nunique()), archetypes=int(cl.archetype.nunique()),
             fine_by_tier=fr.tier.value_counts().to_dict(),
             archetypes_with_tier={t: int(sr[(sr.tier == t) & (sr.role == "tier_scan_representative")].archetype.nunique())
                                   for t in TIERS},
             scan_pwms=files, archetype_extras=sr[sr.role == "archetype_extra"].tier.value_counts().to_dict())
    (OUT / "summary.json").write_text(json.dumps(s, indent=2) + "\n")
    commit = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True,
                            cwd=Path(__file__).parent).stdout.strip()
    (OUT / "session_info.txt").write_text(
        f"commit: {commit}\nlayer: {LAYER}\npython: {sys.version.split()[0]}\nnumpy: {np.__version__}\n"
        f"pandas: {pd.__version__}\n")
    print(json.dumps(s, indent=2))


if __name__ == "__main__":
    main()
