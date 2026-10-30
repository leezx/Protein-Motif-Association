# Figure for Context Query v0.1 (HT29 SOX9-BAF x PMA), from the tables of 48_ht29_context_query.R. Light; local.
# usage: Rscript 49_ht29_context_query_figure.R <query dir of 48> <out_dir>
# A depletion / recovery (CUT&RUN library-size normalised, ATAC); B, C, D calibration of PMA evidence against HT29 observations;
# E, F SOX9-dependent loss vs BAF evidence; G recovery trajectories; H SMARCC1 vs ATAC change; I co-regulator ranking;
# J mechanism classes of SOX9-bound regions.
suppressPackageStartupMessages({library(data.table); library(ggplot2); library(patchwork); library(scales); library(ggrepel)})
args <- commandArgs(trailingOnly = TRUE)
q <- args[1]; out <- args[2]
dir.create(out, showWarnings = FALSE, recursive = TRUE)
theme_set(theme_classic(base_size = 7) + theme(legend.key.size = unit(2.6, "mm"), legend.text = element_text(size = 5.5),
                                               legend.title = element_text(size = 6), plot.tag = element_text(face = "bold"),
                                               plot.title = element_text(size = 7)))
DAYS <- c("DMSO", "D2", "D4", "D7", "D10", "D13")
EV <- c(Observed = "#b2182b", Supported = "#ef8a62", Inferred = "#92c5de", Unknown = "#bdbdbd")
rd <- function(f) fread(file.path(q, f))

# A: depletion and recovery
t0 <- rd("T0_depletion.tsv")
t0 <- t0[!(grepl("CUT&RUN", assay) & norm != "libsize")]
t0 <- rbind(t0, unique(t0[, .(norm, assay, contrast = "DMSO_vs_DMSO", median_log2FC = 0, share_down = 0, n)]))
t0[, day := factor(sub("_vs_DMSO", "", contrast), DAYS)]
A <- ggplot(t0, aes(day, median_log2FC, colour = assay, group = assay)) +
  geom_hline(yintercept = 0, linewidth = 0.3, colour = "grey60") + geom_line(linewidth = 0.5) + geom_point(size = 1) +
  scale_colour_manual(values = c("SOX9 CUT&RUN at SOX9 sites" = "#08519c", "SMARCC1 CUT&RUN at SOX9+SMARCC1 sites" = "#b2182b",
                                 "SMARCC1 CUT&RUN at SMARCC1-only sites" = "#fc9272", "ATAC at SOX9 sites" = "#238b45",
                                 "ATAC at non-SOX9 sites" = "#a1d99b"), name = NULL) +
  labs(x = "dTAG time course", y = "Median log2FC vs DMSO", title = "SOX9 depletion and recovery") +
  guides(colour = guide_legend(ncol = 2)) + theme(legend.position = "bottom", legend.margin = margin(0, 0, 0, 0))

# B: AUROC of cross-context scores for HT29 observations
t1a <- rd("T1_auroc.tsv")
t1a[, outcome := fifelse(outcome == "smarcc1_ht29", "HT29 SMARCC1", "HT29 SOX9")]
t1a[, score := factor(score, rev(unique(score)))]
B <- ggplot(t1a, aes(auc, score, fill = grepl("PMA", score))) + geom_col(width = 0.7) +
  geom_vline(xintercept = 0.5, linetype = "dashed", linewidth = 0.3) +
  geom_text(aes(label = sprintf("%.2f", auc)), hjust = -0.15, size = 1.9) +
  facet_grid(outcome ~ ., scales = "free_y", space = "free_y") +
  scale_fill_manual(values = c(`TRUE` = "#b2182b", `FALSE` = "#969696"), guide = "none") +
  scale_x_continuous(limits = c(0, 1.05), breaks = c(0, 0.5, 1)) + labs(x = "AUROC", y = NULL) +
  theme(strip.background = element_blank(), strip.text = element_text(size = 5.5))

# C: observed SMARCC1 rate by PMA BAF experiments within HT29 ATAC quintiles
t1c <- rd("T1_rate_by_atac_baf.tsv")
t1c[, baf_bin := factor(baf_bin, c("0", "1", "2-3", "4-10", ">10"))]
C <- ggplot(t1c[n >= 30], aes(baf_bin, smarcc1_rate, colour = atac_q, group = atac_q)) + geom_line(linewidth = 0.45) +
  geom_point(size = 0.9) + scale_colour_brewer(palette = "Greens", name = "HT29 ATAC\nquintile") +
  scale_y_continuous(labels = percent) + labs(x = "PMA BAF experiments at region", y = "HT29 SMARCC1-bound")

# forest helper
forest <- function(x, title) {
  x <- copy(x)[, predictor := factor(predictor, rev(unique(predictor)))]
  ggplot(x, aes(OR, predictor, colour = adjusted)) + geom_vline(xintercept = 1, linetype = "dashed", linewidth = 0.3) +
    geom_errorbar(aes(xmin = lo, xmax = hi), width = 0.25, linewidth = 0.35, orientation = "y") + geom_point(size = 1) +
    scale_x_log10() + scale_colour_manual(values = c(`TRUE` = "#000000", `FALSE` = "#969696"),
                                          labels = c(`TRUE` = "adjusted", `FALSE` = "unadjusted"), name = NULL) +
    labs(x = "Odds ratio (95% CI)", y = NULL, title = title)
}
t1b <- rd("T1_or.tsv")
t1b[, predictor := paste0(sub("_ht29", "", outcome), " ~ ", predictor)]
D <- forest(t1b, "PMA evidence -> HT29 occupancy")

# E: SOX9-dependent loss vs BAF evidence
t2 <- rd("T2_or.tsv")
E <- forest(t2, "ATAC loss at D4 (SOX9-bound unless noted)")

# F: loss rate by BAF evidence level
t2r <- rd("T2_rate_by_baf_evidence.tsv")
t2r[, baf_evidence := factor(baf_evidence, names(EV))]
F <- ggplot(t2r, aes(baf_evidence, lost_D4, fill = baf_evidence)) + geom_col(width = 0.7) +
  geom_text(aes(label = sprintf("%.0f%%\nn=%s", 100 * lost_D4, comma(n))), vjust = -0.15, size = 1.8, lineheight = 0.85) +
  scale_fill_manual(values = EV, guide = "none") + scale_y_continuous(labels = percent, expand = expansion(c(0, 0.25))) +
  labs(x = "BAF evidence (SOX9-bound regions)", y = "ATAC lost at D4")

# G: trajectories
t3s <- rd("T3_trajectory.tsv")
t3s <- rbind(t3s, unique(t3s[, .(lost_D4, baf_evidence, day = "DMSO", n, median = 0, q25 = 0, q75 = 0)]))
t3s[, `:=`(day = factor(day, DAYS), baf_evidence = factor(baf_evidence, names(EV)),
           grp = fifelse(lost_D4, "lost at D4", "not lost"))]
G <- ggplot(t3s, aes(day, median, colour = baf_evidence, group = interaction(baf_evidence, grp))) +
  geom_hline(yintercept = 0, linewidth = 0.3, colour = "grey60") +
  geom_line(aes(linetype = grp), linewidth = 0.45) + geom_point(size = 0.8) +
  scale_colour_manual(values = EV, name = "BAF evidence") + scale_linetype_manual(values = c("solid", "dotted"), name = NULL) +
  labs(x = "dTAG time course", y = "Median ATAC log2FC (SOX9-bound)")

# H: SMARCC1 change vs ATAC change at SOX9 + SMARCC1 sites
re <- fread(file.path(q, "region_evidence.tsv.gz"))
h <- re[sox9_ht29 == TRUE & smarcc1_ht29 == TRUE & !is.na(smarcc1cnr_log2FC_D4)]
t4 <- rd("T4_smarcc1_vs_atac.tsv")
H <- ggplot(h, aes(atac_log2FC_D4, smarcc1cnr_log2FC_D4)) + geom_bin2d(bins = 60) +
  scale_fill_viridis_c(trans = "log10", name = "regions") +
  geom_hline(yintercept = 0, linewidth = 0.3, colour = "grey60") + geom_vline(xintercept = 0, linewidth = 0.3, colour = "grey60") +
  annotate("text", x = -Inf, y = Inf, hjust = -0.05, vjust = 1.2, size = 1.9, lineheight = 0.9,
           label = sprintf("rho = %.2f, n = %s\nSMARCC1 median: ATAC-lost %.2f\nvs not lost %.2f, P = %.0e",
                           t4$spearman_smarcc1_vs_atac_D4, comma(t4$n), t4$smarcc1_lfc_lost, t4$smarcc1_lfc_notlost,
                           t4$wilcox_p)) +
  labs(x = "ATAC log2FC D4", y = "SMARCC1 CUT&RUN log2FC D4 (library size)")

# I: co-regulator ranking
t5 <- rd("T5_coregulator_rank.tsv")
t5[, cls := fifelse(is_baf, "BAF subunit", fifelse(grepl("^SOX", predictor), "SOX family", "other"))]
lab <- unique(rbind(t5[order(p)][1:10], t5[is_baf == TRUE & padj < 0.05], t5[cls == "SOX family"]))
I <- ggplot(t5, aes(log2(OR), -log10(padj), colour = cls)) + geom_point(size = 0.6, alpha = 0.7) +
  geom_text_repel(data = lab, aes(label = predictor), size = 1.7, max.overlaps = 40, segment.size = 0.2,
                  min.segment.length = 0, show.legend = FALSE) +
  scale_colour_manual(values = c("BAF subunit" = "#b2182b", "SOX family" = "#08519c", other = "#bdbdbd"), name = NULL) +
  geom_hline(yintercept = -log10(0.05), linetype = "dashed", linewidth = 0.3) +
  labs(x = "log2 adjusted OR for ATAC loss at D4", y = "-log10 FDR", title = sprintf("%d PMA targets ranked", nrow(t5)))

# J: mechanism classes
t2m <- rd("T2_mechanism_counts.tsv")
t2m[, motif := fifelse(sox9_motif, "SOX9 motif", "no motif")]
J <- ggplot(t2m, aes(N, mechanism, fill = motif)) + geom_col(width = 0.7) +
  scale_fill_manual(values = c("SOX9 motif" = "#08519c", "no motif" = "#9ecae1"), name = NULL) +
  scale_x_continuous(labels = comma) + labs(x = "SOX9-bound regions", y = NULL)

p <- (A | B) / (C | D) / (E | F) / (G | H) / (I | J) + plot_layout(heights = c(1.1, 1, 1.15, 1, 1.15)) + plot_annotation(tag_levels = "A")
ggsave(file.path(out, "ContextQuery_SOX9BAF.pdf"), p, width = 210, height = 297, units = "mm")
ggsave(file.path(out, "ContextQuery_SOX9BAF.png"), p, width = 210, height = 297, units = "mm", dpi = 300)
