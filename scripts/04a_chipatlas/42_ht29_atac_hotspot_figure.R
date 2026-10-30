# Combined figure: one sample's ATAC peaks vs protein hotspots, both directions plus genome compression.
# usage: Rscript 42_ht29_atac_hotspot_figure.R <panel_dir with panels_38.rds and panels_41.rds> <out_name> [label]
# Panel order: A forward composition; B reverse (hotspot bins open); C, D genome coverage vs recall (linear, log);
# E outside share robustness; F proteins per peak by ATAC tier; G-I strong peaks outside top20 (cCRE, TSS,
# ChIP-Atlas openness); J, K top1 bins closed in the sample (ChIP-Atlas openness, cCRE).
suppressPackageStartupMessages({library(ggplot2); library(patchwork)})

args <- commandArgs(trailingOnly = TRUE)
dir <- args[1]; name <- args[2]; lab <- if (length(args) > 2) args[3] else "Sample"
theme_set(theme_classic(base_size = 7) + theme(legend.key.size = unit(2.6, "mm"), legend.text = element_text(size = 5.5),
                                               legend.title = element_text(size = 6), plot.tag = element_text(face = "bold")))
p38 <- readRDS(file.path(dir, "panels_38.rds"))
p41 <- readRDS(file.path(dir, "panels_41.rds"))
short <- function(x) sub("\n.*", "", x)

A <- p38$a + scale_x_discrete(labels = short) + labs(x = sprintf("%s ATAC peak tier", lab))
B <- p41$a + labs(y = sprintf("Hotspot bins with %s ATAC peak", lab)) +
  theme(axis.text.x = element_text(angle = 40, hjust = 1, size = 5.5), strip.background = element_blank())
C <- p41$d + labs(x = "Genome covered (2.83 Gb universe)", y = "ATAC peaks recalled")
D <- p41$e + labs(x = "Genome covered (log)", y = "ATAC peaks recalled")
E <- p38$c + scale_x_discrete(labels = short) + labs(y = "% peaks outside top20") +
  theme(legend.position = c(0.38, 0.6))
F <- p38$b + scale_x_discrete(labels = c(high = "High", mid = "Mid", low = "Low", rest = "Rest")) +
  labs(y = "Max proteins over peak (+1)")
G <- p38$d + labs(x = "Strong peaks (high + mid)")
H <- p38$e + labs(x = "Distance to TSS (bp)")
I <- p38$f + labs(x = "ChIP-Atlas ATAC open share (+0.01%)") + theme(legend.position = c(0.25, 0.85))
J <- p41$b + labs(x = "ChIP-Atlas ATAC open share", y = "Density (top1 bins)") + theme(legend.position = c(0.62, 0.85))
K <- p41$c + labs(x = "top1 bins") + theme(axis.text.x = element_text(size = 5.5))

row1 <- (A | B) + plot_layout(widths = c(1, 1.7))
row2 <- (C | D | E) + plot_layout(widths = c(1.45, 0.9, 0.9))
row3 <- (F | G | H) + plot_layout(widths = c(0.9, 1.2, 0.9))
row4 <- (I | J | K) + plot_layout(widths = c(1, 1, 1.1))
p <- (row1 / row2 / row3 / row4) + plot_annotation(tag_levels = "A")
ggsave(file.path(dir, paste0(name, ".pdf")), p, width = 210, height = 290, units = "mm")
ggsave(file.path(dir, paste0(name, ".png")), p, width = 210, height = 290, units = "mm", dpi = 300)
