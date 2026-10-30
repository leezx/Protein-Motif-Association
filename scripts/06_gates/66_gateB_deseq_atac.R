# Gate B preflight fix 1: ATAC DESeq2 on the baseline-only universe with alpha matched to the padj threshold, and the
# reason for every NA padj. Same model as 47_ht29_dtag_deseq.R (ATAC, ~time, median-of-ratios) except
# results(..., alpha = 0.05) so independent filtering is optimised for the 0.05 cut used by Y1.
# usage: Rscript 66_gateB_deseq_atac.R <gateB counts dir>
# Writes de_ATAC_alpha05.tsv.gz (region, contrast, baseMean, log2FC, lfcSE, pvalue, padj, na_reason) and
# na_reasons.tsv. na_reason: all_zero (baseMean 0), cooks_outlier (pvalue NA, baseMean > 0),
# independent_filtering (pvalue present, padj NA).
suppressPackageStartupMessages({library(DESeq2); library(data.table)})
dir <- commandArgs(trailingOnly = TRUE)[1]
cnt <- fread(file.path(dir, "counts.tsv.gz"))
lib <- fread(file.path(dir, "lib_size.tsv"))
s <- lib[assay == "ATAC"]
m <- as.matrix(cnt[, s$sample, with = FALSE]); rownames(m) <- cnt$region
cd <- data.frame(time = factor(s$time, c("DMSO", "D2", "D4", "D7", "D10", "D13")), row.names = s$sample)
dds <- DESeq(DESeqDataSetFromMatrix(m, cd, ~time), quiet = TRUE)
out <- rbindlist(lapply(c("D2", "D4", "D7", "D10", "D13"), function(d) {
  r <- results(dds, contrast = c("time", d, "DMSO"), alpha = 0.05)
  data.table(region = rownames(r), contrast = paste0(d, "_vs_DMSO"), baseMean = r$baseMean, log2FC = r$log2FoldChange,
             lfcSE = r$lfcSE, pvalue = r$pvalue, padj = r$padj)
}))
out[, na_reason := fifelse(!is.na(padj), "", fifelse(baseMean == 0, "all_zero",
                    fifelse(is.na(pvalue), "cooks_outlier", "independent_filtering")))]
fwrite(out, file.path(dir, "de_ATAC_alpha05.tsv.gz"), sep = "\t")
fwrite(out[, .N, by = .(contrast, na_reason)], file.path(dir, "na_reasons.tsv"), sep = "\t")
print(out[, .N, by = .(contrast, na_reason)])
writeLines(capture.output(sessionInfo()), file.path(dir, "sessionInfo.66.txt"))
