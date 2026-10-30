# Panels for 32_hotspot_context.py (cell-type context of hotspot bins). Light; runs locally.
# usage: Rscript 34_hotspot_context_panels.R <context_dir> <annotation_dir> <out_dir>
# Needs <out_dir>/bin_ccre.tsv (bin_id, ccre) for the context bins, written from bins_annotation.npz by
# 34_bin_ccre.py. Writes HotspotContext_panels.{pdf,png}, breadth_by_class.tsv.
suppressPackageStartupMessages({library(data.table); library(ggplot2); library(patchwork); library(scales)})

args <- commandArgs(trailingOnly = TRUE)
ctx <- args[1]; ann <- args[2]; out <- args[3]
dir.create(out, showWarnings = FALSE, recursive = TRUE)
theme_set(theme_classic(base_size = 8) + theme(legend.key.size = unit(3, "mm"), plot.tag = element_text(face = "bold")))
GRP <- c(low = "1-16", b20 = "17-35", b5 = "70-243", top1 = ">=244 (top1)")
GRP_COL <- setNames(c("#c6dbef", "#6baed6", "#2171b5", "#08306b"), GRP)
CCRE <- c("PLS", "pELS", "dELS", "CA-H3K4me3", "CA-CTCF", "CA-TF", "TF", "CA", "none")
SET_COL <- c(DBP = "#2166ac", cofactor = "#d6604d", other = "#969696", all = "#4d4d4d")

br <- fread(file.path(ctx, "breadth.tsv"))
br[, grp := factor(GRP[group], GRP)]
ct <- fread(file.path(ctx, "celltypes.tsv"))
nct <- nrow(ct)

# annotate bins with cCRE class and residual flag
bed <- fread(file.path(ann, "residual_top1.bed"), header = FALSE)
res_loci <- paste0(bed$V1, ":", bed$V2)
br[, residual := locus %in% res_loci]
cc <- fread(file.path(out, "bin_ccre.tsv"))
br <- merge(br, cc, by = "bin_id", all.x = TRUE)
br[, ccre3 := factor(fifelse(ccre %in% c("PLS", "pELS", "dELS"), ccre, "other"), c("PLS", "pELS", "dELS", "other"))]

# A: breadth by occupancy band
a <- ggplot(br, aes(n_active, after_stat(density), fill = grp)) +
  geom_histogram(binwidth = 1, boundary = -0.5, position = "identity", alpha = 0.55) +
  scale_fill_manual(values = GRP_COL, name = "Proteins in bin") +
  labs(x = sprintf("Active cell types (of %d)", nct), y = "Density") + theme(legend.position = c(0.75, 0.7))

# B: top1 breadth by cCRE class and residual status
t1 <- br[group == "top1"]
t1[, set := factor(fifelse(residual, "residual", "other top1"), c("other top1", "residual"))]
bt <- t1[, .(n = .N, median = as.numeric(median(n_active)), mean = mean(n_active), pct_ge10 = mean(n_active >= 10),
             pct_le2 = mean(n_active <= 2)), by = .(ccre3, set)][order(ccre3, set)]
fwrite(bt, file.path(out, "breadth_by_class.tsv"), sep = "\t")
b <- ggplot(t1, aes(ccre3, n_active, fill = set)) + geom_boxplot(outlier.size = 0.1, linewidth = 0.3, width = 0.7) +
  scale_fill_manual(values = c("other top1" = "#9ecae1", residual = "#cb181d"), name = NULL) +
  labs(x = "ENCODE cCRE (top1 bins)", y = "Active cell types") + theme(legend.position = "top")

# C: per cell type, share of top1 bins active
ct[, cell_type := factor(cell_type, cell_type[order(pct_top1_active)])]
c_ <- ggplot(ct, aes(pct_top1_active, cell_type)) + geom_col(fill = "#4393c3", width = 0.7) +
  geom_text(aes(label = tested_targets), hjust = -0.2, size = 1.9, colour = "grey30") +
  scale_x_continuous(labels = percent, expand = expansion(c(0, 0.15))) +
  labs(x = "% top1 bins active (label: targets tested)", y = NULL) + theme(axis.text.y = element_text(size = 5.5))

# D: per-target consistency by group
ctg <- fread(file.path(ctx, "consistency_target.tsv"))[n_bins >= 50]
ctg[, group := factor(group, c("DBP", "cofactor", "other"))]
d <- ggplot(ctg, aes(group, mean_consistency, fill = group)) +
  geom_violin(scale = "width", linewidth = 0.3, alpha = 0.6) + geom_boxplot(width = 0.15, outlier.shape = NA, linewidth = 0.3) +
  scale_fill_manual(values = SET_COL, guide = "none") + scale_y_continuous(labels = percent, limits = c(0, 1)) +
  labs(x = NULL, y = "Mean consistency across\nactive cell types (per protein)",
       subtitle = paste(ctg[, sprintf("%s n=%d", group, .N), by = group]$V1, collapse = ", ")) +
  theme(plot.subtitle = element_text(size = 6))

# E: noise ceiling, experiment-pair agreement within vs between cell types (unit weighting, matched cells)
ra <- fread(file.path(ctx, "replicate_agreement.tsv"))[weighting == "unit" & targets == "matched" & group != "other"]
rl <- melt(ra, id.vars = "group", measure.vars = c("within_agreement", "between_agreement"), variable.name = "kind",
           value.name = "agree")
rl[, kind := factor(kind, c("within_agreement", "between_agreement"), c("same cell type", "different cell types"))]
e <- ggplot(rl, aes(group, agree, fill = kind)) + geom_col(position = position_dodge(0.75), width = 0.7) +
  geom_text(data = ra, aes(group, between_agreement, label = sprintf("x%.2f", ratio_between_within)),
            inherit.aes = FALSE, vjust = -0.4, size = 2.2, nudge_x = 0.19) +
  scale_fill_manual(values = c("same cell type" = "#525252", "different cell types" = "#e08214"), name = NULL) +
  scale_y_continuous(limits = c(0, 0.5)) +
  labs(x = NULL, y = "Experiment-pair agreement
at the same top1 bin") + theme(legend.position = "top")

# F: composition similarity across cell types, observed vs shuffled
jg <- fread(file.path(ctx, "jaccard_group.tsv"))
jl <- melt(jg, id.vars = "group", measure.vars = c("observed_mean", "shuffled_mean"), variable.name = "kind",
           value.name = "jaccard")
jl[, kind := factor(kind, c("observed_mean", "shuffled_mean"), c("same bin", "shuffled bin"))]
jl[, group := factor(group, c("all", "DBP", "cofactor"))]
f <- ggplot(jl, aes(group, jaccard, fill = kind)) + geom_col(position = position_dodge(0.75), width = 0.7) +
  geom_text(data = jg[, .(group = factor(group, c("all", "DBP", "cofactor")), y = observed_mean,
                          lab = sprintf("x%.2f", ratio_mean))], aes(group, y, label = lab), inherit.aes = FALSE,
            vjust = -0.4, size = 2.2, nudge_x = -0.19) +
  scale_fill_manual(values = c("same bin" = "#08306b", "shuffled bin" = "#bdbdbd"), name = NULL) +
  scale_y_continuous(expand = expansion(c(0, 0.12))) +
  labs(x = NULL, y = "Mean Jaccard between two\nactive cell types (top1 bins)") + theme(legend.position = "top")

p <- (a | b) / (c_ | d) / (e | f) + plot_annotation(tag_levels = "A")
ggsave(file.path(out, "HotspotContext_panels.pdf"), p, width = 180, height = 210, units = "mm")
ggsave(file.path(out, "HotspotContext_panels.png"), p, width = 180, height = 210, units = "mm", dpi = 300)
print(bt)
