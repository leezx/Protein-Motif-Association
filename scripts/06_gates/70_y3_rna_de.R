# Y3 (gene-level RNA response; Gate B follow-up): HT29 dTAG-SOX9 RNA-seq differential expression.
# usage: Rscript 70_y3_rna_de.R <rna_pipeline/2.RSEM dir> <genes.gtf> <out dir>
# Import equivalent to tximport(type = "rsem", txIn = FALSE, txOut = FALSE) + DESeqDataSetFromTximport: rounded
# gene expected counts; per-sample effective lengths used as a normalisation matrix (estimateSizeFactors(normMatrix)).
# DESeq2 ~ time (DMSO, D2, D4, D7, D10, D13; 2 replicates); results(alpha = 0.05) for each day vs DMSO; apeglm-shrunken
# log2FC for D4 vs DMSO. Genes: GENCODE v32 protein-coding and lncRNA. Writes rna_de.tsv.gz (gene_id, symbol, chrom, tss,
# strand, gene_type, baseMean, D4 log2FC / lfcSE / pvalue / padj / shrunken log2FC, na_reason) and rna_de_all_days.tsv.gz.
suppressPackageStartupMessages({library(DESeq2); library(data.table)})
a <- commandArgs(trailingOnly = TRUE); rsem <- a[1]; gtf <- a[2]; out <- a[3]
dir.create(out, showWarnings = FALSE, recursive = TRUE)
smp <- paste0(rep(c("DMSO", "D2", "D4", "D7", "D10", "D13"), each = 2), "_", 1:2)
rd <- lapply(smp, function(s) fread(file.path(rsem, paste0(s, ".genes.results")), select = c("gene_id", "effective_length", "expected_count")))
gid <- rd[[1]]$gene_id; stopifnot(all(sapply(rd, function(x) identical(x$gene_id, gid))))
cnt <- round(sapply(rd, `[[`, "expected_count")); len <- sapply(rd, `[[`, "effective_length")
colnames(cnt) <- colnames(len) <- smp; rownames(cnt) <- rownames(len) <- gid
g <- fread(cmd = paste("grep -P '\\tgene\\t'", gtf), header = FALSE, sep = "\t")
g[, `:=`(gene_id = sub('.*gene_id "([^".]+).*', "\\1", V9), gene_type = sub('.*gene_type "([^"]+)".*', "\\1", V9),
         symbol = sub('.*gene_name "([^"]+)".*', "\\1", V9))]
g <- g[gene_type %in% c("protein_coding", "lncRNA"), .(gene_id, symbol, gene_type, chrom = V1,
        tss = fifelse(V7 == "+", V4 - 1L, V5 - 1L), strand = V7)]
ens <- sub("_.*", "", gid)
keep <- ens %in% g$gene_id & rowSums(cnt) > 0
cnt <- cnt[keep, ]; len <- len[keep, ]; len[len <= 0] <- 1
nm <- len / exp(rowMeans(log(len)))
cd <- data.frame(time = factor(sub("_.*", "", smp), c("DMSO", "D2", "D4", "D7", "D10", "D13")), row.names = smp)
dds <- DESeqDataSetFromMatrix(cnt, cd, ~time)
dds <- estimateSizeFactors(dds, normMatrix = nm)
dds <- DESeq(dds, quiet = TRUE)
allr <- rbindlist(lapply(c("D2", "D4", "D7", "D10", "D13"), function(d) {
  r <- results(dds, contrast = c("time", d, "DMSO"), alpha = 0.05)
  data.table(gene = rownames(r), contrast = d, baseMean = r$baseMean, log2FC = r$log2FoldChange, padj = r$padj) }))
fwrite(allr, file.path(out, "rna_de_all_days.tsv.gz"), sep = "\t")
r4 <- results(dds, contrast = c("time", "D4", "DMSO"), alpha = 0.05)
sh <- lfcShrink(dds, coef = "time_D4_vs_DMSO", type = "apeglm", quiet = TRUE)
o <- data.table(gene = rownames(r4), gene_id = sub("_.*", "", rownames(r4)), baseMean = r4$baseMean, log2FC = r4$log2FoldChange,
                lfcSE = r4$lfcSE, pvalue = r4$pvalue, padj = r4$padj, log2FC_shrunk = sh$log2FoldChange)
o[, na_reason := fifelse(!is.na(padj), "", fifelse(is.na(pvalue), "cooks_outlier_or_zero", "independent_filtering"))]
o <- merge(o, g, by = "gene_id")
fwrite(o, file.path(out, "rna_de.tsv.gz"), sep = "\t")
t <- o[na_reason == ""]
cat("genes", nrow(o), "testable", nrow(t), "| D4 padj<0.05:", t[padj < 0.05, .N], "(up", t[padj < 0.05 & log2FC > 0, .N],
    "down", t[padj < 0.05 & log2FC < 0, .N], ") | padj<0.05 & |shrunk|>=0.585:", t[padj < 0.05 & abs(log2FC_shrunk) >= 0.585, .N], "\n")
print(table(o$na_reason)); print(summary(abs(t$log2FC_shrunk)))
s <- o[symbol == "SOX9"]; print(s)
writeLines(capture.output(sessionInfo()), file.path(out, "sessionInfo.70.txt"))
