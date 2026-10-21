"""Step 4a §12: experiment inclusion for the accessibility and histone evidence tracks.

usage: 11_experiment_filter.py <experimentList.tab> <peak_counts_all.tsv> <out.tsv> [min_peaks=10000]
One row per hg38 experiment of class ATAC-Seq, DNase-seq or Histone:
  experiment_id, class, n_peaks, include, reasons (';' separated), title
Rules (user decision 2026-10-20):
  single_cell        title/attributes mention single-cell / single-nucleus, sc/snATAC, sci-ATAC, 10x/Chromium,
                     multiome, SHARE/SNARE-seq, droplet, scCUT&Tag, scChIP (all three classes)
  non_accessibility  ATAC/DNase only: the title names another assay (RNA-seq, ChIP-seq/ChIP-exo, a histone mark,
                     CUT&Tag/CUT&RUN, MNase, NOMe/bisulfite/WGBS, Hi-C/HiChIP/PLAC-seq, KAS-seq) or a control
                     (IgG, input, deproteinized / naked DNA, digestion background)
  low_peaks          ATAC/DNase only: fewer than min_peaks peaks in the q < 1e-5 archive
Word boundaries throughout: 'placenta' is not PLAC-seq and 'genome' is not NOMe.
"""
import re
import sys

SC = re.compile(r"single[- _]?(cell|nucle(us|i)\b)|\b(sc|sn)[- _]?(ATAC|DNase|CUT|ChIP)|\bsci[- ]?(ATAC|ChIP)\b|\b10x Genomics\b"
                r"|\bchromium\b|\bmultiome|\bSHARE[- ]?seq\b|\bSNARE[- ]?seq\b|\bdroplet|\bscCUT&?Tag\b|\bscChIP", re.I)
NONACC = re.compile(r"\bRNA[- ]?seq\b|\bChIP[- ]?(seq|exo)\b|\bChIPseq\b|\bH[1-4][AB]?K\d+|CUT\s?&\s?(Tag|RUN)\b"
                    r"|\bcut[- ]and[- ](tag|run)\b|\bMNase\b|micrococcal|\bNOMe[- ]?seq\b|\bbisulfite\b|\bWGBS\b"
                    r"|\bHi-?C\b|\bHiChIP\b|\bPLAC[- ]?seq\b|\bKAS[- ]?(seq|ATAC)\b|\bIgG\b|\binput\b"
                    r"|deproteini[sz]ed|naked DNA|digestion background", re.I)
RNA_ONLY = re.compile(r"\bRNA[- ]?seq\b", re.I)
ACC = re.compile(r"ATAC|DNase", re.I)
CLASSES = ("ATAC-Seq", "DNase-seq", "Histone")


def non_accessibility(title):
    """Title core without the GEO '; Homo sapiens; <strategy>' suffix names another assay or a control.
    A study title listing RNA-seq next to ATAC/DNase (multi-assay study) is not flagged for RNA-seq alone."""
    core = title.split("; Homo sapiens")[0]
    hits = {m.group(0) for m in NONACC.finditer(core)}
    if not hits:
        return False
    if ACC.search(core) and all(RNA_ONLY.fullmatch(h) for h in hits):
        return False
    return True


def main(explist, counts, out, min_peaks=10000):
    peaks = {}
    for line in open(counts):
        k, v = line.rstrip("\n").split("\t"); peaks[k] = int(v)
    n = {}
    with open(out, "w") as w:
        w.write("experiment_id\tclass\tn_peaks\tinclude\treasons\ttitle\n")
        for line in open(explist, encoding="utf-8", errors="replace"):
            f = line.rstrip("\n").split("\t")
            if len(f) < 9 or f[1] != "hg38" or f[2] not in CLASSES:
                continue
            p = peaks.get(f[0], 0); r = []
            if SC.search(" ".join(f[5:])):
                r.append("single_cell")
            if f[2] != "Histone":
                if non_accessibility(f[8]):
                    r.append("non_accessibility")
                if p < min_peaks:
                    r.append("low_peaks")
            inc = not r
            n.setdefault(f[2], [0, 0, 0, 0])
            n[f[2]][0] += 1; n[f[2]][1] += inc; n[f[2]][2] += p; n[f[2]][3] += p * inc
            w.write(f"{f[0]}\t{f[2]}\t{p}\t{inc}\t{';'.join(r) or '.'}\t{f[8][:200]}\n")
    for k, v in n.items():
        print(f"{k}: experiments {v[0]} included {v[1]}; peaks {v[2]} included {v[3]} ({100 * v[3] / max(v[2], 1):.1f}%)")


if __name__ == "__main__":
    a = sys.argv[1:]
    main(*a[:3], min_peaks=int(a[3]) if len(a) > 3 else 10000)
