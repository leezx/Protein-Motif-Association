"""Step 2c: ENCODE GRAMMAR BPNet / ChromBPNet per-model TF-MoDISco motifs.

usage: fetch_encode_models.py list  <out_dir>            # write models.tsv from the ENCODE API
       fetch_encode_models.py fetch <out_dir> [n_par]    # stream + extract, resumable

For every released BPNet-model / ChromBPNet-model annotation, the
"sequence motifs" tar.gz is streamed once from ENCODE S3. The md5 of the
whole stream is checked against ENCODE; only `*.PFM.meme` (counts and
profile heads) and README.txt are written to
<out_dir>/<model_type>/<annotation>/. The tar (TF-MoDISco h5 files with
seqlet-level data, ~90 MB per model uncompressed) is never stored.
stdlib only (Argos anaconda python).
"""
import csv
import hashlib
import json
import os
import re
import sys
import tarfile
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

API = ("https://www.encodeproject.org/search/?type=Annotation&annotation_type={t}&status=released&limit=all"
       "&field=accession&field=description&field=targets.label&field=biosample_ontology.term_name"
       "&field=biosample_ontology.classification&field=biosample_ontology.organ_slims"
       "&field=biosample_ontology.cell_slims&field=biosample_ontology.system_slims"
       "&field=files.accession&field=files.output_type&field=files.status&field=files.file_size"
       "&field=files.md5sum&field=files.cloud_metadata.url&format=json")
COLS = ["model_type", "annotation", "experiment", "target", "biosample", "biosample_class", "organ_slims",
        "cell_slims", "system_slims", "description", "file", "url", "md5", "size"]
KEEP = re.compile(r"(\.PFM\.meme$|\.ppm\.fwd\.meme$|README\.txt$)")  # ppm.fwd: ProCapNet layout


def get_json(url):
    req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "PMA-fetch"})
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.load(r)


def list_models(out):
    rows = []
    for t in ("BPNet-model", "ChromBPNet-model"):
        for a in get_json(API.format(t=t))["@graph"]:
            f = [x for x in a.get("files", []) if x.get("output_type") == "sequence motifs" and x.get("status") == "released"]
            if len(f) != 1:
                continue
            f = f[0]
            bo = a.get("biosample_ontology") or {}
            bo = bo[0] if isinstance(bo, list) else bo
            m = re.search(r"\((ENCSR\w+)\)", a.get("description", ""))
            rows.append(dict(model_type=t.split("-")[0], annotation=a["accession"], experiment=m.group(1) if m else "",
                             target=";".join(x["label"] for x in a.get("targets", []) or []),
                             biosample=bo.get("term_name", ""), biosample_class=bo.get("classification", ""),
                             organ_slims=";".join(bo.get("organ_slims", []) or []),
                             cell_slims=";".join(bo.get("cell_slims", []) or []),
                             system_slims=";".join(bo.get("system_slims", []) or []),
                             description=a.get("description", ""), file=f["accession"],
                             url=(f.get("cloud_metadata") or {}).get("url", ""), md5=f.get("md5sum", ""),
                             size=f.get("file_size", 0)))
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "models.tsv", "w", newline="") as fh:
        w = csv.DictWriter(fh, COLS, delimiter="\t")
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} models; {sum(int(r['size']) for r in rows) / 1e9:.1f} GB to stream")


class Md5Reader:
    """File-like wrapper that hashes every byte read from the HTTP stream."""
    def __init__(self, fh):
        self.fh, self.h, self.n = fh, hashlib.md5(), 0

    def read(self, k=-1):
        b = self.fh.read(k)
        self.h.update(b)
        self.n += len(b)
        return b


def fetch_one(row, out):
    d = out / row["model_type"] / row["annotation"]
    done = d / ".done"
    if done.exists():
        return row["annotation"], "skip", 0
    d.mkdir(parents=True, exist_ok=True)
    for attempt in range(3):
        try:
            req = urllib.request.Request(row["url"], headers={"User-Agent": "PMA-fetch"})
            with urllib.request.urlopen(req, timeout=600) as r:
                src = Md5Reader(r)
                kept = []
                with tarfile.open(fileobj=src, mode="r|gz") as t:
                    for m in t:
                        if m.isfile() and KEEP.search(m.name):
                            name = m.name.lstrip("./").replace("/", "__")
                            (d / name).write_bytes(t.extractfile(m).read())
                            kept.append(name)
                while src.read(1 << 20):  # drain to the end so the md5 covers the whole file
                    pass
            if src.h.hexdigest() != row["md5"]:
                raise IOError(f"md5 mismatch {src.h.hexdigest()} != {row['md5']}")
            if not any(k.endswith((".PFM.meme", ".ppm.fwd.meme")) for k in kept):
                raise IOError("no PFM.meme in tar")
            done.write_text(f"{row['file']}\t{row['md5']}\t{src.n}\t{';'.join(kept)}\n")
            return row["annotation"], "ok", src.n
        except Exception as e:  # noqa: BLE001
            err = f"{type(e).__name__}: {e}"
            time.sleep(10 * (attempt + 1))
    (d / ".failed").write_text(err + "\n")
    return row["annotation"], "failed: " + err, 0


def fetch(out, n_par=32):
    rows = list(csv.DictReader(open(out / "models.tsv"), delimiter="\t"))
    rows.sort(key=lambda r: (r["model_type"] != "BPNet", r["annotation"]))  # TF ChIP first
    t0, tot = time.time(), 0
    with ThreadPoolExecutor(n_par) as ex, open(out / "fetch_log.tsv", "a") as log:
        for i, (a, st, n) in enumerate(ex.map(lambda r: fetch_one(r, out), rows), 1):
            tot += n
            log.write(f"{a}\t{st}\t{n}\n")
            log.flush()
            if i % 50 == 0:
                print(f"{i}/{len(rows)} {tot / 1e9:.1f} GB {tot / 1e6 / (time.time() - t0):.1f} MB/s", flush=True)
    print("done")


if __name__ == "__main__":
    mode, out = sys.argv[1], Path(sys.argv[2])
    if mode == "list":
        list_models(out)
    else:
        fetch(out, int(sys.argv[3]) if len(sys.argv) > 3 else 32)
