# Context Query v0.1 (HT29 SOX9-BAF): region evidence table and the four tests. Argos, r4p3.
# usage: Rscript 48_ht29_context_query.R <out_root> (holds counts/ from 45 + 47 and pma/ from 46); writes <out_root>/query
#
# Units: HT29 consensus ATAC regions (45), ENCODE blacklist removed. HT29 observations (this context, 'Observed'):
# SOX9 / SMARCC1 CUT&RUN DMSO peak in both replicates; ATAC response = DESeq2 day vs DMSO (47). PMA cross-context
# evidence (46; ChIP-Atlas has no HT-29 BAF experiment, so it is fully external): BAF subunit targets below;
# pma_baf = >= 1 BAF target with >= 2 experiments (the support rule of the hotspot work); SOX9 evidence excludes HT-29.
# SOX9 response: lost = D4 vs DMSO padj < 0.05 and log2FC < 0; recovery share at D13 = 1 - LFC_D13 / LFC_D4,
# recovered when >= 0.5. Covariates (cov): natural splines of DMSO log2 CPM and GC, TSS class, cCRE class,
# log1p(P_max), SOX9 motif hit.
# T0 SOX9 depletion (CUT&RUN, library-size normalised; 47). T1 calibration: does PMA BAF evidence predict HT29 SMARCC1 occupancy,
# beyond P_max and openness? (and SOX9 evidence -> HT29 SOX9). T2 main: in SOX9-bound regions, is D4 loss associated
# with BAF evidence (PMA vs observed SMARCC1)? T3 recovery. T4 SMARCC1 loss at SOX9 sites. T5 co-regulator ranking:
# per PMA target with >= 2 experiments in >= 100 SOX9-bound regions (>= 10 lost and >= 10 kept among them),
# covariate-adjusted OR for D4 loss.
suppressPackageStartupMessages({library(data.table); library(splines)})
args <- commandArgs(trailingOnly = TRUE)
root <- args[1]; out <- file.path(root, "query"); dir.create(out, showWarnings = FALSE)
BAF <- c("SMARCA4", "SMARCA2", "ARID1A", "ARID1B", "ARID2", "PBRM1", "SMARCC1", "SMARCC2", "SMARCB1", "SMARCD1",
         "SMARCD2", "SMARCD3", "SMARCE1", "BRD9", "DPF1", "DPF2", "DPF3", "ACTL6A", "BICRA", "BICRAL", "SS18",
         "BRD7", "PHF10")
DAYS <- c("D2", "D4", "D7", "D10", "D13")

ann <- fread(file.path(root, "pma/annotation.tsv.gz"))
occ <- fread(file.path(root, "counts/occupancy.tsv.gz"))
cnt <- fread(file.path(root, "counts/counts.tsv.gz"))
lib <- fread(file.path(root, "counts/lib_size.tsv"))
pr <- fread(file.path(root, "pma/pairs.tsv.gz"))
dA <- fread(file.path(root, "counts/de_ATAC.tsv.gz"))
dS <- fread(file.path(root, "counts/de_SOX9.tsv.gz"))
dB <- fread(file.path(root, "counts/de_SMARCC1.tsv.gz"))

# ---- region evidence table ----
d <- ann[blacklist == FALSE]
dm <- lib[assay == "ATAC" & time == "DMSO", sample]
d[, atac_dmso_log2cpm := log2(rowMeans(sweep(as.matrix(cnt[match(d$region, region), dm, with = FALSE]), 2,
                                                lib[match(dm, sample), lib_size] / 1e6, "/")) + 0.1)]
o <- occ[match(d$region, region)]
d[, `:=`(sox9_ht29 = o$SOX9_DMSO_both, smarcc1_ht29 = o$SMARCC1_DMSO_both,
         sox9_ht29_any = o$SOX9_DMSO_any, smarcc1_ht29_any = o$SMARCC1_DMSO_any)]
pr[, sup := n_exp >= 2]
agg <- pr[, .(pma_targets_ge2 = sum(sup), pma_baf_targets_ge2 = sum(sup & target %in% BAF),
              pma_baf_exp = sum(n_exp[target %in% BAF]), pma_baf_exp_gut = sum(n_exp_gut[target %in% BAF]),
              pma_baf_celltypes = max(c(0L, n_celltypes[target %in% BAF])),
              pma_sox9_exp_ext = sum((n_exp - n_exp_ht29)[target == "SOX9"]),
              pma_sox9_exp_ht29 = sum(n_exp_ht29[target == "SOX9"]),
              pma_ep300 = any(sup & target == "EP300"), pma_ctcf = any(sup & target == "CTCF")), by = region]
d <- merge(d, agg, by = "region", all.x = TRUE)
for (v in names(agg)[-1]) set(d, which(is.na(d[[v]])), v, if (is.logical(agg[[v]])) FALSE else 0L)
d[, `:=`(pma_baf = pma_baf_targets_ge2 >= 1, pma_baf_gut = pma_baf_exp_gut >= 1,
         pma_baf_nongut = (pma_baf_exp - pma_baf_exp_gut) >= 2, pma_sox9 = pma_sox9_exp_ext >= 1,
         motif = sox9_motif_hits > 0,
         tss_cls = factor(fifelse(tss_dist <= 1000, "promoter", fifelse(tss_dist <= 5000, "proximal", "distal")),
                          c("distal", "proximal", "promoter")),
         ccre_cls = factor(fifelse(ccre %in% c("PLS", "pELS", "dELS", "CA-CTCF"), ccre, "other"),
                           c("other", "PLS", "pELS", "dELS", "CA-CTCF")))]
wide <- function(x, pre) {
  w <- dcast(x, region ~ contrast, value.var = c("log2FC", "padj"))
  setnames(w, -1, paste0(pre, "_", sub("_vs_DMSO", "", names(w)[-1])))
  w
}
d <- merge(d, wide(dA, "atac"), by = "region", all.x = TRUE)
d <- merge(d, wide(dS[norm == "libsize"], "sox9cnr"), by = "region", all.x = TRUE)
d <- merge(d, wide(dB[norm == "libsize"], "smarcc1cnr"), by = "region", all.x = TRUE)
d[, `:=`(lost_D4 = !is.na(atac_padj_D4) & atac_padj_D4 < 0.05 & atac_log2FC_D4 < 0,
         gained_D4 = !is.na(atac_padj_D4) & atac_padj_D4 < 0.05 & atac_log2FC_D4 > 0,
         lost_D2 = !is.na(atac_padj_D2) & atac_padj_D2 < 0.05 & atac_log2FC_D2 < 0)]
d[lost_D4 == TRUE, recovery_D13 := 1 - atac_log2FC_D13 / atac_log2FC_D4]
d[, baf_evidence := factor(fifelse(smarcc1_ht29, "Observed",
                            fifelse(pma_baf & pma_baf_celltypes >= 2, "Supported",
                                    fifelse(pma_baf_exp >= 1, "Inferred", "Unknown"))),
                           c("Observed", "Supported", "Inferred", "Unknown"))]
d[, sox9_evidence := factor(fifelse(sox9_ht29, "Observed",
                             fifelse(sox9_ht29_any | (pma_sox9 & motif), "Supported",
                                     fifelse(pma_sox9 | motif, "Inferred", "Unknown"))),
                            c("Observed", "Supported", "Inferred", "Unknown"))]
d[, mechanism := fifelse(!sox9_ht29, "not SOX9-bound",
                  paste0(fifelse(lost_D4, "SOX9-dependent", "SOX9-independent"), " / ",
                         fifelse(baf_evidence %in% c("Observed", "Supported"), "BAF-associated", "no BAF evidence")))]
fwrite(d, file.path(out, "region_evidence.tsv.gz"), sep = "\t")

# ---- helpers ----
COV <- "ns(atac_dmso_log2cpm, 4) + ns(gc, 3) + tss_cls + ccre_cls + log1p(P_max) + motif"
or_fit <- function(dat, y, x, cov = COV, label = x) {
  f <- as.formula(paste(y, "~", x, if (nchar(cov)) paste("+", cov) else ""))
  m <- glm(f, binomial, dat)
  k <- grep(paste0("^", x), names(coef(m)))[1]
  b <- coef(m)[k]; se <- sqrt(vcov(m)[k, k])
  data.table(outcome = y, predictor = label, adjusted = nchar(cov) > 0, n = nrow(dat), n_pos = sum(dat[[y]]),
             OR = exp(b), lo = exp(b - 1.96 * se), hi = exp(b + 1.96 * se), p = 2 * pnorm(-abs(b / se)))
}
auroc <- function(score, y) {
  r <- rank(score); n1 <- as.numeric(sum(y)); n0 <- as.numeric(sum(!y))
  (sum(r[y]) - n1 * (n1 + 1) / 2) / (n1 * n0)
}

# ---- T0: SOX9 depletion and SMARCC1 response (CUT&RUN, all three normalisations) ----
t0 <- rbind(
  dS[region %in% d[sox9_ht29 == TRUE, region], .(assay = "SOX9 CUT&RUN at SOX9 sites", median_log2FC = median(log2FC,
     na.rm = TRUE), share_down = mean(padj < 0.05 & log2FC < 0, na.rm = TRUE), n = .N), by = .(norm, contrast)],
  dB[region %in% d[smarcc1_ht29 == TRUE & sox9_ht29 == TRUE, region], .(assay = "SMARCC1 CUT&RUN at SOX9+SMARCC1 sites",
     median_log2FC = median(log2FC, na.rm = TRUE), share_down = mean(padj < 0.05 & log2FC < 0, na.rm = TRUE), n = .N),
     by = .(norm, contrast)],
  dB[region %in% d[smarcc1_ht29 == TRUE & sox9_ht29 == FALSE, region], .(assay = "SMARCC1 CUT&RUN at SMARCC1-only sites",
     median_log2FC = median(log2FC, na.rm = TRUE), share_down = mean(padj < 0.05 & log2FC < 0, na.rm = TRUE), n = .N),
     by = .(norm, contrast)],
  dA[region %in% d[sox9_ht29 == TRUE, region], .(norm = "median_ratio", assay = "ATAC at SOX9 sites", median_log2FC = median(log2FC, na.rm = TRUE),
     share_down = mean(padj < 0.05 & log2FC < 0, na.rm = TRUE), n = .N), by = contrast],
  dA[region %in% d[sox9_ht29 == FALSE, region], .(norm = "median_ratio", assay = "ATAC at non-SOX9 sites", median_log2FC = median(log2FC,
     na.rm = TRUE), share_down = mean(padj < 0.05 & log2FC < 0, na.rm = TRUE), n = .N), by = contrast])
fwrite(t0, file.path(out, "T0_depletion.tsv"), sep = "\t")

# ---- T1: calibration of cross-context evidence against HT29 observations ----
t1a <- rbindlist(list(
  data.table(outcome = "smarcc1_ht29", score = "PMA BAF experiments", auc = auroc(d$pma_baf_exp, d$smarcc1_ht29)),
  data.table(outcome = "smarcc1_ht29", score = "PMA BAF experiments (non-gut)",
             auc = auroc(d$pma_baf_exp - d$pma_baf_exp_gut, d$smarcc1_ht29)),
  data.table(outcome = "smarcc1_ht29", score = "PMA BAF experiments (gut: HCT116, DLD-1)",
             auc = auroc(d$pma_baf_exp_gut, d$smarcc1_ht29)),
  data.table(outcome = "smarcc1_ht29", score = "P_max (all proteins)", auc = auroc(d$P_max, d$smarcc1_ht29)),
  data.table(outcome = "smarcc1_ht29", score = "ChIP-Atlas ATAC openness", auc = auroc(d$chipatlas_atac_frac, d$smarcc1_ht29)),
  data.table(outcome = "smarcc1_ht29", score = "HT29 ATAC (DMSO)", auc = auroc(d$atac_dmso_log2cpm, d$smarcc1_ht29)),
  data.table(outcome = "sox9_ht29", score = "PMA SOX9 experiments (non-HT-29)", auc = auroc(d$pma_sox9_exp_ext, d$sox9_ht29)),
  data.table(outcome = "sox9_ht29", score = "SOX9 motif best score", auc = auroc(d$sox9_motif_best, d$sox9_ht29)),
  data.table(outcome = "sox9_ht29", score = "P_max (all proteins)", auc = auroc(d$P_max, d$sox9_ht29)),
  data.table(outcome = "sox9_ht29", score = "HT29 ATAC (DMSO)", auc = auroc(d$atac_dmso_log2cpm, d$sox9_ht29))))
t1b <- rbindlist(list(
  or_fit(d, "smarcc1_ht29", "pma_baf", ""), or_fit(d, "smarcc1_ht29", "pma_baf"),
  or_fit(d, "smarcc1_ht29", "pma_baf_gut"), or_fit(d, "smarcc1_ht29", "pma_baf_nongut"),
  or_fit(d, "smarcc1_ht29", "pma_ep300", label = "pma_ep300 (control)"),
  or_fit(d, "smarcc1_ht29", "pma_ctcf", label = "pma_ctcf (control)"),
  or_fit(d, "sox9_ht29", "pma_sox9", ""), or_fit(d, "sox9_ht29", "pma_sox9")))
# precision of PMA BAF evidence by BAF experiment count, within HT29 ATAC strength quintiles
d[, atac_q := cut(atac_dmso_log2cpm, quantile(atac_dmso_log2cpm, 0:5 / 5), include.lowest = TRUE, labels = paste0("Q", 1:5))]
d[, baf_bin := cut(pma_baf_exp, c(-1, 0, 1, 3, 10, Inf), labels = c("0", "1", "2-3", "4-10", ">10"))]
t1c <- d[, .(n = .N, smarcc1_rate = mean(smarcc1_ht29)), by = .(atac_q, baf_bin)][order(atac_q, baf_bin)]
fwrite(t1a, file.path(out, "T1_auroc.tsv"), sep = "\t")
fwrite(t1b, file.path(out, "T1_or.tsv"), sep = "\t")
fwrite(t1c, file.path(out, "T1_rate_by_atac_baf.tsv"), sep = "\t")

# ---- T2: SOX9-dependent accessibility vs BAF evidence ----
sb <- d[sox9_ht29 == TRUE & !is.na(atac_padj_D4)]
nb <- d[sox9_ht29 == FALSE & !is.na(atac_padj_D4)]
t2 <- rbindlist(list(
  or_fit(sb, "lost_D4", "pma_baf", "", "PMA BAF (unadjusted)"), or_fit(sb, "lost_D4", "pma_baf", label = "PMA BAF"),
  or_fit(sb, "lost_D4", "smarcc1_ht29", "", "HT29 SMARCC1 (unadjusted)"),
  or_fit(sb, "lost_D4", "smarcc1_ht29", label = "HT29 SMARCC1"),
  or_fit(sb, "lost_D4", "pma_baf", paste(COV, "+ smarcc1_ht29"), "PMA BAF | HT29 SMARCC1"),
  or_fit(sb, "lost_D4", "smarcc1_ht29", paste(COV, "+ pma_baf"), "HT29 SMARCC1 | PMA BAF"),
  or_fit(sb, "lost_D4", "pma_baf_gut", label = "PMA BAF gut"),
  or_fit(sb, "lost_D4", "pma_ep300", label = "PMA EP300 (control)"),
  or_fit(sb, "lost_D4", "pma_ctcf", label = "PMA CTCF (control)"),
  or_fit(sb, "lost_D4", "motif", sub(" \\+ motif", "", COV), "SOX9 motif"),
  or_fit(sb, "lost_D2", "pma_baf", label = "PMA BAF (D2 loss)"),
  or_fit(sb, "lost_D2", "smarcc1_ht29", label = "HT29 SMARCC1 (D2 loss)"),
  or_fit(nb, "lost_D4", "pma_baf", label = "PMA BAF, non-SOX9 sites"),
  or_fit(nb, "lost_D4", "smarcc1_ht29", label = "HT29 SMARCC1, non-SOX9 sites")))
t2[, set := fifelse(grepl("non-SOX9", predictor), "not SOX9-bound", "SOX9-bound")]
# interaction: is the BAF association specific to SOX9-bound regions?
dd <- d[!is.na(atac_padj_D4)]
mi <- glm(as.formula(paste("lost_D4 ~ smarcc1_ht29 * sox9_ht29 +", COV)), binomial, dd)
mj <- glm(as.formula(paste("lost_D4 ~ pma_baf * sox9_ht29 +", COV)), binomial, dd)
t2i <- rbind(data.table(model = "HT29 SMARCC1 x SOX9-bound", term = rownames(summary(mi)$coef),
                        summary(mi)$coef)[grepl(":", term)],
             data.table(model = "PMA BAF x SOX9-bound", term = rownames(summary(mj)$coef),
                        summary(mj)$coef)[grepl(":", term)])
t2m <- sb[, .N, by = .(mechanism, sox9_motif = motif)][order(mechanism)]
t2r <- sb[, .(n = .N, lost_D4 = mean(lost_D4), median_lfc_D4 = median(atac_log2FC_D4)), by = baf_evidence][order(baf_evidence)]
fwrite(t2, file.path(out, "T2_or.tsv"), sep = "\t")
fwrite(t2i, file.path(out, "T2_interaction.tsv"), sep = "\t")
fwrite(t2m, file.path(out, "T2_mechanism_counts.tsv"), sep = "\t")
fwrite(t2r, file.path(out, "T2_rate_by_baf_evidence.tsv"), sep = "\t")

# ---- T3: recovery kinetics of lost SOX9 sites ----
ls_ <- sb[lost_D4 == TRUE & !is.na(recovery_D13)]
ls_[, recovered := recovery_D13 >= 0.5]
t3 <- rbindlist(list(
  or_fit(ls_, "recovered", "pma_baf", label = "PMA BAF"), or_fit(ls_, "recovered", "smarcc1_ht29", label = "HT29 SMARCC1"),
  or_fit(ls_, "recovered", "motif", sub(" \\+ motif", "", COV), "SOX9 motif")))
traj <- melt(sb[, c("region", "lost_D4", "baf_evidence", paste0("atac_log2FC_", DAYS)), with = FALSE],
             id.vars = c("region", "lost_D4", "baf_evidence"), variable.name = "day", value.name = "log2FC")
traj[, day := sub("atac_log2FC_", "", day)]
t3s <- traj[, .(n = .N, median = median(log2FC, na.rm = TRUE), q25 = quantile(log2FC, 0.25, na.rm = TRUE),
                q75 = quantile(log2FC, 0.75, na.rm = TRUE)), by = .(lost_D4, baf_evidence, day)]
fwrite(t3, file.path(out, "T3_or.tsv"), sep = "\t")
fwrite(t3s, file.path(out, "T3_trajectory.tsv"), sep = "\t")
fwrite(ls_[, .(n = .N, recovered = mean(recovered), median_recovery = median(recovery_D13)), by = baf_evidence],
       file.path(out, "T3_recovery_by_baf.tsv"), sep = "\t")

# ---- T4: SMARCC1 occupancy change vs accessibility change at SOX9 sites ----
t4d <- d[sox9_ht29 == TRUE & smarcc1_ht29 == TRUE & !is.na(smarcc1cnr_log2FC_D4)]
t4 <- data.table(n = nrow(t4d), spearman_smarcc1_vs_atac_D4 = cor(t4d$smarcc1cnr_log2FC_D4, t4d$atac_log2FC_D4,
                 method = "spearman", use = "complete.obs"), spearman_sox9_vs_atac_D4 = cor(t4d$sox9cnr_log2FC_D4, t4d$atac_log2FC_D4,
                 method = "spearman", use = "complete.obs"),
                 smarcc1_lfc_lost = median(t4d[lost_D4 == TRUE, smarcc1cnr_log2FC_D4]),
                 smarcc1_lfc_notlost = median(t4d[lost_D4 == FALSE, smarcc1cnr_log2FC_D4]),
                 wilcox_p = wilcox.test(smarcc1cnr_log2FC_D4 ~ lost_D4, t4d)$p.value)
fwrite(t4, file.path(out, "T4_smarcc1_vs_atac.tsv"), sep = "\t")

# ---- T5: candidate co-regulator ranking (all PMA targets) ----
ps <- pr[sup == TRUE & region %in% sb$region]
keep <- ps[, .N, by = target][N >= 100, target]
X <- dcast(ps[target %in% keep, .(region, target, v = TRUE)], region ~ target, value.var = "v", fill = FALSE)
sbt <- merge(sb[, c("region", "lost_D4", "atac_dmso_log2cpm", "gc", "tss_cls", "ccre_cls", "P_max", "motif"),
               with = FALSE], X, by = "region", all.x = TRUE)
for (v in keep) set(sbt, which(is.na(sbt[[v]])), v, FALSE)
t5 <- rbindlist(lapply(keep, function(g) {
  sbt[, x := get(g)]
  r <- tryCatch(or_fit(sbt, "lost_D4", "x", label = g), error = function(e) NULL)
  if (!is.null(r)) r[, `:=`(n_with = sum(sbt$x), lost_with = mean(sbt$lost_D4[sbt$x]),
                           lost_without = mean(sbt$lost_D4[!sbt$x]))]
  if (!is.null(r) && min(sum(sbt$x & sbt$lost_D4), sum(sbt$x & !sbt$lost_D4)) < 10) r <- NULL  # separation
  r
}))
t5[, `:=`(padj = p.adjust(p, "BH"), is_baf = predictor %in% BAF)]
t5 <- t5[order(-OR)]
t5[, rank := seq_len(.N)]
fwrite(t5, file.path(out, "T5_coregulator_rank.tsv"), sep = "\t")

summ <- list(regions = nrow(d), sox9_bound = nrow(sb), smarcc1_bound = sum(d$smarcc1_ht29),
             lost_D4_sox9 = sum(sb$lost_D4), lost_D4_nonsox9 = sum(nb$lost_D4), gained_D4_sox9 = sum(sb$gained_D4),
             pma_baf = sum(d$pma_baf), targets_ranked = nrow(t5), baf_targets_ranked = sum(t5$is_baf))
print(summ); print(t0[contrast == "D4_vs_DMSO"]); print(t1a); print(t1b); print(t2); print(t2i); print(t2r); print(t3)
print(t4); print(head(t5[, .(rank, predictor, OR, lo, hi, padj, n_with, is_baf)], 25)); print(t5[is_baf == TRUE])
jsonlite::write_json(summ, file.path(out, "summary.json"), auto_unbox = TRUE, pretty = TRUE)
writeLines(capture.output(sessionInfo()), file.path(out, "sessionInfo.48.txt"))
