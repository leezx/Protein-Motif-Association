# Gate V figure from the outputs of 79_gateV_model.R (and 77 outcome QA). Light; local.
# usage: Rscript 80_gateV_figure.R <79 model dir> <77 outcome_v2 dir> <figure out dir>
# A outcome reliability: lane-wise GATA1 effect at bound vs unbound peaks and the NT-vs-NT null; B OOF AP per arm with
# prevalence; C nested gains with chromosome-bootstrap CI and the 0.02 GO line; D B3 - B2 against NC2
# (chromosome-preserving occupancy-row permutation); E per-guide Delta AP (pooled OOF predictions, each guide's own
# testable peaks) and the K562-ATAC universe sensitivity; F leave-one-chromosome-out; G subgroups; H Y2 (held-out).
suppressPackageStartupMessages({library(data.table); library(ggplot2); library(patchwork); library(scales)})
a <- commandArgs(trailingOnly = TRUE); d <- a[1]; oc <- a[2]; out <- a[3]
dir.create(out, showWarnings = FALSE, recursive = TRUE)
theme_set(theme_classic(base_size = 7) + theme(legend.key.size = unit(2.6, "mm"), legend.text = element_text(size = 5.5),
                                               plot.tag = element_text(face = "bold"), strip.background = element_blank(),
                                               plot.title = element_text(size = 7)))
cmp <- fread(file.path(d, "baseline_comparison.tsv"))
oof <- fread(file.path(d, "oof_predictions.tsv.gz"))
ap <- function(s, y) { o <- order(-s); y <- y[o]; mean(cumsum(y)[y == 1] / which(y == 1)) }
obs <- cmp[comparison == "B3_B2", dAP]

lc <- melt(fread(file.path(oc, "lane_consistency.tsv"))[, .(lane, bound = median_diff_bound, unbound = median_diff_unbound)],
           id.vars = "lane", variable.name = "peaks")
nn <- fread(file.path(oc, "NT_null_contrast.tsv"))
A <- ggplot(lc, aes(lane, value, colour = peaks)) + geom_hline(yintercept = 0, linewidth = 0.3) + geom_point(size = 1.2) +
  scale_colour_manual(values = c(bound = "#b2182b", unbound = "grey50"), labels = c("GATA1-bound", "unbound"), name = NULL) +
  labs(x = "10x lane", y = "Median log2 CPM (GATA1 - NT)",
       title = sprintf("Per-lane effect; NT-vs-NT null: %d losses / %d gains", sum(nn$apparent_loss), sum(nn$apparent_gain))) +
  theme(legend.position = "top", axis.text.x = element_text(angle = 35, hjust = 1, size = 5))

arms <- c("B0", "B1", "B2", "B3")
al <- data.table(arm = factor(arms, arms), AP = sapply(arms, function(x) ap(oof[[x]], oof$y)))
lab <- c(B0 = "B0\nATAC/seq\nmotif", B1 = "B1\n+ GATA1\nChIP", B2 = "B2\n+ histone\n+ PMA degree", B3 = "B3\n+ PMA SVD")
B <- ggplot(al, aes(arm, AP)) + geom_col(fill = c("#d9d9d9", "#9ecae1", "#4292c6", "#08519c"), width = 0.65) +
  geom_hline(yintercept = mean(oof$y), linetype = "dashed", linewidth = 0.3) +
  geom_text(aes(label = sprintf("%.3f", AP)), vjust = -0.3, size = 2) + scale_x_discrete(labels = lab) +
  scale_y_continuous(expand = expansion(c(0, 0.12))) +
  labs(x = NULL, y = "Out-of-fold AP (GATA1 CRISPRi loss)",
       title = sprintf("n = %d GATA1-bound peaks, %d lost (dashed: prevalence)", nrow(oof), sum(oof$y))) +
  theme(axis.text.x = element_text(size = 5.5))
cl <- c(B1_B0 = "B1-B0\nGATA1 ChIP", B2_B1 = "B2-B1\nchromatin", B3_B2 = "B3-B2\nPMA\n(primary)", B3_B1 = "B3-B1")
cmp[, comp := factor(cl[comparison], cl)]
C <- ggplot(cmp, aes(comp, dAP, colour = comparison == "B3_B2")) + geom_hline(yintercept = 0, linewidth = 0.3) +
  geom_hline(yintercept = 0.02, linetype = "dashed", linewidth = 0.3, colour = "#b2182b") +
  geom_pointrange(aes(ymin = ci_lo, ymax = ci_hi), size = 0.25) +
  scale_colour_manual(values = c(`TRUE` = "#08519c", `FALSE` = "grey40"), guide = "none") +
  labs(x = NULL, y = "Delta AP (95% chromosome-bootstrap CI)", title = "Dashed red: GO minimum 0.02") +
  theme(axis.text.x = element_text(size = 5.5))
nc2 <- fread(file.path(d, "nc2_permutation.tsv"))
D <- ggplot(nc2, aes(dAP)) + geom_histogram(bins = 30, fill = "grey60") +
  geom_vline(xintercept = obs, colour = "#08519c", linewidth = 0.6) +
  geom_vline(xintercept = quantile(nc2$dAP, 0.95), linetype = "dashed", linewidth = 0.3) +
  labs(x = "AP(B3) - AP(B2)", y = "Count",
       title = sprintf("NC2 (n = %d, within chromosome): observed %.4f (blue), p95 dashed", nrow(nc2), obs))
gd <- fread(file.path(d, "guide_validation.tsv"))
us <- fread(file.path(d, "universe_sensitivity.tsv"))
ge <- rbind(gd[, .(lab = sprintf("%s\n(+%d / %d)", sub("^sg", "", guide), n_pos, n_testable), dAP, ci_lo, ci_hi, kind = "guide")],
            us[universe == "k562_atac_ref", .(lab = sprintf("K562-ATAC\nuniverse\n(+%d / %d)", n_pos, n), dAP, ci_lo = NA_real_,
                                              ci_hi = NA_real_, kind = "universe")])
ge[, lab := factor(lab, lab)]
E <- ggplot(ge, aes(lab, dAP, colour = kind)) + geom_hline(yintercept = c(0, obs), linetype = c("solid", "dashed"), linewidth = 0.3) +
  geom_pointrange(aes(ymin = fifelse(is.na(ci_lo), dAP, ci_lo), ymax = fifelse(is.na(ci_hi), dAP, ci_hi)), size = 0.25) +
  scale_colour_manual(values = c(guide = "#08519c", universe = "#e6550d"), guide = "none") +
  labs(x = NULL, y = "AP(B3) - AP(B2)", title = "Per guide (pooled model) and universe sensitivity") +
  theme(axis.text.x = element_text(size = 5))
loco <- fread(file.path(d, "chromosome_influence.tsv"))
loco[, dropped := factor(dropped, paste0("chr", c(1:22, "X")))]
F <- ggplot(loco, aes(dropped, dAP)) + geom_hline(yintercept = c(0, obs), linetype = c("solid", "dashed"), linewidth = 0.3) +
  geom_point(size = 0.9, colour = "grey30") + labs(x = "Chromosome dropped", y = "AP(B3) - AP(B2)", title = "Leave-one-chromosome-out") +
  theme(axis.text.x = element_text(angle = 90, vjust = 0.5, size = 4.5))
sub <- fread(file.path(d, "subgroups.tsv"))
sub[, lab := sprintf("%s: %s\n(n=%d, +%d)", ifelse(group == "tss", "TSS", "GATA motif"), level, n, pos)]
G <- ggplot(sub, aes(lab, dAP)) + geom_col(fill = "#08519c", width = 0.6) + geom_hline(yintercept = 0, linewidth = 0.3) +
  labs(x = NULL, y = "AP(B3) - AP(B2)", title = "Pre-specified subgroups (secondary)") +
  theme(axis.text.x = element_text(angle = 35, hjust = 1, size = 5))
y2 <- melt(fread(file.path(d, "y2_continuous.tsv")), id.vars = "arm", variable.name = "metric")
H <- ggplot(y2, aes(metric, value, fill = arm)) + geom_col(position = position_dodge(0.75), width = 0.7) +
  geom_text(aes(label = sprintf("%.2f", value)), position = position_dodge(0.75), vjust = -0.3, size = 2) +
  scale_fill_manual(values = c(B2 = "#4292c6", B3 = "#08519c"), name = NULL) + scale_y_continuous(expand = expansion(c(0, 0.15))) +
  labs(x = NULL, y = "Held-out value", title = "Y2: pooled log2FC (supportive)") + theme(legend.position = "top")
p <- (A | B) / (C | D) / (E | F) / (G | H) + plot_annotation(tag_levels = "A")
ggsave(file.path(out, "GateV_gata1_k562.pdf"), p, width = 180, height = 260, units = "mm")
ggsave(file.path(out, "GateV_gata1_k562.png"), p, width = 180, height = 260, units = "mm", dpi = 300)
