"""Step 4b-1: fragments (5-column, +4/-5 shifted) -> paired-end BAM for BAM-only callers (HINT-ATAC, TOBIAS).

usage: frags_to_bam.py <frags.tsv.gz> <chrom.sizes> <regions.bed> <out.bam> [pad=2000]
Only fragments overlapping regions (+/- pad) are written. Each fragment becomes a proper pair of 50 bp reads (shorter
fragments: read length = fragment length) placed so the Tn5 cut sites are restored (R1 starts at start - 4 on +,
R2 ends at end + 5 on -). Sequences are N, qualities constant: callers only use positions. Output is sorted + indexed.
"""
import sys

import pysam

frags, sizes, bed, out = sys.argv[1:5]
pad = int(sys.argv[5]) if len(sys.argv) > 5 else 2000
chroms = [line.split()[:2] for line in open(sizes)]
hdr = {"HD": {"VN": "1.6", "SO": "unsorted"}, "SQ": [{"SN": c, "LN": int(n)} for c, n in chroms]}
tid = {c: i for i, (c, _) in enumerate(chroms)}
tb = pysam.TabixFile(frags)
tmp = out + ".unsorted.bam"
n = 0
seen = set()
with pysam.AlignmentFile(tmp, "wb", header=hdr) as w:
    for line in open(bed):
        c, s, e = line.split("\t")[:3]
        for row in tb.fetch(c, max(0, int(s) - pad), int(e) + pad):
            f = row.split("\t")
            a, b = int(f[1]) - 4, int(f[2]) + 5
            key = (c, a, b, f[3])
            if key in seen or b - a < 20:
                continue
            seen.add(key)
            for k in range(int(f[4]) if len(f) > 4 else 1):
                L = min(50, b - a)
                name = f"f{n}"
                n += 1
                for first in (True, False):
                    r = pysam.AlignedSegment()
                    r.query_name = name
                    r.reference_id = tid[c]
                    r.reference_start = a if first else b - L
                    r.query_sequence = "N" * L
                    r.query_qualities = pysam.qualitystring_to_array("I" * L)
                    r.cigarstring = f"{L}M"
                    r.mapping_quality = 60
                    r.flag = (1 | 2 | (64 if first else 128) | (32 if first else 16))
                    r.next_reference_id = tid[c]
                    r.next_reference_start = b - L if first else a
                    r.template_length = (b - a) if first else -(b - a)
                    w.write(r)
pysam.sort("-@", "4", "-o", out, tmp)
pysam.index(out)
import os
os.remove(tmp)
print(out, n, "fragments")
