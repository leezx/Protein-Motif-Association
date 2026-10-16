"""Step 2c: raw-layer provenance files for the de novo sources (append-only raw).

usage: write_raw_manifests.py <encode|cistrome|hdma> <raw_dir>

Writes, next to the kept files, README.source.md, checksums.md5 (every kept
file, recursive) and, where the fetcher did not already write one,
source_manifest.tsv (one row per original download: accession, URL, md5,
bytes, kept files, status). Existing files are never overwritten: run once
per raw release, after the fetch finished. stdlib only.
"""
import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKIP = {"checksums.md5", "README.source.md"}

README = {
    "encode": """# ENCODE GRAMMAR BPNet / ChromBPNet per-model TF-MoDISco motifs (raw, {date})

- Source: ENCODE portal, annotation types `BPNet-model` and `ChromBPNet-model`,
  released files with output_type `sequence motifs` (one tar.gz per model).
- Listing: `models.tsv` (API query by `fetch_encode_models.py list`), with model
  annotation, experiment, target, biosample + slims, file accession, URL, md5, size.
- Originals were streamed, md5-checked against ENCODE and **not stored**; only
  `*.PFM.meme` (BPNet/ChromBPNet; ChromBPNet names end in `.<ENCSR>`),
  `*.ppm.fwd.meme` (ProCapNet) and README.txt were extracted, under
  `<BPNet|ChromBPNet>/<annotation>/` (tar path `/` -> `__`). Re-fetch any original
  by its file accession + md5 in `source_manifest.tsv`.
- Run 1 (`fetch_log.run1.tsv`) failed all ChromBPNet models (name pattern bug,
  fixed in commit a66f668); run 2 (`fetch_log.tsv`) retried them.
- Also here: MotifCompendium supplementary zip (Zenodo 17179111) and the ENCODE
  MotifCompendium tar index (partial head read of ENCFF372VWB), see README.md.
- Extraction code: {commit} (`scripts/02c_denovo_sources/fetch_encode_models.py`).
""",
    "cistrome": """# Cistrome DB 2 de novo (MDSeqPos) motifs (raw, {date})

- Source: Cistrome Data Browser 2 web API, http://dc2.cistrome.org
  (`/api/inspector?id=<DCid>` per sample; `/motif_html/<DCid>/motif_list.json` per sample).
- `inspector.jsonl`: sample metadata for DCid 1..145000 (factor, species, cell
  line/type, tissue, disease, GSM, PMID, qc_judge).
- `denovo.jsonl`: `denovo*` motifs only (PSSM, z-score, -log10 p, hits, cutoff,
  mean position) for samples kept by the fetcher: Homo sapiens, status completed,
  motif results present, factor not a histone mark (12,682 samples; 9,922 with
  >= 1 de novo motif). Per-sample plot data was discarded.
- `cistrome_denovo.meme` / `.tsv`: export of `denovo.jsonl` (147,569 motifs).
- Cistrome API responses carry no file checksums; `checksums.md5` covers the
  harvested files. Re-harvest by DCid with the same code.
- Extraction code: {commit} (`scripts/02c_denovo_sources/fetch_cistrome.py`).
""",
    "hdma": """# HDMA (human development multi-omic atlas) ChromBPNet TF-MoDISco motifs (raw, {date})

- Source: Zenodo records 17427146 (motif compendium: 508 merged PPMs, trimmed
  PPMs, modisco object, CWM images) and 16747618 (per-cluster modisco outputs,
  `merged_modisco_patterns_map.tsv`); see `source_manifest.tsv` (written by
  the fetcher) for URL, md5 and bytes of every original.
- `all_modisco_outputs.tar.gz` (13.6 GB) was streamed and md5-checked; only the
  per-cluster PPMs were extracted to `per_cluster_patterns.meme` / `.tsv`
  (6,362 patterns from 189 cell-cluster h5 files) and the original deleted.
- Extraction code: {commit} (`scripts/02c_denovo_sources/fetch_hdma.py`).
""",
}


def md5(path):
    h = hashlib.md5()
    with open(path, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def encode_manifest(raw):
    rows = list(csv.DictReader(open(raw / "models.tsv"), delimiter="\t"))
    with open(raw / "source_manifest.tsv", "w", newline="") as fh:
        w = csv.writer(fh, delimiter="\t")
        w.writerow(["model_type", "annotation", "experiment", "file", "url", "md5", "bytes", "status", "kept_files"])
        for r in rows:
            d = raw / r["model_type"] / r["annotation"]
            if (d / ".done").exists():
                f, m, n, kept = (d / ".done").read_text().rstrip("\n").split("\t")
                st = "ok" if m == r["md5"] else "md5_mismatch"
            else:
                n, kept = "", ""
                st = "failed: " + (d / ".failed").read_text().strip() if (d / ".failed").exists() else "missing"
            w.writerow([r["model_type"], r["annotation"], r["experiment"], r["file"], r["url"], r["md5"], n, st, kept])


def cistrome_manifest(raw):
    n_ins = sum(1 for _ in open(raw / "inspector.jsonl"))
    n_den = sum(1 for _ in open(raw / "denovo.jsonl"))
    with open(raw / "source_manifest.tsv", "w", newline="") as fh:
        w = csv.writer(fh, delimiter="\t")
        w.writerow(["endpoint", "records", "local_file", "md5"])
        w.writerow(["http://dc2.cistrome.org/api/inspector?id=<DCid>", n_ins, "inspector.jsonl", md5(raw / "inspector.jsonl")])
        w.writerow(["http://dc2.cistrome.org/motif_html/<DCid>/motif_list.json", n_den, "denovo.jsonl", md5(raw / "denovo.jsonl")])


def main(src, raw):
    commit = subprocess.run(["git", "-C", str(HERE), "rev-parse", "--short", "HEAD"], capture_output=True,
                            text=True).stdout.strip() or "unknown"
    if not (raw / "README.source.md").exists():
        (raw / "README.source.md").write_text(README[src].format(date=raw.name, commit=commit))
    if not (raw / "source_manifest.tsv").exists():
        {"encode": encode_manifest, "cistrome": cistrome_manifest}[src](raw)
    if not (raw / "checksums.md5").exists():
        files = sorted(p for p in raw.rglob("*") if p.is_file() and p.name not in SKIP)
        with open(raw / "checksums.md5", "w") as fh:
            for p in files:
                fh.write(f"{md5(p)}  {p.relative_to(raw)}\n")
    print(json.dumps({"source": src, "commit": commit, "files": sum(1 for _ in open(raw / "checksums.md5"))}))


if __name__ == "__main__":
    main(sys.argv[1], Path(sys.argv[2]))
