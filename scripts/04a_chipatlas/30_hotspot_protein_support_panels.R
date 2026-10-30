# Panels and tables for hotspot protein support (29_hotspot_protein_support.py output). Light; runs locally.
# usage: Rscript 30_hotspot_protein_support_panels.R <support_dir> <out_dir>
# Writes HotspotSupport_panels.{pdf,png}, counts_by_tier.tsv, top1_target_frequency.tsv.
suppressPackageStartupMessages({library(data.table); library(ggplot2); library(patchwork); library(scales)})

args <- commandArgs(trailingOnly = TRUE)
inp <- args[1]; out <- args[2]
dir.create(out, showWarnings = FALSE, recursive = TRUE)
TIERS <- c("top1", "top5", "top10", "top20")
CRIT <- c(n_ge1 = ">=1 experiment", n_ge2exp = ">=2 experiments", n_ge2ct = ">=2 experiments, >=2 cell types")
CRIT_COL <- c("#bdbdbd", "#2166ac", "#b2182b")
CLASS <- c("Sequence-specific TF", "Transcription machinery", "Histone writer/eraser", "Histone reader",
           "Chromatin remodeler", "Architectural/cohesin", "Other/ambiguous", "Non-gene label")
CLASS_COL <- setNames(c("#2166ac", "#e08214", "#7b3294", "#c2a5cf", "#1b7837", "#a6dba0", "#969696", "#d9d9d9"), CLASS)
theme_set(theme_classic(base_size = 8) + theme(legend.key.size = unit(3, "mm"), plot.tag = element_text(face = "bold")))

reg <- rbindlist(lapply(TIERS, function(t) fread(file.path(inp, sprintf("%s.regions.tsv.gz", t)))[, tier := t]))
reg[, tier := factor(tier, TIERS)]
long <- melt(reg, id.vars = c("name", "tier", "n_bins"), measure.vars = names(CRIT), variable.name = "crit",
             value.name = "n")
long[, crit := factor(CRIT[as.character(crit)], CRIT)]

tab <- long[, .(regions = .N, mean = mean(n), q25 = as.numeric(quantile(n, .25)), median = as.numeric(median(n)), q75 = as.numeric(quantile(n, .75)),
                max = as.numeric(max(n)), pct_zero = 100 * mean(n == 0), pct_ge10 = 100 * mean(n >= 10),
                pct_ge50 = 100 * mean(n >= 50), pct_ge100 = 100 * mean(n >= 100)), by = .(tier, crit)]
fwrite(tab[order(tier, crit)], file.path(out, "counts_by_tier.tsv"), sep = "\t")

# A: top1 distribution under the three rules
# peak = mode of a Sheather-Jones KDE; the >=1 curve starts at 244 because top1 is defined by a per-bin P >= 244
kde_mode <- function(x) { d <- density(x, bw = "SJ", n = 4096); d$x[which.max(d$y)] }
pk <- long[tier == "top1", .(x = round(kde_mode(n))), by = crit]
pk[, y := long[tier == "top1"][, .N, by = .(crit, b = floor(n / 10))][, max(N), by = crit]$V1]
fwrite(pk, file.path(out, "top1_peak_positions.tsv"), sep = "\t")
a <- ggplot(long[tier == "top1"], aes(n, colour = crit)) +
  geom_vline(xintercept = 244, linetype = "dotted", colour = "grey40", linewidth = 0.3) +
  geom_freqpoly(binwidth = 10, boundary = 0, linewidth = 0.5) +
  geom_segment(data = pk, aes(x = x, xend = x, y = 0, yend = y), linetype = "dashed", linewidth = 0.3) +
  geom_label(data = pk, aes(x = x, y = y, label = x), vjust = -0.15, hjust = c(0, 1, 1), size = 2.3,
             label.size = 0, label.padding = unit(0.5, "mm"), fill = "white", show.legend = FALSE) +
  annotate("text", x = 345, y = 520, label = "shoulder ~330:\n>=1.5 kb regions", hjust = 0, vjust = 0, size = 2,
           colour = CRIT_COL[3], lineheight = 0.9) +
  scale_colour_manual(values = CRIT_COL, name = NULL) + scale_y_continuous(expand = expansion(c(0, 0.08))) +
  labs(x = "Proteins per hotspot region", y = "Top1 hotspot regions (bin = 10)") +
  theme(legend.position = c(0.68, 0.85))

# B: per tier, primary rule, with the >=1 median for reference
b <- ggplot(long[crit != CRIT[3]], aes(tier, n, fill = crit)) +
  geom_boxplot(outlier.size = 0.1, outlier.alpha = 0.2, linewidth = 0.3, width = 0.7) +
  scale_fill_manual(values = CRIT_COL[1:2], name = NULL) + scale_y_continuous(trans = "log1p",
  breaks = c(0, 10, 30, 100, 300, 1000)) + labs(x = "Protein hotspot tier", y = "Proteins per region") +
  theme(legend.position = "top")

# C: share of >=1 proteins that keep >=2-experiment support
reg[, keep := n_ge2exp / pmax(n_ge1, 1)]
c_ <- ggplot(reg, aes(tier, keep)) + geom_violin(fill = "#92c5de", linewidth = 0.3, scale = "width") +
  geom_boxplot(width = 0.12, outlier.shape = NA, linewidth = 0.3) +
  scale_y_continuous(labels = percent, limits = c(0, 1)) +
  labs(x = "Protein hotspot tier", y = "Proteins retained at >=2 experiments")

# D: class composition of >=2-experiment proteins (pooled over regions)
cls_cols <- grep("^ge2exp_", names(reg), value = TRUE)
comp <- melt(reg[, lapply(.SD, sum), by = tier, .SDcols = cls_cols], id.vars = "tier")
comp[, class := factor(CLASS[match(variable, paste0("ge2exp_", gsub("[^A-Za-z0-9]+", "_", CLASS)))], rev(CLASS))]
comp[, share := value / sum(value), by = tier]
d <- ggplot(comp, aes(tier, share, fill = class)) + geom_col(width = 0.7) +
  scale_fill_manual(values = CLASS_COL, name = NULL, breaks = CLASS) + scale_y_continuous(labels = percent) +
  labs(x = "Protein hotspot tier", y = "Share of protein-region pairs (>=2 exp.)")

# E: proteins most often supported in top1 hotspots
pairs <- fread(file.path(inp, "top1.pairs.tsv.gz"))
nreg <- reg[tier == "top1", .N]
freq <- pairs[, .(pct_ge1 = 100 * .N / nreg, pct_ge2exp = 100 * sum(n_experiments >= 2) / nreg,
                  pct_ge2ct = 100 * sum(n_experiments >= 2 & n_celltypes >= 2) / nreg), by = .(target, class)]
setorder(freq, -pct_ge2exp)
fwrite(freq, file.path(out, "top1_target_frequency.tsv"), sep = "\t")
top <- freq[1:30][, target := factor(target, rev(target))]
e <- ggplot(top, aes(y = target)) +
  geom_col(aes(x = pct_ge1), fill = "grey88", width = 0.75) +
  geom_col(aes(x = pct_ge2exp, fill = class), width = 0.75) +
  scale_fill_manual(values = CLASS_COL, guide = "none") +
  labs(x = "% of top1 hotspot regions (grey: >=1 exp.)", y = NULL) + theme(axis.text.y = element_text(size = 6))

# F: region length confound (top1)
reg[, len := factor(pmin(n_bins, 4), 1:4, c("0.5 kb", "1 kb", "1.5 kb", ">=2 kb"))]
f <- ggplot(reg[tier == "top1"], aes(len, n_ge2exp)) + geom_boxplot(outlier.size = 0.1, linewidth = 0.3,
  fill = "#92c5de") + labs(x = "Top1 region length", y = "Proteins (>=2 exp.)")

p <- (a | b | c_) / (d | e | f) + plot_annotation(tag_levels = "A")
ggsave(file.path(out, "HotspotSupport_panels.pdf"), p, width = 180, height = 150, units = "mm")
ggsave(file.path(out, "HotspotSupport_panels.png"), p, width = 180, height = 150, units = "mm", dpi = 300)
print(tab[order(tier, crit)])

# ---- direct DNA-binding proteins (DBP = Lambert 2018 TF list; seqtf = class 'Sequence-specific TF', sensitivity)
dl <- melt(reg, id.vars = c("name", "tier", "n_bins"), measure.vars = patterns("^(dbp|seqtf)_"), value.name = "n")
dl[, n := as.numeric(n)][, set := sub("_.*", "", variable)][, crit := factor(CRIT[sub("^(dbp|seqtf)_", "n_", variable)], CRIT)]
dtab <- dl[, .(regions = .N, n_with_ge1 = sum(n >= 1), pct_with_ge1 = 100 * mean(n >= 1),
               pct_with_ge5 = 100 * mean(n >= 5), mean = mean(n), q25 = quantile(n, .25), median = median(n),
               q75 = quantile(n, .75), max = as.numeric(max(n))), by = .(set, tier, crit)]
fwrite(dtab[order(set, tier, crit)], file.path(out, "dbp_by_tier.tsv"), sep = "\t")
dbp <- dl[set == "dbp"]

# G: share of regions with >= k DBPs (>=1 is ~100% at every tier, so show the whole survival curve)
ks <- c(1, 2, 5, 10, 20, 50, 100, 200, 500)
surv <- dbp[crit == CRIT[2], .(k = ks, pct = sapply(ks, function(x) 100 * mean(n >= x))), by = tier]
fwrite(surv, file.path(out, "dbp_survival_ge2exp.tsv"), sep = "\t")
g <- ggplot(surv, aes(k, pct, colour = tier)) + geom_line(linewidth = 0.5) + geom_point(size = 0.8) +
  scale_x_log10(breaks = ks) + scale_colour_manual(values = c("#08306b", "#2171b5", "#6baed6", "#c6dbef"), name = NULL) +
  labs(x = "k (DBPs, >=2 exp. each)", y = "% regions with >=k DBPs") + theme(legend.position = c(0.2, 0.3))

# H: top1 DBP count distribution
h <- ggplot(dbp[tier == "top1"], aes(n, colour = crit)) + geom_freqpoly(binwidth = 5, boundary = 0, linewidth = 0.5) +
  scale_colour_manual(values = CRIT_COL, name = NULL) + labs(x = "DBPs per top1 hotspot region", y = "Regions") +
  theme(legend.position = c(0.62, 0.85))

# I: DBP count per tier, primary rule
i <- ggplot(dbp[crit != CRIT[3]], aes(tier, n, fill = crit)) +
  geom_boxplot(outlier.size = 0.1, outlier.alpha = 0.2, linewidth = 0.3, width = 0.7) +
  scale_fill_manual(values = CRIT_COL[1:2], guide = "none") +
  scale_y_continuous(trans = "log1p", breaks = c(0, 3, 10, 30, 100, 300)) +
  labs(x = "Protein hotspot tier", y = "DBPs per region")

# J: DBP share among >=2-experiment proteins
reg[, dbp_share := dbp_ge2exp / n_ge2exp]
j <- ggplot(reg[n_ge2exp > 0], aes(tier, dbp_share)) + geom_violin(fill = "#92c5de", linewidth = 0.3, scale = "width") +
  geom_boxplot(width = 0.12, outlier.shape = NA, linewidth = 0.3) + scale_y_continuous(labels = percent) +
  labs(x = "Protein hotspot tier", y = "DBP share of proteins (>=2 exp.)")

# E/F: DBP count vs region length within tier, and the DBP share that stays flat (count tracks total proteins)
reg[, len := factor(pmin(n_bins, 4), 1:4, c("0.5", "1", "1.5", ">=2"))]
lt <- reg[, .(dbp = as.numeric(median(dbp_ge2exp)), all = as.numeric(median(n_ge2exp)),
              share = median(dbp_share, na.rm = TRUE), N = .N), by = .(tier, len)]
fwrite(lt[order(tier, len)], file.path(out, "dbp_by_tier_length.tsv"), sep = "\t")
rho <- reg[, .(len_dbp = cor(n_bins, dbp_ge2exp, method = "spearman"),
               maxp_dbp = cor(max_proteins, dbp_ge2exp, method = "spearman"),
               len_maxp = cor(n_bins, max_proteins, method = "spearman"),
               maxp_share = cor(max_proteins, dbp_share, method = "spearman", use = "complete.obs"),
               len_share = cor(n_bins, dbp_share, method = "spearman", use = "complete.obs")), by = tier]
fwrite(rho, file.path(out, "dbp_spearman.tsv"), sep = "\t")
TIER_COL <- c(top1 = "#08306b", top5 = "#2171b5", top10 = "#6baed6", top20 = "#c6dbef")
e2 <- ggplot(lt, aes(len, dbp, colour = tier, group = tier)) + geom_line(linewidth = 0.5) + geom_point(size = 0.8) +
  scale_y_log10() + scale_colour_manual(values = TIER_COL, name = NULL) +
  labs(x = "Region length (kb)", y = "Median DBPs (>=2 exp.)") + theme(legend.position = c(0.85, 0.3))
f2 <- ggplot(lt, aes(len, share, colour = tier, group = tier)) + geom_line(linewidth = 0.5) + geom_point(size = 0.8) +
  scale_y_continuous(labels = percent, limits = c(0, 1)) + scale_colour_manual(values = TIER_COL, guide = "none") +
  geom_hline(yintercept = 1058 / 1865, linetype = "dotted", colour = "grey40") +
  annotate("text", x = 0.6, y = 1058 / 1865 - 0.05, label = "catalogue 56.7%", hjust = 0, size = 2, colour = "grey40") +
  labs(x = "Region length (kb)", y = "Median DBP share (>=2 exp.)")

q <- (g | h) / (i | j) / (e2 | f2) + plot_annotation(tag_levels = "A")
ggsave(file.path(out, "HotspotDBP_panels.pdf"), q, width = 150, height = 175, units = "mm")
ggsave(file.path(out, "HotspotDBP_panels.png"), q, width = 150, height = 175, units = "mm", dpi = 300)
print(dtab[order(set, tier, crit)])
