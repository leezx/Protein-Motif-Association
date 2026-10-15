"""Step 2: QC and summary tables for the v0.2 raw layer (design §7, §9).

Small tables go to the repo (results/02_motif_import/); nothing here
changes the processed layer.
"""
import json
import os
from itertools import combinations
from pathlib import Path

import pandas as pd

IN = Path(os.environ["PMA_MOTIF_PROCESSED"]) / "v0.2_raw_layer"
REPO = Path(__file__).resolve().parents[2] / "results" / "02_motif_import"
SRC = ["Codebook", "JASPAR", "HOCOMOCO", "CisBP", "Factorbook"]
FLAGS = ["no_matrix_license", "qc_fail_format", "qc_fail_norm", "short_lt5", "long_gt40", "low_ic"]


def main():
    REPO.mkdir(parents=True, exist_ok=True)
    md = pd.read_csv(IN / "PMA_motif_metadata.tsv", sep="\t", low_memory=False)
    ln = pd.read_csv(IN / "PMA_motif_tf_links.tsv", sep="\t", low_memory=False)
    md["src"] = md.source_db + ":" + md.source_set
    fl = md.qc_flags.fillna("")

    # 1. per-source counts and QC flags
    t = md.groupby("src").agg(n_motifs=("pma_id", "size"))
    for f in FLAGS:
        t[f] = fl.str.contains(f).groupby(md.src).sum()
    t["in_meme"] = (~fl.str.contains("no_matrix_license|qc_fail")).groupby(md.src).sum()
    t["n_tf_hgnc"] = ln.merge(md[["pma_id", "src"]]).query("tf_hgnc == tf_hgnc").groupby("src").tf_hgnc.nunique()
    t["composite"] = md.is_composite.groupby(md.src).sum()
    t.loc["TOTAL"] = t.sum()
    t.loc["TOTAL", "n_tf_hgnc"] = ln.tf_hgnc.nunique()  # union, not a sum
    t.to_csv(REPO / "source_counts_qc.tsv", sep="\t")

    # 2. evidence model and species by source
    ev = pd.concat({
        "assay_class": pd.crosstab(md.src, md.assay_class),
        "direct_binding_evidence": pd.crosstab(md.src, md.direct_binding_evidence),
        "species_basis": pd.crosstab(md.src, md.species_basis),
        "experiment_identity": pd.crosstab(md.src, md.experiment_identity),
    }, axis=1)
    ev[("derived_from", "recorded")] = md.derived_from.notna().groupby(md.src).sum()
    ev.to_csv(REPO / "evidence_by_source.tsv", sep="\t")

    # 3. length / IC distribution
    ok = md.length.notna()
    q = md[ok].groupby("src")[["length", "ic_mean"]].describe(percentiles=[.1, .5, .9])
    q.columns = [f"{a}_{b}" for a, b in q.columns]
    bins = pd.cut(md.length, [0, 8, 10, 12, 15, 1000], labels=["<=8", "9-10", "11-12", "13-15", ">15"])
    q = q.join(pd.crosstab(md.src[ok], bins[ok]).add_prefix("len_"))
    q.round(3).to_csv(REPO / "length_ic_by_source.tsv", sep="\t")

    # 4. TF coverage overlap (HGNC symbols), all links vs human direct-binding-supported
    def tfsets(sub):
        x = ln.merge(sub[["pma_id"]]).dropna(subset=["tf_hgnc"])
        return {s: set(x.tf_hgnc[x.source_db == s]) for s in SRC}
    rows = []
    for label, sub in (("any_link", md),
                       ("human_supported", md[(md.direct_binding_evidence == "supported") &
                                              (md.species_basis == "human")])):
        s = tfsets(sub)
        union = set().union(*s.values())
        for a in SRC:
            others = set().union(*(s[b] for b in SRC if b != a))
            rows.append(dict(set=label, source=a, n_tf=len(s[a]), unique_to_source=len(s[a] - others),
                             union=len(union)))
        for a, b in combinations(SRC, 2):
            rows.append(dict(set=label, source=f"{a}&{b}", n_tf=len(s[a] & s[b])))
    pd.DataFrame(rows).to_csv(REPO / "tf_coverage_overlap.tsv", sep="\t", index=False)

    # 5. exact / rounded duplicate groups across sources
    dd = []
    for col in ("exact_dup_group", "rounded_equiv_group"):
        g = md.dropna(subset=[col]).groupby(col).source_db.agg(lambda x: "+".join(sorted(set(x))))
        dd.append(g.value_counts().rename_axis("sources").reset_index(name="n_groups").assign(kind=col))
    pd.concat(dd).to_csv(REPO / "duplicate_groups_by_sources.tsv", sep="\t", index=False)

    # 6. provenance of occupancy-derived motifs
    occ = md[md.assay_class == "in_vivo_occupancy"]
    prov = occ.groupby("src").agg(n=("pma_id", "size"),
                                  discovery_dataset_known=("discovery_dataset_known", lambda x: (x == True).sum()))  # noqa: E712
    prov.to_csv(REPO / "occupancy_discovery_dataset.tsv", sep="\t")

    cur = pd.read_csv(IN / "codebook_table13_mapping.tsv", sep="\t")
    summary = dict(
        n_motifs=int(len(md)), n_in_meme=int(t.loc["TOTAL", "in_meme"]),
        n_links=int(len(ln)), n_tf_hgnc_any=int(ln.tf_hgnc.nunique()),
        unmapped_links=ln[ln.hgnc_how == "unmapped"].groupby("source_db").size().to_dict(),
        exact_dup_motifs=int(md.exact_dup_group.notna().sum()),
        rounded_equiv_motifs=int(md.rounded_equiv_group.notna().sum()),
        table13_rows=int(len(cur)), table13_mapped=int((cur.n_mapped > 0).sum()),
        table13_consistent_ok=int(cur.consistent_ok.sum()),
        table13_consistent_ok_mapped=int((cur.consistent_ok & (cur.n_mapped > 0)).sum()),
        table13_mapped_by_source=cur[cur.n_mapped > 0].source.value_counts().to_dict(),
        artifact_flagged=int(md.artifact_flag.notna().sum()),
    )
    (REPO / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
