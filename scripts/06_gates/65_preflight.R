# Preflight summary for Gate A / B (plan v0.2 E5 P0): label counts, anchors, universe, fold balance. No model is fitted.
# usage: Rscript 65_preflight.R <gateA root> <gateB root>
suppressPackageStartupMessages(library(data.table))
a <- commandArgs(TRUE); A <- a[1]; B <- a[2]
prot <- fread(file.path(A, "features/proteins.tsv")); pr <- fread(file.path(A, "features/pairs.tsv.gz"))
cand <- prot[cls == "Sequence-specific TF" & n_exp >= 20 & n_celltypes >= 3, protein]
np <- sapply(cand, function(x) pr[(protein_a == x | protein_b == x) & same_complex == TRUE, .N])
cat("GateA anchor candidates", length(cand), "evaluable(>=3 CP)", sum(np >= 3), "positives in evaluable", sum(np[np >= 3]), "\n")
print(sort(np[np >= 3], decreasing = TRUE))
bp <- "/home/zz950/DATA/2.PROJECTS/PMA/occupancy_chipatlas/raw/2026-10-30_bioplex"
for (f in list.files(bp, "tsv$", full.names = TRUE)) { b <- fread(f); n <- unique(c(b$SymbolA, b$SymbolB))
  ev <- cand[np >= 3]; k <- paste(pmin(b$SymbolA, b$SymbolB), pmax(b$SymbolA, b$SymbolB))
  x <- pr[(protein_a %in% ev | protein_b %in% ev) & protein_a %in% n & protein_b %in% n & same_complex == FALSE]
  cat(basename(f), "eligible pairs", nrow(x), "BioPlex positives", sum(paste(x$protein_a, x$protein_b) %in% k), "anchors in network", sum(ev %in% n), "\n") }
f <- fread(file.path(B, "features/features.tsv.gz")); de <- fread(file.path(B, "counts/de_ATAC.tsv.gz"))[contrast == "D4_vs_DMSO"]
f <- merge(f, de[, .(region, log2FC, padj)], by = "region", all.x = TRUE)
f[, y := !is.na(padj) & padj < 0.05 & log2FC < 0]
U <- f[sox9_dmso_both == TRUE & blacklist == FALSE]
cat("GateB all regions", nrow(f), "lost_D4 all", sum(f$y), "; primary universe", nrow(U), "positives", sum(U$y), "prevalence", round(mean(U$y), 3), "\n")
cat("NA padj in primary", sum(is.na(U$padj)), "; HT-29 ATAC peak regions in primary", sum(U$ext_atac_ht29_n > 0), "\n")
print(U[, .(n = .N, pos = sum(y)), by = chrom][order(-n)])
print(summary(U[, .(atac_log2cpm, sox9_log2cpm, h3k27ac_log2cpm, pma_degree, ext_atac_frac, near_gene_log2tpm)]))
