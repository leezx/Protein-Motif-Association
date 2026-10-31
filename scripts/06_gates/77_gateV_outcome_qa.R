# Gate V preflight amendment v0.2 (paper_ideas_v2_gateV_preflight_review1.md): outcome with author NT-guide QC and the
# outcome-reliability QA. Replaces 76 as the outcome builder.
# usage: Rscript 77_gateV_outcome_qa.R <decompressed Peak_Matrix_SE.rds> <gata1_chip.tsv.gz of 75> <out dir>
# Cells: sgAssignFinal (authors' high-confidence calls). NT = sgsgNT minus the guides the authors excluded as
# pseudobulk-PCA outliers (sgNT-5, -6, -8, -11, -12; Pierce et al. 2021). Pseudobulk samples = (group, lane). Universe:
# NT pseudobulk CPM >= 1 (retained NT cells only) -> "NT-accessible subset of pooled-called ArchR peaks". DESeq2
# ~ lane + group, median-of-ratios, alpha 0.05; Y1 = padj < 0.05 & log2FC < 0 (GATA1 CRISPRi vs NT). Bound = >= 2
# unperturbed K562 GATA1 ChIP-Atlas experiments.
# QA: (A) lane x guide cells / fragments / median nFrags / TSS enrichment, design rank; (B) NT-vs-NT null: retained
# NT guides split by guide number (odd vs even), same pipeline, apparent loss at bound regions; (C) NT downsampled
# within lane to the GATA1 cell count (seed 20261031), compared with the full contrast; (P1) per-guide log2FC on all
# bound testable regions (sign agreement, correlation with pooled, leave-one-guide-out pooled effect).
suppressPackageStartupMessages({library(SummarizedExperiment); library(data.table); library(Matrix); library(DESeq2)})
a <- commandArgs(trailingOnly = TRUE); out <- a[3]; dir.create(out, showWarnings = FALSE, recursive = TRUE)
se <- readRDS(a[1]); cd <- as.data.table(as.data.frame(colData(se)), keep.rownames = "cell")
chip <- fread(a[2]); m <- assay(se)
OUTLIER_NT <- paste0("sgsgNT-", c(5, 6, 8, 11, 12))

# ---- P0-1 control-guide QC ----
ntc <- cd[sgAssignFinal == "sgsgNT"]
cg <- ntc[, .(cells = .N, author_outlier = sgIndividual[1] %in% OUTLIER_NT), by = .(guide = sgIndividual)][order(guide)]
cg <- merge(cg, dcast(ntc[, .N, by = .(guide = sgIndividual, Sample)], guide ~ Sample, value.var = "N", fill = 0), by = "guide")
fwrite(cg, file.path(out, "control_guide_qc.tsv"), sep = "\t")
cat("NT cells (sgAssignFinal)", nrow(ntc), "; in author-outlier guides", sum(ntc$sgIndividual %in% OUTLIER_NT),
    "; guide identity missing", sum(!grepl("^sgsgNT-", ntc$sgIndividual)), "\n")
cd[, grp := fifelse(sgAssignFinal == "sgGATA1", "GATA1",
            fifelse(sgAssignFinal == "sgsgNT" & !sgIndividual %in% OUTLIER_NT & grepl("^sgsgNT-", sgIndividual), "NT", NA_character_))]

# ---- (A) lane x guide QA ----
lg <- cd[!is.na(grp), .(cells = .N, frags = sum(nFrags), median_nFrags = median(nFrags), median_TSSe = median(TSSEnrichment),
                        median_FRIP = median(FRIP)), by = .(grp, guide = sgIndividual, lane = Sample)][order(grp, guide, lane)]
fwrite(lg, file.path(out, "lane_guide_counts.tsv"), sep = "\t")
qc_grp <- cd[!is.na(grp), .(cells = .N, median_nFrags = median(nFrags), median_TSSe = median(TSSEnrichment), median_FRIP = median(FRIP)), by = grp]
print(qc_grp)

pb <- function(lab, keep) { grp <- factor(paste(lab[keep], cd$Sample[keep], sep = "|"))
  x <- m[, keep] %*% sparseMatrix(seq_along(grp), as.integer(grp), x = 1); colnames(x) <- levels(grp); as.matrix(x) }
de <- function(P, uni, a_lab, b_lab) {
  g <- sub("\\|.*", "", colnames(P))
  cm <- data.frame(group = factor(ifelse(g == b_lab, "B", "A"), c("B", "A")), lane = factor(sub(".*\\|", "", colnames(P))))
  X <- model.matrix(~lane + group, cm)
  dds <- DESeq(DESeqDataSetFromMatrix(round(P[uni, ]), cm, ~lane + group), quiet = TRUE)
  r <- results(dds, contrast = c("group", "A", "B"), alpha = 0.05)
  list(rank_ok = qr(X)$rank == ncol(X), d = data.table(peak = which(uni) - 1L, log2FC = r$log2FoldChange, padj = r$padj))
}
keep <- !is.na(cd$grp)
P <- pb(cd$grp, keep)
nt <- grepl("^NT\\|", colnames(P))
cpm <- rowSums(P[, nt]) / sum(P[, nt]) * 1e6
uni <- cpm >= 1
main <- de(P, uni, "GATA1", "NT")
d <- merge(main$d, chip[, .(peak, gata1_n_exp)], by = "peak")
d[, `:=`(bound = gata1_n_exp >= 2, lost = !is.na(padj) & padj < 0.05 & log2FC < 0)]
s_main <- d[, .(n = .N, testable = sum(!is.na(padj)), lost = sum(lost), median_lfc = median(log2FC, na.rm = TRUE)), by = bound]
cat("universe", sum(uni), "; design full rank", main$rank_ok, "\n"); print(s_main)
lane_cor <- NULL
# per-lane consistency of the GATA1 effect at bound regions (log2 CPM difference per lane)
lc <- rbindlist(lapply(sort(unique(cd$Sample)), function(L) {
  g <- P[, paste0("GATA1|", L)]; n <- P[, paste0("NT|", L)]
  dd <- log2((g + 0.5) / sum(g) * 1e6) - log2((n + 0.5) / sum(n) * 1e6)
  data.table(lane = L, median_diff_bound = median(dd[uni & chip$gata1_n_exp >= 2]), median_diff_unbound = median(dd[uni & chip$gata1_n_exp < 2]),
             cor_with_pooled_bound = cor(dd[d$peak[d$bound] + 1L], d$log2FC[d$bound], use = "complete.obs")) }))
fwrite(lc, file.path(out, "lane_consistency.tsv"), sep = "\t"); print(lc)

# ---- (B) NT-vs-NT null (odd vs even retained NT guide numbers) ----
ntg <- sort(unique(cd$sgIndividual[cd$grp %in% "NT"]))
num <- as.integer(sub("sgsgNT-", "", ntg))
half <- ifelse(num %% 2 == 1, "NTodd", "NTeven")
lab_b <- ifelse(cd$grp %in% "NT", half[match(cd$sgIndividual, ntg)], NA)
Pb <- pb(lab_b, !is.na(lab_b))
nb <- de(Pb, uni, "NTodd", "NTeven")
db <- merge(nb$d, chip[, .(peak, gata1_n_exp)], by = "peak")[, bound := gata1_n_exp >= 2]
ntnull <- db[, .(n = .N, testable = sum(!is.na(padj)), apparent_loss = sum(!is.na(padj) & padj < 0.05 & log2FC < 0),
                 apparent_gain = sum(!is.na(padj) & padj < 0.05 & log2FC > 0), median_lfc = median(log2FC, na.rm = TRUE),
                 sd_lfc = sd(log2FC, na.rm = TRUE)), by = bound]
ntnull[, `:=`(odd_guides = paste(ntg[half == "NTodd"], collapse = ","), even_guides = paste(ntg[half == "NTeven"], collapse = ","),
              cells_odd = sum(lab_b == "NTodd", na.rm = TRUE), cells_even = sum(lab_b == "NTeven", na.rm = TRUE), rank_ok = nb$rank_ok)]
fwrite(ntnull, file.path(out, "NT_null_contrast.tsv"), sep = "\t"); print(ntnull)

# ---- (C) NT downsampled within lane to the GATA1 cell count ----
set.seed(20261031)
gl <- cd[grp %in% "GATA1", .N, by = Sample]
sub_nt <- cd[grp %in% "NT", .(cell = cell[sample.int(.N, min(.N, gl$N[gl$Sample == .BY$Sample]))]), by = Sample]$cell
lab_c <- ifelse(cd$grp %in% "GATA1" | cd$cell %in% sub_nt, cd$grp, NA)
Pc <- pb(lab_c, !is.na(lab_c))
dc <- de(Pc, uni, "GATA1", "NT")$d
x <- merge(d[bound == TRUE, .(peak, lfc = log2FC, padj, lost)], dc[, .(peak, lfc_c = log2FC, padj_c = padj)], by = "peak")
x[, lost_c := !is.na(padj_c) & padj_c < 0.05 & lfc_c < 0]
cds <- data.table(nt_cells_full = sum(cd$grp %in% "NT"), nt_cells_matched = length(sub_nt), gata1_cells = sum(cd$grp %in% "GATA1"),
                  bound_testable_full = sum(!is.na(x$padj)), bound_testable_matched = sum(!is.na(x$padj_c)),
                  lost_full = sum(x$lost), lost_matched = sum(x$lost_c), lost_full_also_matched = sum(x$lost & x$lost_c),
                  share_full_lost_negative_in_matched = mean(x$lfc_c[x$lost] < 0, na.rm = TRUE),
                  cor_lfc = cor(x$lfc, x$lfc_c, use = "complete.obs"))
fwrite(cds, file.path(out, "cell_depth_sensitivity.tsv"), sep = "\t"); print(cds)

# ---- P1 guide concordance on all bound testable regions ----
g3 <- sort(unique(cd$sgIndividual[cd$grp %in% "GATA1"]))
GL <- lapply(setNames(g3, g3), function(gi) {
  lab <- ifelse(cd$sgIndividual == gi & cd$grp %in% "GATA1", "G", ifelse(cd$grp %in% "NT", "NT", NA))
  de(pb(lab, !is.na(lab)), uni, "G", "NT")$d })
LOGO <- lapply(setNames(g3, g3), function(gi) {
  lab <- ifelse(cd$grp %in% "GATA1" & cd$sgIndividual != gi, "G", ifelse(cd$grp %in% "NT", "NT", NA))
  de(pb(lab, !is.na(lab)), uni, "G", "NT")$d })
bt <- d[bound == TRUE & !is.na(padj), peak]
gc <- rbindlist(lapply(g3, function(gi) { y <- GL[[gi]][peak %in% bt]; z <- d[match(y$peak, peak)]; lo <- LOGO[[gi]][match(y$peak, peak)]
  data.table(guide = gi, cells = sum(cd$sgIndividual == gi & cd$grp %in% "GATA1"), bound_testable_pooled = length(bt),
             testable_in_guide = sum(!is.na(y$padj)), share_negative_lfc = mean(y$log2FC < 0, na.rm = TRUE),
             median_lfc = median(y$log2FC, na.rm = TRUE), cor_with_pooled = cor(y$log2FC, z$log2FC, use = "complete.obs"),
             cor_with_leave_this_guide_out = cor(y$log2FC, lo$log2FC, use = "complete.obs"),
             lost_in_guide = sum(!is.na(y$padj) & y$padj < 0.05 & y$log2FC < 0)) }))
fwrite(gc, file.path(out, "guide_concordance.tsv"), sep = "\t"); print(gc)

# ---- peak table for the model (all peaks) ----
pt <- data.table(peak = seq_len(nrow(P)) - 1L, nt_log2cpm = log2(cpm + 0.5), universe = uni)
pt <- merge(pt, d[, .(peak, log2FC, padj)], by = "peak", all.x = TRUE)
for (gi in g3) pt <- merge(pt, setnames(copy(GL[[gi]]), c("log2FC", "padj"), paste0(c("lfc_", "padj_"), gi)), by = "peak", all.x = TRUE)
fwrite(pt, file.path(out, "peak_table.tsv.gz"), sep = "\t")
fwrite(s_main, file.path(out, "pooled_summary.tsv"), sep = "\t")
writeLines(capture.output(sessionInfo()), file.path(out, "sessionInfo.77.txt"))
