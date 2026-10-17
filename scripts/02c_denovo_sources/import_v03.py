"""Step 3b: build raw layer v0.3 = v0.2.1 + de novo sources (design §3, §4.1, §4.3).

Design: docs/STEP3B_V03_INTEGRATION_DESIGN.md rev 1 (frozen). Nothing is
dropped: every parsed profile gets a row; `cluster_pool` + `pool_exclusion`
say whether it enters Step 3b clustering. Matrices of MoDISco profiles are
end-trimmed (contiguous columns IC < 0.25 bits); the untrimmed hash and the
trim are recorded. Run on Argos (paths from env: PMA_MOTIF_RAW,
PMA_MOTIF_PROCESSED, PMA_HGNC_MAP; date via PMA_DENOVO_DATE).

Outputs (processed/v0.3_raw_layer/):
  PMA_motifs_raw.meme, PMA_motif_metadata.tsv, PMA_motif_tf_links.tsv,
  PMA_motif_provenance.tsv, import_summary.json
"""
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "02_motif_import"))
import pma_motif as pm  # noqa: E402

RAW = Path(os.environ["PMA_MOTIF_RAW"])
PROC = Path(os.environ["PMA_MOTIF_PROCESSED"])
DATE = os.environ.get("PMA_DENOVO_DATE", "2026-10-16")
OUT = Path(os.environ.get("PMA_V03_OUT", PROC / "v0.3_raw_layer"))  # override for test runs
ENC = RAW / "encode_grammar" / DATE
CIS = RAW / "cistrome_db2" / DATE
HD = RAW / "hdma_2026" / DATE

TRIM_IC = 0.25          # §3.4 contiguous end trimming
MIN_LEN, LONG = 5, 30   # §3.4
CIS_MIN_QC, CIS_MIN_LOGP = 5, 10.0   # §3.2
CIS_QC = ("map", "peaks", "fastqc", "frip", "pbc", "dhs")
ENCODE_PMIDS = {22955616, 32728249}  # ENCODE consortium papers (2012, 2020)
COGNATE = {"A": "cognate_invitro_supported", "B-NZ": "paralog_invitro_supported", "B-Z": "b1h_supported",
           "C": "cognate_unconfirmed", "X": "indirect_association"}
NEW_COLS = ["evidence_type", "model_type", "model_annotation", "head", "posneg", "pattern",
            "n_seqlets", "mc_join", "mc_flag_remove", "mc_flag_type", "direct_type_raw",
            "chip_cognate_status", "mc_num_subunit", "composite_status", "mc_cluster_name",
            "cis_zscore", "cis_log10p", "cis_numhits", "cis_qc_pass", "cis_peaks_pass", "cis_pmid",
            "biosample_class", "organ", "cell_type", "disease", "cell_cluster_id",
            "hdma_merged_pattern", "independent_experiment_id", "independence_status",
            "untrimmed_length", "trim_left", "trim_right", "untrimmed_hash",
            "cluster_pool", "pool_exclusion"]


def col_ic(m):
    p = np.clip(m, 1e-9, 1)
    return 2 + (p * np.log2(p)).sum(axis=1)


def trim(m):
    """Contiguous end columns with IC < TRIM_IC removed; internal kept."""
    ic = col_ic(m)
    keep = np.flatnonzero(ic >= TRIM_IC)
    if len(keep) == 0:
        return m[:0], len(m), 0
    lo, hi = keep[0], keep[-1] + 1
    return m[lo:hi], int(lo), int(len(m) - hi)


class Rows:
    """New-source records in the v0.2.1 metadata schema + NEW_COLS."""

    def __init__(self, resolve):
        self.resolve, self.rows, self.links, self.mats = resolve, [], [], {}

    def add(self, pid, raw, rec, tfs, trim_it, reasons):
        rec = dict(pma_id=pid, species_basis="human", fetch_date=DATE, source_status="imported", **rec)
        flags = []
        bad = pm.check_matrix(raw)
        if bad:
            flags.append("qc_fail_format")
            rec["qc_fail_reason"] = bad
            reasons = reasons + ["qc_fail_format"]
        else:
            m, gaps = pm.normalise(raw)
            rec.update(untrimmed_length=len(m), untrimmed_hash=pm.sha1(m), n_gap_rows=len(gaps))
            if trim_it:
                m, tl, tr = trim(m)
            else:
                tl = tr = 0
            rec.update(trim_left=tl, trim_right=tr)
            if len(m) == 0:
                flags.append("qc_fail_trim_empty")
                reasons = reasons + ["trimmed_empty"]
            else:
                key, orient = pm.rounded_key(m)
                ic = pm.info_content(m)
                rec.update(length=len(m), ic_total=ic, ic_mean=ic / len(m), normalized_matrix_hash=pm.sha1(m),
                           raw_matrix_hash=pm.sha1(raw), _rkey=key, equiv_orientation=orient)
                if len(m) < MIN_LEN:
                    flags.append("short_lt5")
                    reasons = reasons + ["short_lt5"]
                if len(m) > LONG:
                    flags.append("long_gt30")
                if ic / len(m) < 0.5:
                    flags.append("low_ic")
                self.mats[pid] = m
        rec["qc_flags"] = ";".join(flags)
        rec["cluster_pool"] = not reasons
        rec["pool_exclusion"] = ";".join(dict.fromkeys(reasons))
        hg = []
        for t in tfs:
            h, how = self.resolve(t)
            self.links.append(dict(pma_id=pid, source_db=rec["source_db"], tf_raw=t, tf_hgnc=h, hgnc_how=how,
                                   source_link_status="assayed_target"))
            hg.append(h or str(t).upper())
        rec["motif_tf_assignment"] = ";".join(dict.fromkeys(hg))
        self.rows.append(rec)


# ---- ENCODE BPNet / ChromBPNet / ProCapNet ----------------------------------

MC_NAME = re.compile(r"^(pos|neg)_patterns\..*_(ENCSR\w+)_(counts|profile)_pattern_(\d+)$")
PAT = re.compile(r"^(?:(pos|neg)_patterns\.)?(?:.*_)?pattern_(\d+)$")
PROCAP = re.compile(r"\.(counts|profile)\.(pos|neg)\.motif_(\d+)\.ppm\.fwd\.meme$")


def read_single_ppm(path):
    """ProCapNet *.ppm.fwd.meme: one matrix, no MOTIF line."""
    rows, on = [], False
    for line in open(path):
        if line.startswith("letter-probability matrix"):
            on = True
        elif on and line.strip():
            rows.append([float(x) for x in line.split()])
    return np.array(rows, dtype=float)


def import_encode(b, stats):
    """Per-model PFMs joined to the MotifCompendium per-pattern index on
    (model annotation, head, pattern index, posneg). Three motif-name
    layouts occur: '<pos|neg>_patterns.<...>_<annot>_<head>_pattern_<i>',
    the same without the posneg prefix, and bare 'pattern_<i>'. Without a
    prefix, posneg comes from the index only when exactly one of pos/neg
    exists for the key; otherwise the join is ambiguous/unmatched."""
    models = pd.read_csv(ENC / "models.tsv", sep="\t", dtype=str).fillna("")
    mc = pd.read_csv(ENC / "ENCODE-MotifCompendium.index.tsv", sep="\t", low_memory=False)
    key = mc.name.str.extract(MC_NAME)
    assert key.notna().all().all(), mc.name[key.isna().any(axis=1)].head().tolist()
    mc["k"] = list(zip(key[1], key[2], key[3].astype(int), key[0]))
    dup = mc.k.duplicated(keep=False)
    stats["mc_index_duplicate_keys"] = int(dup.sum())
    mc = dict(zip(mc.k[~dup], mc[~dup].drop(columns="k").to_dict("records")))
    geo = pd.read_csv(ENC / "experiment_dbxrefs.tsv", sep="\t", dtype=str).fillna("")
    parsed = []
    for r in models.itertuples():
        d = ENC / r.model_type / r.annotation
        if not (d / ".done").exists():
            stats["encode_model_missing"] += 1
            continue
        files = sorted(d.iterdir())
        procap = any(f.name.endswith(".ppm.fwd.meme") for f in files)  # ProCapNet layout
        for f in files:
            if procap and f.name.endswith(".ppm.fwd.meme"):
                mm = PROCAP.search(f.name)
                parsed.append((r, f, f.name, read_single_ppm(f), mm.group(1), mm.group(2), int(mm.group(3)), True))
            elif ".PFM.meme" in f.name:
                head = "counts" if f.name.startswith("counts__") else "profile"
                assert f.name.startswith(head + "__"), f
                for mid, _, mat in pm.read_meme(f):
                    mm = PAT.match(mid)
                    assert mm, (f, mid)
                    parsed.append((r, f, mid, mat, head, mm.group(1) or "", int(mm.group(2)), False))
    seen = Counter((p[0].annotation, p[4], p[6], p[5]) for p in parsed)
    for r, f, mid, mat, head, posneg, pat, procap in parsed:
        prefix = "ENPC" if procap else ("ENBP" if r.model_type == "BPNet" else "ENCB")
        row, join = None, "not_applicable"
        if not procap:
            if posneg:
                cands = [posneg]
            else:
                cands = [x for x in ("pos", "neg") if (r.annotation, head, pat, x) in mc]
                stats["encode_name_without_posneg"] += 1
            if seen[(r.annotation, head, pat, posneg)] > 1 or len(cands) > 1:
                join = "ambiguous"
            elif cands and (r.annotation, head, pat, cands[0]) in mc:
                posneg, join = cands[0], "matched"
                row = mc[(r.annotation, head, pat, posneg)]
            else:
                join = "unmatched"
        posneg = posneg or "unknown"
        pid = f"{prefix}_{r.annotation}_{head}_{posneg}_{pat}"
        g = lambda k: (row[k] if row is not None and pd.notna(row[k]) else "")  # noqa: E731
        reasons = []
        if procap:
            reasons.append("procap_annotation_only")
        if head != "counts":
            reasons.append("profile_head")
        if posneg == "neg":
            reasons.append("negative_pattern")
        elif posneg == "unknown":
            reasons.append("posneg_unknown")
        if not procap and join != "matched":
            reasons.append(f"mc_join_{join}")
        elif join == "matched" and str(row["flag_remove"]) == "True":
            reasons.append("mc_flag_remove")
        dt = g("direct_type")
        nsub = g("num_subunit")
        ev = ("transcription_model_derived" if procap else
              "chip_model_derived" if r.model_type == "BPNet" else "accessibility_model_derived")
        exp = r.experiment
        b.add(pid, mat, dict(
            source_db=f"ENCODE_{'ProCapNet' if procap else r.model_type}", source_version="ENCODE4_GRAMMAR",
            source_set=f"{head}_{posneg}", source_motif_id=mid, source_file=f"{r.model_type}/{r.annotation}/{f.name}",
            motif_name=(r.target or g("simple_name") or mid)[:60], assay_raw=r.description,
            assay_class=ev, assayed_target=r.target, assignment_basis="model_derived",
            direct_binding_evidence="", is_composite=bool(nsub and float(nsub) >= 2), n_components=nsub or "",
            publication="ENCODE4", source_identifier=r.file, experiment_ids=f"ENCODE:{exp}" if exp else "",
            discovery_dataset=exp, discovery_target=r.target, discovery_biosample=r.biosample,
            tf_family=g("family"), evidence_type=ev, model_type="ProCapNet" if procap else r.model_type,
            model_annotation=r.annotation, head=head, posneg=posneg, pattern=pat, n_seqlets="",
            mc_join=join, mc_flag_remove=g("flag_remove"), mc_flag_type=g("flag_type"), direct_type_raw=dt,
            chip_cognate_status=COGNATE.get(dt, "") if r.model_type == "BPNet" else "",
            mc_num_subunit=nsub,
            composite_status=("composite" if nsub and float(nsub) >= 2 else
                              "monomer_annotated" if nsub else "unknown"),
            mc_cluster_name=g("cluster_name"), biosample_class=r.biosample_class,
            organ=r.organ_slims, cell_type=r.cell_slims or g("celltype"),
            independent_experiment_id=f"ENCODE:{exp}" if exp else "",
            independence_status="accession" if exp else "unresolved"),
            [r.target] if r.target and r.model_type == "BPNet" else [], not procap, reasons)
    gsm = {}
    for x in geo.itertuples():
        for a in filter(None, x.geo.split(";")):
            gsm[a] = x.experiment
    stats["encode_profiles"] = len(parsed)
    return gsm


# ---- Cistrome ----------------------------------------------------------------

def import_cistrome(b, gsm2enc, stats):
    tsv = pd.read_csv(CIS / "cistrome_denovo.tsv", sep="\t", dtype={"gsm": str})
    mats = {mid: m for mid, _, m in pm.read_meme(CIS / "cistrome_denovo.meme")}
    qc = {}
    with open(CIS / "inspector.jsonl") as fh:
        for line in fh:
            r = json.loads(line)
            j = r.get("qc_judge") or {}
            qc[r.get("id")] = (sum(bool(j.get(k)) for k in CIS_QC), bool(j.get("peaks")))
    for r in tsv.itertuples():
        nqc, peaks = qc.get(r.dcid, (0, False))
        reasons = []
        if nqc < CIS_MIN_QC:
            reasons.append("cis_sample_qc_lt5")
        if not peaks:
            reasons.append("cis_peaks_fail")
        if not (r.pvalue >= CIS_MIN_LOGP and r.zscore < 0):
            reasons.append("cis_motif_stat")
        g = str(r.gsm) if pd.notna(r.gsm) else ""
        if g in gsm2enc:
            iid, ist = f"ENCODE:{gsm2enc[g]}", "crosswalk_encode"
        elif g and pd.notna(r.pmid) and int(r.pmid) in ENCODE_PMIDS:
            iid, ist = f"GEO:{g}", "independence_unresolved"
        elif g:
            iid, ist = f"GEO:{g}", "accession"
        else:
            iid, ist = "", "unresolved"
        b.add(r.motif_id, mats[r.motif_id], dict(
            source_db="Cistrome_DB2", source_version="dc2_MDSeqPos", source_set="denovo",
            source_motif_id=f"{r.dcid}:{r.denovo}", source_file="cistrome_denovo.meme",
            motif_name=str(r.factor)[:60], assay_raw="ChIP-seq (Cistrome MDSeqPos de novo)",
            assay_class="chip_denovo_derived", assayed_target=r.factor, assignment_basis="chip_denovo",
            direct_binding_evidence="", is_composite=False, n_components="", publication=f"PMID:{r.pmid}",
            source_identifier=f"DCid:{r.dcid}", experiment_ids=f"GEO:{g}" if g else "",
            discovery_dataset=g, discovery_target=r.factor, discovery_biosample=r.cell_line,
            evidence_type="chip_denovo_derived", cis_zscore=r.zscore, cis_log10p=r.pvalue,
            cis_numhits=r.numhits, cis_qc_pass=nqc, cis_peaks_pass=peaks, cis_pmid=r.pmid,
            organ=r.tissue, cell_type=r.cell_type, disease=r.disease, composite_status="unknown",
            independent_experiment_id=iid, independence_status=ist),
            [r.factor], False, reasons)
    stats["cistrome_profiles"] = len(tsv)


# ---- HDMA -------------------------------------------------------------------

def import_hdma(b, stats):
    tsv = pd.read_csv(HD / "per_cluster_patterns.tsv", sep="\t")
    mats = {mid: m for mid, _, m in pm.read_meme(HD / "per_cluster_patterns.meme")}
    mp = pd.read_csv(HD / "merged_modisco_patterns_map.tsv", sep="\t")
    comp = mp.groupby("component_pattern").merged_pattern.agg(lambda x: ";".join(sorted(set(x))))
    for r in tsv.itertuples():
        cell, head = r.cluster.rsplit("__", 1)
        posneg = r.posneg.split("_")[0]
        key = f"{cell}__{r.posneg}.{r.pattern}"
        merged = comp.get(key, "")
        reasons = []
        if head != "counts":
            reasons.append("profile_head")
        if posneg != "pos":
            reasons.append("negative_pattern")
        if not merged:
            reasons.append("hdma_not_in_merge")
        b.add("HDMA_" + re.sub(r"[^A-Za-z0-9_.]", "_", r.motif_id), mats[r.motif_id], dict(
            source_db="HDMA", source_version="zenodo16747618", source_set=f"{head}_{posneg}",
            source_motif_id=r.motif_id, source_file="per_cluster_patterns.meme", motif_name=cell[:60],
            assay_raw="scATAC ChromBPNet TF-MoDISco (HDMA)", assay_class="accessibility_model_derived",
            assayed_target="", assignment_basis="model_derived", direct_binding_evidence="",
            is_composite=False, n_components="", publication="HDMA", source_identifier=r.motif_id,
            experiment_ids="", discovery_dataset=cell, discovery_biosample=cell,
            evidence_type="accessibility_model_derived", model_type="ChromBPNet_HDMA", head=head,
            posneg=posneg, pattern=r.pattern, n_seqlets=r.n_seqlets, organ=cell.split("_c")[0],
            cell_cluster_id=cell, hdma_merged_pattern=merged, composite_status="unknown",
            independent_experiment_id="", independence_status="unresolved"),
            [], True, reasons)
    stats["hdma_profiles"] = len(tsv)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    stats = Counter()
    b = Rows(pm.hgnc_resolver(os.environ["PMA_HGNC_MAP"]))
    gsm2enc = import_encode(b, stats)
    import_cistrome(b, gsm2enc, stats)
    import_hdma(b, stats)
    new = pd.DataFrame(b.rows)
    assert new.pma_id.is_unique, new.pma_id[new.pma_id.duplicated()].head().tolist()

    v21 = PROC / "v0.2.1_raw_layer"
    old = pd.read_csv(v21 / "PMA_motif_metadata.tsv", sep="\t", low_memory=False)
    old_ok = ~old.qc_flags.fillna("").str.contains("no_matrix_license|qc_fail_format|qc_fail_norm")
    old["cluster_pool"] = old_ok
    old["pool_exclusion"] = np.where(old_ok, "", "v0.2.1_qc_fail")
    old["evidence_type"] = ""  # filled by evidence annotation v2
    old["composite_status"] = np.where(old.is_composite.astype(str) == "True", "composite", "v0.2.1_monomer")
    old["independent_experiment_id"] = old.experiment_ids.fillna("")
    old["independence_status"] = old.experiment_identity.fillna("unknown")
    assert not set(old.pma_id) & set(new.pma_id)

    # exact-duplicate groups over the whole v0.3 universe (flag only; nodes are
    # built in Step 3b from the RC-collapsed matrix key)
    md = pd.concat([old.drop(columns=["exact_dup_group", "rounded_equiv_group"]),
                    new.drop(columns="_rkey", errors="ignore")], ignore_index=True)
    n = md.groupby("normalized_matrix_hash").normalized_matrix_hash.transform("size")
    md["exact_dup_group"] = np.where(n > 1, md.normalized_matrix_hash.fillna("").str[:12], "")

    old_mats = {mid: m for mid, _, m in pm.read_meme(v21 / "PMA_motifs_raw.meme")}
    ok_old = [p for p in old.pma_id[old_ok] if p in old_mats]
    assert len(ok_old) == int(old_ok.sum()), (len(ok_old), int(old_ok.sum()))
    name = dict(zip(md.pma_id, md.motif_name.astype(str)))
    pm.write_meme([(p, name[p].replace(" ", "_")[:60], old_mats[p]) for p in ok_old] +
                  [(p, name[p].replace(" ", "_")[:60], m) for p, m in b.mats.items()],
                  OUT / "PMA_motifs_raw.meme")
    md.to_csv(OUT / "PMA_motif_metadata.tsv", sep="\t", index=False)
    links = pd.concat([pd.read_csv(v21 / "PMA_motif_tf_links.tsv", sep="\t", dtype=str), pd.DataFrame(b.links)])
    links.to_csv(OUT / "PMA_motif_tf_links.tsv", sep="\t", index=False)
    prov_cols = ["pma_id", "source_db", "experiment_ids", "independent_experiment_id", "independence_status",
                 "publication", "source_identifier", "discovery_dataset", "discovery_target", "discovery_biosample",
                 "model_annotation", "mc_cluster_name", "hdma_merged_pattern", "untrimmed_hash", "trim_left",
                 "trim_right"]
    md[prov_cols].to_csv(OUT / "PMA_motif_provenance.tsv", sep="\t", index=False)

    summ = dict(stats)
    summ["rows_total"] = len(md)
    summ["meme_profiles"] = len(ok_old) + len(b.mats)
    summ["by_source_pool"] = {f"{s}|{p}": int(n) for (s, p), n in md.groupby(["source_db", "cluster_pool"]).size().items()}
    ex = Counter(r for v in new.pool_exclusion for r in filter(None, v.split(";")))
    summ["new_exclusion_reasons"] = dict(ex.most_common())
    summ["mc_join"] = {f"{s}|{j}": int(n) for (s, j), n in new.groupby(["source_db", "mc_join"]).size().items()
                       if j}
    summ["independence_status"] = {f"{s}|{j}": int(n) for (s, j), n in
                                   new.groupby(["source_db", "independence_status"]).size().items()}
    summ["composite_status_pool"] = {k: int(v) for k, v in new[new.cluster_pool].composite_status.value_counts().items()}
    (OUT / "import_summary.json").write_text(json.dumps(summ, indent=1, default=str))
    print(json.dumps(summ, indent=1, default=str))


if __name__ == "__main__":
    main()
