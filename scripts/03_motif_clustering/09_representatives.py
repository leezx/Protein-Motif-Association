"""Step 3 §8.3–8.5: representatives, fidelity gate, tiers, cluster annotations,
non-redundancy QC, and the v0.3 reference files. Runs on Argos.

Inputs ($PMA_MOTIF_RESULT/step3_motif_clustering): seurat/seurat_<part>.tsv,
kmer/features.f32 + kmer/nodes.tsv, nodes/motif_nodes.tsv,
eligible_directed.tsv.gz, edges.tsv.gz; the v0.2.1 raw layer.
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
NK = 32896
COVERAGE = 0.90
DELTA = 0.05
REDUNDANT_S = 0.85
NOT_EXPERIMENT_NS = {"ENA"}
QUALITY = {"A": 0, "B": 1, "C": 2, "D": 3, "CORE": 0, "UNVALIDATED": 1}


def accessions(eid, ident):
    if ident != "accession":
        return []
    return [a for a in eid.split(";") if a and a.split(":", 1)[0] not in NOT_EXPERIMENT_NS]


def rank_key(c, same_src):
    return (pc.EVIDENCE_RANK.get(c["evidence"], 3), c["quality_rank"] if same_src else 0,
            -c["n_experiments"], -c["mean_s"], c["length_dev"], c["pma_id"])


def ranked(cands):
    """All candidates in §3.4 order with the fidelity window applied first
    (window members, then the rest by mean similarity)."""
    pool = [c for c in cands if c["eligible"]] or list(cands)
    best = max(c["mean_s"] for c in pool)
    win = [c for c in pool if c["mean_s"] >= best - DELTA - 1e-12]
    same = len({c["source_db"] for c in win}) == 1
    rest = sorted([c for c in pool if c not in win], key=lambda c: (-c["mean_s"], c["pma_id"]))
    return sorted(win, key=lambda c: rank_key(c, same)) + rest


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    md = pd.read_csv(PROC / "PMA_motif_metadata.tsv", sep="\t", keep_default_na=False, low_memory=False)
    links = pd.read_csv(PROC / "PMA_motif_tf_links.tsv", sep="\t", keep_default_na=False)
    mem = pd.read_csv(PROC / "PMA_hocomoco_collection_memberships.tsv", sep="\t", keep_default_na=False)
    ml = pd.read_csv(MASTER, sep="\t", keep_default_na=False)
    mn = pd.read_csv(R / "nodes" / "motif_nodes.tsv", sep="\t", keep_default_na=False)
    mn["unclusterable"] = mn.unclusterable.astype(str).eq("True")
    seu = pd.concat([pd.read_csv(R / "seurat" / f"seurat_{p}.tsv", sep="\t", dtype={"cluster": str})
                     for p in ("monomer", "composite")], ignore_index=True)
    kn = pd.read_csv(R / "kmer" / "nodes.tsv", sep="\t")
    feat = np.memmap(R / "kmer" / "features.f32", dtype="<f4", mode="r", shape=(len(kn), NK))
    frow = dict(zip(kn.node_id, range(len(kn))))

    # public cluster IDs: per partition, by size (desc) then Seurat label
    size = seu.groupby(["partition", "cluster"]).size().rename("n").reset_index()
    size["k"] = size.cluster.astype(int)
    cid = {}
    for p, pre in (("monomer", "PMA_M"), ("composite", "PMA_C")):
        s = size[size.partition == p].sort_values(["n", "k"], ascending=[False, True])
        cid.update({(p, c): f"{pre}{i + 1:04d}" for i, c in enumerate(s.cluster)})
    seu["cluster_id"] = [cid[(p, c)] for p, c in zip(seu.partition, seu.cluster)]

    tclass = pc.target_class(md, links, ml)
    hq = mem.assign(r=mem.quality.map(QUALITY)).groupby("pma_id").r.min()
    fam = ml[ml["curated:uniprot_id"].str.endswith("_HUMAN")].drop_duplicates("auto:gene_symbol") \
        .set_index("auto:gene_symbol")["tfclass:family"]
    rec = mn.merge(md, on="pma_id", how="left", validate="1:1")
    rec["target_class"] = rec.pma_id.map(tclass)
    rec["acc"] = [accessions(e, i) for e, i in zip(rec.experiment_ids, rec.experiment_identity)]
    rec["quality_rank"] = np.where(rec.source_db == "HOCOMOCO", rec.pma_id.map(hq),
                                   rec.source_quality.map(QUALITY)).astype(float)
    rec["quality_rank"] = rec.quality_rank.fillna(9)
    rec = rec.merge(seu[["node_id", "cluster_id", "UMAP_1", "UMAP_2"]], on="node_id", how="left")
    assert rec[~rec.unclusterable].cluster_id.notna().all(), "clusterable motif without a cluster"
    cl = rec[~rec.unclusterable].copy()

    ed = pd.read_csv(R / "eligible_directed.tsv.gz", sep="\t")
    nbr = {}
    for q, t in zip(ed["query"], ed["target"]):
        nbr.setdefault(q, set()).add(t)
        nbr.setdefault(t, set()).add(q)  # either direction covers
    edges = pd.read_csv(R / "edges.tsv.gz", sep="\t", usecols=["a", "b", "s"])
    S = {(a, b): s for a, b, s in edges.itertuples(index=False)}

    def tier(g):
        seq = g[(g.direct_binding_evidence == "supported") & (g.species_basis == "human")
                & (g.qc_flags == "") & (g.target_class == "sequence_specific_TF")]
        if len(seq):
            return "CORE_sequence", 0, seq
        occ = g[(g.assay_class == "in_vivo_occupancy") & (g.target_class == "sequence_specific_TF")]
        n = pc.n_independent_experiments([a for x in occ.acc for a in x])
        return ("CORE_occupancy" if n >= 2 else "EXTENDED"), n, seq

    rep_rows, ann_rows = [], []
    for c, g in cl.groupby("cluster_id", sort=True):
        nodes = g.node_id.unique()
        F = np.asarray(feat[[frow[n] for n in nodes]], dtype=np.float64)
        tot = F.sum(0)
        mean = dict(zip(nodes, ((F @ tot) - 1.0) / max(len(nodes) - 1, 1) if len(nodes) > 1 else np.ones(1)))
        node_exp = g.groupby("node_id").acc.apply(lambda s: pc.n_independent_experiments([a for x in s for a in x]))
        all_low = (g.qc_flags == "low_ic").all()
        any_tf = (g.target_class == "sequence_specific_TF").any()
        med = g.length.astype(float).median()
        cands = [dict(pma_id=r.pma_id, node=r.node_id, eligible=(r.qc_flags == "" or (all_low and r.qc_flags == "low_ic"))
                      and (r.target_class == "sequence_specific_TF" or not any_tf),
                      mean_s=float(mean[r.node_id]), evidence=r.direct_binding_evidence, source_db=r.source_db,
                      quality_rank=r.quality_rank, n_experiments=int(node_exp[r.node_id]),
                      length_dev=abs(float(r.length) - med)) for r in g.itertuples()]
        order = ranked(cands)
        primary = order[0]
        # fidelity gate over member nodes with no QC flag (§8.3)
        elig_nodes = set(g[g.qc_flags == ""].node_id) or set(nodes)
        cov_of = lambda n: ({n} | nbr.get(n, set())) & set(nodes)  # noqa: E731
        covered = cov_of(primary["node"])
        reps = [(primary, "primary")]
        while len(covered & elig_nodes) / len(elig_nodes) < COVERAGE:
            unc = [x for x in order if x["eligible"] and x["node"] in elig_nodes - covered]
            if not unc:
                break
            gain = {x["pma_id"]: len(cov_of(x["node"]) & (elig_nodes - covered)) for x in unc}
            best = max(gain.values())
            pick = next(x for x in unc if gain[x["pma_id"]] == best)  # ties by rank order
            reps.append((pick, "representative_extra"))
            covered |= cov_of(pick["node"])
        t, n_occ, qual = tier(g)
        if t == "CORE_sequence" and primary["pma_id"] not in set(qual.pma_id):
            core = [x for x in order if x["pma_id"] in set(qual.pma_id)][0]
            reps.append((core, "core_scan_representative"))
        cover_frac = len(covered & elig_nodes) / len(elig_nodes)
        for x, role in reps:
            s_to_primary = 1.0 if x["node"] == primary["node"] else S.get(tuple(sorted((x["node"], primary["node"]))), 0.0)
            rep_rows.append(dict(cluster_id=c, partition=g.partition.iloc[0], role=role, pma_id=x["pma_id"],
                                 node_id=x["node"], mean_corr=round(x["mean_s"], 4), evidence=x["evidence"],
                                 source_db=x["source_db"], s_tomtom_to_primary=round(s_to_primary, 4),
                                 coverage_after=round(cover_frac, 4)))
        tfs = sorted(set(links[links.pma_id.isin(g.pma_id)].tf_hgnc) - {""})
        ann_rows.append(dict(
            cluster_id=c, partition=g.partition.iloc[0], tier=t, n_motifs=len(g), n_nodes=len(nodes),
            n_tfs=len(tfs), primary_representative=primary["pma_id"], n_scan_pwms=len(reps),
            coverage=round(cover_frac, 4), n_occupancy_experiments=n_occ,
            n_direct_supported=int((g.direct_binding_evidence == "supported").sum()),
            sources=";".join(f"{k}:{v}" for k, v in g.source_db.value_counts().items()),
            assays=";".join(f"{k}:{v}" for k, v in g.assay_class.value_counts().items()),
            tf_families=";".join(sorted({fam[x] for x in tfs if x in fam.index})),
            codebook_clusters=";".join(sorted(set(g.codebook_cluster) - {""})),
            tfs=";".join(tfs), member_pma_ids=";".join(sorted(g.pma_id))))
    reps = pd.DataFrame(rep_rows)
    ann = pd.DataFrame(ann_rows)
    clu = rec[["pma_id", "node_id", "node_orientation", "partition", "unclusterable", "cluster_id", "UMAP_1", "UMAP_2"]] \
        .merge(ann[["cluster_id", "tier"]], on="cluster_id", how="left")
    clu["is_scan_representative"] = clu.pma_id.isin(reps.pma_id)
    assert clu.pma_id.is_unique and len(clu) == len(mn)

    # non-redundancy QC (§8.4): scanning PWM pairs passing v0.1 both ways with s >= 0.85
    rn = reps.drop_duplicates("pma_id")
    rset = set(rn.node_id)
    red = edges[edges.a.isin(rset) & edges.b.isin(rset) & (edges.s >= REDUNDANT_S)]
    node2c = dict(zip(rn.node_id, rn.cluster_id))
    red = red.assign(cluster_a=red.a.map(node2c), cluster_b=red.b.map(node2c))
    red = red[red.cluster_a != red.cluster_b]

    clu.to_csv(OUT / "PMA_motif_clusters.tsv", sep="\t", index=False)
    reps.to_csv(OUT / "PMA_motif_representatives.tsv", sep="\t", index=False)
    ann.to_csv(OUT / "PMA_motif_cluster_annotations.tsv", sep="\t", index=False)
    red.to_csv(OUT / "PMA_representative_redundancy_alerts.tsv", sep="\t", index=False)
    mats = {m: (m, a, x) for m, a, x in pm.read_meme(PROC / "PMA_motifs_raw.meme")}
    name = dict(zip(reps.pma_id, reps.cluster_id))
    tier_of = dict(zip(ann.cluster_id, ann.tier))
    files = {"PMA_motifs_reference.meme": sorted(rn.pma_id)}
    for t, fn in (("CORE_sequence", "PMA_motifs_core.meme"), ("CORE_occupancy", "PMA_motifs_core_occupancy.meme"),
                  ("EXTENDED", "PMA_motifs_extended.meme")):
        files[fn] = sorted(p for p in rn.pma_id if tier_of[name[p]] == t)
    for fn, ids in files.items():
        pm.write_meme([(i, name[i], mats[i][2]) for i in ids], OUT / fn)
    s = dict(layer=LAYER, motifs=len(clu), unclusterable=int(clu.unclusterable.sum()),
             clusters=ann.partition.value_counts().to_dict(), clusters_by_tier=ann.tier.value_counts().to_dict(),
             scan_pwms=int(len(rn)), roles=reps.role.value_counts().to_dict(),
             compression_motifs_per_scan_pwm=round(len(clu) / len(rn), 2),
             clusters_below_coverage=int((ann.coverage < COVERAGE).sum()),
             redundancy_alert_pairs=int(len(red)), meme_files={k: len(v) for k, v in files.items()})
    (OUT / "summary.json").write_text(json.dumps(s, indent=2) + "\n")
    commit = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True,
                            cwd=Path(__file__).parent).stdout.strip() or os.environ.get("PMA_COMMIT", "")
    (OUT / "session_info.txt").write_text(f"commit: {commit}\nlayer: {LAYER}\npython: {sys.version.split()[0]}\n"
                                          f"numpy: {np.__version__}\npandas: {pd.__version__}\n")
    print(json.dumps(s, indent=2))


if __name__ == "__main__":
    main()
