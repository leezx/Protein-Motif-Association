# Gate V feasibility preflight: inventory of the Spear-ATAC K562 LargeScreen peak matrix (GSE168851).
# usage: Rscript 74_gateV_inventory.R <decompressed *_Peak_Matrix_SE.rds> <out dir>
# Reports the SummarizedExperiment layout, the sgRNA / target assignment columns, cells per GATA1 guide and per
# non-targeting guide by replicate (sample), the peak set, and pseudobulk counts per (guide, replicate). Writes
# cells_by_guide.tsv, colData_head.tsv, peaks.bed.gz, pseudobulk_counts.rds (peak x [guide, sample]) for the
# feasibility decision. No outcome model is fitted.
suppressPackageStartupMessages({library(SummarizedExperiment); library(data.table); library(Matrix)})
a <- commandArgs(trailingOnly = TRUE); out <- a[2]; dir.create(out, showWarnings = FALSE, recursive = TRUE)
se <- readRDS(a[1])
print(se); print(assayNames(se))
cd <- as.data.table(as.data.frame(colData(se)), keep.rownames = "cell")
fwrite(head(cd, 50), file.path(out, "colData_head.tsv"), sep = "\t")
cat("colData columns:\n"); print(sapply(cd, function(x) if (is.numeric(x)) "num" else length(unique(x))))
r <- rowRanges(se)
cat("peaks", length(r), "; widths", paste(head(sort(unique(width(r)))), collapse = ","), "; seqnames", paste(head(unique(as.character(seqnames(r))), 3), collapse = ","), "\n")
fwrite(data.table(chrom = as.character(seqnames(r)), start = start(r) - 1L, end = end(r)), file.path(out, "peaks.bed.gz"), sep = "\t", col.names = FALSE)
cand <- names(cd)[sapply(cd, function(x) is.character(x) || is.factor(x))]
for (g in cand) { u <- unique(as.character(cd[[g]])); if (length(u) > 1 && length(u) < 2000 && any(grepl("GATA1|NT|non|Non", u))) {
  cat("== column", g, ":", length(u), "levels\n"); t <- sort(table(cd[[g]]), decreasing = TRUE)
  print(head(t, 10)); print(t[grepl("GATA1", names(t))]); print(head(t[grepl("^NT|non|Non|safe", names(t))], 20)) } }
gc <- intersect(c("sgAssign", "sgRNA", "sgAssignFinal", "Guide"), names(cd))[1]
sc <- intersect(c("Sample", "sample", "Rep"), names(cd))[1]
cat("guide column:", gc, "; sample column:", sc, "\n")
if (!is.na(gc)) {
  cd[, guide := as.character(get(gc))]; cd[, smp := if (!is.na(sc)) as.character(get(sc)) else "all"]
  keep <- cd[grepl("GATA1", guide) | grepl("^NT|non-?target|Non", guide)]
  cb <- keep[, .N, by = .(guide, smp)][order(guide, smp)]
  fwrite(cb, file.path(out, "cells_by_guide.tsv"), sep = "\t"); print(dcast(cb, guide ~ smp, value.var = "N", fill = 0))
  m <- assay(se)[, keep$cell]
  grp <- paste(keep$guide, keep$smp, sep = "|")
  pb <- m %*% sparseMatrix(seq_along(grp), as.integer(factor(grp)), x = 1, dimnames = list(NULL, levels(factor(grp))))
  saveRDS(list(counts = as.matrix(pb), groups = levels(factor(grp))), file.path(out, "pseudobulk_counts.rds"))
  cat("pseudobulk columns", ncol(pb), "; total fragments per group:\n"); print(round(colSums(pb)))
}
