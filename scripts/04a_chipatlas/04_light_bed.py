"""Step 4a §10: light per-target non-redundant BED from an experiment-level occupancy BED6+18 (Output A layout).

usage: 04_light_bed.py <occupancy.bed.gz> <experiments.tsv.gz> <chrom.sizes> <release_dir> <prefix> [workers]
For each target (HGNC symbol, else the ChIP-Atlas antigen with whitespace -> _), overlapping or book-ended peaks
of that target are merged across all its experiments (chained, like bedtools merge per name). Writes to release_dir:
  <prefix>.bed.gz (+.tbi), <prefix>.bb   BED6: chrom, start, end, target, score = min(1000, n_experiments), .
  <prefix>.detail.tsv.gz (+.tbi)          chrom, start, end, target, n_experiments, n_peaks, max_qscore,
                                          n_peaks_blacklist, experiments (sorted, comma separated)
  <prefix>.experiments.tsv.gz             experiment context table (copy of the input experiments table)
  <prefix>.targets.tsv                    per target: regions, peaks, experiments, bp covered, width quantiles
  <prefix>.qc.json, MANIFEST.json
Join: BED row -> detail row by (chrom, start, end, target), unique by construction; detail -> context by experiment.
Invariants (asserted): every input row is merged exactly once (sum n_peaks = rows in); per-target regions disjoint.
Runs per chromosome in parallel (tabix); memory is per-target open intervals only.
"""
import collections
import gzip
import hashlib
import json
import multiprocessing as mp
import os
import shutil
import subprocess
import sys
from pathlib import Path


def target_of(f):
    t = f[8] if f[8] != "." else f[7]
    return "_".join(t.split()) or "."


def merge_chrom(args):
    bed, chrom, part = args
    rows, out_n, unsorted = 0, 0, 0
    widths = collections.Counter()  # log2 width bins
    per_t = collections.defaultdict(lambda: [0, 0, 0])  # regions, peaks, bp
    max_w = (0, "")
    open_ = {}
    prev_s = -1
    with open(part, "w") as w:
        def emit(t, o):
            nonlocal out_n, max_w
            s, e, exps, npk, mq, nbl = o
            w.write(f"{chrom}\t{s}\t{e}\t{t}\t{min(1000, len(exps))}\t.\t{len(exps)}\t{npk}\t{mq:g}\t{nbl}\t"
                    f"{','.join(sorted(exps))}\n")
            out_n += 1
            width = e - s
            widths[width.bit_length()] += 1
            p = per_t[t]; p[0] += 1; p[1] += npk; p[2] += width
            if width > max_w[0]:
                max_w = (width, f"{chrom}:{s}-{e} {t}")
        p = subprocess.Popen(["tabix", bed, chrom], stdout=subprocess.PIPE, text=True, bufsize=1 << 20)
        for line in p.stdout:
            f = line.rstrip("\n").split("\t")
            s, e = int(f[1]), int(f[2])
            rows += 1
            if s < prev_s:
                unsorted += 1
            prev_s = s
            t = target_of(f)
            bl = "blacklist_majority_overlap" in f[23]
            q = float(f[6])
            o = open_.get(t)
            if o is not None and s <= o[1]:
                if e > o[1]:
                    o[1] = e
                o[2].add(f[3]); o[3] += 1; o[4] = max(o[4], q); o[5] += bl
            else:
                if o is not None:
                    emit(t, o)
                open_[t] = [s, e, {f[3]}, 1, q, int(bl)]
        if p.wait() != 0:
            raise RuntimeError(f"tabix failed on {chrom}")
        for t, o in open_.items():
            emit(t, o)
    return dict(chrom=chrom, rows_in=rows, regions=out_n, unsorted=unsorted, widths=dict(widths),
                per_target={k: v for k, v in per_t.items()}, max_width=max_w)


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


def sh(cmd):
    subprocess.run(["bash", "-o", "pipefail", "-c", cmd], check=True)


def main(bed, exps, sizes, rel, prefix, workers=4):
    rel = Path(rel); rel.mkdir(parents=True, exist_ok=True)
    work = rel / f"{prefix}_work"; work.mkdir(exist_ok=True)
    chroms = subprocess.run(["tabix", "-l", bed], capture_output=True, text=True, check=True).stdout.split()
    if os.environ.get("PMA_LIGHT_CHROMS"):  # test runs only
        chroms = [c for c in chroms if c in os.environ["PMA_LIGHT_CHROMS"].split(",")]
    known = {l.split("\t")[0] for l in Path(sizes).read_text().splitlines() if l}
    assert set(chroms) <= known, f"chromosomes missing from chrom.sizes: {sorted(set(chroms) - known)[:5]}"
    jobs = [(bed, c, str(work / f"part.{i:04d}.tsv")) for i, c in enumerate(chroms)]
    with mp.Pool(workers) as pool:
        res = pool.map(merge_chrom, jobs, chunksize=1)
    assert all(r["unsorted"] == 0 for r in res), "input not start-sorted within chromosome"
    env = f"export LC_ALL=C; cd {work};"
    sorted_ = work / "merged.sorted.tsv"
    sh(f"{env} cat part.*.tsv | sort -k1,1 -k2,2n -k3,3n -k4,4 -S 3G --parallel={workers} -T . > {sorted_}")
    b, d = rel / f"{prefix}.bed.gz", rel / f"{prefix}.detail.tsv.gz"
    sh(f"{env} cut -f1-6 {sorted_} | tee bed6.tmp | bgzip -@ {workers} > {b} && tabix -f -p bed {b}")
    sh(f"{env} cut -f1-4,7- {sorted_} | bgzip -@ {workers} > {d} && tabix -f -p bed {d}")
    sh(f"{env} bedToBigBed -type=bed6 -tab bed6.tmp {sizes} {rel / (prefix + '.bb')}")
    shutil.copyfile(exps, rel / f"{prefix}.experiments.tsv.gz")
    # independent recount from the sorted release file: peaks conserved, per-target regions disjoint, unique keys
    rows_in = sum(r["rows_in"] for r in res)
    n_reg = n_pk = overlaps = dup = 0
    last_end, last_key = {}, None
    with open(sorted_) as f:
        for line in f:
            c, s, e, t, sc, st, ne, npk, mq, nbl, ex = line.rstrip("\n").split("\t")
            s, e = int(s), int(e)
            n_reg += 1; n_pk += int(npk)
            key = (c, s, e, t)
            dup += key == last_key; last_key = key
            le = last_end.get((c, t))
            overlaps += le is not None and s <= le
            last_end[(c, t)] = e
            assert int(sc) == min(1000, int(ne)) and len(ex.split(",")) == int(ne) <= int(npk)
        last_end.clear()
    per_t = collections.defaultdict(lambda: [0, 0, 0])
    widths = collections.Counter()
    for r in res:
        for k, v in r["per_target"].items():
            p = per_t[k]; p[0] += v[0]; p[1] += v[1]; p[2] += v[2]
        widths.update({int(k): v for k, v in r["widths"].items()})
    exp_by_t = collections.defaultdict(set)
    with gzip.open(d, "rt") as f:
        for line in f:
            x = line.rstrip("\n").split("\t")
            exp_by_t[x[3]].update(x[8].split(","))
    with open(rel / f"{prefix}.targets.tsv", "w") as f:
        f.write("target\tregions\tpeaks\texperiments\tbp_covered\tmean_width\n")
        for k in sorted(per_t):
            v = per_t[k]
            f.write(f"{k}\t{v[0]}\t{v[1]}\t{len(exp_by_t[k])}\t{v[2]}\t{v[2] / v[0]:.1f}\n")
    qc = dict(rows_in=rows_in, regions=n_reg, peaks_in_regions=n_pk, peaks_conserved=n_pk == rows_in,
              duplicate_keys=dup, same_target_overlaps=overlaps, targets=len(per_t), chromosomes=len(chroms),
              reduction=round(rows_in / max(n_reg, 1), 2),
              width_log2_bins={f"<2^{k}": widths[k] for k in sorted(widths)},
              max_width=max((r["max_width"] for r in res), key=lambda x: x[0]),
              status="PASS" if (n_pk == rows_in and dup == 0 and overlaps == 0) else "FAIL")
    (rel / f"{prefix}.qc.json").write_text(json.dumps(qc, indent=1) + "\n")
    commit = subprocess.run(["git", "-C", str(Path(__file__).parent), "rev-parse", "HEAD"],
                            capture_output=True, text=True).stdout.strip()
    outs = [f"{prefix}{x}" for x in (".bed.gz", ".bed.gz.tbi", ".bb", ".detail.tsv.gz", ".detail.tsv.gz.tbi",
                                     ".experiments.tsv.gz", ".targets.tsv", ".qc.json")]
    man = dict(prefix=prefix, design="docs/STEP4A_CHIPATLAS_OCCUPANCY_DESIGN.md §10", code_commit=commit,
               inputs={str(bed): sha256(bed), str(exps): sha256(exps), str(sizes): sha256(sizes)},
               merge_rule="per target, overlapping or book-ended (start <= open end) peaks chained across experiments",
               outputs={o: sha256(rel / o) for o in outs}, qc_status=qc["status"])
    (rel / "MANIFEST.json").write_text(json.dumps(man, indent=1) + "\n")
    shutil.rmtree(work)
    print(json.dumps(qc))
    return 0 if qc["status"] == "PASS" else 1


if __name__ == "__main__":
    a = sys.argv[1:]
    sys.exit(main(*a[:5], workers=int(a[5]) if len(a) > 5 else 4))
