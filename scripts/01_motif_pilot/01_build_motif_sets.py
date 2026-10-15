"""Step 1 pilot: convert Codebook 2026 and JASPAR 2026 CORE vertebrates
(non-redundant) into MEME files plus harmonised metadata tables.

Design: docs/STEP1_MOTIF_PILOT_DESIGN.md §3.1–3.2.
Paths come from env (config/pma_env.sh); run via scripts/01_motif_pilot/run_pilot.sh.
"""
import os
import re
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

RAW = Path(os.environ["PMA_MOTIF_RAW"])
OUT = Path(os.environ["PMA_MOTIF_PROCESSED"]) / "v0.1_pilot"
HGNC = Path(os.environ["PMA_HGNC_MAP"])
DATE = os.environ.get("PMA_FETCH_DATE", "2026-10-14")
CB_DIR = RAW / "codebook_2026" / DATE / "unpacked"
JA_DIR = RAW / "jaspar_2026" / DATE
TABLES = CB_DIR / "Nature2026_SupplementaryTables_MOESM3" / "2024-11-25439B-s3"
NT = "ACGT"


def normalise(m):
    """Row-normalise; all-zero rows (spacer/gap positions in composite
    motifs, e.g. Codebook FOSL2_1, VDR_1) become uniform 0.25. Returns
    (matrix, n_zero_rows) so the gap count is kept in metadata."""
    rs = m.sum(axis=1, keepdims=True)
    zero = (rs[:, 0] == 0)
    m = np.where(zero[:, None], 0.25, m / np.where(rs == 0, 1, rs))
    return m, int(zero.sum())


def info_content(p):
    p = np.clip(p, 1e-9, 1)
    return float((2 + (p * np.log2(p)).sum(axis=1)).sum())


def write_meme(motifs, path):
    """motifs: list of (motif_id, alt_name, prob matrix Lx4)."""
    with open(path, "w") as fh:
        fh.write("MEME version 4\n\nALPHABET= ACGT\n\nstrands: + -\n\n"
                 "Background letter frequencies\nA 0.25 C 0.25 G 0.25 T 0.25\n\n")
        for mid, alt, m in motifs:
            fh.write(f"MOTIF {mid} {alt}\nletter-probability matrix: alength= 4 w= {len(m)} nsites= 20 E= 0\n")
            for row in m:
                fh.write(" ".join(f"{x:.6f}" for x in row) + "\n")
            fh.write("\n")


def read_meme(path):
    motifs, cur, mat = [], None, []
    with open(path) as fh:
        lines = fh.readlines()
    for line in lines:
        if line.startswith("MOTIF"):
            if cur:
                motifs.append((*cur, np.array(mat)))
            parts = line.split()
            cur, mat = (parts[1], parts[2] if len(parts) > 2 else ""), []
        elif cur and re.match(r"^\s*[0-9.]+\s+[0-9.]+\s+[0-9.]+\s+[0-9.]+\s*$", line):
            mat.append([float(x) for x in line.split()])
    if cur:
        motifs.append((*cur, np.array(mat)))
    return motifs


def hgnc_resolver():
    h = pd.read_csv(HGNC, sep="\t", dtype=str).fillna("")
    sym = {s.upper(): s for s in h.symbol}
    prev, alias = {}, {}
    for s, p, a in zip(h.symbol, h.previous_symbols, h.alias_symbols):
        for x in filter(None, (t.strip() for t in p.split(","))):
            prev.setdefault(x.upper(), set()).add(s)
        for x in filter(None, (t.strip() for t in a.split(","))):
            alias.setdefault(x.upper(), set()).add(s)

    def resolve(name):
        u = name.upper()
        if u in sym:
            return sym[u], "symbol"
        for table, how in ((prev, "previous"), (alias, "alias")):
            hits = table.get(u, set())
            if len(hits) == 1:
                return next(iter(hits)), how
            if len(hits) > 1:
                return "", f"{how}_ambiguous"
        return "", "unmapped"
    return resolve


def build_codebook(resolve):
    t10 = pd.read_excel(TABLES / "SupplementaryTable10_RepresentPWMs.xlsx", sheet_name="TableS10")
    files = sorted((CB_DIR / "Nature2026_SupplementaryData1_MOESM4" / "SupplementaryData1").glob("*.txt"))
    motifs, rows = [], []
    for f in files:
        lines = f.read_text().splitlines()
        tf = lines[0].split("\t")[1].strip()
        src_id = lines[1].split("\t")[1].strip()
        assert lines[2].split("\t")[1:5] == list(NT), f
        m = np.array([[float(x) for x in ln.split("\t")[1:5]] for ln in lines[3:] if ln.strip()])
        m, n_zero = normalise(m)
        pid = f"CB26_{f.stem}"
        motifs.append((pid, tf, m))
        rows.append(dict(pma_id=pid, file=f.name, tf_file=tf, source_motif_id=src_id,
                         length=len(m), n_zero_rows=n_zero, ic_total=info_content(m)))
    md = pd.DataFrame(rows).merge(t10, how="left", left_on="file", right_on="Representative motif filename")
    md["tf_hgnc"] = md["TF (HGNC)"].fillna(md.tf_file)
    md["evidence_class"] = np.where(md["Motif evidence"].astype(str).str.startswith("Direct"), "direct",
                           np.where(md["Motif evidence"].astype(str).str.startswith("Inferred"), "inferred", "other"))
    res = md.tf_hgnc.map(resolve)
    md["hgnc_current"] = [r[0] or s for r, s in zip(res, md.tf_hgnc)]
    md["hgnc_how"] = [r[1] for r in res]
    n_unjoined = md["Motif ID"].isna().sum()
    print(f"Codebook: {len(md)} PWMs, {md.tf_hgnc.nunique()} TFs, {n_unjoined} without Table-10 row")
    return motifs, md


def build_jaspar(resolve):
    motifs = read_meme(JA_DIR / "JASPAR2026_CORE_vertebrates_non-redundant_pfms_meme.txt")
    con = sqlite3.connect(JA_DIR / "JASPAR2026.sqlite")
    mat = pd.read_sql("select ID, BASE_ID||'.'||VERSION as matrix_id, NAME from MATRIX where COLLECTION='CORE'", con)
    ann = pd.read_sql("select ID, TAG, VAL from MATRIX_ANNOTATION", con)
    ann = ann[ann.TAG.isin(["type", "class", "family", "source", "tax_group"])]
    ann = ann.groupby(["ID", "TAG"]).VAL.agg(";".join).unstack()
    sp = pd.read_sql("select ID, TAX_ID from MATRIX_SPECIES", con).groupby("ID").TAX_ID.agg(
        lambda x: ";".join(map(str, sorted(set(x)))))
    up = pd.read_sql("select ID, ACC from MATRIX_PROTEIN", con).groupby("ID").ACC.agg(";".join)
    meta = mat.set_index("ID").join(ann).join(sp.rename("tax_ids")).join(up.rename("uniprot")).reset_index()
    meta = meta.set_index("matrix_id")
    rows, out = [], []
    for mid, alt, m in motifs:
        m, n_zero = normalise(m)
        pid = f"JA26_{mid}"
        out.append((pid, alt, m))
        r = meta.loc[mid]
        comps = [c for c in re.split(r"::", r.NAME) if c]
        tax = str(r.tax_ids).split(";")
        is_human = "9606" in tax
        mapped = [resolve(c) for c in comps]
        rows.append(dict(pma_id=pid, matrix_id=mid, name=r.NAME, n_components=len(comps),
                         components=";".join(comps),
                         components_hgnc=";".join(h or c.upper() for (h, _), c in zip(mapped, comps)),
                         hgnc_how=";".join(how for _, how in mapped),
                         species_tax=r.tax_ids, is_human=is_human,
                         species_basis="human" if is_human else "ortholog_by_symbol",
                         type=r.get("type"), tf_class=r.get("class"), tf_family=r.get("family"),
                         uniprot=r.get("uniprot"), length=len(m), n_zero_rows=n_zero, ic_total=info_content(m)))
    md = pd.DataFrame(rows)
    print(f"JASPAR CORE vert NR: {len(md)} motifs, human {md.is_human.sum()}, "
          f"heterodimer {(md.n_components > 1).sum()}")
    return out, md


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    resolve = hgnc_resolver()
    cb, cb_md = build_codebook(resolve)
    write_meme(cb, OUT / "codebook2026_representative.meme")
    cb_md.to_csv(OUT / "codebook2026_motif_metadata.tsv", sep="\t", index=False)
    ja, ja_md = build_jaspar(resolve)
    write_meme(ja, OUT / "jaspar2026_core_vert_nr.meme")
    ja_md.to_csv(OUT / "jaspar2026_core_vert_nr_metadata.tsv", sep="\t", index=False)


if __name__ == "__main__":
    main()
