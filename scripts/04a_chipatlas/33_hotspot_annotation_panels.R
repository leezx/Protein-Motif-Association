# Panels for 31_hotspot_annotation.py (genomic annotation of 500 bp bins by protein-occupancy band). Light; local.
# usage: Rscript 33_hotspot_annotation_panels.R <annotation_dir> <out_dir>
# Writes HotspotAnnotation_panels.{pdf,png}.
suppressPackageStartupMessages({library(data.table); library(ggplot2); library(patchwork); library(scales)})

args <- commandArgs(trailingOnly = TRUE)
inp <- args[1]; out <- args[2]
dir.create(out, showWarnings = FALSE, recursive = TRUE)
theme_set(theme_classic(base_size = 8) + theme(legend.key.size = unit(3, "mm"), plot.tag = element_text(face = "bold")))
BANDS <- c(none = "0", low = "1-16", b20 = "17-35", b10 = "36-69", b5 = "70-243", b1 = ">=244 (top1)")
CCRE <- c("PLS", "pELS", "dELS", "CA-H3K4me3", "CA-CTCF", "CA-TF", "TF", "CA", "none")
CCRE_COL <- setNames(c("#b2182b", "#ef8a62", "#fddbc7", "#7b3294", "#1b7837", "#a6dba0", "#2166ac", "#92c5de", "#e0e0e0"),
                     CCRE)
TSS_COL <- c(promoter = "#b2182b", proximal = "#f4a582", distal = "#d9d9d9")

cb <- fread(file.path(inp, "composition_band.tsv"))[group != "all"]
cb[, band := factor(BANDS[group], BANDS)]

tl <- melt(cb, id.vars = "band", measure.vars = patterns("^tss_"), variable.name = "cls", value.name = "share")
tl[, cls := factor(sub("tss_", "", cls), names(TSS_COL))]
a <- ggplot(tl, aes(band, share, fill = cls)) + geom_col(width = 0.75) +
  scale_fill_manual(values = TSS_COL, name = "TSS distance", labels = c("<=1 kb", "1-5 kb", ">5 kb")) +
  scale_y_continuous(labels = percent) + labs(x = "Proteins in 500 bp bin", y = "Share of bins") +
  theme(axis.text.x = element_text(angle = 30, hjust = 1))

cl <- melt(cb, id.vars = "band", measure.vars = patterns("^ccre_"), variable.name = "cls", value.name = "share")
cl[, cls := factor(sub("ccre_", "", cls), CCRE)]
b <- ggplot(cl, aes(band, share, fill = cls)) + geom_col(width = 0.75) +
  scale_fill_manual(values = CCRE_COL, name = "ENCODE cCRE") + scale_y_continuous(labels = percent) +
  labs(x = "Proteins in 500 bp bin", y = "Share of bins") + theme(axis.text.x = element_text(angle = 30, hjust = 1))

fl <- melt(cb, id.vars = "band", measure.vars = c("cpg", "atac_open", "gc_median", "atac_frac_median"),
           variable.name = "feat", value.name = "v")
fl[, feat := factor(feat, c("gc_median", "cpg", "atac_open", "atac_frac_median"),
                    c("median GC", "CpG island", "open in >=1 ATAC exp.", "median ATAC open fraction"))]
c_ <- ggplot(fl, aes(band, v, colour = feat, group = feat)) + geom_line(linewidth = 0.5) + geom_point(size = 0.8) +
  scale_y_continuous(labels = percent, limits = c(0, 1)) + scale_colour_brewer(palette = "Dark2", name = NULL) +
  labs(x = "Proteins in 500 bp bin", y = "Value") + theme(axis.text.x = element_text(angle = 30, hjust = 1),
  legend.position = "bottom") + guides(colour = guide_legend(ncol = 2))

oc <- fread(file.path(inp, "occupancy_by_class.tsv"))[variable == "ccre"]
oc[, cls := factor(cls, rev(CCRE))]
d <- ggplot(oc, aes(y = cls)) +
  geom_col(aes(x = pct_top1, fill = cls), width = 0.7, show.legend = FALSE) +
  geom_text(aes(x = pct_top1, label = sprintf("%.2f%%  (%s of top1)", 100 * pct_top1, percent(share_of_top1, 0.1))),
            hjust = -0.05, size = 2) +
  scale_fill_manual(values = CCRE_COL) + scale_x_continuous(labels = percent, expand = expansion(c(0, 1.1))) +
  labs(x = "% of bins in class that are top1", y = NULL)

s <- jsonlite::fromJSON(file.path(inp, "summary.json"))
r2 <- data.table(block = c("GC + CpG", "TSS + cCRE", "ATAC + DNase", "all (joint strata)"),
                 r2 = c(s$r2_single_blocks$gc_cpg, s$r2_single_blocks$promoter_ccre,
                        s$r2_single_blocks$accessibility, s$r2_all_covariates))
r2[, block := factor(block, block)]
e <- ggplot(r2, aes(r2, block)) + geom_col(fill = "#4393c3", width = 0.65) +
  geom_text(aes(label = sprintf("%.2f", r2)), hjust = -0.15, size = 2.3) +
  scale_x_continuous(limits = c(0, 1)) + labs(x = expression(R^2~"of log(1+proteins), occupied bins"), y = NULL)

res <- fread(file.path(inp, "residual.tsv"))
rc <- data.table(set = c("all top1 bins", "residual top1 (r >= 0.99)"),
                 PLS = c(cb[group == "b1", ccre_PLS], s$residual_top1_composition$PLS),
                 pELS = c(cb[group == "b1", ccre_pELS], s$residual_top1_composition$pELS),
                 dELS = c(cb[group == "b1", ccre_dELS], s$residual_top1_composition$dELS))
rc[, other := 1 - PLS - pELS - dELS]
rl <- melt(rc, id.vars = "set", variable.name = "cls", value.name = "share")
rl[, cls := factor(cls, c("PLS", "pELS", "dELS", "other"))]
rl[, set := factor(set, rev(rc$set))]
nres <- s$residual_top1_bins
f <- ggplot(rl, aes(share, set, fill = cls)) + geom_col(width = 0.6) +
  scale_fill_manual(values = c(CCRE_COL[c("PLS", "pELS", "dELS")], other = "#bdbdbd"), name = NULL) +
  scale_x_continuous(labels = percent) +
  labs(x = "Share of bins (ENCODE cCRE)", y = NULL,
       subtitle = sprintf("%s of %s top1 bins (%.1f%%) stay in the\ntop 1%% of their covariate stratum",
                          comma(nres), comma(res[group == "top1", bins]), 100 * res[group == "top1", pct_r_ge99])) +
  theme(legend.position = "bottom", plot.subtitle = element_text(size = 6.5))

p <- (a | b) / (c_ | d) / (e | f) + plot_annotation(tag_levels = "A")
ggsave(file.path(out, "HotspotAnnotation_panels.pdf"), p, width = 180, height = 200, units = "mm")
ggsave(file.path(out, "HotspotAnnotation_panels.png"), p, width = 180, height = 200, units = "mm", dpi = 300)
