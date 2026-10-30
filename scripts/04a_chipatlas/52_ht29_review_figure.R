# Supplementary figure for the review checks of 51_ht29_review_checks.R. Light; local.
# usage: Rscript 52_ht29_review_figure.R <query/review1 dir> <out_dir>
# A normalisation-free composition change per replicate pairing (SMARCC1 vs IgG background vs SOX9), two contrasts;
# B D4 loss rate by SOX motif tertile x PMA SOX-family ChIP; C cross-validated AUROC of nested models;
# D SOX-family ChIP OR alone vs given motif, with and without baseline SOX9 occupancy.
suppressPackageStartupMessages({library(data.table); library(ggplot2); library(patchwork); library(scales)})
args <- commandArgs(trailingOnly = TRUE)
q <- args[1]; out <- args[2]
dir.create(out, showWarnings = FALSE, recursive = TRUE)
theme_set(theme_classic(base_size = 7) + theme(legend.key.size = unit(2.6, "mm"), legend.text = element_text(size = 5.5),
                                               plot.tag = element_text(face = "bold"), strip.background = element_blank()))
DAYS <- c("D2", "D4", "D7", "D10", "D13")

r1 <- fread(file.path(q, "R1_delta_by_pairing.tsv"))
r1[, `:=`(day = factor(day, DAYS), assay = factor(assay, c("SMARCC1", "IgG", "SOX9")))]
A <- ggplot(r1, aes(day, delta_log2, colour = assay, shape = pairing)) +
  geom_hline(yintercept = 0, linewidth = 0.3, colour = "grey60") +
  geom_point(position = position_dodge(width = 0.5), size = 1.1) +
  facet_wrap(~contrast, scales = "free_y") +
  scale_colour_manual(values = c(SMARCC1 = "#b2182b", IgG = "#969696", SOX9 = "#08519c"), name = NULL) +
  scale_shape_manual(values = c(matched = 16, crossed = 1), name = "replicate pairing") +
  labs(x = NULL, y = "Change in log2 fragment ratio vs DMSO")

r2s <- fread(file.path(q, "R2_rate_by_motif_tertile.tsv"))
r2s[, `:=`(motif_tertile = factor(motif_tertile, c("low", "mid", "high")),
           sox_fam = factor(fifelse(sox_fam, "SOX-family ChIP (PMA)", "none"), c("none", "SOX-family ChIP (PMA)")))]
B <- ggplot(r2s, aes(motif_tertile, lost_D4, fill = sox_fam)) + geom_col(position = position_dodge(0.75), width = 0.7) +
  geom_text(aes(label = sprintf("%.0f%%\nn=%s", 100 * lost_D4, comma(n))), position = position_dodge(0.75),
            vjust = -0.15, size = 1.8, lineheight = 0.85) +
  scale_fill_manual(values = c(none = "#bdbdbd", "SOX-family ChIP (PMA)" = "#08519c"), name = NULL) +
  scale_y_continuous(labels = percent, expand = expansion(c(0, 0.3))) +
  labs(x = "SOX motif score tertile (6 PWMs)", y = "SOX9-bound regions lost at D4") + theme(legend.position = "top")

r2 <- fread(file.path(q, "R2_sox_chip_vs_motif.tsv"))
cv <- melt(r2, id.vars = c("base", "chip_term"), measure.vars = patterns("^cvAUC_"), variable.name = "model", value.name = "auc")
cv[, model := factor(sub("cvAUC_", "", model), c("base", "motif", "chip", "both"),
                     c("covariates", "+ motif", "+ ChIP", "+ motif + ChIP"))]
cv[, base := fifelse(base == "B0", "without baseline SOX9", "with baseline SOX9")]
C <- ggplot(cv, aes(model, auc, colour = chip_term, group = chip_term)) + geom_line(linewidth = 0.4) + geom_point(size = 1) +
  facet_wrap(~base) + scale_colour_manual(values = c("sox_fam" = "#6baed6", "log1p(sox_fam_exp)" = "#08306b"),
                                           labels = c("sox_fam" = "binary", "log1p(sox_fam_exp)" = "log experiments"), name = "ChIP term") +
  labs(x = NULL, y = "10 x 5-fold CV AUROC (D4 loss)") + theme(axis.text.x = element_text(angle = 30, hjust = 1))

fo <- rbind(r2[, .(base, chip_term, model = "ChIP alone", OR = OR_chip_only, lo = lo_chip_only, hi = hi_chip_only)],
            r2[, .(base, chip_term, model = "ChIP | motif", OR = OR_chip_given_motif, lo = lo_given_motif, hi = hi_given_motif)])
fo[, lab := sprintf("%s, %s, %s", chip_term, fifelse(base == "B0", "no SOX9 base", "+ SOX9 base"), model)]
D <- ggplot(fo, aes(OR, lab, colour = model)) + geom_vline(xintercept = 1, linetype = "dashed", linewidth = 0.3) +
  geom_errorbar(aes(xmin = lo, xmax = hi), width = 0.25, linewidth = 0.35, orientation = "y") + geom_point(size = 1) +
  scale_x_log10() + scale_colour_manual(values = c("ChIP alone" = "#969696", "ChIP | motif" = "#08519c"), name = NULL) +
  labs(x = "Adjusted OR for D4 loss (95% CI)", y = NULL)

p <- A / (B | C) / D + plot_layout(heights = c(1, 1, 0.8)) + plot_annotation(tag_levels = "A")
ggsave(file.path(out, "ContextQuery_SOX9BAF_review1.pdf"), p, width = 180, height = 200, units = "mm")
ggsave(file.path(out, "ContextQuery_SOX9BAF_review1.png"), p, width = 180, height = 200, units = "mm", dpi = 300)
