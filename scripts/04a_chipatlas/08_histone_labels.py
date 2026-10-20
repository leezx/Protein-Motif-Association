"""Step 4a §11: deterministic classification of ChIP-Atlas histone-class labels.

usage: 08_histone_labels.py <histone_marks.tsv (mark, n_experiments, ...)> <out.tsv>
category:
  histone_modification       one histone, one residue, one defined modification (e.g. H3K27ac, H2A.XS139ph)
  histone_variant_or_core    core histones, variants, linker histones, CENPA, oncohistone mutants (H3K27M)
  pan_or_ambiguous           pan/global antibodies, unspecified degree (H3K27me), multi-site or dual-modification
                             antibodies, unspecified site (H2Aub), nonstandard labels (H4K4me3, H3K14me3, H3K4ox)
  non_histone_target         DNA-binding proteins filed under Histone (CENPB, HINFP)
canonical_label merges spelling variants of one modification only (H2BK120ub1 -> H2BK120ub; Ub -> ub).
functional_group is set for the six core marks; other modifications get '.'.
"""
import re
import sys

NON_HISTONE = {"CENPB", "HINFP"}
NONSTANDARD = {"H4K4me3", "H3K14me3", "H3K4ox", "H3K9acS10ph"}
CORE = {"H3K27ac": "active_regulatory", "H3K4me3": "active_regulatory", "H3K4me1": "enhancer_associated",
        "H3K27me3": "repressive", "H3K9me3": "repressive", "H3K36me3": "transcription_elongation"}
HIST = r"(?:H1(?:\.\d)?|H2A(?:\.X|\.Z(?:\.\d)?)?|H2B|H3(?:\.\d)?|H4)"
MOD = r"(?:ac|me1|me2|me3|ph|ub1?|Ub|cr|la|su|suc|bu|sc|cit|GlcNAc)"
SINGLE = re.compile(rf"^{HIST}[KRSTYP]\d+{MOD}$")
VARIANT = re.compile(r"^(?:H1(?:\.\d|\.X|B|t)?|H2|H2A(?:\.X|\.Z(?:\.\d)?)?|H2B|H3(?:\.\d|\.Y|\.3B)?|H4"
                     r"|macroH2A\d(?:\.\d)?|CENPA|H3(?:\.3)?K27M)$")


def classify(m):
    if m in NON_HISTONE:
        return "non_histone_target", "filed under Histone in ChIP-Atlas; DNA-binding protein"
    if m in NONSTANDARD:
        return "pan_or_ambiguous", "nonstandard or dual-modification label"
    if VARIANT.match(m):
        return "histone_variant_or_core", "core/linker histone, variant or oncohistone mutant"
    if SINGLE.match(m):
        return "histone_modification", ""
    return "pan_or_ambiguous", "pan, unspecified degree or site, or multi-site antibody"


def canonical(m):
    return re.sub(r"ub1$", "ub", re.sub(r"Ub$", "ub", m))


def main(src, out):
    rows = [l.rstrip("\n").split("\t") for l in open(src)][1:]
    with open(out, "w") as w:
        w.write("label\tcategory\tcanonical_label\tfunctional_group\tn_experiments\tnote\n")
        for r in rows:
            cat, note = classify(r[0])
            can = canonical(r[0]) if cat == "histone_modification" else "."
            w.write(f"{r[0]}\t{cat}\t{can}\t{CORE.get(can, '.')}\t{r[1]}\t{note}\n")


if __name__ == "__main__":
    main(*sys.argv[1:3])
