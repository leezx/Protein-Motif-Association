"""Step 2c: HDMA (Nature 2026) de novo motifs from Zenodo.

usage: fetch_hdma.py <out_dir>

- Small files (md5 checked against Zenodo): the 508-motif compendium PPMs
  (full and trimmed), its modisco h5, CWM images, and the 6,362-pattern
  map (record 16747618).
- all_modisco_outputs.tar.gz (13.6 GB, one TF-MoDISco h5 per cell
  cluster with seqlet-level data) is streamed once with an md5 check;
  each h5 is written to a temporary file, its pattern PPMs
  (`<pos|neg>_patterns/pattern_<i>/sequence`) and seqlet counts are
  written to per_cluster_patterns.meme / .tsv, and the h5 is deleted.
stdlib + numpy + h5py (Argos anaconda python).
"""
import hashlib
import json
import os
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path

import h5py
import numpy as np

SMALL = {17427146: ["motif_compendium.PPM.memedb.txt", "motif_compendium.trimmed.PPM.memedb.txt",
                    "motif_compendium.modisco_object.h5", "denovo_motifs_508_cwm_images.tar.gz"],
         16747618: ["merged_modisco_patterns_map.tsv"]}
BIG = (16747618, "all_modisco_outputs.tar.gz")


def files_of(rec):
    req = urllib.request.Request(f"https://zenodo.org/api/records/{rec}", headers={"User-Agent": "PMA-fetch"})
    with urllib.request.urlopen(req, timeout=120) as r:
        d = json.load(r)
    return {f["key"]: (f["links"]["self"], f["checksum"].split(":", 1)[1], f["size"]) for f in d["files"]}


class Md5Reader:
    def __init__(self, fh):
        self.fh, self.h, self.n = fh, hashlib.md5(), 0

    def read(self, k=-1):
        b = self.fh.read(k)
        self.h.update(b)
        self.n += len(b)
        return b


def main(out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    man = open(out / "source_manifest.tsv", "a")
    for rec, names in SMALL.items():
        fl = files_of(rec)
        for n in names:
            url, md5, size = fl[n]
            if not (out / n).exists():
                urllib.request.urlretrieve(url, out / n)
            got = hashlib.md5((out / n).read_bytes()).hexdigest()
            assert got == md5, f"{n}: md5 {got} != {md5}"
            man.write(f"zenodo:{rec}\t{n}\t{url}\t{size}\t{md5}\tkept\n")
    url, md5, size = files_of(BIG[0])[BIG[1]]
    tmpdir = Path(tempfile.mkdtemp(dir=out))
    rows, n_h5 = [], 0
    with open(out / "per_cluster_patterns.meme", "w") as meme:
        meme.write("MEME version 4\n\nALPHABET= ACGT\n\nstrands: + -\n\n"
                   "Background letter frequencies\nA 0.25 C 0.25 G 0.25 T 0.25\n\n")
        req = urllib.request.Request(url, headers={"User-Agent": "PMA-fetch"})
        with urllib.request.urlopen(req, timeout=1200) as r:
            src = Md5Reader(r)
            with tarfile.open(fileobj=src, mode="r|gz") as t:
                for m in t:
                    if not (m.isfile() and m.name.endswith(".h5")):
                        continue
                    cluster = os.path.basename(m.name).replace("_modisco_output.h5", "")
                    tmp = tmpdir / "x.h5"
                    with open(tmp, "wb") as fh:
                        fh.write(t.extractfile(m).read())
                    with h5py.File(tmp, "r") as h:
                        for pn in ("pos_patterns", "neg_patterns"):
                            if pn not in h:
                                continue
                            for p in sorted(h[pn], key=lambda s: int(s.split("_")[-1])):
                                ppm = np.asarray(h[pn][p]["sequence"])
                                ns = int(h[pn][p]["seqlets"]["n_seqlets"][()]) if "seqlets" in h[pn][p] else -1
                                mid = f"{cluster}__{pn}.{p}"
                                meme.write(f"MOTIF {mid}\nletter-probability matrix: alength= 4 w= {len(ppm)} "
                                           f"nsites= {max(ns, 1)} E= 0\n")
                                meme.write("".join(" ".join(f"{x:.6f}" for x in row) + "\n" for row in ppm) + "\n")
                                rows.append(f"{mid}\t{cluster}\t{pn}\t{p}\t{len(ppm)}\t{ns}\n")
                    tmp.unlink()
                    n_h5 += 1
                    print(n_h5, cluster, flush=True)
            while src.read(1 << 20):
                pass
    tmpdir.rmdir()
    assert src.h.hexdigest() == md5, f"big tar md5 {src.h.hexdigest()} != {md5}"
    with open(out / "per_cluster_patterns.tsv", "w") as fh:
        fh.write("motif_id\tcluster\tposneg\tpattern\tlength\tn_seqlets\n")
        fh.writelines(rows)
    man.write(f"zenodo:{BIG[0]}\t{BIG[1]}\t{url}\t{size}\t{md5}\tstreamed; PPMs extracted ({len(rows)} patterns "
              f"from {n_h5} h5); archive not kept\n")
    print(f"{len(rows)} patterns from {n_h5} cluster h5 files; md5 ok")


if __name__ == "__main__":
    main(sys.argv[1])
