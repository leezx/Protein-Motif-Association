"""Evidence tier + binding context for every motif record (user request 2026-10-16).

Four tiers, one per motif, from the strongest link between motif and protein:
  1 in_vitro      direct in vitro binding assay of the protein (HT-SELEX, PBM,
                  SMiLE-seq, GHT-SELEX, B1H, ...): gold standard
  2 curated_core  not tier 1, but accepted by a curated core collection for
                  this protein (JASPAR CORE, HOCOMOCO H14CORE)
  3 occupancy     genome-wide occupancy/accessibility data: ChIP-seq family
                  (protein = ChIP target) or ATAC/DNase (protein unknown);
                  context = biosample / organ / cell type
  4 unvalidated   no direct experiment linking motif and protein: JASPAR
                  UNVALIDATED (always, even if from SELEX), homology-transferred
                  (CisBP inferred), literature/Transfac compilations, unknown assay

usage: evidence_tier.py <out_dir>   (annotates the v0.2.1 raw layer)
Context for ENCODE ChIP experiments (Factorbook) comes from one ENCODE API
query (biosample, classification, organ / cell slims).
"""
import json
import os
import sys
import urllib.request
from pathlib import Path

import pandas as pd

LAYER = os.environ.get("PMA_RAW_LAYER", "v0.2.1")
PROC = Path(os.environ["PMA_MOTIF_PROCESSED"]) / f"{LAYER}_raw_layer"
ENC = ("https://www.encodeproject.org/search/?type=Experiment&assay_title=TF+ChIP-seq&limit=all"
       "&field=accession&field=biosample_ontology.term_name&field=biosample_ontology.classification"
       "&field=biosample_ontology.organ_slims&field=biosample_ontology.cell_slims&format=json")
TIER_NAME = {1: "in_vitro", 2: "curated_core", 3: "occupancy", 4: "unvalidated"}


def tier(r):
    """(tier, basis) for one metadata row of the raw layer."""
    if r.source_set.startswith("UNVALIDATED"):
        return 4, "JASPAR UNVALIDATED"
    if r.direct_binding_evidence == "transferred":
        return 4, "homology transfer (inferred from another protein)"
    if r.assay_class in ("in_vitro_selection", "in_vitro_array") and r.direct_binding_evidence == "supported":
        return 1, f"in vitro: {r.assay_raw}"
    if (r.source_db == "JASPAR" and r.source_set.startswith("CORE")) or \
            (r.source_db == "HOCOMOCO" and "H14CORE" in (r.hocomoco_collections or r.source_set)):
        return 2, f"curated core ({r.source_db}); assay: {r.assay_raw or 'unknown'}"
    if r.assay_class == "in_vivo_occupancy":
        return 3, f"occupancy: {r.assay_raw}"
    return 4, f"no direct protein-specific experiment ({r.assay_class}: {r.assay_raw or 'unknown'})"


def encode_context():
    req = urllib.request.Request(ENC, headers={"Accept": "application/json", "User-Agent": "PMA"})
    with urllib.request.urlopen(req, timeout=600) as fh:
        g = json.load(fh)["@graph"]
    rows = []
    for e in g:
        bo = e.get("biosample_ontology") or {}
        bo = bo[0] if isinstance(bo, list) else bo
        rows.append(dict(acc=e["accession"], biosample=bo.get("term_name", ""),
                         biosample_class=bo.get("classification", ""),
                         organ=";".join(bo.get("organ_slims", []) or []),
                         cell_type=";".join(bo.get("cell_slims", []) or [])))
    return pd.DataFrame(rows).set_index("acc")


def main(out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    md = pd.read_csv(PROC / "PMA_motif_metadata.tsv", sep="\t", keep_default_na=False, low_memory=False)
    t = [tier(r) for r in md.itertuples()]
    a = pd.DataFrame({"pma_id": md.pma_id, "evidence_tier": [x[0] for x in t],
                      "evidence_class": [TIER_NAME[x[0]] for x in t], "evidence_basis": [x[1] for x in t],
                      "protein": md.motif_tf_assignment, "source_db": md.source_db, "source_set": md.source_set,
                      "species_basis": md.species_basis, "context_assay": md.assay_raw,
                      "context_biosample": md.discovery_biosample})
    ctx = encode_context()
    enc = md.experiment_ids.str.extract(r"ENCODE:(ENCSR\w+)")[0]
    for col in ("biosample", "biosample_class", "organ", "cell_type"):
        a[f"context_{col}"] = enc.map(ctx[col]).fillna("")
    a["context_biosample"] = a.context_biosample.where(a.context_biosample != "", md.discovery_biosample)
    a.loc[a.evidence_tier != 3, ["context_biosample_class", "context_organ", "context_cell_type"]] = ""
    a.to_csv(out / "PMA_motif_evidence_tier.tsv", sep="\t", index=False)
    s = dict(layer=LAYER, records=len(a), by_tier=a.evidence_class.value_counts().to_dict(),
             tier_by_source=pd.crosstab(a.source_db, a.evidence_class).to_dict("index"),
             occupancy_with_organ=int(((a.evidence_tier == 3) & (a.context_organ != "")).sum()),
             occupancy_total=int((a.evidence_tier == 3).sum()))
    (out / "summary.json").write_text(json.dumps(s, indent=2) + "\n")
    print(json.dumps(s, indent=2))


if __name__ == "__main__":
    main(sys.argv[1])
