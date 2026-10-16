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

Binding mode (separate axis; is the motif the protein's OWN DBD recognition sequence?):
  direct_curated        protein has a DBD (Codebook 2026 TF census, Supp. Table 14,
                        "Is TF? = Yes") and a curated core collection lists the motif
                        for it (JASPAR CORE, HOCOMOCO H14CORE)
  direct_in_vitro       protein has a DBD and the motif is from an in vitro assay of
                        that protein (tier 1)
  direct_chip_confirmed ChIP motif matching a direct motif of the same TF (TOMTOM v0.1
                        both directions; filled after Step 3) or MotifCompendium
                        direct class A/B (new sources)
  indirect              protein has no DBD (e.g. EP300, POLR2A), or the ChIP motif
                        matches other TFs only (MotifCompendium class X)
  unknown               everything else
For multi-protein motifs every component must have a DBD.

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
CENSUS = (Path(os.environ["PMA_MOTIF_RAW"]) / "codebook_2026" / "2026-10-14" / "unpacked" /
          "Nature2026_SupplementaryTables_MOESM3" / "2024-11-25439B-s3" / "SupplementaryTable14_TFCensus.xlsx")
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


def dbd_table():
    """Current HGNC symbol -> DBD for census TFs, joined on Ensembl ID (the census
    uses older symbols, e.g. T for TBXT, ARNTL for BMAL1)."""
    c = pd.read_excel(CENSUS, sheet_name="TableS14")
    c = c[c["Is TF?"].astype(str).str.strip().str.lower() == "yes"]
    by_ens = c.set_index("TF (Ensembl ID)")["TF DBD(s) (Codebook, Jolma 2026)"].astype(str).to_dict()
    h = pd.read_csv(os.environ["PMA_HGNC_MAP"], sep="\t", keep_default_na=False)
    out = {s: by_ens[e] for s, e in zip(h.symbol, h.ensembl_id) if e in by_ens}
    for s, d in zip(c["TF (HGNC)"], c["TF DBD(s) (Codebook, Jolma 2026)"].astype(str)):
        out.setdefault(s, d)
    return out


def binding_mode(tier_, curated, proteins, dbd):
    """(mode, basis) given the evidence tier, curated-core membership and HGNC proteins."""
    if not proteins:
        return "unknown", "no protein assigned"
    no_dbd = [p for p in proteins if p not in dbd]
    if no_dbd:
        return "indirect", f"no DBD in TF census: {','.join(no_dbd)}"
    if curated and tier_ != 4:
        return "direct_curated", "curated core motif of a DBD TF"
    if tier_ == 1:
        return "direct_in_vitro", "in vitro assay of a DBD TF"
    return "unknown", "not confirmed as the TF's own DBD motif"


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
    dbd = dbd_table()
    links = pd.read_csv(PROC / "PMA_motif_tf_links.tsv", sep="\t", keep_default_na=False)
    prot = links[links.tf_hgnc != ""].groupby("pma_id").tf_hgnc.apply(lambda s: sorted(set(s)))
    cur = ((md.source_db == "JASPAR") & md.source_set.str.startswith("CORE")) | \
          ((md.source_db == "HOCOMOCO") & md.hocomoco_collections.str.contains("H14CORE"))
    a["in_curated_core"] = cur.to_numpy()
    bm = [binding_mode(tt, c, prot.get(p, []), dbd) for tt, c, p in zip(a.evidence_tier, cur, a.pma_id)]
    a["binding_mode"], a["binding_basis"] = [x[0] for x in bm], [x[1] for x in bm]
    a["protein_dbd"] = [";".join(dbd.get(x, "none") for x in prot.get(p, [])) for p in a.pma_id]
    ctx = encode_context()
    enc = md.experiment_ids.str.extract(r"ENCODE:(ENCSR\w+)")[0]
    for col in ("biosample", "biosample_class", "organ", "cell_type"):
        a[f"context_{col}"] = enc.map(ctx[col]).fillna("")
    a["context_biosample"] = a.context_biosample.where(a.context_biosample != "", md.discovery_biosample)
    a.loc[a.evidence_tier != 3, ["context_biosample_class", "context_organ", "context_cell_type"]] = ""
    a.to_csv(out / "PMA_motif_evidence_tier.tsv", sep="\t", index=False)
    s = dict(layer=LAYER, records=len(a), by_tier=a.evidence_class.value_counts().to_dict(),
             binding_mode=a.binding_mode.value_counts().to_dict(),
             mode_by_tier=pd.crosstab(a.evidence_class, a.binding_mode).to_dict("index"),
             tier_by_source=pd.crosstab(a.source_db, a.evidence_class).to_dict("index"),
             occupancy_with_organ=int(((a.evidence_tier == 3) & (a.context_organ != "")).sum()),
             occupancy_total=int((a.evidence_tier == 3).sum()))
    (out / "summary.json").write_text(json.dumps(s, indent=2) + "\n")
    print(json.dumps(s, indent=2))


if __name__ == "__main__":
    main(sys.argv[1])
