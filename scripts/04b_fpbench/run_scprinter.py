#!/usr/bin/env python3
"""scPrinter (buenrostrolab, Python successor of PRINT) bulk footprinting on CPU.

The genome object points at local files (same hg38 FASTA and PRINT hg38 Tn5-bias h5 as the other callers),
so nothing is downloaded except scPrinter's pretrained dispersion model on first use.
Fragments are already Tn5-shifted (+4/-5), which is what plus_shift/minus_shift declare.

usage: run_scprinter.py <frags.tsv.gz> <regions.bed> <outdir> <n_jobs> <bias.h5> <genome.fa> <blacklist.bed>
output: <outdir>/scprinter_r<mode>.bedgraph.gz  chrom, start, end, footprint score (-log10 p) per bp
        <outdir>/scprinter_timing.tsv
"""
import gzip, os, sys, time

import numpy as np
import pandas as pd
import scprinter as scp
from scprinter.genome import GRCh38, Genome

MODES = [10, 20]


def main():
    frags, bed, out, n, bias, fa, bl = sys.argv[1:8]
    n = int(n)
    with gzip.open(frags, "rt") as f:
        bc = f.readline().split("\t")[3]  # one pseudobulk barcode
    os.makedirs(out, exist_ok=True)
    timing = {}
    # gff (gencode v41, fetched by scPrinter) is only used for its TSS-enrichment QC at import
    genome = Genome("hg38", GRCh38.chrom_sizes, GRCh38.gff_file, fa, bias, bl, GRCh38.bg, None)
    t0 = time.time()
    printer = scp.pp.import_fragments(path_to_frags=frags, barcodes=[bc], savename=f"{out}/printer.h5ad",
                                      genome=genome, plus_shift=4, minus_shift=-5, auto_detect_shift=False)
    timing["import_fragments"] = time.time() - t0
    t0 = time.time()
    regions = pd.read_csv(bed, sep="\t", header=None).iloc[:, :3]
    regions.columns = ["chrom", "start", "end"]
    scp.tl.get_footprint_score(printer, cell_grouping=[[bc]], group_names=[bc], regions=regions,
                                    region_width=1000, modes=MODES, n_jobs=n, save_key="fp", backed=False,
                                    overwrite=True)
    timing["footprint"] = time.time() - t0
    fp = printer.footprintsadata["fp"]  # obs = groups, obsm[region] = groups x modes x width
    t0 = time.time()
    files = {m: gzip.open(f"{out}/scprinter_r{m}.bedgraph.gz", "wt", compresslevel=3) for m in MODES}
    for rid in fp.obsm.keys():  # one entry per region, keyed "chrom:start-end"
        chrom, se = rid.split(":")
        s, e = (int(x) for x in se.split("-"))
        mat = np.asarray(fp.obsm[rid])[0]  # modes x width
        pos = np.arange(s, s + mat.shape[1])
        for k, m in enumerate(MODES):
            v = mat[k]
            files[m].write("".join(f"{chrom}\t{p}\t{p + 1}\t{x:.4g}\n" for p, x in zip(pos, v) if np.isfinite(x)))
    for f in files.values():
        f.close()
    timing["export"] = time.time() - t0
    pd.Series(timing).to_csv(f"{out}/scprinter_timing.tsv", sep="\t", header=["seconds"])
    printer.close()
    print("done")


if __name__ == "__main__":
    main()
