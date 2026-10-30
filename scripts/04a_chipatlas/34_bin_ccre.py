"""cCRE class of each context bin, for 34_hotspot_context_panels.R.

usage: 34_bin_ccre.py <context_bins.bed> <bins_annotation.npz> <out.tsv>
"""
import sys

import numpy as np

CCRE = ["PLS", "pELS", "dELS", "CA-H3K4me3", "CA-CTCF", "CA-TF", "TF", "CA", "none"]

bed, npz, out = sys.argv[1:4]
cc = np.load(npz)["ccre"]
with open(bed) as f, open(out, "w") as o:
    o.write("bin_id\tccre\n")
    for line in f:
        i = int(line.split("\t")[3])
        o.write(f"{i}\t{CCRE[cc[i]]}\n")
