"""Step 4a §11: split the light protein BED (§10) by primary class; bgzip + tabix + bigBed per class.

usage: 06_split_by_class.py <protein_nr.bed.gz> <class_annotation.csv> <chrom.sizes> <out_dir>
Class from the annotation by target (= HGNC / MGI symbol); targets without one go to Non_gene_label.
Asserts that the class files together hold every input row exactly once.
"""
import csv
import json
import re
import subprocess
import sys
from pathlib import Path

import genome_config as gc


def main(bed, ann, sizes, out):
    cls = {r["gene"]: r["Class"] for r in csv.DictReader(open(ann, encoding="utf-8-sig"))}
    out = Path(out); out.mkdir(parents=True, exist_ok=True)
    fh, n, n_in = {}, {}, 0
    p = subprocess.Popen(["bgzip", "-dc", bed], stdout=subprocess.PIPE, text=True, bufsize=1 << 20)
    for line in p.stdout:
        n_in += 1
        k = re.sub(r"[^A-Za-z0-9]+", "_", cls.get(line.split("\t", 4)[3], "Non-gene label")).strip("_")
        if k not in fh:
            fh[k] = open(out / f"{gc.PREFIX}_protein_nr.{k}.bed", "w"); n[k] = 0
        fh[k].write(line); n[k] += 1
    assert p.wait() == 0
    for k, h in fh.items():
        h.close()
        b = out / f"{gc.PREFIX}_protein_nr.{k}.bed"
        subprocess.run(["bedToBigBed", "-type=bed6", "-tab", str(b), sizes, str(b.with_suffix(".bb"))], check=True)
        subprocess.run(["bgzip", "-f", str(b)], check=True)
        subprocess.run(["tabix", "-f", "-p", "bed", str(b) + ".gz"], check=True)
    qc = dict(rows_in=n_in, rows_by_class=n, rows_out=sum(n.values()),
              status="PASS" if sum(n.values()) == n_in else "FAIL")
    (out / "split_qc.json").write_text(json.dumps(qc, indent=1) + "\n")
    print(json.dumps(qc))
    return 0 if qc["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:5]))
