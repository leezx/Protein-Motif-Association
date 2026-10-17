"""Step 3b §7.2: final reference = annotated clusters + one primary PWM each.

usage: 07_annotate_clusters.py <out_dir>
Inputs: gates/selection.json, gates/final_<part>_<rep>_d<dims>.tsv.gz,
nodes/motif_nodes.tsv + nodes.meme, raw layer v0.3, evidence v2.
Outputs:
  PMA_motif_to_cluster.tsv   every v0.3 source entry -> profile -> node ->
                             Louvain community -> final cluster (or exclusion)
  PMA_cluster_summary.tsv    one row per final cluster (fields of design §7.2)
  PMA_representatives.meme   exactly one PWM per final cluster
  reference_summary.json
Weights for family purity: each independent experiment counts 1 (split over
its profiles); a profile without a resolved experiment counts 1 on its own.
annotation_status: known (a tier <= 2 member: in vitro or curated core);
alternative (known, but its candidate TFs have more tier <= 2 motifs in another
cluster); accessibility_only (every member accessibility/transcription
derived); unresolved (otherwise).
recurrent_uncharacterized: no candidate TF, >= 3 independent experiments
across >= 2 studies and >= 2 biosamples.
PMA_TIER_GRAPH=greedy (§19): tiers from align_tiers_greedy/. Only hub clusters are summarised
and exported to PMA_representatives.meme (the scanning panel); isolated / unassigned /
core_unassigned motifs keep their own rows in PMA_motif_to_cluster.tsv (membership, s_to_hub)
and are listed in PMA_unrepresented_motifs.tsv.
"""
import json
import os
import sys
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "02_motif_import"))
import pma_motif as pm  # noqa: E402

R = Path(os.environ["PMA_MOTIF_RESULT"]) / "step3b_v03"
PROC = Path(os.environ["PMA_MOTIF_PROCESSED"]) / "v0.3_raw_layer"
EVID = Path(os.environ["PMA_MOTIF_PROCESSED"]) / "annotations" / "evidence_v2" / "PMA_motif_evidence.tsv"
GRAPH = os.environ.get("PMA_TIER_GRAPH", "kmer")
TIERS = R / {"kmer": "tiers", "align": "align_tiers", "greedy": "align_tiers_greedy"}[GRAPH]
NO_PROTEIN = {"accessibility_model_derived", "transcription_model_derived"}


def top(counter, n=10):
    return ";".join(f"{k}:{v:g}" for k, v in counter.most_common(n) if k)


def main(out, tier=None):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    md = pd.read_csv(PROC / "PMA_motif_metadata.tsv", sep="\t", keep_default_na=False, low_memory=False)
    ev = pd.read_csv(EVID, sep="\t", keep_default_na=False, low_memory=False)
    nodes = pd.read_csv(R / "nodes" / "motif_nodes.tsv", sep="\t", keep_default_na=False)
    mats = {n: m for n, _, m in pm.read_meme(R / "nodes" / "nodes.meme")}
    if tier:  # §14 three-tier reference
        sel = {"tier": tier, **json.loads((TIERS / "tier_choice.json").read_text())["tiers"][tier]}
        f = pd.read_csv(TIERS / f"final_tier_{tier}.tsv.gz", sep="\t", dtype={"cluster": str})
        a = pd.DataFrame({"node_id": f.node_id, "partition": f.partition, "louvain": f.cluster, "cluster": f.cluster,
                          "rep_node": f.rep_node, "covered_presplit": f.covered.astype(int),
                          "membership": f.get("membership", "connected"), "s_to_hub": f.get("s_to_hub", np.nan)})
    else:
        sel = json.loads((R / "gates" / "selection.json").read_text())
        assign = []
        for part, s in sel.items():
            assert s["status"] == "selected", (part, s)
            f = pd.read_csv(R / "gates" / f"final_{part}_{s['rep']}_d{s['dims']}.tsv.gz", sep="\t", dtype=str)
            c = s["config"]
            assign.append(pd.DataFrame({"node_id": f.node_id, "partition": part, "louvain": f[f"{c}|louvain"],
                                        "cluster": f[f"{c}|cluster"], "rep_node": f[f"{c}|rep"],
                                        "covered_presplit": f[f"{c}|covered_presplit"].astype(int)}))
        a = pd.concat(assign, ignore_index=True)
    size = a.groupby(["partition", "cluster"]).size().rename("n").reset_index()
    size = size.sort_values(["partition", "n", "cluster"], ascending=[True, False, True])
    size["cluster_id"] = [f"PMC_{p[0].upper()}{i:05d}" for p, i in
                          zip(size.partition, size.groupby("partition").cumcount() + 1)]
    a = a.merge(size[["partition", "cluster", "cluster_id"]], on=["partition", "cluster"])
    a["louvain_id"] = a.partition.str[0].str.upper() + "L" + a.louvain.astype(str)

    x = md[["pma_id", "source_db", "cluster_pool", "pool_exclusion", "qc_flags"]].merge(
        nodes[["pma_id", "node_id", "exact_node", "near_dup_of", "unclusterable"]], on="pma_id", how="left").merge(
        a[["node_id", "louvain_id", "cluster_id"] + (["membership", "s_to_hub"] if tier else [])], on="node_id",
        how="left")
    hub_clusters = set(a.cluster_id[a.partition.isin(["monomer", "composite"])])
    x["status"] = np.select([x.cluster_pool.astype(str) != "True", x.unclusterable.astype(str) == "True",
                             x.cluster_id.notna()], ["excluded", "unclusterable_short", "clustered"], "unassigned")
    assert not (x.status == "unassigned").any(), "pool profile without a cluster"
    if tier:  # F54: only hub clusters belong to the scanning reference; others keep their membership as status
        x["in_scanning_reference"] = x.cluster_id.isin(hub_clusters)
        unrep = (x.status == "clustered") & ~x.in_scanning_reference
        x.loc[unrep, "status"] = "unrepresented_" + x.loc[unrep, "membership"].astype(str)
        x["internal_cluster_id"] = x.cluster_id
        x["reference_cluster_id"] = x.cluster_id.where(x.in_scanning_reference)
        x = x.drop(columns="cluster_id")
    x.to_csv(out / "PMA_motif_to_cluster.tsv", sep="\t", index=False)
    if tier:
        x = x.rename(columns={"internal_cluster_id": "cluster_id"})
    if tier and GRAPH == "greedy":
        un = f[~f.partition.isin(["monomer", "composite"])].drop_duplicates("unique_id")
        un[["unique_id", "node_id", "membership", "partition", "s_to_hub", "rep_node"]].to_csv(
            out / "PMA_unrepresented_motifs.tsv", sep="\t", index=False, float_format="%.4f")
        go = pd.read_csv(TIERS / "greedy_order.tsv", sep="\t")
        rank_of = dict(zip(go.unique_id, go["rank"]))
        uid_of = dict(zip(f.node_id, f.unique_id))
    e = ev.merge(x[["pma_id", "node_id", "cluster_id"]], on="pma_id")
    e = e[e.cluster_id.isin(hub_clusters)].copy()
    e = e.merge(md[["pma_id", "ic_total", "length"]], on="pma_id")
    exp = e.independent_experiment_id.where(~e.independence_status.isin(["unresolved", "independence_unresolved"]), "")
    e["exp"] = np.where(exp != "", exp, "solo:" + e.pma_id)
    e["w"] = 1.0 / e.groupby("exp").pma_id.transform("size")
    e["family"] = e.protein_dbd.where(~e.protein_dbd.isin(["", "none"]), "")
    high = e[e.evidence_tier <= 2]
    tf_home = high.groupby("protein").cluster_id.agg(lambda s: s.value_counts().idxmax())

    rep_of = a.drop_duplicates("cluster_id").set_index("cluster_id")
    n_final_per_louvain = a.groupby("louvain_id").cluster_id.nunique()
    cov_of = a.groupby("cluster_id").covered_presplit.mean() if tier else pd.Series(1.0, index=a.cluster_id.unique())
    rows = []
    for cid, g in e.groupby("cluster_id"):
        r = rep_of.loc[cid]
        rn = r.rep_node
        rm = mats[rn]
        rep_members = g[g.node_id == rn].sort_values(["evidence_tier", "pma_id"])
        fam_w = g[g.family != ""].groupby("family").w.sum().sort_values(ascending=False)
        h = g[g.evidence_tier <= 2]
        dbd_targets = g[(g.binding_mode.isin(["chip_cognate_supported", "direct_curated", "direct_in_vitro"]))]
        cand = Counter()
        for p, w in zip(pd.concat([h.protein, dbd_targets.protein]), pd.concat([h.w, dbd_targets.w])):
            for q in filter(None, str(p).split(";")):
                cand[q] += w
        assayed = Counter()
        for p, w, t in zip(g.protein, g.w, g.evidence_type):
            if t in ("chip_model_derived", "chip_denovo_derived", "chip_derived"):
                for q in filter(None, str(p).split(";")):
                    assayed[q] += w
        real = g[g.exp.str.startswith("solo:") == False]  # noqa: E712
        n_exp = real.exp.nunique()
        bios = Counter(dict(real.groupby("context_biosample").exp.nunique()))
        organ = Counter(dict(real.groupby("context_organ").exp.nunique()))
        studies = real.context_study.nunique()
        acc_only = g.evidence_type.isin(NO_PROTEIN).all()
        if len(h):
            alt = all(tf_home.get(q, cid) != cid for q in cand if q in tf_home.index) and \
                any(q in tf_home.index for q in cand)
            status = "alternative" if alt else "known"
        elif acc_only:
            status = "accessibility_only"
        else:
            status = "unresolved"
        gc = float((rm[:, 1] + rm[:, 2]).mean())
        ic = pm.info_content(rm)
        unres = g.independence_status.isin(["unresolved", "independence_unresolved"]).mean()
        flags = [f for f in ("low_ic" if ic / len(rm) < 0.5 else "", "long_gt30" if len(rm) > 30 else "",
                             "provenance_unresolved" if unres > 0.5 else "") if f]
        rows.append(dict(
            cluster_id=cid, partition=r.partition, representative_node=rn,
            representative_id=rep_members.pma_id.iloc[0] if len(rep_members) else "",
            representative_source=rep_members.source_db.iloc[0] if len(rep_members) else "",
            representative_evidence_type=rep_members.evidence_type.iloc[0] if len(rep_members) else "",
            n_nodes=int(g.node_id.nunique()), n_raw_motifs=int(len(g)), n_independent_experiments=int(n_exp),
            source_composition=top(Counter(g.source_db), 20), evidence_composition=top(Counter(g.evidence_type), 10),
            tf_family_primary=fam_w.index[0] if len(fam_w) else "",
            tf_family_purity=round(float(fam_w.iloc[0] / fam_w.sum()), 4) if len(fam_w) else np.nan,
            candidate_tf_ids=top(cand) or "NA", assayed_protein_targets=top(assayed),
            biosample_distribution=top(bios), organ_distribution=top(organ),
            length=len(rm), ic_total=round(ic, 3), gc=round(gc, 3), composite=r.partition == "composite",
            representative_coverage=round(float(cov_of[cid]), 4), parent_louvain_cluster=r.louvain_id,
            split_reason="" if n_final_per_louvain[r.louvain_id] == 1 else "presplit_coverage_lt_0.90",
            annotation_status=status, qc_flags=";".join(flags),
            hub_greedy_rank=rank_of.get(uid_of.get(rn)) if tier and GRAPH == "greedy" else None,
            recurrent_uncharacterized=bool(not cand and n_exp >= 3 and studies >= 2 and len(bios) >= 2)))
    cs = pd.DataFrame(rows).sort_values("cluster_id")
    cs.to_csv(out / "PMA_cluster_summary.tsv", sep="\t", index=False)
    pm.write_meme([(r.cluster_id, r.representative_id or r.representative_node, mats[r.representative_node])
                   for r in cs.itertuples()], out / "PMA_representatives.meme")
    summ = dict(selection=sel, clusters=len(cs), by_partition=cs.partition.value_counts().to_dict(),
                annotation_status=cs.annotation_status.value_counts().to_dict(),
                recurrent_uncharacterized=int(cs.recurrent_uncharacterized.sum()),
                split_clusters=int((cs.split_reason != "").sum()),
                profiles=x.status.value_counts().to_dict(),
                membership=x.drop_duplicates("node_id").membership.value_counts().to_dict() if tier else None)
    (out / "reference_summary.json").write_text(json.dumps(summ, indent=2, default=float) + "\n")
    print(json.dumps(summ, indent=2, default=float))


if __name__ == "__main__":
    # usage: 07_annotate_clusters.py <out_dir> [LOW|MEDIUM|HIGH]
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
