# Gate A figure from the outputs of 61_gateA_benchmark.R. Light; local.
# usage: Rscript 67_gateA_figure.R <61 out dir> <figure out dir>
# A pooled OOF AP of M0/M1/M2 (matched primary, full candidates, bZIP excluded); B M2 - M1 with anchor-bootstrap CI
# against the MH-permutation null; C per-anchor AP M1 -> M2 (matched); D full-candidate top-k lift; E BioPlex
# enrichment (support only); F bZIP vs non-bZIP contribution. C shows all 23 evaluable anchors on the full candidate set.
suppressPackageStartupMessages({library(data.table); library(ggplot2); library(patchwork); library(scales)})
a <- commandArgs(trailingOnly = TRUE); d <- a[1]; out <- a[2]
dir.create(out, showWarnings = FALSE, recursive = TRUE)
theme_set(theme_classic(base_size = 7) + theme(legend.key.size = unit(2.6, "mm"), legend.text = element_text(size = 5.5),
                                               plot.tag = element_text(face = "bold"), strip.background = element_blank(),
                                               plot.title = element_text(size = 7)))
MC <- c(M0 = "#bdbdbd", M1 = "#6baed6", M2 = "#08519c")
res <- fread(file.path(d, "results_summary.tsv"))
lab <- c(matched_primary = "Matched (primary)", all_partners = "All candidates", matched_no_bZIP = "Matched, no bZIP",
         all_no_bZIP = "All, no bZIP")
res <- res[set %in% names(lab)]
res[, set_l := factor(lab[set], lab)]
apl <- melt(res, id.vars = c("set_l", "prevalence"), measure.vars = c("AP_M0", "AP_M1", "AP_M2"), variable.name = "model", value.name = "AP")
apl[, model := sub("AP_", "", model)]
A <- ggplot(apl, aes(set_l, AP, fill = model)) + geom_col(position = position_dodge(0.8), width = 0.75) +
  geom_errorbar(data = res, aes(x = set_l, ymin = prevalence, ymax = prevalence), inherit.aes = FALSE, linetype = "dashed",
                linewidth = 0.3, width = 0.9) +
  scale_fill_manual(values = MC, name = NULL) + labs(x = NULL, y = "Out-of-fold AP (Complex Portal)", title = "Dashed: prevalence") +
  theme(axis.text.x = element_text(angle = 25, hjust = 1), legend.position = "top")
null <- fread(file.path(d, "null_mh_permutation.tsv"))
r <- res[set == "matched_primary"]
B <- ggplot(null, aes(dAP_M2_M1)) + geom_histogram(bins = 30, fill = "grey75") +
  geom_vline(xintercept = r$dAP_M2_M1, colour = "#08519c", linewidth = 0.6) +
  annotate("rect", xmin = r$ci_lo_M2_M1, xmax = r$ci_hi_M2_M1, ymin = -Inf, ymax = Inf, fill = "#08519c", alpha = 0.12) +
  geom_vline(xintercept = quantile(null$dAP_M2_M1, 0.95), linetype = "dashed", linewidth = 0.3) +
  labs(x = "AP(M2) - AP(M1), matched primary", y = "Permutations",
       title = sprintf("Observed %.4f (95%% CI %.4f to %.4f); null p95 dashed", r$dAP_M2_M1, r$ci_lo_M2_M1, r$ci_hi_M2_M1))
pa <- fread(file.path(d, "per_anchor_all_partners.tsv"))
prim <- fread(file.path(d, "per_anchor.tsv"))$anchor
bz <- grepl("^(ATF|BATF|CEBP|CREB|DDIT3|FOS|JUN|MAF|NFE2|BACH)", pa$anchor)
pa[, `:=`(gain = AP_M2 > AP_M1, lab = sprintf("%s%s (%d)", anchor, ifelse(anchor %in% prim, "*", ""), n_pos),
          fam = ifelse(bz, "bZIP", "other"))]
pa[, lab := factor(lab, pa[order(AP_M2 - AP_M1), lab])]
C <- ggplot(pa) + geom_segment(aes(x = AP_M1, xend = AP_M2, y = lab, yend = lab, colour = gain),
                               arrow = arrow(length = unit(1, "mm")), linewidth = 0.4) +
  geom_point(aes(AP_M1, lab, shape = fam), size = 0.8, colour = "#6baed6") +
  scale_colour_manual(values = c(`TRUE` = "#08519c", `FALSE` = "#b2182b"), labels = c(`TRUE` = "M2 > M1", `FALSE` = "M2 <= M1"), name = NULL) +
  scale_shape_manual(values = c(bZIP = 17, other = 16), name = NULL) +
  labs(x = "AP per anchor (all candidates)", y = NULL, title = "M1 -> M2 per anchor; * = matched primary; (positives)") +
  theme(legend.position = "top", axis.text.y = element_text(size = 5))
lift <- fread(file.path(d, "full_candidate_topk.tsv"))
D <- ggplot(lift, aes(factor(top_k), lift, fill = model)) + geom_col(position = position_dodge(0.8), width = 0.75) +
  scale_fill_manual(values = MC, name = NULL) + labs(x = "Top-ranked pairs (all candidates)", y = "Lift over prevalence",
                                                     title = "Full-candidate ranking") + theme(legend.position = "top")
bp <- fread(file.path(d, "bioplex_validation.tsv"))
if ("AP_M2" %in% names(bp)) {
  bp <- bp[!is.na(AP_M2)]
  bpl <- melt(bp, id.vars = c("set", "prevalence", "n_pos"), measure.vars = c("AP_M0", "AP_M1", "AP_M2"), variable.name = "model", value.name = "AP")
  bpl[, `:=`(model = sub("AP_", "", model), set = sub("_Network.*", "", sub("BioPlex_", "", set)))]
  E <- ggplot(bpl, aes(sprintf("%s (n+=%d)", set, n_pos), AP / prevalence, fill = model)) +
    geom_col(position = position_dodge(0.8), width = 0.75) + geom_hline(yintercept = 1, linetype = "dashed", linewidth = 0.3) +
    scale_fill_manual(values = MC, name = NULL) + labs(x = NULL, y = "AP / prevalence",
         title = "BioPlex (not in Complex Portal): support only") + theme(legend.position = "top")
} else E <- ggplot() + annotate("text", 0, 0, label = "BioPlex not evaluable", size = 2.5) + theme_void()
fam <- fread(file.path(d, "family_contribution.tsv"))
F <- ggplot(fam, aes(family, mean_dAP)) + geom_col(fill = "#08519c", width = 0.6) +
  geom_text(aes(label = sprintf("%d anchors\n%d positives\n%d improved", anchors, positives, improved)),
            vjust = ifelse(fam$mean_dAP >= 0, -0.2, 1.2), size = 1.8, lineheight = 0.85) +
  geom_hline(yintercept = 0, linewidth = 0.3) + scale_y_continuous(expand = expansion(0.35)) +
  labs(x = NULL, y = "Mean per-anchor AP(M2) - AP(M1)", title = "Family contribution (matched)")
p <- (A | B) / (C | (D / E)) / F + plot_layout(heights = c(1, 1.6, 0.7)) + plot_annotation(tag_levels = "A")
ggsave(file.path(out, "GateA_cooccupancy_benchmark.pdf"), p, width = 180, height = 210, units = "mm")
ggsave(file.path(out, "GateA_cooccupancy_benchmark.png"), p, width = 180, height = 210, units = "mm", dpi = 300)
