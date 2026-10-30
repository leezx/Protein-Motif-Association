"""Step 4a §19.3: rule-based protein class annotation from MGI GO annotations (mm10; same CSV layout as the hg38
protein class annotation, so 05_occupancy_tracks.py / 06_split_by_class.py read it unchanged).

usage: 29_go_class_annotation.py <experiments.tsv(.gz)> <reference_dir> <out.csv>
Genes = distinct non-missing antigen_<ns>_symbol of the experiment table. Class = first matching rule of
chipatlas_rules.GO_CLASSES (GO term or is_a/part_of descendant, NOT and ND annotations excluded), else
Other/ambiguous. This is a draft: assignment_basis = go_rule / no_go_rule_match; it is not manually curated like the
hg38 v1.1 annotation, so tf/cap tracks built from it must be described as GO-rule classes.
"""
import collections
import csv
import sys
from pathlib import Path

import pandas as pd

import chipatlas_rules as cr
import genome_config as gc

INTERP = {"Sequence-specific TF": "Sequence-specific DNA-binding transcription factor (GO:0003700)",
          "Other/ambiguous": "No GO rule matched; not evidence of lacking DNA/chromatin association"}


def main(exp, ref, out):
    ref = Path(ref)
    classes, tf = cr.load_go_classes(ref / "mgi.gaf.gz", ref / "go-basic.obo")
    b = pd.read_csv(exp, sep="\t", dtype=str, keep_default_na=False)
    genes = sorted(set(b[gc.SYM_COL]) - {"."})
    n = collections.Counter()
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["gene", "Class", "original_class", "functional_tags", "confidence", "assignment_basis",
                    "revision_note", "Biological_interpretation", "review_note"])
        for g in genes:
            k, terms = classes.get(g, ("Other/ambiguous", ""))
            tags = ";".join(filter(None, ["go_tf" if g in tf else "", "go_rule:" + k if terms else ""]))
            basis = "go_rule" if terms else "no_go_rule_match"
            w.writerow([g, k, k, tags or ".", "medium" if terms else "low", basis, ".",
                        INTERP.get(k, terms), "GO-rule draft; manual review pending"])
            n[k] += 1
    print(dict(genes=len(genes), classes=dict(n)))


if __name__ == "__main__":
    main(*sys.argv[1:4])
