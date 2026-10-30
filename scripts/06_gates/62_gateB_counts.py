"""Gate B (plan v0.2 B3): baseline-only region universe and counts for the HT29 dTAG-SOX9 time course.

usage: 62_gateB_counts.py <manifest.tsv> <out_dir> [threads=8]

Same as 45_ht29_dtag_counts.py (fragment rule, occupancy calls, outputs) except that the consensus regions are built
from the two DMSO ATAC samples only (summit +-250 bp, merged, both replicates required), so no post-treatment peak
can decide whether or where a region exists. Context Query v0.1 used all 12 ATAC samples.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "04a_chipatlas"))
m45 = __import__("45_ht29_dtag_counts")
_consensus = m45.consensus


def baseline_consensus(atac):
    return _consensus([(s, p) for s, p in atac if s.startswith("DMSO_")])


m45.consensus = baseline_consensus

if __name__ == "__main__":
    m45.main(sys.argv[1], sys.argv[2], *(int(x) for x in sys.argv[3:4]))
