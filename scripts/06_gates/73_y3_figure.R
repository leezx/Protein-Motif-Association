# Y3 figure from the outputs of 71_y3_model.R. Light; local.
# usage: Rscript 73_y3_figure.R <71 model dir> <figure out dir>
# A held-out Spearman of GA / GB2 / GB3 with |D4 shrunken log2FC|; B Delta rho (GB3 - GB2) against NC1 (link
# specificity) and NC2 (occupancy identity) nulls; C observed response by decile of GB2 / GB3 prediction; D
# leave-one-chromosome-out and sensitivities; E responder AP (Y3a') and direction AUROC (Y3b).
suppressPackageStartupMessages({library(data.table); library(ggplot2); library(patchwork); library(jsonlite)})
a <- commandArgs(trailingOnly = TRUE); d <- a[1]; out <- a[2]
dir.create(out, showWarnings = FALSE, recursive = TRUE)
theme_set(theme_classic(base_size = 7) + theme(legend.key.size = unit(2.6, "mm"), legend.text = element_text(size = 5.5),
                                               plot.tag = element_text(face = "bold"), plot.title = element_text(size = 7)))
cm <- fread(file.path(d, "model_comparison.tsv")); O <- fread(file.path(d, "oof_gene_predictions.tsv.gz"))
dj <- fromJSON(file.path(d, "decision.json"))
A <- ggplot(data.table(arm = factor(c("GA", "GB2", "GB3")), rho = c(cm$rho_GA, cm$rho_GB2, cm$rho_GB3)), aes(arm, rho, fill = arm)) +
  geom_col(width = 0.6) + geom_text(aes(label = sprintf("%.3f", rho)), vjust = -0.3, size = 2) +
  scale_fill_manual(values = c(GA = "#d9d9d9", GB2 = "#4292c6", GB3 = "#08519c"), guide = "none") +
  scale_x_discrete(labels = c(GA = "GA\nbaseline gene", GB2 = "GB2\n+ B2 dependency", GB3 = "GB3\n+ B3 (PMA) dependency")) +
  scale_y_continuous(expand = expansion(c(0, 0.12))) +
  labs(x = NULL, y = "Held-out Spearman (|D4 log2FC|)", title = sprintf("%d SOX9-linked genes; %s", cm$n_genes, dj$decision))
neg <- fread(file.path(d, "negative_controls.tsv"))
B <- ggplot(neg, aes(d_rho, fill = control)) + geom_histogram(bins = 30, alpha = 0.75, position = "identity") +
  geom_vline(xintercept = cm$d_rho, colour = "#08519c", linewidth = 0.6) +
  annotate("rect", xmin = cm$ci_lo, xmax = cm$ci_hi, ymin = -Inf, ymax = Inf, fill = "#08519c", alpha = 0.12) +
  geom_vline(xintercept = 0.02, linetype = "dashed", colour = "#b2182b", linewidth = 0.3) +
  scale_fill_manual(values = c(NC1_link_specificity = "grey60", NC2_occupancy_identity = "#fdae6b"),
                    labels = c(NC1_link_specificity = "NC1 link specificity", NC2_occupancy_identity = "NC2 occupancy identity"), name = NULL) +
  labs(x = "rho(GB3) - rho(GB2)", y = "Count", title = sprintf("Observed %.4f (95%% CI %.4f to %.4f); red: GO minimum", cm$d_rho, cm$ci_lo, cm$ci_hi)) +
  theme(legend.position = "top")
dec <- rbind(O[, .(arm = "GB2", bin = cut(frank(GB2) / .N, 0:10 / 10, labels = FALSE), y3)], O[, .(arm = "GB3", bin = cut(frank(GB3) / .N, 0:10 / 10, labels = FALSE), y3)])
dec <- dec[, .(mean_y = mean(y3)), by = .(arm, bin)]
C <- ggplot(dec, aes(bin, mean_y, colour = arm)) + geom_line(linewidth = 0.5) + geom_point(size = 0.9) +
  scale_colour_manual(values = c(GB2 = "#4292c6", GB3 = "#08519c"), name = NULL) + scale_x_continuous(breaks = 1:10) +
  labs(x = "Decile of out-of-fold prediction", y = "Mean |D4 shrunken log2FC|", title = "Calibration by decile") + theme(legend.position = "top")
loco <- fread(file.path(d, "chromosome_influence.tsv")); sens <- fread(file.path(d, "sensitivity_results.tsv"))
sd_ <- rbind(loco[, .(label = paste0("-", dropped), d_rho, kind = "leave-one-chromosome-out")],
             data.table(label = c("nearest TSS", "promoter only", "distal only", "no top 1% genes", "all regions (secondary)"),
                        d_rho = c(sens[analysis == "nearest_TSS_d_rho", value], sens[analysis == "promoter_only_d_rho", value],
                                  sens[analysis == "distal_only_d_rho", value], cm$d_rho_no_top1pct, sens[analysis == "secondary_all_regions_d_rho", value]),
                        kind = "sensitivity"))
sd_[, label := factor(label, label)]
D <- ggplot(sd_, aes(label, d_rho, colour = kind)) + geom_hline(yintercept = c(0, cm$d_rho), linetype = c("solid", "dashed"), linewidth = 0.3) +
  geom_point(size = 0.9) + scale_colour_manual(values = c(sensitivity = "#e6550d", `leave-one-chromosome-out` = "grey40"), name = NULL) +
  labs(x = NULL, y = "rho(GB3) - rho(GB2)", title = "Stability and sensitivities (dashed: primary)") +
  theme(axis.text.x = element_text(angle = 90, vjust = 0.5, hjust = 1, size = 4.5), legend.position = "top")
e <- sens[analysis %like% "responder_AP|direction_AUROC|responder_AUROC"]
e[, `:=`(metric = sub("_G.*", "", analysis), arm = sub(".*_", "", analysis))]
E <- ggplot(e, aes(metric, value, fill = arm)) + geom_col(position = position_dodge(0.8), width = 0.75) +
  geom_text(aes(label = sprintf("%.3f", value)), position = position_dodge(0.8), vjust = -0.3, size = 1.8) +
  scale_fill_manual(values = c(GA = "#d9d9d9", GB2 = "#4292c6", GB3 = "#08519c"), name = NULL) + scale_y_continuous(expand = expansion(c(0, 0.12))) +
  scale_x_discrete(labels = c(responder_AP = "Responder AP\n(Y3a')", responder_AUROC = "Responder AUROC\n(Y3a')", direction_AUROC = "Direction AUROC\n(Y3b)")) +
  labs(x = NULL, y = "Held-out value", title = sprintf("Secondary outcomes (responder prevalence %.2f)", mean(O$resp))) + theme(legend.position = "top")
p <- (A | B) / (C | E) / D + plot_layout(heights = c(1, 1, 0.9)) + plot_annotation(tag_levels = "A")
ggsave(file.path(out, "Y3_sox9_rna_prediction.pdf"), p, width = 180, height = 200, units = "mm")
ggsave(file.path(out, "Y3_sox9_rna_prediction.png"), p, width = 180, height = 200, units = "mm", dpi = 300)
