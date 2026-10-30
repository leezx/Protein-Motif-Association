# Panels for 39_hotspot_to_atac.py (hotspots -> sample ATAC) and 40_coverage_recall.py (coverage vs recall). Local.
# usage: Rscript 41_hotspot_atac_reverse_panels.R <prefix.rev of 39> <prefix.cov of 40> <sample label> <out_dir>
# Writes HotspotToATAC_panels.{pdf,png} and panels_41.rds (ggplot objects for 42).
suppressPackageStartupMessages({library(data.table); library(ggplot2); library(patchwork); library(scales)})

args <- commandArgs(trailingOnly = TRUE)
rev <- args[1]; cov <- args[2]; lab <- args[3]; out <- args[4]
dir.create(out, showWarnings = FALSE, recursive = TRUE)
theme_set(theme_classic(base_size = 8) + theme(legend.key.size = unit(3, "mm"), plot.tag = element_text(face = "bold")))
ACOL <- c(high = "#7f2704", mid = "#d94801", low = "#fd8d3c", rest = "#fdd0a2")
CCRE <- c("PLS", "pELS", "dELS", "CA-CTCF", "other")
CCRE_COL <- setNames(c("#b2182b", "#ef8a62", "#fddbc7", "#1b7837", "#e0e0e0"), CCRE)

# A: share of bins open in the sample, by hotspot band (exclusive) and nested tier
bt <- fread(paste0(rev, ".bins.tsv"))
bt <- bt[set != "all bins"]
ord <- c("none (0)", "sub (1-16)", "b20 (17-35)", "b10 (36-69)", "b5 (70-243)", "top20 (nested)", "top10 (nested)",
         "top5 (nested)", "top1 (nested)")
bl <- melt(bt, id.vars = "set", measure.vars = paste0("pct_", names(ACOL)), variable.name = "cls", value.name = "share")
bl[, cls := factor(sub("pct_", "", cls), rev(names(ACOL)))][, set := factor(set, ord)]
bl[, kind := fifelse(grepl("nested", set), "nested hotspot tier", "exclusive band")]
lab_a <- bt[, .(set = factor(set, ord), y = pct_open, txt = sprintf("%.1f%%", 100 * pct_open),
                kind = fifelse(grepl("nested", set), "nested hotspot tier", "exclusive band"))]
a <- ggplot(bl, aes(set, share, fill = cls)) + geom_col(width = 0.75) +
  geom_text(data = lab_a, aes(set, y, label = txt), inherit.aes = FALSE, vjust = -0.3, size = 2) +
  facet_grid(. ~ kind, scales = "free_x", space = "free_x") +
  scale_fill_manual(values = ACOL, breaks = names(ACOL), name = sprintf("Strongest %s\nATAC peak tier", lab)) +
  scale_y_continuous(labels = percent, limits = c(0, 0.88)) +
  labs(x = NULL, y = sprintf("500 bp bins with a %s ATAC peak", lab)) +
  theme(axis.text.x = element_text(angle = 35, hjust = 1), strip.background = element_blank())

# B: top1 bins closed in the sample are still open elsewhere
t1 <- fread(paste0(rev, ".top1_bins.tsv.gz"))
t1[, grp := factor(fifelse(open, "open in sample", "not open in sample"), c("open in sample", "not open in sample"))]
b <- ggplot(t1, aes(chipatlas_atac_frac, fill = grp)) + geom_density(alpha = 0.5, linewidth = 0.3) +
  scale_x_continuous(labels = percent) +
  scale_fill_manual(values = c("open in sample" = "#d94801", "not open in sample" = "#6baed6"), name = NULL) +
  labs(x = "Share of 18,651 ChIP-Atlas ATAC experiments open", y = "Density (top1 bins)") +
  theme(legend.position = c(0.7, 0.85))

# C: cCRE / TSS composition of open vs closed top1 bins
t1[, cc := factor(fifelse(ccre %in% CCRE[1:4], ccre, "other"), CCRE)]
cc <- t1[, .N, by = .(grp, cc)][, share := N / sum(N), by = grp]
ns <- t1[, .N, by = grp]
cc[, glab := factor(sprintf("%s\n(n=%s)", grp, comma(ns$N[match(grp, ns$grp)])))]
cc[, glab := factor(glab, unique(glab[order(grp)]))]
c_ <- ggplot(cc, aes(glab, share, fill = cc)) + geom_col(width = 0.6) +
  scale_fill_manual(values = CCRE_COL, name = "ENCODE cCRE") + scale_y_continuous(labels = percent) +
  labs(x = "top1 bins", y = "Share of bins")

# D: genome coverage vs ATAC peak recall
cu <- fread(paste0(cov, ".curve.tsv.gz"))
cl <- melt(cu, id.vars = c("score", "threshold", "coverage"), measure.vars = patterns("_overlap$"),
           variable.name = "tier", value.name = "recall")
cl[, tier := factor(sub("recall_(.*)_overlap", "\\1", tier), c("high", "mid", "low", "all"))]
cl[, score := factor(score, c("protein_hotspot", "chipatlas_atac"), c("protein hotspot (P)", "ChIP-Atlas ATAC openness"))]
at <- fread(paste0(cov, ".at_hotspot_thresholds.tsv"))[basis == "overlap"]
at[, tier := factor(atac_tier, c("high", "mid", "low", "all"))]
TCOL <- c(high = "#7f2704", mid = "#d94801", low = "#fd8d3c", all = "#636363")
d <- ggplot(cl, aes(coverage, recall, colour = tier, linetype = score)) +
  geom_abline(slope = 1, intercept = 0, linetype = "dotted", colour = "grey60", linewidth = 0.3) +
  geom_line(linewidth = 0.45) +
  geom_point(data = at, aes(genome_coverage, recall, colour = tier), inherit.aes = FALSE, size = 1.1) +
  geom_text(data = at[tier == "high"], aes(genome_coverage, recall, label = hotspot), inherit.aes = FALSE,
            size = 2, vjust = -0.8, hjust = -0.1) +
  scale_x_continuous(labels = percent, limits = c(0, 0.4)) + scale_y_continuous(labels = percent, limits = c(0, 1)) +
  scale_colour_manual(values = TCOL, name = sprintf("%s ATAC tier", lab)) +
  scale_linetype_manual(values = c("solid", "dashed"), name = "Genome ranked by") +
  labs(x = "Genome covered (kept 500 bp bins, 2.83 Gb)", y = "ATAC peaks recalled (overlap)")

# E: same, log x to show the top end
e <- d + scale_x_log10(labels = percent, limits = c(1e-3, 1)) + guides(colour = "none", linetype = "none") +
  labs(x = "Genome covered (log)")

p <- (a) / (b | c_) / (d | e) + plot_layout(heights = c(1, 0.9, 1.1)) + plot_annotation(tag_levels = "A")
ggsave(file.path(out, "HotspotToATAC_panels.pdf"), p, width = 180, height = 210, units = "mm")
ggsave(file.path(out, "HotspotToATAC_panels.png"), p, width = 180, height = 210, units = "mm", dpi = 300)
saveRDS(list(a = a, b = b, c = c_, d = d, e = e), file.path(out, "panels_41.rds"))
