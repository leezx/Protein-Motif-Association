# Gate B figure from the outputs of 64_gateB_model.R. Light; local.
# usage: Rscript 68_gateB_figure.R <64 model dir> <figure out dir>
# A OOF AP per arm (B0-B3, GUT) with prevalence; B nested gains with chromosome-bootstrap CI and the 0.02 GO line;
# C B3 - B2 against NC2 (occupancy-row permutation) and NC3 (coverage-preserving shuffled references); D NC4 and
# leave-one-chromosome-out; E subgroups; F exploratory per-protein coefficients (on top of B2).
suppressPackageStartupMessages({library(data.table); library(ggplot2); library(patchwork); library(scales)})
a <- commandArgs(trailingOnly = TRUE); d <- a[1]; out <- a[2]
dir.create(out, showWarnings = FALSE, recursive = TRUE)
theme_set(theme_classic(base_size = 7) + theme(legend.key.size = unit(2.6, "mm"), legend.text = element_text(size = 5.5),
                                               plot.tag = element_text(face = "bold"), strip.background = element_blank(),
                                               plot.title = element_text(size = 7)))
cmp <- fread(file.path(d, "baseline_comparison.tsv"))
oof <- fread(file.path(d, "oof_predictions.tsv.gz"))
ap <- function(s, y) { o <- order(-s); y <- y[o]; mean(cumsum(y)[y == 1] / which(y == 1)) }
arms <- c("B0", "B1", "B2", "B3", "GUT")
al <- data.table(arm = factor(arms, arms), AP = sapply(arms, function(x) ap(oof[[x]], oof$y)))
lab <- c(B0 = "B0 RNA/ATAC/motif", B1 = "B1 + SOX9", B2 = "B2 + chromatin\n+ PMA degree", B3 = "B3 + PMA SVD", GUT = "GUT + gut PMA SVD")
A <- ggplot(al, aes(arm, AP)) + geom_col(fill = c("#d9d9d9", "#9ecae1", "#4292c6", "#08519c", "#41ab5d"), width = 0.65) +
  geom_hline(yintercept = mean(oof$y), linetype = "dashed", linewidth = 0.3) +
  geom_text(aes(label = sprintf("%.3f", AP)), vjust = -0.3, size = 2) + scale_x_discrete(labels = lab) +
  scale_y_continuous(expand = expansion(c(0, 0.12))) +
  labs(x = NULL, y = "Out-of-fold AP (D4 ATAC loss)", title = sprintf("n = %d SOX9-bound regions, %d lost (dashed: prevalence)",
                                                                     nrow(oof), sum(oof$y))) +
  theme(axis.text.x = element_text(size = 5.5))
cl <- c(B1_B0 = "B1 - B0\n(SOX9 CUT&RUN)", B2_B1 = "B2 - B1\n(chromatin, degree)", B3_B2 = "B3 - B2\n(PMA identity; primary)",
        B3_B1 = "B3 - B1", GUT_B2 = "GUT - B2\n(gut PMA)")
cmp[, comp := factor(cl[comparison], cl)]
B <- ggplot(cmp, aes(comp, dAP, colour = comparison == "B3_B2")) + geom_hline(yintercept = 0, linewidth = 0.3) +
  geom_hline(yintercept = 0.02, linetype = "dashed", linewidth = 0.3, colour = "#b2182b") +
  geom_pointrange(aes(ymin = ci_lo, ymax = ci_hi), size = 0.25) +
  scale_colour_manual(values = c(`TRUE` = "#08519c", `FALSE` = "grey40"), guide = "none") +
  labs(x = NULL, y = "Delta AP (95% chromosome-bootstrap CI)", title = "Dashed red: GO minimum 0.02") +
  theme(axis.text.x = element_text(size = 5.2))
neg <- fread(file.path(d, "negative_controls.tsv"))
obs <- cmp[comparison == "B3_B2", dAP]
neg[, control := factor(control, c("NC2_identity_permutation", "NC3_coverage_shuffled_reference"),
                        c("NC2 occupancy-row permutation", "NC3 coverage-preserving reference"))]
C <- ggplot(neg, aes(dAP, fill = control)) + geom_histogram(bins = 30, position = "identity", alpha = 0.7) +
  geom_vline(xintercept = obs, colour = "#08519c", linewidth = 0.6) +
  geom_vline(xintercept = quantile(neg[control == levels(control)[1], dAP], 0.95), linetype = "dashed", linewidth = 0.3) +
  scale_fill_manual(values = c("grey60", "#fdae6b"), name = NULL) +
  labs(x = "AP(B3) - AP(B2)", y = "Count", title = sprintf("Observed %.4f (blue); NC2 p95 dashed", obs)) +
  theme(legend.position = "top")
nc4 <- fread(file.path(d, "nc4_sensitivity.tsv"))
loco <- fread(file.path(d, "chromosome_influence.tsv"))
dd <- rbind(nc4[, .(label = test, dAP, kind = "NC4")], loco[, .(label = paste0("-", dropped), dAP, kind = "leave-one-chromosome-out")])
dd[, label := factor(label, dd$label)]
D <- ggplot(dd, aes(label, dAP, colour = kind)) + geom_hline(yintercept = c(0, obs), linetype = c("solid", "dashed"), linewidth = 0.3) +
  geom_point(size = 0.9) + scale_colour_manual(values = c(NC4 = "#e6550d", `leave-one-chromosome-out` = "grey40"), name = NULL) +
  labs(x = NULL, y = "AP(B3) - AP(B2)", title = "Stability (dashed: primary estimate)") +
  theme(axis.text.x = element_text(angle = 90, vjust = 0.5, size = 4.5), legend.position = "top")
sub <- fread(file.path(d, "subgroups.tsv"))
sub[, lab := sprintf("%s: %s\n(n=%d, +%d)", group, level, n, pos)]
E <- ggplot(sub, aes(lab, dAP)) + geom_col(fill = "#08519c", width = 0.6) + geom_hline(yintercept = 0, linewidth = 0.3) +
  labs(x = NULL, y = "AP(B3) - AP(B2)", title = "Pre-specified subgroups (secondary)") +
  theme(axis.text.x = element_text(angle = 35, hjust = 1, size = 5))
pp <- fread(file.path(d, "exploratory_per_protein.tsv"))[coef != 0]
pp <- head(pp[order(-abs(coef))], 25)
F <- if (nrow(pp)) ggplot(pp, aes(coef, reorder(protein, coef), fill = coef > 0)) + geom_col(width = 0.7) +
  scale_fill_manual(values = c(`TRUE` = "#b2182b", `FALSE` = "#2166ac"), labels = c(`TRUE` = "more loss", `FALSE` = "less loss"), name = NULL) +
  labs(x = "Elastic-net coefficient (on top of B2; exploratory)", y = NULL, title = "Proteins selected (lambda.1se)") +
  theme(axis.text.y = element_text(size = 4.8), legend.position = "top") else
  ggplot() + annotate("text", 0, 0, label = "No protein selected at lambda.1se (exploratory)", size = 2.4) + theme_void()
p <- (A | B) / (C | D) / (E | F) + plot_layout(heights = c(1, 1, 1.1)) + plot_annotation(tag_levels = "A")
ggsave(file.path(out, "GateB_sox9_dependency.pdf"), p, width = 180, height = 210, units = "mm")
ggsave(file.path(out, "GateB_sox9_dependency.png"), p, width = 180, height = 210, units = "mm", dpi = 300)
