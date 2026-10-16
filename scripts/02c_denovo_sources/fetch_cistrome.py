"""Step 2c: Cistrome DB 2 de novo (MDSeqPos) motifs with sample protein + context.

usage: fetch_cistrome.py inspect <out_dir> [max_id]   # sample metadata for every DCid
       fetch_cistrome.py motifs  <out_dir>            # de novo PSSMs for kept samples
       fetch_cistrome.py export  <out_dir>            # cistrome_denovo.meme + .tsv

Polite harvest: 4 concurrent requests, resumable (jsonl caches). Kept
samples: Homo sapiens, status completed, motif results present, factor not
a histone mark. From each motif_list.json only `denovo*` entries are kept
(PSSM + z-score, p-value, hits); the per-sample plot data (~7 MB) is
discarded. stdlib only.
"""
import json
import re
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

BASE = "http://dc2.cistrome.org"
NPAR = 4
HISTONE = re.compile(r"^(H2A|H2B|H3|H4|H1)(K\d|R\d|S\d|T\d|\.|Z|X|$)|^H2AZ|^H3K|^H4K", re.I)
STAT = {k: re.compile(r"'" + k + r"':\s*([-0-9.eE+]+|None|nan)") for k in ("zscore", "pvalue", "numhits", "cutoff",
                                                                      "meanposition")}
TREAT = ["factor__name", "species__name", "cell_line__name", "cell_type__name", "tissue_type__name",
         "disease_state__name", "unique_id", "paper__pmid", "name"]


def get(url, tries=3):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "PMA-research-fetch (contact via GitHub leezx)"})
            with urllib.request.urlopen(req, timeout=120) as r:
                return r.read().decode("utf-8", "replace")
        except Exception:  # noqa: BLE001
            time.sleep(5 * (i + 1))
    return None


def done_ids(path, key="id"):
    if not path.exists():
        return set()
    return {json.loads(l)[key] for l in open(path) if l.strip()}


def inspect_one(i):
    t = get(f"{BASE}/api/inspector?id={i}")
    if not t:
        return dict(id=i, ok=False)
    try:
        d = json.loads(t)
    except ValueError:
        return dict(id=i, ok=False)
    tr = (d.get("treats") or [{}])[0]
    judge = (d.get("qc") or {}).get("judge", {})
    return dict(id=i, ok=True, status=d.get("status"), motif=str(d.get("motif")), **{k: tr.get(k) for k in TREAT},
                qc_judge=judge)


def inspect(out, max_id):
    out.mkdir(parents=True, exist_ok=True)
    p = out / "inspector.jsonl"
    todo = [i for i in range(1, max_id + 1) if i not in done_ids(p)]
    with ThreadPoolExecutor(NPAR) as ex, open(p, "a") as fh:
        for n, r in enumerate(ex.map(inspect_one, todo), 1):
            fh.write(json.dumps(r) + "\n")
            if n % 1000 == 0:
                fh.flush()
                print(n, len(todo), flush=True)


def keep(r):
    return (r.get("ok") and r.get("status") == "completed" and r.get("motif") == "True"
            and (r.get("species__name") or "").lower() == "homo sapiens"
            and r.get("factor__name") and not HISTONE.search(r["factor__name"]))


def motifs_one(i):
    t = get(f"{BASE}/motif_html/{i}/motif_list.json")
    if t is None:
        return dict(id=i, ok=False, denovo=[])
    den = []
    for line in t.splitlines():
        if not line.strip():
            continue
        try:
            m = json.loads(line)
        except ValueError:
            continue
        if not str(m.get("id", "")).startswith("denovo"):
            continue
        sr = m.get("seqpos_results", "") or ""
        st = {k: (rx.search(sr).group(1) if rx.search(sr) else None) for k, rx in STAT.items()}
        den.append(dict(motif=m["id"], pssm=json.loads(m["pssm"].replace("'", '"')) if m.get("pssm") else None, **st))
    return dict(id=i, ok=True, denovo=den)


def motifs(out):
    rows = [json.loads(l) for l in open(out / "inspector.jsonl") if l.strip()]
    ids = sorted({r["id"] for r in rows if keep(r)})
    p = out / "denovo.jsonl"
    todo = [i for i in ids if i not in done_ids(p)]
    print(f"{len(ids)} human non-histone samples with motifs; {len(todo)} to fetch", flush=True)
    with ThreadPoolExecutor(NPAR) as ex, open(p, "a") as fh:
        for n, r in enumerate(ex.map(motifs_one, todo), 1):
            fh.write(json.dumps(r) + "\n")
            if n % 200 == 0:
                fh.flush()
                print(n, len(todo), flush=True)


def export(out):
    meta = {r["id"]: r for r in (json.loads(l) for l in open(out / "inspector.jsonl") if l.strip()) if r.get("ok")}
    n = 0
    with open(out / "cistrome_denovo.meme", "w") as mf, open(out / "cistrome_denovo.tsv", "w") as tf:
        mf.write("MEME version 4\n\nALPHABET= ACGT\n\nstrands: + -\n\n"
                 "Background letter frequencies\nA 0.25 C 0.25 G 0.25 T 0.25\n\n")
        cols = ["motif_id", "dcid", "denovo", "factor", "gsm", "cell_line", "cell_type", "tissue", "disease",
                "pmid", "zscore", "pvalue", "numhits", "length"]
        tf.write("\t".join(cols) + "\n")
        for l in open(out / "denovo.jsonl"):
            r = json.loads(l)
            m = meta.get(r["id"], {})
            for d in r.get("denovo", []):
                if not d.get("pssm"):
                    continue
                mid = f"CIS_{r['id']}_{d['motif']}"
                mf.write(f"MOTIF {mid} {m.get('factor__name')}\nletter-probability matrix: alength= 4 "
                         f"w= {len(d['pssm'])} nsites= 20 E= 0\n")
                mf.write("".join(" ".join(f"{float(x):.6f}" for x in row) + "\n" for row in d["pssm"]) + "\n")
                tf.write("\t".join(str(x) for x in [mid, r["id"], d["motif"], m.get("factor__name"), m.get("unique_id"),
                                                    m.get("cell_line__name"), m.get("cell_type__name"),
                                                    m.get("tissue_type__name"), m.get("disease_state__name"),
                                                    m.get("paper__pmid"), d.get("zscore"), d.get("pvalue"),
                                                    d.get("numhits"), len(d["pssm"])]) + "\n")
                n += 1
    print(f"{n} de novo motifs exported")


if __name__ == "__main__":
    mode, out = sys.argv[1], Path(sys.argv[2])
    if mode == "inspect":
        inspect(out, int(sys.argv[3]) if len(sys.argv) > 3 else 120000)
    elif mode == "motifs":
        motifs(out)
    else:
        export(out)
