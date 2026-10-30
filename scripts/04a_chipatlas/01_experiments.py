"""Step 4a §4: experiment table (Output B, pre-peak stage) from ChIP-Atlas experimentList.tab.

usage: 01_experiments.py <raw_release_dir> <out_dir>
  -> <out_dir>/experiments_stage1.tsv.gz   one row per in-scope experiment of PMA_GENOME (B without archive peak counts)
     <out_dir>/scope_ids.txt               in-scope experiment IDs (for the peak filter)
     <out_dir>/annotation_suffix.tsv       experiment_id + Output A columns 8-24 (minus per-peak flags)
     <out_dir>/metadata_reconciliation.json  counts by genome/class, duplicate keys, mapping summaries
Scope (§2): genome PMA_GENOME (genome_config.py; default hg38, §19 for mm10) and antigen class 'TFs and others'
or 'RNA polymerase'. PMA_OCC_CLASSES (| separated)
overrides the classes, e.g. PMA_OCC_CLASSES=Histone for the §10 histone build.
"""
import collections
import csv
import gzip
import json
import os
import re
import sys
from pathlib import Path

import chipatlas_rules as cr
import genome_config as gc

SCOPE = tuple(os.environ.get("PMA_OCC_CLASSES", "TFs and others|RNA polymerase").split("|"))
ID_RE = re.compile(r"^[SED]RX\d+$")
A_COLS = ["antigen_raw", gc.SYM_COL, gc.ID_COL, "antigen_map_status", "antigen_class",
          "cell_type_class", "cell_type", "tissue", "biosample_type", "disease", "treatment_status", "antibody_id",
          "antibody_label", "antibody_status", "gsm", "study_id", "qc_flags"]
HERE = Path(__file__).resolve().parent


def num(x, f=float):
    try:
        return f(x)
    except (TypeError, ValueError):
        return None


def main(raw, out):
    raw, out = Path(raw), Path(out)
    out.mkdir(parents=True, exist_ok=True)
    ref = raw / "reference"
    if gc.G == "hg38":
        genes = cr.load_hgnc(ref / "hgnc_complete_set.txt")
        tf = {line.strip() for line in open(ref / "lambert2018_TF_names_v_1.01.txt") if line.strip()}
    else:  # mm10: MGI symbols; TF set and chromatin groups from MGI GO annotations (§19.3)
        go_cls, tf = cr.load_go_classes(ref / "mgi.gaf.gz", ref / "go-basic.obo")
        genes = cr.load_mgi(ref / "MRK_List1.rpt", {s: v[1] for s, v in go_cls.items()})
    exc = cr.load_exceptions(HERE.parent.parent / "config" / gc.CFG["exceptions"])
    seen, rows, stats = set(), [], collections.Counter()
    dup, bad_id = [], []
    with open(raw / "experimentList.tab", encoding="utf-8", errors="replace") as f:
        for line in f:
            r = line.rstrip("\n").split("\t")
            if len(r) < 9:
                stats["short_row"] += 1
                continue
            stats[f"genome:{r[1]}"] += 1
            if r[1] != gc.G:
                continue
            stats[f"{gc.G}_class:{r[2]}"] += 1
            if r[2] not in SCOPE:
                continue
            eid = r[0].strip()
            if not ID_RE.match(eid):
                bad_id.append(eid)
                continue
            if eid in seen:
                dup.append(eid)
                continue
            seen.add(eid)
            attrs = [tuple(a.split("=", 1)) if "=" in a else (a, "") for a in r[9:] if a.strip()]
            m = cr.map_antigen(r[3], genes, exc, gc.CFG["gene_ns"])
            ab = cr.parse_antibody(attrs, r[3])
            ctx = cr.parse_context(r[6], attrs, r[4], r[5])
            q = (r[7].split(",") + ["", "", "", ""])[:4]
            reads, pmap, pdup, npk = num(q[0], int), num(q[1]), num(q[2]), num(q[3], int)
            gsm = re.search(r"\bGSM\d+\b", r[8])
            bios = re.search(r"\bSAM[NED][A-Z]?\d+\b", line)
            control = (bool(re.search(r"\bIgG\b|^input$|^mock$", r[3], re.I)) or ab.pop("_control_like", False))
            ab.pop("_control_like", None)
            flags = [f for f, bad in (
                ("low_reads", reads is not None and reads < 5_000_000),
                ("low_mapping", pmap is not None and pmap < 50),
                ("high_duplication", pdup is not None and pdup > 80),
                ("few_peaks", npk is not None and npk < 100),
                ("antibody_metadata_missing", ab["antibody_status"] == "not_reported"),
                ("target_ambiguous", m["hgnc_id"] == cr.MISSING),
                ("tagged_construct", m["status"] == "tag_only" or ab["epitope_tag"] not in ("none", "unknown")),
                ("perturbed_sample", ctx["treatment_status"] == "treated" or ctx["perturbation"] != cr.MISSING),
                ("control_like", control)) if bad]
            rows.append(dict(
                experiment_id=eid, genome=r[1], antigen_class=r[2], gsm=gsm.group(0) if gsm else cr.MISSING,
                study_id=cr.MISSING, biosample_id=bios.group(0) if bios else cr.MISSING,
                antigen_raw=cr.clean(r[3]), **{gc.SYM_COL: m["symbol"], gc.ID_COL: m["hgnc_id"]},
                antigen_map_method=m["method"], antigen_map_status=m["status"],
                target_modification=m["modification"], target_category=cr.target_category(r[2], m, tf, genes[3]),
                target_candidates=m["candidates"], **ab,
                cell_type_class=cr.clean(r[4]), cell_type=cr.clean(r[5]), cell_type_description=cr.clean(r[6])[:500],
                **ctx, cellosaurus_id=cr.MISSING, uberon_id=cr.MISSING, cl_id=cr.MISSING,
                context_mapping_status="not_mapped_v1",
                reads=reads, pct_mapped=pmap, pct_duplicates=pdup, n_peaks_reported=npk,
                qc_flags=";".join(flags) or cr.MISSING, primary_protein_occupancy_eligible=not control,
                title=cr.clean(r[8])[:300], attributes_raw=json.dumps(attrs, ensure_ascii=False)[:4000],
                metadata_release="experimentList.tab 2026-10-14", rules_version=cr.RULES_VERSION))
    cols = list(rows[0])
    with gzip.open(out / "experiments_stage1.tsv.gz", "wt", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, delimiter="\t", lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({k: ("." if v is None else str(v).replace("\t", " ")) for k, v in r.items()})
    with open(out / "scope_ids.txt", "w") as f:
        f.writelines(r["experiment_id"] + "\n" for r in rows)
    with open(out / "annotation_suffix.tsv", "w", encoding="utf-8") as f:
        for r in rows:
            f.write("\t".join([r["experiment_id"]] + [str(r[c]).replace("\t", " ") or "." for c in A_COLS]) + "\n")
    c = collections.Counter
    summ = dict(rules_version=cr.RULES_VERSION, in_scope=len(rows), duplicate_ids=len(dup), bad_ids=bad_id[:20],
                n_bad_ids=len(bad_id), source_counts=dict(stats),
                antigen_map_status=c(r["antigen_map_status"] for r in rows),
                antigen_map_status_distinct=c(st for _, st in {(r["antigen_raw"], r["antigen_map_status"]) for r in rows}),
                target_category=c(r["target_category"] for r in rows),
                antibody_status=c(r["antibody_status"] for r in rows), epitope_tag=c(r["epitope_tag"] for r in rows),
                biosample_type=c(r["biosample_type"] for r in rows),
                treatment_status=c(r["treatment_status"] for r in rows),
                qc_flags=c(f for r in rows for f in r["qc_flags"].split(";") if f != "."),
                eligible=c(str(r["primary_protein_occupancy_eligible"]) for r in rows),
                unmapped_antigens=c(r["antigen_raw"] for r in rows if r[gc.ID_COL] == ".").most_common(60))
    (out / "metadata_reconciliation.json").write_text(json.dumps(summ, indent=1, default=dict) + "\n")
    print(json.dumps({k: v for k, v in summ.items() if k != "source_counts"}, indent=1, default=dict))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
