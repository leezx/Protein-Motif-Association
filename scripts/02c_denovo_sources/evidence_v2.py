"""Step 3b §7.1: motif-level evidence annotation v2 over raw layer v0.3.

v0.2.1 rows: v1 rules (evidence_tier.py: tier, curated core, DBD census,
binding mode, ENCODE context). New de novo rows (all tier 3, protein = ChIP
target where one exists):
  evidence_type      chip_model_derived (BPNet) / chip_denovo_derived (Cistrome) /
                     accessibility_model_derived (ChromBPNet, HDMA) /
                     transcription_model_derived (ProCapNet)
  chip_cognate_status  MotifCompendium direct_type (BPNet only; raw kept)
  binding_mode       indirect (target without DBD) / chip_cognate_supported
                     (DBD target, direct_type A, B-NZ, B-Z) / indirect_association
                     (direct_type X) / no_protein (accessibility, transcription) /
                     unknown
None of these means "direct binding confirmed in this experiment".
v0.2.1 evidence_type: tier 1 direct_in_vitro, tier 2 curated_reference,
tier 3 chip_derived, tier 4 unvalidated.

usage: evidence_v2.py <out_dir>   (env PMA_MOTIF_PROCESSED, PMA_MOTIF_RAW, PMA_HGNC_MAP)
"""
import json
import os
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import evidence_tier as v1  # noqa: E402

PROC = Path(os.environ["PMA_MOTIF_PROCESSED"]) / "v0.3_raw_layer"
V1_TYPE = {1: "direct_in_vitro", 2: "curated_reference", 3: "chip_derived", 4: "unvalidated"}
SUPPORTED = {"cognate_invitro_supported", "paralog_invitro_supported", "b1h_supported"}


def main(out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    md = pd.read_csv(PROC / "PMA_motif_metadata.tsv", sep="\t", keep_default_na=False, low_memory=False)
    new = md.evidence_type != ""
    dbd = v1.dbd_table()
    links = pd.read_csv(PROC / "PMA_motif_tf_links.tsv", sep="\t", keep_default_na=False)
    prot = links[links.tf_hgnc != ""].groupby("pma_id").tf_hgnc.apply(lambda s: sorted(set(s)))
    cur = ((md.source_db == "JASPAR") & md.source_set.str.startswith("CORE")) | \
          ((md.source_db == "HOCOMOCO") & md.hocomoco_collections.str.contains("H14CORE"))
    rows = []
    for r, c, is_new in zip(md.itertuples(), cur, new):
        p = prot.get(r.pma_id, [])
        if not is_new:
            t, basis = v1.tier(r)
            mode, mbasis = v1.binding_mode(t, c, p, dbd)
            et, cog = V1_TYPE[t], ""
        else:
            t, et, cog = 3, r.evidence_type, r.chip_cognate_status
            basis = f"{et}: {r.source_db} {r.model_annotation or r.source_identifier}"
            no_dbd = [x for x in p if x not in dbd]
            if et in ("accessibility_model_derived", "transcription_model_derived"):
                mode, mbasis = "no_protein", "no protein assayed"
            elif not p:
                mode, mbasis = "unknown", "ChIP target not mapped to HGNC"
            elif no_dbd:
                mode, mbasis = "indirect", f"no DBD in TF census: {','.join(no_dbd)}"
            elif cog in SUPPORTED:
                mode, mbasis = "chip_cognate_supported", f"MotifCompendium direct_type {r.direct_type_raw}"
            elif cog == "indirect_association":
                mode, mbasis = "indirect_association", "MotifCompendium direct_type X"
            else:
                mode, mbasis = "unknown", "not confirmed as the target's own DBD motif"
        rows.append(dict(pma_id=r.pma_id, evidence_tier=t, evidence_class=v1.TIER_NAME[t], evidence_type=et,
                         evidence_basis=basis, protein=";".join(p) or r.motif_tf_assignment, source_db=r.source_db,
                         source_set=r.source_set, in_curated_core=bool(c), binding_mode=mode, binding_basis=mbasis,
                         chip_cognate_status=cog, direct_type_raw=r.direct_type_raw,
                         protein_dbd=";".join(dbd.get(x, "none") for x in p),
                         independent_experiment_id=r.independent_experiment_id,
                         independence_status=r.independence_status, context_assay=r.assay_raw,
                         context_biosample=r.discovery_biosample, context_biosample_class=r.biosample_class,
                         context_organ=r.organ, context_cell_type=r.cell_type, context_disease=r.disease,
                         context_study=r.publication, cell_cluster_id=r.cell_cluster_id,
                         cluster_pool=r.cluster_pool, pool_exclusion=r.pool_exclusion))
    a = pd.DataFrame(rows)
    ctx = v1.encode_context()
    enc = md.experiment_ids.str.extract(r"ENCODE:(ENCSR\w+)")[0]
    old = ~new.to_numpy()
    for col in ("biosample_class", "organ", "cell_type"):
        fill = enc.map(ctx[col]).fillna("")
        a.loc[old & (a.evidence_tier == 3).to_numpy(), f"context_{col}"] = fill[old & (a.evidence_tier == 3).to_numpy()]
    a.to_csv(out / "PMA_motif_evidence.tsv", sep="\t", index=False)
    s = dict(layer="v0.3", records=len(a), by_evidence_type=a.evidence_type.value_counts().to_dict(),
             binding_mode=a.binding_mode.value_counts().to_dict(),
             type_by_mode=pd.crosstab(a.evidence_type, a.binding_mode).to_dict("index"),
             cognate_status=a.chip_cognate_status.replace("", "NA").value_counts().to_dict(),
             with_organ=int((a.context_organ != "").sum()))
    (out / "summary.json").write_text(json.dumps(s, indent=1, default=int) + "\n")
    print(json.dumps(s, indent=1, default=int))


if __name__ == "__main__":
    main(sys.argv[1])
