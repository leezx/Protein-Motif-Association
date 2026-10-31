# Gate V feasibility: pseudobulk GATA1-knockdown vs non-targeting accessibility outcome on Spear-ATAC K562 peaks.
# usage: Rscript 76_gateV_outcome.R <decompressed Peak_Matrix_SE.rds> <gata1_chip.tsv.gz of 75> <out dir>
# Cells: authors' high-confidence assignment sgAssignFinal (sgGATA1 vs sgsgNT); per-guide checks use sgIndividual.
# Pseudobulk samples = (group, 10x lane 'Sample'). Baseline universe: peaks with NT pseudobulk CPM >= 1 summed over
# lanes (NT cells only decide inclusion). DESeq2 ~ lane + group, median-of-ratios, results(alpha = 0.05); Y1 = padj <
# 0.05 and log2FC < 0. GATA1-bound = >= 2 unperturbed K562 GATA1 ChIP-Atlas experiments. Per guide: DESeq2 of each
# GATA1 guide vs NT (same lanes) and sign agreement with the pooled log2FC at bound peaks. Also writes peak_table.tsv.gz
# (all peaks: NT log2 CPM, universe flag, pooled and per-guide log2FC / padj) for the Gate V model.
suppressPackageStartupMessages({library(SummarizedExperiment); library(data.table); library(Matrix); library(DESeq2)})
a <- commandArgs(trailingOnly = TRUE); out <- a[3]; dir.create(out, showWarnings = FALSE, recursive = TRUE)
se <- readRDS(a[1]); cd <- as.data.table(as.data.frame(colData(se)), keep.rownames = "cell")
chip <- fread(a[2])
m <- assay(se)
pb <- function(lab, keep) { grp <- factor(paste(lab[keep], cd$Sample[keep], sep = "|"))
  x <- m[, keep] %*% sparseMatrix(seq_along(grp), as.integer(grp), x = 1); colnames(x) <- levels(grp); as.matrix(x) }
keep <- cd$sgAssignFinal %in% c("sgGATA1", "sgsgNT")
P <- pb(cd$sgAssignFinal, keep)
nt <- grepl("^sgsgNT", colnames(P))
cpm <- rowSums(P[, nt]) / sum(P[, nt]) * 1e6
uni <- cpm >= 1
cat("cells GATA1", sum(cd$sgAssignFinal == "sgGATA1"), "NT", sum(cd$sgAssignFinal == "sgsgNT"), "; universe peaks (NT CPM >= 1)", sum(uni), "of", nrow(P), "\n")
cdm <- data.frame(group = factor(ifelse(nt, "NT", "GATA1"), c("NT", "GATA1")), lane = factor(sub(".*\\|", "", colnames(P))))
dds <- DESeq(DESeqDataSetFromMatrix(round(P[uni, ]), cdm, ~lane + group), quiet = TRUE)
r <- results(dds, contrast = c("group", "GATA1", "NT"), alpha = 0.05)
d <- data.table(peak = which(uni) - 1L, baseMean = r$baseMean, log2FC = r$log2FoldChange, padj = r$padj)
d <- merge(d, chip[, .(peak, gata1_n_exp)], by = "peak")
d[, `:=`(bound = gata1_n_exp >= 2, lost = !is.na(padj) & padj < 0.05 & log2FC < 0)]
s <- d[, .(n = .N, testable = sum(!is.na(padj)), lost = sum(lost), gained = sum(!is.na(padj) & padj < 0.05 & log2FC > 0),
           median_lfc = median(log2FC, na.rm = TRUE)), by = bound]
print(s)
fwrite(d, file.path(out, "pooled_de.tsv.gz"), sep = "\t"); fwrite(s, file.path(out, "pooled_summary.tsv"), sep = "\t")
# per guide (sgIndividual) vs NT
g <- sort(unique(cd$sgIndividual[grepl("^sgGATA1-", cd$sgIndividual)]))
GL <- list()
gs <- rbindlist(lapply(g, function(gi) {
  kk <- cd$sgIndividual == gi | cd$sgAssignFinal == "sgsgNT"
  lab <- ifelse(cd$sgIndividual == gi, gi, "sgsgNT"); Q <- pb(lab, kk)
  nq <- grepl("^sgsgNT", colnames(Q))
  cm <- data.frame(group = factor(ifelse(nq, "NT", "G"), c("NT", "G")), lane = factor(sub(".*\\|", "", colnames(Q))))
  dq <- DESeq(DESeqDataSetFromMatrix(round(Q[uni, ]), cm, ~lane + group), quiet = TRUE)
  rq <- results(dq, contrast = c("group", "G", "NT"), alpha = 0.05)
  GL[[gi]] <<- data.table(peak = which(uni) - 1L, lfc = rq$log2FoldChange, padj = rq$padj)
  x <- GL[[gi]][d, on = "peak"]
  x[bound == TRUE, .(guide = gi, cells = sum(cd$sgIndividual == gi), lanes = sum(!nq), bound_testable = sum(!is.na(padj)),
                     lost = sum(!is.na(padj) & padj < 0.05 & lfc < 0), median_lfc = median(lfc, na.rm = TRUE),
                     sign_agree_with_pooled_lost = mean(sign(lfc[lost]) == -1, na.rm = TRUE),
                     cor_with_pooled = cor(lfc, log2FC, use = "complete.obs"))]
}))
print(gs); fwrite(gs, file.path(out, "per_guide.tsv"), sep = "\t")
pt <- data.table(peak = seq_len(nrow(P)) - 1L, nt_log2cpm = log2(cpm + 0.5), universe = uni)
pt <- merge(pt, d[, .(peak, log2FC, padj)], by = "peak", all.x = TRUE)
for (gi in names(GL)) pt <- merge(pt, setnames(copy(GL[[gi]]), c("lfc", "padj"), paste0(c("lfc_", "padj_"), gi)), by = "peak", all.x = TRUE)
fwrite(pt, file.path(out, "peak_table.tsv.gz"), sep = "\t")
