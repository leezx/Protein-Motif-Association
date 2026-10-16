"""Step 3b §4.3: ENCODE experiment -> GEO crosswalk for experiment identity.

usage: fetch_encode_dbxrefs.py <encode_raw_dir>

Reads models.tsv (experiment accessions of every BPNet / ChromBPNet model)
and writes experiment_dbxrefs.tsv: experiment, lab, award, GEO accessions
(GSM / GSE from dbxrefs), all dbxrefs. 100 accessions per ENCODE search
request. stdlib only; new raw file, never overwritten.
"""
import csv
import json
import sys
import time
import urllib.request
from pathlib import Path

URL = ("https://www.encodeproject.org/search/?type=Experiment&{acc}&field=accession&field=dbxrefs"
       "&field=lab.title&field=award.project&limit=all&format=json")


def get_json(url):
    for i in range(4):
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "PMA-fetch"})
            with urllib.request.urlopen(req, timeout=300) as r:
                return json.load(r)
        except Exception:  # noqa: BLE001
            time.sleep(10 * (i + 1))
    raise IOError(url[:120])


def main(raw):
    out = raw / "experiment_dbxrefs.tsv"
    assert not out.exists(), out
    exps = sorted({r["experiment"] for r in csv.DictReader(open(raw / "models.tsv"), delimiter="\t")
                   if r["experiment"]})
    rows = {}
    for i in range(0, len(exps), 100):
        q = "&".join(f"accession={a}" for a in exps[i:i + 100])
        for g in get_json(URL.format(acc=q))["@graph"]:
            x = g.get("dbxrefs", []) or []
            rows[g["accession"]] = dict(experiment=g["accession"], lab=(g.get("lab") or {}).get("title", ""),
                                        project=(g.get("award") or {}).get("project", ""),
                                        geo=";".join(sorted(v.split(":", 1)[1] for v in x if v.startswith("GEO:"))),
                                        dbxrefs=";".join(x))
        time.sleep(1)
    with open(out, "w", newline="") as fh:
        w = csv.DictWriter(fh, ["experiment", "lab", "project", "geo", "dbxrefs"], delimiter="\t")
        w.writeheader()
        for a in exps:
            w.writerow(rows.get(a, dict(experiment=a, lab="", project="", geo="", dbxrefs="")))
    print(f"{len(exps)} experiments; {len(rows)} returned; {sum(bool(r['geo']) for r in rows.values())} with GEO")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
