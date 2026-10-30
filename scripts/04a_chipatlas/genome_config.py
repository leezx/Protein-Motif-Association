"""Step 4a: per-genome settings (design §19). PMA_GENOME = hg38 (default) | mm10.

Python: `import genome_config as gc; gc.G, gc.CFG[...]`. Shell: `eval "$(python genome_config.py)"` exports
G, RAW_RELEASE, PEAKS, SIZES_NAME, BLACKLIST_NAME, GENE_NS. hg38 values reproduce the v1 release exactly.
"""
import os
import sys

GENOMES = {
    "hg38": dict(
        raw_release="2026-10-17", gene_ns="hgnc", gene_authority="HGNC",
        peaks="allPeaks_light.hg38.05.bed.gz", sizes="hg38.chrom.sizes", blacklist="hg38-blacklist.v2.bed.gz",
        exceptions="chipatlas_antigen_exceptions.tsv",
        release="PMA_ChIPAtlas_hg38_20260926peaks_20261014meta_v1", peaks_date="2026-09-26",
        sources=dict(hgnc="hgnc_complete_set.txt downloaded 2026-10-17",
                     blacklist="ENCODE hg38 blacklist v2 (Boyle-Lab/Blacklist)",
                     tf_list="Lambert et al. 2018 TF_names_v_1.01"),
        tabix_checks="chr1:1000000-1010000 chrX:73800000-73900000 chr17:7660000-7690000"),
    "mm10": dict(
        raw_release="2026-10-30", gene_ns="mgi", gene_authority="MGI",
        peaks="allPeaks_light.mm10.05.bed.gz", sizes="mm10.chrom.sizes", blacklist="mm10-blacklist.v2.bed.gz",
        exceptions="chipatlas_antigen_exceptions.mm10.tsv",
        release="PMA_ChIPAtlas_mm10_20260926peaks_20261014meta_v1", peaks_date="2026-09-26",
        sources=dict(mgi="MGI MRK_List1.rpt (markers incl. withdrawn) downloaded with the raw release",
                     go="GO Consortium mgi.gaf.gz + go-basic.obo downloaded with the raw release",
                     blacklist="ENCODE mm10 blacklist v2 (Boyle-Lab/Blacklist)",
                     tf_list="MGI GO: GO:0003700 DNA-binding transcription factor activity and descendants"),
        tabix_checks="chr1:4800000-4900000 chrX:103400000-103500000 chr11:69580000-69600000"),  # Trp53 on chr11
}
G = os.environ.get("PMA_GENOME", "hg38")
if G not in GENOMES:
    sys.exit(f"PMA_GENOME={G!r} not supported; use one of {sorted(GENOMES)}")
CFG = GENOMES[G]
PREFIX = f"PMA_chipatlas_{G}"
SYM_COL, ID_COL = f"antigen_{CFG['gene_ns']}_symbol", f"antigen_{CFG['gene_ns']}_id"

if __name__ == "__main__":
    c = CFG
    for k, v in (("G", G), ("RAW_RELEASE", os.environ.get("PMA_RAW_RELEASE", c["raw_release"])),
                 ("PEAKS", c["peaks"]), ("SIZES_NAME", c["sizes"]), ("BLACKLIST_NAME", c["blacklist"]),
                 ("GENE_NS", c["gene_ns"]), ("TABIX_CHECKS", c["tabix_checks"])):
        print(f"{k}='{v}'")
