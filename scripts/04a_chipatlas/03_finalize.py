"""Step 4a §4/§6/§8: final experiment table, reconciliation report, column contract and MANIFEST.

usage: 03_finalize.py <raw_release_dir> <stage_dir> <release_dir>
Inputs (stage_dir): experiments_stage1.tsv.gz, peak_counts_all.tsv (every experiment ID in the archive, any class),
peak_counts_included.tsv, peaks_summary.json, metadata_reconciliation.json, rejected_records.tsv.
Release dir must already hold PMA_chipatlas_<genome>_occupancy.bed.gz (+ .tbi; genome = PMA_GENOME). Writes there:
  PMA_chipatlas_<genome>_experiments.tsv.gz, PMA_chipatlas_<genome>_occupancy.as, schema.json,
  reconciliation_report.json, MANIFEST.json
"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pandas as pd

import chipatlas_rules as cr
import genome_config as gc

RELEASE = gc.CFG["release"]
NS, AUTH = gc.CFG["gene_ns"], gc.CFG["gene_authority"]
A_COLS = [  # name, autoSql type, description
    ("chrom", "string", f"Reference sequence chromosome or scaffold (source naming, {gc.G})"),
    ("chromStart", "uint", "Start position, 0-based"),
    ("chromEnd", "uint", "End position, half-open"),
    ("name", "string", "ChIP-Atlas experiment accession (SRX/ERX/DRX)"),
    ("score", "uint", "Browser score = min(1000, max(0, round(macs2_qscore)))"),
    ("strand", "char[1]", "Always ."),
    ("macs2_qscore", "float", "-10*log10(MACS2 q-value), raw, uncapped (q < 1e-5 archive)"),
    ("antigen_raw", "string", "ChIP-Atlas curated antigen"),
    (gc.SYM_COL, "string", f"{AUTH} approved symbol or ."),
    (gc.ID_COL, "string", f"{AUTH} ID or ."),
    ("antigen_map_status", "string", "approved_exact|previous_symbol|unique_alias|manual_curated|ambiguous|"
                                     "complex_or_family|tag_only|non_gene_target|unmapped"),
    ("antigen_class", "string", "ChIP-Atlas antigen class"),
    ("cell_type_class", "string", "ChIP-Atlas cell type class"),
    ("cell_type", "string", "ChIP-Atlas cell type"),
    ("tissue", "string", "Tissue (cell-line primary tissue or sample tissue) or ."),
    ("biosample_type", "string", "cell_line|primary_cells|primary_tissue|organoid|stem_cell_derived|other|unknown"),
    ("disease", "string", "Disease / tissue diagnosis as reported, or ."),
    ("treatment_status", "string", "treated|untreated|not_reported|ambiguous"),
    ("antibody_id", "string", "vendor:catalog, ENCAB or RRID when explicit, else ."),
    ("antibody_label", "string", "Short antibody description"),
    ("antibody_status", "string", "catalog_resolved|clone_resolved|description_only|not_reported|ambiguous"),
    ("gsm", "string", "GEO sample accession or ."),
    ("study_id", "string", "Study accession or . (not resolved in v1)"),
    ("qc_flags", "string", "Experiment QC flags plus per-peak blacklist_majority_overlap, ; separated, or ."),
]


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 24), b""):
            h.update(b)
    return h.hexdigest()


def main(raw, stage, rel):
    raw, stage, rel = Path(raw), Path(stage), Path(rel)
    bed = rel / f"{gc.PREFIX}_occupancy.bed.gz"
    assert bed.exists() and Path(str(bed) + ".tbi").exists(), "occupancy BED and tabix index must exist"
    b = pd.read_csv(stage / "experiments_stage1.tsv.gz", sep="\t", dtype=str, keep_default_na=False)
    inc = pd.read_csv(stage / "peak_counts_included.tsv", sep="\t", dtype={"n_peaks_in_archive": int})
    allc = pd.read_csv(stage / "peak_counts_all.tsv", sep="\t", names=["experiment_id", "n"], dtype={"n": int})
    b = b.merge(inc, on="experiment_id", how="left")
    b["n_peaks_in_archive"] = b.n_peaks_in_archive.fillna(0).astype(int)
    rep = pd.to_numeric(b.n_peaks_reported.replace(".", None), errors="coerce")
    mism = rep.notna() & (rep != b.n_peaks_in_archive)
    b["qc_flags"] = [(f if f != "." else "") for f in b.qc_flags]
    b.loc[mism, "qc_flags"] = [(f + ";" if f else "") + "peak_count_mismatch" for f in b.qc_flags[mism]]
    b.loc[b.n_peaks_in_archive == 0, "qc_flags"] = [(f + ";" if f else "") + "no_peaks_in_archive"
                                                     for f in b.qc_flags[b.n_peaks_in_archive == 0]]
    b["qc_flags"] = b.qc_flags.replace("", ".")
    cols = [c for c in b.columns if c not in ("title", "attributes_raw", "metadata_release", "rules_version")] + \
        ["title", "attributes_raw", "metadata_release", "rules_version"]
    b = b[cols]
    b.to_csv(rel / f"{gc.PREFIX}_experiments.tsv.gz", sep="\t", index=False)

    # reconciliation: every experiment ID in the archive is in scope, out of scope (other class / genome) or
    # missing from the metadata snapshot (quarantined)
    # one experimentList row per (experiment, genome): an ID may also be listed for another assembly (hg19, mm39)
    meta_ids, meta_g = set(), set()
    with open(raw / "experimentList.tab", encoding="utf-8", errors="replace") as f:
        for line in f:
            r = line.split("\t", 4)
            if len(r) >= 3:
                meta_ids.add(r[0])
                if r[1] == gc.G:
                    meta_g.add(r[0])
    scope = set(b.experiment_id)
    cat = allc.experiment_id.map(lambda i: "in_scope" if i in scope else
                                 ("missing_from_metadata" if i not in meta_ids else
                                  ("other_genome" if i not in meta_g else "out_of_scope_class")))
    by = allc.assign(cat=cat).groupby("cat").n.agg(["count", "sum"])
    ps = json.loads((stage / "peaks_summary.json").read_text())
    md = json.loads((stage / "metadata_reconciliation.json").read_text())
    rec = dict(
        release=RELEASE, duplicate_metadata_keys=md["duplicate_ids"], bad_ids=md["n_bad_ids"],
        archive_experiments_by_category={k: dict(experiments=int(v["count"]), rows=int(v["sum"]))
                                         for k, v in by.iterrows()},
        archive_rows_total=int(allc.n.sum()),
        in_scope_rows_streamed=ps["rows_in"], rows_written=ps["rows_out"], rows_rejected=ps["rejected"],
        sort_violations=ps["sort_violations"], chromosomes=ps["chromosomes"],
        blacklist_majority_overlap_rows=ps["blacklist_majority_overlap"],
        metadata_in_scope=len(b), metadata_in_scope_without_peaks=int((b.n_peaks_in_archive == 0).sum()),
        peak_count_mismatch_experiments=int(mism.sum()),
        peak_count_mismatch_examples=b.loc[mism, ["experiment_id", "n_peaks_reported", "n_peaks_in_archive"]]
        .head(10).to_dict("records"),
        missing_from_metadata_examples=allc.experiment_id[cat == "missing_from_metadata"].head(20).tolist())
    rec["rows_accounted"] = (rec["archive_rows_total"] ==
                             sum(v["rows"] for v in rec["archive_experiments_by_category"].values()) and
                             rec["in_scope_rows_streamed"] == rec["rows_written"] + sum(ps["rejected"].values()))
    assert rec["sort_violations"] == 0, "unsorted output: external sort required before release"
    assert rec["rows_accounted"], "row accounting failed"
    (rel / "reconciliation_report.json").write_text(json.dumps(rec, indent=1) + "\n")

    as_txt = [f'table {gc.PREFIX}_occupancy', f'"{RELEASE}: ChIP-Atlas {gc.G} TF/other-protein and RNA '
              'polymerase ChIP-seq peaks (MACS2 q < 1e-5), one row per experiment peak"', "("]
    as_txt += [f'    {t} {n};    "{d}"' for n, t, d in A_COLS] + [")"]
    (rel / f"{gc.PREFIX}_occupancy.as").write_text("\n".join(as_txt) + "\n")
    schema = dict(release=RELEASE, format="BED6+18, 0-based half-open, bgzip + tabix, no header",
                  columns=[dict(index=i + 1, name=n, type=t, description=d) for i, (n, t, d) in enumerate(A_COLS)],
                  missing_value=".", key=f"name = experiment_id in {gc.PREFIX}_experiments.tsv.gz",
                  notes=["A row is a ChIP-Atlas peak interval of one experiment: evidence of chromatin association "
                         "of the assayed antigen, not proof of direct DNA contact; no merging across experiments.",
                         "Filtering macs2_qscore >= 100 / >= 200 is a peak-score view of the q < 1e-5 calls; it is "
                         "NOT equivalent to the ChIP-Atlas q < 1e-10 / 1e-20 archives (separate peak calls; pilot §7).",
                         "QC flags are warnings; nothing was filtered on them."])
    (rel / "schema.json").write_text(json.dumps(schema, indent=1) + "\n")

    commit = subprocess.run(["git", "-C", str(Path(__file__).parent), "rev-parse", "HEAD"], capture_output=True,
                            text=True).stdout.strip()
    inputs = {p.name: sha256(p) for p in sorted(raw.glob("*")) if p.is_file() and p.suffix in (".tab", ".gz")}
    inputs.update({f"reference/{p.name}": sha256(p) for p in sorted((raw / "reference").glob("*"))
                   if p.is_file() and p.name != "MD5SUMS"})
    outputs = {p.name: sha256(p) for p in sorted(rel.glob("*")) if p.is_file() and p.name != "MANIFEST.json"}
    man = dict(release=RELEASE, design="docs/STEP4A_CHIPATLAS_OCCUPANCY_DESIGN.md", code_commit=commit,
               rules_version=cr.RULES_VERSION,
               sources=dict(peaks=f"https://chip-atlas.dbcls.jp/data/{gc.G}/allPeaks_light/{gc.CFG['peaks']} "
                                  f"(Last-Modified {gc.CFG['peaks_date']})",
                            metadata="https://chip-atlas.dbcls.jp/data/metadata/experimentList.tab "
                                     "(Last-Modified 2026-10-14)",
                            **gc.CFG["sources"]),
               counts=dict(experiments=len(b), experiments_with_peaks=int((b.n_peaks_in_archive > 0).sum()),
                           peak_rows=ps["rows_out"]),
               input_sha256=inputs, output_sha256=outputs)
    (rel / "MANIFEST.json").write_text(json.dumps(man, indent=1) + "\n")
    print(json.dumps({k: v for k, v in rec.items() if not k.endswith("examples")}, indent=1))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3])
