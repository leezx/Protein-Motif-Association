"""Step 2: import all sources into the PMA raw motif layer (v0.2.1).

Design: docs/STEP2_MOTIF_IMPORT_DESIGN.md §2-§7 and §12 (v0.2.1 amendment:
HOCOMOCO H14INVITRO/H14INVIVO matrices not identical to an H14CORE matrix).
No motif is dropped; QC only adds flags. Paths from config/pma_env.sh; run
via run_import.sh. PMA_RAW_LAYER=v0.2 rebuilds the frozen v0.2 layer.

Outputs (processed/<PMA_RAW_LAYER>_raw_layer/):
  PMA_motifs_raw.meme, PMA_motif_metadata.tsv,
  PMA_motif_tf_links.tsv, PMA_motif_provenance.tsv
"""
import json
import os
import re
import sqlite3
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pma_motif as pm  # noqa: E402

RAW = Path(os.environ["PMA_MOTIF_RAW"])
LAYER = os.environ.get("PMA_RAW_LAYER", "v0.2.1")
assert LAYER in ("v0.2", "v0.2.1"), LAYER
OUT = Path(os.environ["PMA_MOTIF_PROCESSED"]) / f"{LAYER}_raw_layer"
DATE = os.environ.get("PMA_FETCH_DATE", "2026-10-14")
CB = RAW / "codebook_2026" / DATE
CB_TABLES = CB / "unpacked" / "Nature2026_SupplementaryTables_MOESM3" / "2024-11-25439B-s3"
JA = RAW / "jaspar_2026" / DATE
HO = RAW / "hocomoco_v14" / DATE
CI = RAW / "cisbp_3_10" / DATE
FB = RAW / "factorbook" / DATE

# Codebook / MEX dataset codenames look like 'foggy-red-dalmatian'.
CODENAME = re.compile(r"@[a-z]+-[a-z]+-[a-z]+(?:\+[a-z]+-[a-z]+-[a-z]+)*@")
# Motif collections (not primary experiments) named as a CisBP / JASPAR source.
HGNC_BY_ID = {}
MOTIF_DBS = {"jaspar", "hocomoco", "factorbook", "homer", "codebook", "jolma2026a",
             "jolma2026b", "transfac", "encode", "cepd", "idmmpmm"}


def species_from_tax(tax_ids, tax_group):
    tax = set(str(tax_ids).split(";"))
    if "9606" in tax:
        return "human"
    if "10090" in tax:
        return "mouse_ortholog"
    if str(tax_group) == "vertebrates":
        return "other_vertebrate"
    return "non_vertebrate" if tax_group and str(tax_group) != "nan" else "unknown"


class Builder:
    """Collects motif records, TF links and provenance rows."""

    def __init__(self, resolve):
        self.resolve = resolve
        self.rows, self.links, self.mats = [], [], {}

    def map_tf(self, name, species_basis):
        h, how = self.resolve(name)
        if species_basis != "human" and how != "unmapped":
            how = f"ortholog_by_symbol:{how}"
        return h, how

    def add(self, pid, raw, rec, links):
        """raw: source matrix as parsed (None if withheld). rec: metadata.
        links: [(tf_raw, source_link_status)]."""
        flags = []
        rec = dict(pma_id=pid, **rec)
        if raw is None:
            flags.append("no_matrix_license")
        else:
            bad = pm.check_matrix(raw)
            if bad:
                flags.append("qc_fail_format")
                rec["qc_fail_reason"] = bad
        if not flags:
            m, gaps = pm.normalise(raw)
            if not np.allclose(m.sum(axis=1), 1, atol=1e-6):
                flags.append("qc_fail_norm")
            key, orient = pm.rounded_key(m)
            ic = pm.info_content(m)
            rec.update(length=len(m), ic_total=ic, ic_mean=ic / len(m),
                       n_gap_rows=len(gaps), gap_mask=",".join(map(str, gaps)),
                       raw_matrix_hash=pm.sha1(raw), normalized_matrix_hash=pm.sha1(m),
                       _rkey=key, equiv_orientation=orient)
            if len(m) < 5:
                flags.append("short_lt5")
            if len(m) > 40:
                flags.append("long_gt40")
            if ic / len(m) < 0.5:
                flags.append("low_ic")
            if "qc_fail_norm" not in flags:
                self.mats[pid] = m
        rec["qc_flags"] = ";".join(flags)
        hg = []
        for tf_raw, status in links:
            h, how = self.map_tf(tf_raw, rec.get("species_basis", "unknown"))
            self.links.append(dict(pma_id=pid, source_db=rec["source_db"], tf_raw=tf_raw,
                                   tf_hgnc=h, hgnc_how=how, source_link_status=status))
            hg.append(h or str(tf_raw).upper())
        rec["motif_tf_assignment"] = ";".join(dict.fromkeys(hg))
        self.rows.append(rec)


def base(db, ver, sset, sid, sfile, status="imported"):
    return dict(source_db=db, source_version=ver, fetch_date=DATE, source_set=sset,
                source_motif_id=sid, source_file=sfile, source_status=status)


# ---- Codebook -------------------------------------------------------------

def import_codebook(b):
    t10 = pd.read_excel(CB_TABLES / "SupplementaryTable10_RepresentPWMs.xlsx", sheet_name="TableS10")
    t10 = t10.set_index("Representative motif filename")
    files = sorted((CB / "unpacked" / "Nature2026_SupplementaryData1_MOESM4" /
                    "SupplementaryData1").glob("*.txt"))
    for f in files:
        lines = f.read_text().splitlines()
        tf = lines[0].split("\t")[1].strip()
        sid = lines[1].split("\t")[1].strip()
        assert lines[2].split("\t")[1:5] == list(pm.NT), f
        raw = np.array([[float(x) for x in ln.split("\t")[1:5]] for ln in lines[3:] if ln.strip()])
        r = t10.loc[f.name] if f.name in t10.index else None
        tf = str(r["TF (HGNC)"]) if r is not None and pd.notna(r["TF (HGNC)"]) else \
            re.sub(r"\.(FL|NA|e?DBD\d*)$", "", tf)
        ev = str(r["Motif evidence"]) if r is not None else ""
        assay_raw = r["Motif experiment source"] if r is not None else None
        pub = str(r["Motif source (publication or database)"]) if r is not None else ""
        ident = str(r["Motif source identifier"]) if r is not None else ""
        acls = pm.assay_class(assay_raw)
        inferred = ev.startswith("Inferred")
        species, target = "human", tf
        if inferred:
            mm = re.match(r"Inferred - (\S+) \(.*?,\s*(.+?)\)", ev)
            target = mm.group(1) if mm else ""
            sp = mm.group(2) if mm else ""
            species = ("human" if sp == "Homo sapiens" else
                       "mouse_ortholog" if sp == "Mus musculus" else
                       "other_vertebrate" if sp else "unknown")
        basis, direct = pm.evidence(acls, homology=inferred)
        derived = pub if pub.lower() in MOTIF_DBS else ""
        exp_ids = "" if pub in ("", "nan", "Jolma2026") or derived else f"{pub}:{ident}"
        b.add(f"CB26_{f.stem}", raw, dict(
            **base("Codebook", "Nature2026_SuppData1", "representative", sid, f.name),
            motif_name=tf, assay_raw=assay_raw, assay_class=acls, assayed_target=target,
            assignment_basis=basis, direct_binding_evidence=direct,
            source_link_status=ev.split(" ")[0] if ev else "", species_basis=species,
            source_quality="", is_composite=False, n_components=1, components_hgnc="",
            publication=pub, source_identifier=ident, experiment_ids=exp_ids,
            derived_from=f"{pub}:{ident}" if derived else "",
            codebook_cluster=r["Motif cluster"] if r is not None else np.nan),
            [(tf, ev.split(" ")[0] if ev else "")])


# ---- JASPAR ---------------------------------------------------------------

def jaspar_meta():
    con = sqlite3.connect(JA / "JASPAR2026.sqlite")
    mat = pd.read_sql("select ID, BASE_ID||'.'||VERSION as matrix_id, COLLECTION, NAME from MATRIX", con)
    ann = pd.read_sql("select ID, TAG, VAL from MATRIX_ANNOTATION", con)
    ann = ann[ann.TAG.isin(["type", "class", "family", "source", "tax_group", "medline"])]
    ann = ann.groupby(["ID", "TAG"]).VAL.agg(";".join).unstack()
    sp = pd.read_sql("select ID, TAX_ID from MATRIX_SPECIES", con).groupby("ID").TAX_ID.agg(
        lambda x: ";".join(map(str, sorted(set(x)))))
    return mat.set_index("ID").join(ann).join(sp.rename("tax_ids")).reset_index().set_index("matrix_id")


def import_jaspar(b):
    meta = jaspar_meta()
    for prefix, fname, sset in (
            ("JA26", "JASPAR2026_CORE_vertebrates_non-redundant_pfms_meme.txt", "CORE_vertebrates_nr"),
            ("JU26", "JASPAR2026_UNVALIDATED_non-redundant_pfms_meme.txt", "UNVALIDATED_nr")):
        for mid, _alt, raw in pm.read_meme(JA / fname):
            r = meta.loc[mid]
            comps = [c for c in str(r.NAME).split("::") if c]
            species = species_from_tax(r.tax_ids, r.get("tax_group"))
            acls = pm.assay_class(r.get("type"))
            basis, direct = pm.evidence(acls)
            src = str(r.get("source") or "")
            occ = acls == "in_vivo_occupancy"
            b.add(f"{prefix}_{mid}", raw, dict(
                **base("JASPAR", "2026", sset, mid, fname),
                motif_name=r.NAME, assay_raw=r.get("type"), assay_class=acls,
                assayed_target=r.NAME, assignment_basis=basis, direct_binding_evidence=direct,
                source_link_status="", species_basis=species, species_raw=r.tax_ids,
                source_quality=r.COLLECTION, is_composite=len(comps) > 1,
                n_components=len(comps),
                components_hgnc=";".join(b.map_tf(c, species)[0] or c.upper() for c in comps)
                if len(comps) > 1 else "",
                publication=f"PMID:{r.medline}" if str(r.get("medline")) not in ("None", "nan") else "",
                source_identifier=src, experiment_ids="",
                discovery_dataset=src if occ and src and not src.isdigit() else "",
                derived_from=src if src.lower() in MOTIF_DBS else "",
                tf_class=r.get("class"), tf_family=r.get("family")),
                [(c, "") for c in comps])


# ---- HOCOMOCO -------------------------------------------------------------

def hocomoco_experiment(name, origin, dtype):
    if dtype == "H":
        return "", "", ""
    if re.match(r"^E?PEAKS\d+", origin):
        return f"GTRD:{origin}", "", ""
    if CODENAME.search(name):
        return f"CODEBOOK:{origin}", "Codebook", ""
    if re.match(r"^(Yin2017|Jolma2013)\.", origin):
        return selex_key(*origin.split(".")[:3]), "", ""
    if re.match(r"^(Yin|Jolma|Yang)\d{4}\.", origin):
        return f"{origin.split('.')[0]}:{origin}", "", ""
    return f"HOCOMOCO_origin:{origin}", "", ""


def hocomoco_collections():
    """(records, memberships) via pm.merge_hocomoco (design §12).
    v0.2: H14CORE only. v0.2.1 adds H14INVITRO/H14INVIVO entries; an entry is
    merged into an existing record only for an identical count matrix from the
    same source experiment."""
    pcms = pm.read_fasta_pcm(HO / "H14CORE_pcms.txt")
    entries = [("H14CORE", a, pcms[a["name"]]) for a in map(json.loads, open(HO / "H14CORE_annotation.jsonl"))]
    if LAYER != "v0.2":
        for coll in ("H14INVITRO", "H14INVIVO"):
            entries += [(coll, a, a["pcm"]) for a in map(json.loads, open(HO / f"{coll}_annotation.jsonl"))]
    records, memberships = pm.merge_hocomoco(entries)
    if LAYER != "v0.2":
        assert len(records) - 1595 == 840, len(records) - 1595  # design §12 count
    return records, memberships


def import_hocomoco(b, artifacts):
    records, memberships = hocomoco_collections()
    for a, pcm, colls, alt in records:
        om = a["original_motif"]
        dtype = om["motif_datatype"]
        sp = om["species"]
        species = {"HUMAN": "human", "MOUSE": "mouse_ortholog"}.get(sp, "unknown")
        mi = a["masterlist_info"]["species"]
        rec_h = mi.get("HUMAN") or {}
        # HGNC ID first: HOCOMOCO gene_symbol is sometimes a UniProt-style
        # name (ZN704), which is not an HGNC symbol.
        sym = next((HGNC_BY_ID[h] for h in rec_h.get("hgnc", []) if h in HGNC_BY_ID), "") or \
            rec_h.get("gene_symbol") or (mi.get("MOUSE") or {}).get("gene_symbol") or om["tf"]
        acls = pm.assay_class(pm.HOCOMOCO_DATATYPE[dtype])
        basis, direct = pm.evidence(acls)
        exp, derived, _ = hocomoco_experiment(om["name"], om["origin"], dtype)
        tfc = a["masterlist_info"]
        sset = colls[0]
        sfile = "H14CORE_pcms.txt" if sset == "H14CORE" else f"{sset}_annotation.jsonl"
        extra = {} if LAYER == "v0.2" else dict(
            hocomoco_collections=";".join(colls), hocomoco_alt_names=";".join(alt))
        b.add(f"HO14_{a['name']}", pcm, dict(
            **base("HOCOMOCO", "v14", sset, a["name"], sfile),
            motif_name=a["name"], assay_raw=pm.HOCOMOCO_DATATYPE[dtype], assay_class=acls,
            assayed_target=om["tf"], assignment_basis=basis, direct_binding_evidence=direct,
            source_link_status="", species_basis=species, species_raw=sp,
            source_quality=a["quality"], is_composite=False, n_components=1, components_hgnc="",
            publication="", source_identifier=om["name"], experiment_ids=exp,
            discovery_dataset=om["origin"] if dtype == "P" else "",
            derived_from=f"Codebook:{om['name']}" if derived else "",
            hocomoco_datatype_all=a["datatype"], tfclass_id=tfc.get("tfclass_id"),
            tf_class=tfc.get("tfclass_class"), tf_family=tfc.get("tfclass_family"),
            tfclass_superclass=tfc.get("tfclass_superclass"),
            artifact_flag=artifacts.get(om["name"], ""), **extra),
            [(sym, "")])
    return pd.DataFrame(memberships)


# ---- CisBP ----------------------------------------------------------------

def import_cisbp(b):
    d = CI / "unpacked"
    t = pd.read_csv(d / "CisBP_3_10_Homo_sapiens_PWMs_TFinfo" / "TF_Information_all_motifs.txt",
                    sep="\t", dtype=str, keep_default_na=False)
    t.columns = [c if i != 13 else "DBID_motif" for i, c in enumerate(t.columns)]
    t = t[t.Motif_ID != "."]
    pw = d / "EntireDataset_PWMs" / "pwms"
    for mid, g in t.groupby("Motif_ID", sort=True):
        f = pw / f"{mid}.txt"
        assert f.name == f"{mid}.txt" and f.exists(), mid  # name checked per motif (§2)
        x = pd.read_csv(f, sep="\t")
        raw = None if x.empty else x[list(pm.NT)].to_numpy(float)
        r = g.iloc[0]
        acls = pm.assay_class(r.Motif_Type if r.Motif_Type not in ("NULL", "") else r.MSource_Type)
        has_d = (g.TF_Status == "D").any()
        basis, direct = pm.evidence(acls, homology=not has_d)
        src = str(r.MSource_Identifier)
        derived = src.lower() in MOTIF_DBS
        b.add(f"CI310_{mid}", raw, dict(
            **base("CisBP", "3.10", "Homo_sapiens_all_motifs", mid, f"pwms/{mid}.txt",
                   status="imported" if raw is not None else "no_matrix_license"),
            motif_name=";".join(dict.fromkeys(g.TF_Name)), assay_raw=r.Motif_Type, assay_class=acls,
            assayed_target=";".join(dict.fromkeys(g.TF_Name[g.TF_Status == "D"])),
            assignment_basis=basis, direct_binding_evidence=direct,
            source_link_status=";".join(sorted(set(g.TF_Status))),
            species_basis="human" if has_d else "unknown", source_quality="",
            is_composite=False, n_components=1, components_hgnc="",
            publication=f"PMID:{r.PMID}" if r.PMID not in ("NULL", None) else "",
            source_identifier=f"{src}:{r.DBID_motif}",
            experiment_ids="" if derived or r.DBID_motif in ("NULL", None) else f"{src}:{r.DBID_motif}",
            derived_from=f"{src}:{r.DBID_motif}" if derived else "",
            tf_family=r.Family_Name),
            list(zip(g.TF_Name, g.TF_Status)))


# ---- Factorbook -----------------------------------------------------------

def import_factorbook(b):
    t = pd.read_csv(FB / "factorbook_chip_seq_meme_motifs.tsv", sep="\t", dtype=str)
    motifs = pm.read_meme(FB / "unpacked" / "factorbook_chip_seq_meme_motif_catalog.meme")
    ids = [m[0] for m in motifs]
    assert ids == (t.dataset_accession + "_" + t.name).tolist(), "Factorbook TSV/MEME order"
    seen = {}
    for (mid, _alt, raw), r in zip(motifs, t.itertuples()):
        key = f"{r.accession}_{r.name}"
        seen[key] = seen.get(key, 0) + 1
        sid = key if seen[key] == 1 else f"{key}_{seen[key]}"
        species = "human" if r.assembly == "GRCh38" else "mouse_ortholog"
        basis, direct = pm.evidence("in_vivo_occupancy")
        b.add(f"FBC_{sid}", raw, dict(
            **base("Factorbook", DATE, "ChIP-seq_MEME", sid, "factorbook_chip_seq_meme_motif_catalog.meme"),
            motif_name=f"{r.target}:{r.name}", assay_raw="ChIP-seq", assay_class="in_vivo_occupancy",
            assayed_target=r.target, assignment_basis=basis, direct_binding_evidence=direct,
            source_link_status="", species_basis=species, species_raw=r.assembly, source_quality="",
            is_composite=False, n_components=1, components_hgnc="", publication="",
            source_identifier=mid, experiment_ids=f"ENCODE:{r.dataset_accession}",
            discovery_dataset=f"{r.dataset_accession}/{r.accession}", discovery_target=r.target,
            discovery_biosample=r.biosample, encode_audit=r.Information, derived_from=""),
            [(re.sub(r"phospho\w+$", "", r.target), "")])
    return t


# ---- Factorbook HT-SELEX (ZMotif) ----------------------------------------

SELEX_PUB = {"PRJEB9797": ("Yin2017", "PMID:28473536"), "PRJEB3289": ("Jolma2013", "PMID:23332764")}
LIGAND = re.compile(r"^[ACGT]*\d+N[ACGT]*$")


def selex_key(pub, ligand, batch):
    """Experiment-series key shared by ENA aliases and HOCOMOCO origins:
    publication + SELEX ligand + batch (all cycles of one experiment)."""
    return f"SELEX:{pub}.{ligand.upper()}.{batch.upper()}"


def parse_alias(alias):
    t = alias.split("_")
    lig = next(x for x in t if LIGAND.match(x))
    batch = next((x for x in t[1:] if re.fullmatch(r"[A-Z]{1,3}", x)), "")
    cyc = next((x for x in t[1:] if x.isdigit()), "")
    return t[0], lig, batch, cyc


def import_factorbook_selex(b):
    ena = pd.concat([pd.read_csv(FB / f"ena_read_run_{s}.tsv", sep="\t", dtype=str) for s in SELEX_PUB])
    ena = ena.drop_duplicates("run_accession").set_index("run_accession")
    for run, _alt, raw in pm.read_meme(FB / "unpacked" / "all-selex-motifs.meme"):
        r = ena.loc[run]  # KeyError = unresolved run; all 6,700 resolve
        tf, lig, batch, cyc = parse_alias(r.sample_alias)
        pub, pmid = SELEX_PUB[r.study_accession]
        assay = "Methyl-HT-SELEX" if str(r.sample_title).startswith("mHT-SELEX") else "HT-SELEX"
        # Jolma 2013 includes mouse proteins, named in mouse case (e.g. Msx3)
        species = "mouse_ortholog" if re.search(r"[a-z]", tf) else "human"
        basis, direct = pm.evidence("in_vitro_selection")
        b.add(f"FBS_{run}", raw, dict(
            **base("Factorbook", "2026-10-15", "HT-SELEX_ZMotif", run, "all-selex-motifs.meme"),
            motif_name=tf, assay_raw=assay, assay_class="in_vitro_selection", assayed_target=tf,
            assignment_basis=basis, direct_binding_evidence=direct, source_link_status="",
            species_basis=species, species_raw=r.scientific_name, source_quality="",
            is_composite=False, n_components=1, components_hgnc="", publication=pmid,
            source_identifier=r.sample_alias,
            experiment_ids=f"ENA:{run};{selex_key(pub, lig, batch)}",
            selex_cycle=cyc, derived_from=""),
            [(tf, "")])


# ---- curation labels (Codebook Supp. Tables 13 and 16) --------------------

def artifact_ids():
    t = pd.read_excel(CB_TABLES / "SupplementaryTable16_ArtifactMotifs.xlsx", sheet_name="TableS16")
    t = t.dropna(subset=[t.columns[2]])
    typ = t[t.columns[0]].ffill() if t[t.columns[0]].isna().any() else t[t.columns[0]]
    return {re.sub(r"\.(pcm|pwm|ppm)$", "", str(i)): str(a).split("\n")[0]
            for i, a in zip(t[t.columns[2]], typ)}


def curation_labels(md, fb):
    """Table 13 rows -> PMA motifs where the source ID resolves.
    HOCOMOCO v12 IDs do not exist in v14 and stay unmapped."""
    t = pd.read_excel(CB_TABLES / "SupplementaryTable13_ExtPWMCuration.xlsx", sheet_name="TableS13")
    fb = fb.assign(pid="FBC_" + fb.accession + "_" + fb.name)
    rows = []
    for r in t.itertuples():
        label = f"{r[7]}|{r[6]}"
        hits = []
        if r.Source.startswith("Factorbook"):
            enc = str(r[1 + 3])  # experiment identifier column
            hits = fb.pid[(fb.dataset_accession == enc) & (fb.name == r.Consensus)].tolist()
        elif r.Source.startswith("Jaspar"):
            hits = md.pma_id[md.source_motif_id.str.split(".").str[0] ==
                             str(r[2]).split(".")[0]].tolist()
            hits = [h for h in hits if h.startswith(("JA26_", "JU26_"))]
        rows.append(dict(tf=r.TF, pwm_id=r[2], source=r.Source, label=label,
                         consistent_ok=(r[6] == "consistent with codebook motif" and r[7] == "ok"),
                         pma_ids=";".join(dict.fromkeys(hits)), n_mapped=len(set(hits))))
    return pd.DataFrame(rows)


# ---- main -----------------------------------------------------------------

def main():
    global HGNC_BY_ID
    OUT.mkdir(parents=True, exist_ok=True)
    h = pd.read_csv(os.environ["PMA_HGNC_MAP"], sep="\t", dtype=str)
    HGNC_BY_ID = dict(zip(h.hgnc_id.str.replace("HGNC:", "", regex=False), h.symbol))
    b = Builder(pm.hgnc_resolver(os.environ["PMA_HGNC_MAP"]))
    arts = artifact_ids()
    import_codebook(b)
    import_jaspar(b)
    ho_members = import_hocomoco(b, arts)
    import_cisbp(b)
    fb = import_factorbook(b)
    import_factorbook_selex(b)
    md = pd.DataFrame(b.rows)
    assert md.pma_id.is_unique, md.pma_id[md.pma_id.duplicated()].tolist()[:5]

    # exact duplicates and rounded-equivalence groups (flag only, never merged)
    for col, grp in (("normalized_matrix_hash", "exact_dup_group"), ("_rkey", "rounded_equiv_group")):
        n = md.groupby(col)[col].transform("size")
        md[grp] = np.where(n > 1, md[col].fillna("").str[:12], "")
    md.loc[md.rounded_equiv_group == "", "equiv_orientation"] = ""
    md = md.drop(columns="_rkey")
    # accession: a resolvable experiment accession (ENCODE ENCSR, GTRD peaks,
    # Codebook experiment ID). publication_record: publication + source
    # record ID, which names the experiment series but is not an accession.
    eid = md.experiment_ids.fillna("")
    md["experiment_identity"] = np.select(
        [eid == "", eid.str.match(r"^(ENCODE|GTRD|CODEBOOK|ENA|SELEX):")],
        ["unknown", "accession"], "publication_record")
    occ = md.assay_class == "in_vivo_occupancy"
    md["discovery_dataset_known"] = np.where(occ, md.discovery_dataset.fillna("") != "", pd.NA)

    cur = curation_labels(md, fb)
    lab = {p: l for ps, l in zip(cur.pma_ids, cur.label) for p in filter(None, ps.split(";"))}
    md["curation_label"] = md.pma_id.map(lab).fillna("")
    cur.to_csv(OUT / "codebook_table13_mapping.tsv", sep="\t", index=False)

    ok = md.qc_flags.fillna("").str.contains("no_matrix_license|qc_fail_format|qc_fail_norm") == False  # noqa: E712
    pm.write_meme([(p, n.replace(" ", "_")[:60], b.mats[p]) for p, n in
                   zip(md.pma_id[ok], md.motif_name[ok].astype(str))], OUT / "PMA_motifs_raw.meme")
    prov_cols = ["pma_id", "source_db", "experiment_ids", "experiment_identity", "publication",
                 "source_identifier", "discovery_dataset", "discovery_target", "discovery_biosample",
                 "discovery_dataset_known", "derived_from"]
    md[prov_cols].to_csv(OUT / "PMA_motif_provenance.tsv", sep="\t", index=False)
    md.to_csv(OUT / "PMA_motif_metadata.tsv", sep="\t", index=False)
    pd.DataFrame(b.links).to_csv(OUT / "PMA_motif_tf_links.tsv", sep="\t", index=False)
    if LAYER != "v0.2":  # one row per HOCOMOCO collection entry (design §12)
        assert set(ho_members.pma_id) <= set(md.pma_id)
        ho_members.to_csv(OUT / "PMA_hocomoco_collection_memberships.tsv", sep="\t", index=False)
    print(md.groupby(["source_db", "source_set"]).size().to_string())
    print(f"total {len(md)}; in MEME {int(ok.sum())}; links {len(b.links)}")


if __name__ == "__main__":
    main()
