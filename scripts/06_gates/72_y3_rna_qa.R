# Y3 preflight P0-1: RNA outcome QA for 70_y3_rna_de.R.
# usage: Rscript 72_y3_rna_qa.R <rna_pipeline/2.RSEM dir> <70 out dir (rna_de.tsv.gz)> <qa out dir>
# (1) Numerical equivalence of the length correction: route A = 70's estimateSizeFactors(normMatrix = centred effective
#     lengths); route B = DESeq2's own tximport path (assay "avgTxLength" set as DESeqDataSetFromTximport does; zero
#     lengths -> 1 as in the DESeq2 vignette for RSEM gene-level input). Compare normalizationFactors and D4 results.
# (2) Gene / sample alignment across the 12 RSEM files. (3) Size factors, replicate Pearson correlations of
#     log2(normalised + 1), PCA (top 2,000 variable genes, VST). Writes rna_qa.tsv, rna_pca.tsv, rna_rep_cor.tsv,
#     rna_pca.png, rna_outcome_QA.md and prints a summary.
suppressPackageStartupMessages({library(DESeq2); library(data.table); library(ggplot2)})
a <- commandArgs(trailingOnly = TRUE); rsem <- a[1]; de_dir <- a[2]; out <- a[3]
dir.create(out, showWarnings = FALSE, recursive = TRUE)
smp <- paste0(rep(c("DMSO", "D2", "D4", "D7", "D10", "D13"), each = 2), "_", 1:2)
rd <- lapply(smp, function(s) fread(file.path(rsem, paste0(s, ".genes.results")), select = c("gene_id", "effective_length", "expected_count", "TPM")))
gid <- rd[[1]]$gene_id
aligned <- all(sapply(rd, function(x) identical(x$gene_id, gid)))
o <- fread(file.path(de_dir, "rna_de.tsv.gz"))
keep <- gid %in% o$gene
cnt <- round(sapply(rd, `[[`, "expected_count"))[keep, ]; len <- sapply(rd, `[[`, "effective_length")[keep, ]
colnames(cnt) <- colnames(len) <- smp; rownames(cnt) <- rownames(len) <- gid[keep]
len[len <= 0] <- 1
cd <- data.frame(time = factor(sub("_.*", "", smp), c("DMSO", "D2", "D4", "D7", "D10", "D13")), row.names = smp)
# route A (70)
dA <- DESeqDataSetFromMatrix(cnt, cd, ~time)
dA <- estimateSizeFactors(dA, normMatrix = len / exp(rowMeans(log(len))))
# route B (DESeq2 tximport path)
dB <- DESeqDataSetFromMatrix(cnt, cd, ~time)
assays(dB)[["avgTxLength"]] <- len
dB <- estimateSizeFactors(dB)
nfA <- normalizationFactors(dA); nfB <- normalizationFactors(dB)
eq_nf <- max(abs(log(nfA) - log(nfB)))
dA <- DESeq(dA, quiet = TRUE); dB <- DESeq(dB, quiet = TRUE)
rA <- results(dA, contrast = c("time", "D4", "DMSO"), alpha = 0.05); rB <- results(dB, contrast = c("time", "D4", "DMSO"), alpha = 0.05)
eq_lfc <- max(abs(rA$log2FoldChange - rB$log2FoldChange), na.rm = TRUE)
same_calls <- identical(!is.na(rA$padj) & rA$padj < 0.05, !is.na(rB$padj) & rB$padj < 0.05)
same_as_70 <- isTRUE(all.equal(rA$log2FoldChange[match(o$gene, rownames(rA))], o$log2FC, tolerance = 1e-8))
# library-level QA
sfA <- colMeans(nfA)
vs <- vst(dA, blind = TRUE)
m <- assay(vs); top <- order(-apply(m, 1, var))[1:2000]
pc <- prcomp(t(m[top, ]))
ve <- round(100 * pc$sdev^2 / sum(pc$sdev^2), 1)
pcd <- data.table(sample = smp, time = cd$time, PC1 = pc$x[, 1], PC2 = pc$x[, 2])
ln <- log2(counts(dA, normalized = TRUE) + 1)
rc <- data.table(time = levels(cd$time), rep_pearson = sapply(levels(cd$time), function(t) cor(ln[, paste0(t, "_1")], ln[, paste0(t, "_2")])))
cc <- cor(ln); diag(cc) <- NA
nearest <- data.table(sample = smp, best_partner = colnames(cc)[apply(cc, 2, which.max)])
nearest[, partner_is_replicate := sub("_.*", "", sample) == sub("_.*", "", best_partner)]
qa <- data.table(check = c("rsem_gene_order_aligned", "normFactor_max_abs_log_diff_A_vs_B", "D4_log2FC_max_abs_diff_A_vs_B",
                           "D4_significant_calls_identical", "routeA_equals_70_output", "nearest_sample_is_replicate"),
                 value = c(aligned, signif(eq_nf, 3), signif(eq_lfc, 3), same_calls, same_as_70, all(nearest$partner_is_replicate)))
fwrite(qa, file.path(out, "rna_qa.tsv"), sep = "\t"); fwrite(pcd, file.path(out, "rna_pca.tsv"), sep = "\t")
fwrite(merge(rc, data.table(time = sub("_.*", "", smp), sample = smp, mean_norm_factor = sfA)[, .(mean_norm_factor = paste(round(mean_norm_factor, 3), collapse = ", ")), by = time], by = "time"),
       file.path(out, "rna_rep_cor.tsv"), sep = "\t")
p <- ggplot(pcd, aes(PC1, PC2, colour = time, label = sample)) + geom_point(size = 2) + geom_text(size = 2, vjust = -0.8) +
  labs(x = sprintf("PC1 (%s%%)", ve[1]), y = sprintf("PC2 (%s%%)", ve[2]), title = "HT29 dTAG-SOX9 RNA-seq, VST top 2,000 genes") + theme_classic(base_size = 8)
ggsave(file.path(out, "rna_pca.png"), p, width = 120, height = 90, units = "mm", dpi = 200)
print(qa); print(rc); print(nearest); cat("PC1/PC2 % var:", ve[1:2], "\n"); print(pcd)
