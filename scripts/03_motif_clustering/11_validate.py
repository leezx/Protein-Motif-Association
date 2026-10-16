"""Step 3 §8.4 validation and figures (descriptive; nothing here changes the
primary clustering). Runs on Argos after 09_representatives.py.

- benchmark pairs: P-high / P-provisional / N-challenge co-clustering
- ARI / purity vs Codebook Table 10 (codebook_cluster), Codebook Table 11
  (H13CORE names -> v14 records via original_motif) and HOCOMOCO
  H14CORE-CLUSTERED, over the motifs present in both
- within-cluster TOMTOM agreement (share of node pairs passing v0.1 in
  either direction)
- resolution / dims sensitivity (cluster counts, ARI vs primary)
- UMAPs coloured by tier, source, TF family
Outputs: results/03_motif_clustering/ (repo, small tables) and
$PMA_MOTIF_RESULT/step3_motif_clustering/report/ (figures).
"""
import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import adjusted_rand_score

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

LAYER = os.environ.get("PMA_RAW_LAYER", "v0.2.1")
PROC = Path(os.environ["PMA_MOTIF_PROCESSED"]) / f"{LAYER}_raw_layer"
REF = Path(os.environ["PMA_MOTIF_PROCESSED"]) / "v0.3_reference"
R = Path(os.environ["PMA_MOTIF_RESULT"]) / "step3_motif_clustering"
RAW = Path(os.environ["PMA_MOTIF_RAW"])
FIG = R / "report"
TAB = Path(__file__).resolve().parents[2] / "results" / "03_motif_clustering"
CB = RAW / "codebook_2026" / "2026-10-14" / "unpacked" / "Nature2026_SupplementaryTables_MOESM3" / "2024-11-25439B-s3"


def purity(truth, pred):
    """Share of motifs whose PMA cluster's majority external label equals theirs."""
    d = pd.DataFrame({"t": truth, "p": pred})
    return float(d.groupby("p").t.agg(lambda s: s.value_counts().iloc[0]).sum() / len(d))


def compare(name, ext, clu):
    """ext: Series pma_id -> external cluster label."""
    m = clu.set_index("pma_id").cluster_id.reindex(ext.index).dropna()
    e = ext.loc[m.index]
    return dict(reference=name, n_motifs=int(len(m)), n_ext_clusters=int(e.nunique()), n_pma_clusters=int(m.nunique()),
                ARI=round(adjusted_rand_score(e, m), 4), purity_pma_vs_ext=round(purity(e, m), 4),
                purity_ext_vs_pma=round(purity(m, e), 4))


def main():
    FIG.mkdir(parents=True, exist_ok=True)
    TAB.mkdir(parents=True, exist_ok=True)
    md = pd.read_csv(PROC / "PMA_motif_metadata.tsv", sep="\t", keep_default_na=False, low_memory=False)
    clu = pd.read_csv(REF / "PMA_motif_clusters.tsv", sep="\t", keep_default_na=False)
    clu = clu[clu.cluster_id != ""]
    ann = pd.read_csv(REF / "PMA_motif_cluster_annotations.tsv", sep="\t", keep_default_na=False)
    out = {}

    # benchmark pairs
    pairs = pd.read_csv(Path(os.environ["PMA_MOTIF_RESULT"]) / "step2_motif_import" / "benchmark" / "benchmark_pairs.tsv",
                        sep="\t", keep_default_na=False)
    c = clu.set_index("pma_id").cluster_id
    ok = pairs.m1.isin(c.index) & pairs.m2.isin(c.index)
    pairs = pairs[ok].assign(same=lambda d: c.reindex(d.m1).to_numpy() == c.reindex(d.m2).to_numpy())
    bt = pairs.groupby("set").same.agg(["size", "mean"]).round(4).reset_index()
    bt.columns = ["set", "n_pairs", "co_clustered"]
    bt.to_csv(TAB / "benchmark_coclustering.tsv", sep="\t", index=False)
    out["benchmark"] = bt.set_index("set").to_dict("index")

    # external clusterings
    rows = []
    cb10 = md.set_index("pma_id").codebook_cluster
    rows.append(compare("Codebook Table 10", cb10[cb10 != ""], clu))
    hc = pd.read_csv(RAW / "hocomoco_v14" / "2026-10-14" / "H14CORE-CLUSTERED_cluster_list.tsv", sep="\t")
    h14 = {f"HO14_{m.strip()}": rep for rep, ms in zip(hc.Representative_Motif, hc.Clustered_Motifs) for m in ms.split(";")}
    rows.append(compare("HOCOMOCO H14CORE-CLUSTERED", pd.Series(h14), clu))
    t11 = CB / "SupplementaryTable11_MARA_Clusters.v2026.2.xlsx"
    h13 = RAW / "hocomoco_v13" / "extracted" / "hocomoco13" / "H13CORE" / "H13CORE_annotation.jsonl"
    if t11.exists() and h13.exists():
        t = pd.read_excel(t11, sheet_name="TableS11")
        lab = {m.strip(): rep for rep, ms in zip(t.Representative_Motif, t.Clustered_Motifs) for m in ms.split(";")}
        orig = {}
        for line in open(h13):
            a = json.loads(line)
            orig[a["name"]] = a.get("original_motif", {}).get("name", "")
        mem = pd.read_csv(PROC / "PMA_hocomoco_collection_memberships.tsv", sep="\t", keep_default_na=False)
        by_orig = mem.drop_duplicates("original_motif").set_index("original_motif").pma_id
        mapped = {by_orig[orig[n]]: l for n, l in lab.items() if orig.get(n) in by_orig.index}
        r = compare("Codebook Table 11 (H13 -> v14 via original_motif)", pd.Series(mapped), clu)
        r["table11_motifs"], r["mapped"] = len(lab), len(mapped)
        rows.append(r)
    ext = pd.DataFrame(rows)
    ext.to_csv(TAB / "external_concordance.tsv", sep="\t", index=False)
    out["external"] = rows

    # within-cluster TOMTOM agreement over node pairs
    ed = pd.read_csv(R / "eligible_directed.tsv.gz", sep="\t", usecols=["query", "target"])
    nodes = clu.drop_duplicates("node_id").set_index("node_id").cluster_id
    a, b = ed["query"].map(nodes), ed["target"].map(nodes)
    pair = pd.DataFrame({"x": np.minimum(ed["query"], ed["target"]), "y": np.maximum(ed["query"], ed["target"]),
                         "c": a})[a.notna() & (a == b) & (ed["query"] != ed["target"])].drop_duplicates(["x", "y"])
    within = pair.groupby("c").size()
    nn = nodes.value_counts()
    agree = (within.reindex(nn.index).fillna(0) / (nn * (nn - 1) / 2)).where(nn > 1)
    ann["tomtom_pair_agreement"] = ann.cluster_id.map(agree).round(4)
    ann[["cluster_id", "partition", "tier", "n_nodes", "n_tfs", "coverage", "tomtom_pair_agreement"]].to_csv(
        TAB / "cluster_fidelity.tsv", sep="\t", index=False)
    out["tomtom_pair_agreement_median"] = float(agree.median())

    # sensitivity
    sens = []
    for p in ("monomer", "composite"):
        s = pd.read_csv(R / "seurat" / f"seurat_{p}.tsv", sep="\t")
        for col in [x for x in s.columns if "res." in x or x.startswith("clust_dims")]:
            sens.append(dict(partition=p, setting=col, n_clusters=int(s[col].nunique()),
                             ARI_vs_primary=round(adjusted_rand_score(s.cluster, s[col]), 4)))
    pd.DataFrame(sens).to_csv(TAB / "sensitivity.tsv", sep="\t", index=False)
    out["sensitivity"] = sens

    # figures
    nodes_df = clu.drop_duplicates("node_id").merge(md[["pma_id", "source_db"]], on="pma_id")
    for p in ("monomer", "composite"):
        d = nodes_df[nodes_df.partition == p]
        for col in ("tier", "source_db"):
            fig, ax = plt.subplots(figsize=(8, 7))
            for k, g in d.groupby(col):
                ax.scatter(g.UMAP_1, g.UMAP_2, s=1.5, alpha=0.5, label=f"{k} ({len(g)})", rasterized=True)
            ax.legend(markerscale=6, fontsize=8, frameon=False)
            ax.set_title(f"PMA motif UMAP ({p}) by {col}")
            ax.set_xlabel("UMAP_1"); ax.set_ylabel("UMAP_2")
            fig.savefig(FIG / f"umap_{col}_{p}.png", dpi=200, bbox_inches="tight")
            plt.close(fig)
    (TAB / "validation_summary.json").write_text(json.dumps(out, indent=2, default=str) + "\n")
    print(json.dumps(out, indent=2, default=str)[:4000])


if __name__ == "__main__":
    main()
