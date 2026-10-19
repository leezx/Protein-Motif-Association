#!/usr/bin/env python3
"""Independent check of the coordinate-unique ChIP-Atlas BED6 release against the verified Step 4a v1 build.

Streaming, low memory. Three parts, each runnable alone so they can run in parallel:
  bed      BED6 well-formed, sorted, coordinate-unique, name = recomputed region_id, score = min(1000, n_exp)
           (joined in file order with region_summary.tsv.gz); totals of summary vs region_experiment.
  prov     peak_provenance included rows per experiment; TF/Pol experiments must equal v1 per-experiment
           peak counts (v1_work/peak_counts_included.tsv) exactly; Histone reported separately.
  merge    combine the part JSONs into one verdict.
usage: verify_unique_bed6.py bed   <release_dir> <chrom.sizes> <out.json>
       verify_unique_bed6.py prov  <release_dir> <v1_peak_counts_included.tsv> <out.json>
       verify_unique_bed6.py merge <out.json> <part.json>...
"""
import collections, gzip, hashlib, json, subprocess, sys
from pathlib import Path


def zlines(path):
    """Decompress with an external process (faster than gzip module); yield text lines."""
    p = subprocess.Popen(["gzip", "-dc", str(path)], stdout=subprocess.PIPE, bufsize=1 << 20)
    for raw in p.stdout:
        yield raw.decode("utf-8").rstrip("\n")
    if p.wait() != 0:
        raise SystemExit(f"gzip failed on {path}")


def region_id(chrom, start, end):
    payload = "\t".join(("PMA-region-v1", "hg38", chrom, start, end)).encode("utf-8")
    return "PMA_hg38_" + hashlib.sha256(payload).hexdigest()


def check_bed(rel, sizes_path, out):
    sizes = dict(l.split("\t")[:2] for l in Path(sizes_path).read_text().splitlines() if l)
    sizes = {k: int(v) for k, v in sizes.items()}
    err = collections.Counter(); ex = {}
    def bad(kind, line):
        err[kind] += 1; ex.setdefault(kind, line[:300])
    summ = zlines(rel / "region_summary.tsv.gz"); hdr = next(summ).split("\t")
    ix = {k: i for i, k in enumerate(hdr)}
    n = 0; sum_exp = 0; sum_src = 0; score_hist = collections.Counter(); seen_chroms = set()
    prev = None; regions_by_chrom = collections.Counter()
    for line in zlines(rel / "PMA_chipatlas_hg38_unique_regions.bed.gz"):
        n += 1
        f = line.split("\t")
        if len(f) != 6:
            bad("bed_not_6_columns", line); continue
        chrom, s, e, name, score, strand = f
        if chrom not in sizes: bad("unknown_chrom", line)
        si, ei = int(s), int(e)
        if not (0 <= si < ei <= sizes.get(chrom, 0)): bad("bad_interval", line)
        if strand != ".": bad("strand_not_dot", line)
        if name != region_id(chrom, s, e): bad("region_id_mismatch", line)
        if prev is not None and chrom != prev[0]:
            if chrom in seen_chroms: bad("chrom_block_not_contiguous", line)
        elif prev is not None and (si, ei) <= (prev[1], prev[2]):
            bad("not_sorted_or_duplicate_coordinate", line)
        if prev is None or chrom != prev[0]: seen_chroms.add(chrom)
        prev = (chrom, si, ei); regions_by_chrom[chrom] += 1
        s_line = next(summ, None)
        if s_line is None:
            bad("summary_shorter_than_bed", line); continue
        sf = s_line.split("\t")
        if (sf[ix["region_id"]], sf[ix["chrom"]], sf[ix["start"]], sf[ix["end"]]) != (name, chrom, s, e):
            bad("summary_order_or_content_mismatch", line + " | " + s_line); continue
        nexp = int(sf[ix["supporting_experiments"]]); sum_exp += nexp
        sum_src += int(sf[ix["source_peak_rows"]])
        if int(score) != min(1000, nexp): bad("score_not_min1000_nexp", line)
        score_hist[min(nexp, 10)] += 1
    if next(summ, None) is not None: bad("summary_longer_than_bed", "")
    n_link = sum(1 for _ in zlines(rel / "region_experiment.tsv.gz")) - 1
    if n_link != sum_exp: bad("region_experiment_rows_ne_sum_supporting", f"{n_link} vs {sum_exp}")
    res = {"part": "bed", "regions": n, "sum_supporting_experiments": sum_exp, "region_experiment_rows": n_link,
           "sum_source_peak_rows": sum_src, "supporting_experiments_hist_capped10": dict(sorted(score_hist.items())),
           "chromosomes": len(regions_by_chrom), "errors": dict(err), "error_examples": ex,
           "status": "PASS" if not err else "FAIL"}
    Path(out).write_text(json.dumps(res, indent=1))


def check_prov(rel, v1_counts, out):
    meta = {}
    m = zlines(rel / "experiment_metadata.tsv.gz"); next(m)
    for line in m:
        f = line.split("\t"); meta[f[0]] = f[2]
    p = zlines(rel / "peak_provenance.tsv.gz"); hdr = next(p).split("\t")
    ie, ist = hdr.index("experiment_id"), hdr.index("primary_status")
    per_exp = collections.Counter(); status = collections.Counter()
    for line in p:
        f = line.split("\t", ist + 1)
        status[f[ist]] += 1
        if f[ist].startswith("INCLUDED"): per_exp[f[ie]] += 1
    v1 = {}
    for line in Path(v1_counts).read_text().splitlines()[1:]:
        k, v = line.split("\t"); v1[k] = int(v)
    by_class_rows = collections.Counter(); by_class_exp = collections.Counter()
    for k, v in per_exp.items():
        by_class_rows[meta.get(k, "NO_METADATA")] += v; by_class_exp[meta.get(k, "NO_METADATA")] += 1
    tfpol = {k: v for k, v in per_exp.items() if meta.get(k) in ("TFs and others", "RNA polymerase")}
    v1_pos = {k: v for k, v in v1.items() if v > 0}
    only_v1 = sorted(set(v1_pos) - set(tfpol)); only_new = sorted(set(tfpol) - set(v1_pos))
    diff = sorted(k for k in set(tfpol) & set(v1_pos) if tfpol[k] != v1_pos[k])
    res = {"part": "prov", "provenance_status_rows": dict(status), "included_rows_by_class": dict(by_class_rows),
           "experiments_by_class": dict(by_class_exp),
           "tfpol_rows_new": sum(tfpol.values()), "tfpol_rows_v1": sum(v1_pos.values()),
           "tfpol_experiments_new": len(tfpol), "tfpol_experiments_v1": len(v1_pos),
           "experiments_only_in_v1": len(only_v1), "experiments_only_in_new": len(only_new),
           "experiments_count_differs": len(diff),
           "examples": {"only_v1": only_v1[:10], "only_new": only_new[:10],
                        "differs": [(k, v1_pos[k], tfpol[k]) for k in diff[:10]]},
           "status": "PASS" if not (only_v1 or only_new or diff) else "FAIL"}
    Path(out).write_text(json.dumps(res, indent=1))


def merge(out, parts):
    rs = [json.loads(Path(x).read_text()) for x in parts]
    res = {"parts": rs, "status": "PASS" if all(r["status"] == "PASS" for r in rs) else "FAIL"}
    b = next((r for r in rs if r["part"] == "bed"), None); p = next((r for r in rs if r["part"] == "prov"), None)
    if b and p:
        inc = sum(v for k, v in p["provenance_status_rows"].items() if k.startswith("INCLUDED"))
        res["cross"] = {"included_provenance_rows": inc, "summary_source_peak_rows": b["sum_source_peak_rows"],
                        "match": inc == b["sum_source_peak_rows"]}
        if not res["cross"]["match"]: res["status"] = "FAIL"
    Path(out).write_text(json.dumps(res, indent=1)); print(res["status"])


if __name__ == "__main__":
    mode = sys.argv[1]
    if mode == "bed": check_bed(Path(sys.argv[2]), sys.argv[3], sys.argv[4])
    elif mode == "prov": check_prov(Path(sys.argv[2]), sys.argv[3], sys.argv[4])
    elif mode == "merge": merge(sys.argv[2], sys.argv[3:])
    else: raise SystemExit(__doc__)
