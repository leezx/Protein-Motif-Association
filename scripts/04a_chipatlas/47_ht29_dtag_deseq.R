# Differential ATAC and CUT&RUN signal over the HT29 dTAG-SOX9 time course (Context Query v0.1). Argos, r4p3.
# usage: Rscript 47_ht29_dtag_deseq.R <out_dir of 45> <cutrun_pipeline dir (2.Ecoli_bam/*.Ecoli.Map2GenomeStat.xls)>
# ATAC: DESeq2 ~ time on all consensus regions, median-of-ratios size factors; each day vs DMSO (Wald, BH).
# CUT&RUN (SOX9, SMARCC1): DESeq2 ~ time on regions with a DMSO peak of that assay in either replicate. Primary size
# factors = total counted fragments (lib_size of 45) scaled to geometric mean 1, so a global loss of the antibody
# signal is not normalised away. Sensitivities: E. coli spike-in (concordant pairs; fails QC here: carry-over is ~10x
# lower in every D4 library incl. IgG, i.e. a library batch) and median-of-ratios (removes global change). Writes de_<assay>.tsv.gz (region, contrast,
# baseMean, log2FC, lfcSE, pvalue, padj, norm) and size_factors.tsv.
suppressPackageStartupMessages({library(DESeq2); library(data.table)})
args <- commandArgs(trailingOnly = TRUE)
dir <- args[1]; cnr <- args[2]
cnt <- fread(file.path(dir, "counts.tsv.gz"))
lib <- fread(file.path(dir, "lib_size.tsv"))
occ <- fread(file.path(dir, "occupancy.tsv.gz"))
DAYS <- c("D2", "D4", "D7", "D10", "D13")

spike <- function(s) {
  x <- readLines(file.path(cnr, "2.Ecoli_bam", paste0(s, ".Ecoli.Map2GenomeStat.xls")))
  sum(as.numeric(sub("^\\s*(\\d+).*", "\\1", grep("aligned concordantly (exactly 1|>1) time", x, value = TRUE))))
}

run <- function(target, keep, norm) {
  s <- lib[assay == target]
  m <- as.matrix(cnt[keep, s$sample, with = FALSE]); rownames(m) <- cnt$region[keep]
  cd <- data.frame(time = factor(s$time, c("DMSO", DAYS)), row.names = s$sample)
  dds <- DESeqDataSetFromMatrix(m, cd, ~time)
  if (norm %in% c("spikein", "libsize")) {
    sf <- if (norm == "spikein") sapply(s$sample, spike) else s$lib_size
    sizeFactors(dds) <- sf / exp(mean(log(sf)))
  } else dds <- estimateSizeFactors(dds)
  dds <- DESeq(dds, quiet = TRUE)
  sfo <- data.table(sample = s$sample, assay = target, norm = norm, size_factor = sizeFactors(dds))
  res <- rbindlist(lapply(DAYS, function(d) {
    r <- results(dds, contrast = c("time", d, "DMSO"))
    data.table(region = rownames(r), contrast = paste0(d, "_vs_DMSO"), baseMean = r$baseMean,
               log2FC = r$log2FoldChange, lfcSE = r$lfcSE, pvalue = r$pvalue, padj = r$padj, norm = norm)
  }))
  list(res = res, sf = sfo)
}

out <- list(); sfs <- list()
a <- run("ATAC", rep(TRUE, nrow(cnt)), "median_ratio"); out$ATAC <- a$res; sfs$ATAC <- a$sf
for (as in c("SOX9", "SMARCC1")) {
  keep <- occ[[paste0(as, "_DMSO_any")]]
  r <- lapply(c("libsize", "spikein", "median_ratio"), function(n) run(as, keep, n))
  out[[as]] <- rbindlist(lapply(r, `[[`, "res")); sfs[[as]] <- rbindlist(lapply(r, `[[`, "sf"))
}
for (as in names(out)) fwrite(out[[as]], file.path(dir, sprintf("de_%s.tsv.gz", as)), sep = "\t")
fwrite(rbindlist(sfs), file.path(dir, "size_factors.tsv"), sep = "\t")
for (as in names(out)) print(out[[as]][, .(n = .N, up = sum(padj < 0.05 & log2FC > 0, na.rm = TRUE),
                                         down = sum(padj < 0.05 & log2FC < 0, na.rm = TRUE),
                                         median_lfc = median(log2FC, na.rm = TRUE)), by = .(norm, contrast)])
print(rbindlist(sfs))
writeLines(capture.output(sessionInfo()), file.path(dir, "sessionInfo.47.txt"))
