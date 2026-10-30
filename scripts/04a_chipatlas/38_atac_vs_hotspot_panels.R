# Panels for 37_atac_vs_hotspot.py (one sample's ATAC peaks vs protein hotspots). Light; runs locally.
# usage: Rscript 38_atac_vs_hotspot_panels.R <out_prefix of 37> <sample label> <out_dir>
# Writes ATACvsHotspot_panels.{pdf,png}, outside_vs_inside.tsv and panels_38.rds (ggplot objects for 42).
suppressPackageStartupMessages({library(data.table); library(ggplot2); library(patchwork); library(scales)})

args <- commandArgs(trailingOnly = TRUE)
pre <- args[1]; lab <- args[2]; out <- args[3]
dir.create(out, showWarnings = FALSE, recursive = TRUE)
theme_set(theme_classic(base_size = 8) + theme(legend.key.size = unit(3, "mm"), plot.tag = element_text(face = "bold")))
TIER <- c(high = "High\n(1-20k)", mid = "Mid\n(20-40k)", low = "Low\n(40-60k)", rest = "Rest")
HOT <- c("top1", "top5", "top10", "top20", "sub-hotspot", "none")
HOT_LAB <- c("top1 (>=244)", "top5 (70-243)", "top10 (36-69)", "top20 (17-35)", "below hotspot (1-16)", "no protein")
HOT_COL <- setNames(c("#08306b", "#2171b5", "#6baed6", "#c6dbef", "#fdae6b", "#d94801"), HOT)
CCRE <- c("PLS", "pELS", "dELS", "CA-H3K4me3", "CA-CTCF", "CA-TF", "TF", "CA", "none")
CCRE_COL <- setNames(c("#b2182b", "#ef8a62", "#fddbc7", "#7b3294", "#1b7837", "#a6dba0", "#2166ac", "#92c5de", "#e0e0e0"),
                     CCRE)

s <- fread(paste0(pre, ".tsv"))
d <- fread(paste0(pre, ".peaks.tsv.gz"))[blacklist == FALSE]
d[, tier := factor(atac_tier, names(TIER))]

# A: hotspot class composition by ATAC tier
sa <- melt(s[rank_by == "fe" & basis == "peak"], id.vars = "atac_tier", measure.vars = HOT, variable.name = "hot",
           value.name = "n")
sa[, share := n / sum(n), by = atac_tier][, tier := factor(TIER[atac_tier], TIER)][, hot := factor(hot, rev(HOT))]
lab_out <- s[rank_by == "fe" & basis == "peak", .(tier = factor(TIER[atac_tier], TIER),
                                                  txt = sprintf("%.1f%%\noutside", 100 * pct_not_in_top20))]
a <- ggplot(sa, aes(tier, share, fill = hot)) + geom_col(width = 0.75) +
  geom_text(data = lab_out, aes(tier, 1.02, label = txt), inherit.aes = FALSE, vjust = 0, size = 2, lineheight = 0.85) +
  scale_fill_manual(values = HOT_COL, breaks = HOT, labels = HOT_LAB, name = "Protein hotspot") +
  scale_y_continuous(labels = percent, breaks = seq(0, 1, 0.25), expand = expansion(c(0, 0.12))) +
  labs(x = sprintf("%s ATAC peak tier (fold enrichment)", lab), y = "Share of peaks")

# B: proteins per peak by ATAC tier
b <- ggplot(d, aes(tier, P_max + 1)) + geom_violin(fill = "#9ecae1", linewidth = 0.3, scale = "width") +
  geom_boxplot(width = 0.12, outlier.shape = NA, linewidth = 0.3) +
  geom_hline(yintercept = c(17, 244) + 1, linetype = "dashed", linewidth = 0.3, colour = c("grey50", "#08306b")) +
  annotate("text", x = 4.45, y = c(17, 244) + 1, label = c("top20", "top1"), vjust = -0.4, hjust = 1, size = 2) +
  scale_x_discrete(labels = TIER) + scale_y_log10() +
  labs(x = "ATAC peak tier", y = "Max ChIP-Atlas proteins over peak (+1)")

# C: robustness of the 'outside top20' share
sc <- s[, .(tier = factor(TIER[atac_tier], TIER), variant = paste(ifelse(rank_by == "fe", "fold enrichment", "-log10 q"),
                                                                  basis, sep = ", "), pct = pct_not_in_top20)]
c_ <- ggplot(sc, aes(tier, pct, colour = variant, group = variant)) + geom_line(linewidth = 0.4) +
  geom_point(size = 1) + scale_y_continuous(labels = percent) + scale_colour_brewer(palette = "Set2", name = NULL) +
  labs(x = "ATAC peak tier", y = "% peaks outside top20 hotspots") + theme(legend.position = c(0.35, 0.8))

# D-F: strong peaks (high + mid) outside vs inside top20 hotspots
st <- d[atac_tier %in% c("high", "mid")]
st[, set := factor(fifelse(hot %in% c("sub-hotspot", "none"), "outside", "inside"), c("inside", "outside"))]
ns <- st[, .N, by = set]
st[, set_lab := factor(sprintf("%s\n(n=%s)", set, comma(ns$N[match(set, ns$set)])))]
st[, set_lab := factor(set_lab, unique(set_lab[order(set)]))]
fwrite(st[, .(peaks = .N, pct_distal_5kb = mean(tss_dist > 5000), median_P = as.numeric(median(P_max)),
              median_chipatlas_atac_frac = median(chipatlas_atac_frac), pct_PLS = mean(ccre == "PLS"),
              pct_dELS = mean(ccre == "dELS"), pct_CA_CTCF = mean(ccre == "CA-CTCF")), by = set],
       file.path(out, "outside_vs_inside.tsv"), sep = "\t")
cd <- st[, .N, by = .(set_lab, ccre)][, share := N / sum(N), by = set_lab][, ccre := factor(ccre, CCRE)]
dd <- ggplot(cd, aes(set_lab, share, fill = ccre)) + geom_col(width = 0.65) +
  scale_fill_manual(values = CCRE_COL, name = "ENCODE cCRE") + scale_y_continuous(labels = percent) +
  labs(x = "Strong peaks (high + mid) vs top20 hotspots", y = "Share of peaks")
e <- ggplot(st, aes(tss_dist + 1, colour = set)) + stat_ecdf(linewidth = 0.5) +
  geom_vline(xintercept = c(1000, 5000), linetype = "dotted", linewidth = 0.3) +
  scale_x_log10(labels = label_number(scale_cut = cut_short_scale())) +
  scale_colour_manual(values = c(inside = "#2171b5", outside = "#d94801"), name = NULL) +
  scale_y_continuous(labels = percent) + labs(x = "Distance to nearest TSS (bp)", y = "Cumulative share") +
  theme(legend.position = c(0.25, 0.8))
f <- ggplot(st, aes(chipatlas_atac_frac + 1e-4, fill = set)) +
  geom_density(alpha = 0.5, linewidth = 0.3, adjust = 1.2) +
  scale_x_log10(labels = percent, breaks = c(1e-4, 1e-3, 1e-2, 1e-1, 1)) +
  scale_fill_manual(values = c(inside = "#2171b5", outside = "#d94801"), name = NULL) +
  labs(x = "Share of 18,651 ChIP-Atlas ATAC experiments open (+0.01%)", y = "Density") +
  theme(legend.position = c(0.2, 0.8))

p <- (a | b) / (c_ | dd) / (e | f) + plot_annotation(tag_levels = "A")
ggsave(file.path(out, "ATACvsHotspot_panels.pdf"), p, width = 180, height = 200, units = "mm")
ggsave(file.path(out, "ATACvsHotspot_panels.png"), p, width = 180, height = 200, units = "mm", dpi = 300)
saveRDS(list(a = a, b = b, c = c_, d = dd, e = e, f = f), file.path(out, "panels_38.rds"))
print(fread(file.path(out, "outside_vs_inside.tsv")))
