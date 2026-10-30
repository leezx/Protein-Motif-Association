# Context Query v0.1, GPT review round 1 (2026-10-30): two required checks + one allowed analysis. Argos, r4p3.
# usage: Rscript 51_ht29_review_checks.R <out_root> (counts/, pma/ with sox_motifs.tsv.gz of 50, query/ of 48)
# Writes <out_root>/query/review1/.
# R1 SMARCC1 replicate consistency, normalisation-free: per CUT&RUN sample, log2(fragments in SOX9+SMARCC1 regions /
#    fragments in SMARCC1-only regions); day effect = sample ratio minus DMSO ratio, for each replicate pairing
#    (1-1, 2-2, 1-2, 2-1). Same for ATAC-lost vs not-lost SOX9+SMARCC1 regions; IgG (background) for both contrasts.
#    Specific signal = SMARCC1 delta minus IgG delta (IgG: DMSO x2, D4 x2, D13 rep 2 only).
#    Per-region view: median log2(CPM+0.5) change per replicate pairing.
# R2 SOX-family ChIP vs SOX motif (SOX9-bound regions, outcome ATAC lost at D4): ChIP = PMA SOX targets other than
#    SOX9 (all external to HT-29), sox_fam = >= 1 such target with >= 2 experiments, sox_fam_exp = their experiments;
#    motif = 6 SOX PWMs (50): ns(best margin, 3) + log1p(hits). Bases: B0 = ns(ATAC, 4) + ns(GC, 3) + CpG + TSS class
#    + cCRE class + log1p(P_max); B1 = B0 + ns(DMSO SOX9 CUT&RUN log2 CPM, 3) (baseline SOX9 occupancy; a possible
#    mediator, so both are reported). Models motif / ChIP / both: ChIP OR, LR test both vs motif, 10 x 5-fold CV AUROC.
# R3 BAF models (T2) re-fitted on B0 and B1.
suppressPackageStartupMessages({library(data.table); library(splines)})
args <- commandArgs(trailingOnly = TRUE)
root <- args[1]; out <- file.path(root, "query/review1"); dir.create(out, showWarnings = FALSE, recursive = TRUE)
d <- fread(file.path(root, "query/region_evidence.tsv.gz"))
cnt <- fread(file.path(root, "counts/counts.tsv.gz"))
lib <- fread(file.path(root, "counts/lib_size.tsv"))
pr <- fread(file.path(root, "pma/pairs.tsv.gz"))
mo <- fread(file.path(root, "pma/sox_motifs.tsv.gz"))
DAYS <- c("D2", "D4", "D7", "D10", "D13")
cnt <- cnt[match(d$region, region)]

# ---- R1 ----
grp <- d[, fifelse(smarcc1_ht29 & sox9_ht29, "SOX9+SMARCC1", fifelse(smarcc1_ht29, "SMARCC1-only", NA_character_))]
sub <- d[, fifelse(smarcc1_ht29 & sox9_ht29, fifelse(lost_D4, "ATAC-lost", "not lost"), NA_character_)]
comp <- function(assay_, g, a, b) {
  s <- lib[assay == assay_]
  rbindlist(lapply(seq_len(nrow(s)), function(i) {
    x <- cnt[[s$sample[i]]]
    data.table(assay = assay_, sample = s$sample[i], time = s$time[i], rep = s$rep[i],
               log2_ratio = log2(sum(x[which(g == a)]) / sum(x[which(g == b)])))
  }))
}
r1 <- rbind(comp("SMARCC1", grp, "SOX9+SMARCC1", "SMARCC1-only")[, contrast := "SOX9+SMARCC1 / SMARCC1-only"],
            comp("IgG", grp, "SOX9+SMARCC1", "SMARCC1-only")[, contrast := "SOX9+SMARCC1 / SMARCC1-only"],
            comp("SMARCC1", sub, "ATAC-lost", "not lost")[, contrast := "ATAC-lost / not lost (SOX9+SMARCC1)"],
            comp("IgG", sub, "ATAC-lost", "not lost")[, contrast := "ATAC-lost / not lost (SOX9+SMARCC1)"],
            comp("SOX9", grp, "SOX9+SMARCC1", "SMARCC1-only")[, contrast := "SOX9+SMARCC1 / SMARCC1-only"])
pairs_ <- CJ(rep_day = 1:2, rep_dmso = 1:2)
r1d <- rbindlist(lapply(split(r1, by = c("assay", "contrast")), function(x) {
  dm <- x[time == "DMSO"]
  rbindlist(lapply(DAYS, function(dy) {
    dd <- x[time == dy]
    if (!nrow(dd) || !nrow(dm)) return(NULL)
    pp <- pairs_[rep_day %in% dd$rep & rep_dmso %in% dm$rep]
    pp[, `:=`(assay = x$assay[1], contrast = x$contrast[1], day = dy,
              delta_log2 = dd$log2_ratio[match(rep_day, dd$rep)] - dm$log2_ratio[match(rep_dmso, dm$rep)])]
  }))
}))
r1d[, pairing := fifelse(rep_day == rep_dmso, "matched", "crossed")]
r1s <- r1d[, .(n_pairs = .N, min = min(delta_log2), max = max(delta_log2), same_sign = all(sign(delta_log2) == sign(delta_log2[1]))),
           by = .(assay, contrast, day)]
# per-region medians per replicate pairing (SMARCC1, library size CPM)
cpm <- function(s) (cnt[[s]] / lib[sample == s, lib_size]) * 1e6
r1r <- rbindlist(lapply(DAYS, function(dy) rbindlist(lapply(seq_len(nrow(pairs_)), function(k) {
  a <- sprintf("%s_SMARCC1_%d", dy, pairs_$rep_day[k]); b <- sprintf("DMSO_SMARCC1_%d", pairs_$rep_dmso[k])
  lfc <- log2(cpm(a) + 0.5) - log2(cpm(b) + 0.5)
  data.table(day = dy, rep_day = pairs_$rep_day[k], rep_dmso = pairs_$rep_dmso[k],
             sox9_smarcc1 = median(lfc[which(grp == "SOX9+SMARCC1")]), smarcc1_only = median(lfc[which(grp == "SMARCC1-only")]),
             atac_lost = median(lfc[which(sub == "ATAC-lost")]), not_lost = median(lfc[which(sub == "not lost")]))
}))))
r1r[, `:=`(diff_sox9_vs_only = sox9_smarcc1 - smarcc1_only, diff_lost_vs_not = atac_lost - not_lost)]
fwrite(r1, file.path(out, "R1_composition_by_sample.tsv"), sep = "\t")
fwrite(r1d, file.path(out, "R1_delta_by_pairing.tsv"), sep = "\t")
fwrite(r1s, file.path(out, "R1_consistency.tsv"), sep = "\t")
fwrite(r1r, file.path(out, "R1_region_medians_by_pairing.tsv"), sep = "\t")

# ---- R2 ----
sox <- pr[grepl("^SOX[0-9]+$", target) & target != "SOX9" & n_exp >= 1]
sa <- sox[, .(sox_fam = any(n_exp - n_exp_ht29 >= 2), sox_fam_exp = sum(n_exp - n_exp_ht29),
              sox_fam_targets = sum(n_exp - n_exp_ht29 >= 2)), by = region]
d <- merge(d, sa, by = "region", all.x = TRUE)
d[is.na(sox_fam), `:=`(sox_fam = FALSE, sox_fam_exp = 0L, sox_fam_targets = 0L)]
d <- merge(d, mo[, .(region, sox_motif_hits, sox_motif_margin)], by = "region")
sx <- lib[assay == "SOX9" & time == "DMSO", sample]
d[, sox9_dmso_log2cpm := log2(rowMeans(sapply(sx, cpm))[match(region, cnt$region)] + 0.5)]
d[, `:=`(tss_cls = factor(tss_cls, c("distal", "proximal", "promoter")),
         ccre_cls = factor(ccre_cls, c("other", "PLS", "pELS", "dELS", "CA-CTCF")))]
sb <- d[sox9_ht29 == TRUE & !is.na(atac_padj_D4)]
B0 <- "ns(atac_dmso_log2cpm, 4) + ns(gc, 3) + cpg + tss_cls + ccre_cls + log1p(P_max)"
B1 <- paste(B0, "+ ns(sox9_dmso_log2cpm, 3)")
MOT <- "ns(sox_motif_margin, 3) + log1p(sox_motif_hits)"
fit <- function(rhs, dat = sb) glm(as.formula(paste("lost_D4 ~", rhs)), binomial, dat)
coef_or <- function(m, term) {
  k <- which(startsWith(names(coef(m)), term))[1]; b <- unname(coef(m)[k]); se <- sqrt(vcov(m)[k, k])
  c(OR = exp(b), lo = exp(b - 1.96 * se), hi = exp(b + 1.96 * se), p = 2 * pnorm(-abs(b / se)))
}
auroc <- function(s, y) {
  r <- rank(s); n1 <- as.numeric(sum(y)); n0 <- as.numeric(sum(!y)); (sum(r[y]) - n1 * (n1 + 1) / 2) / (n1 * n0)
}
cv_auc <- function(rhs, dat = sb, reps = 10, k = 5) {
  mean(sapply(seq_len(reps), function(r) {
    set.seed(20261030 + r); f <- sample(rep(seq_len(k), length.out = nrow(dat))); pred <- numeric(nrow(dat))
    for (i in seq_len(k)) {
      m <- glm(as.formula(paste("lost_D4 ~", rhs)), binomial, dat[f != i])
      pred[f == i] <- predict(m, dat[f == i], type = "response")
    }
    auroc(pred, dat$lost_D4)
  }))
}
r2 <- rbindlist(lapply(c(B0 = B0, B1 = B1), function(B) {
  rbindlist(lapply(c("sox_fam", "log1p(sox_fam_exp)"), function(chip) {
    m_base <- fit(B); m_mot <- fit(paste(B, "+", MOT)); m_chip <- fit(paste(B, "+", chip)); m_both <- fit(paste(B, "+", MOT, "+", chip))
    lr <- anova(m_mot, m_both, test = "LRT")
    a <- coef_or(m_chip, chip); b <- coef_or(m_both, chip)
    data.table(chip_term = chip, OR_chip_only = a[["OR"]], lo_chip_only = a[["lo"]], hi_chip_only = a[["hi"]],
               OR_chip_given_motif = b[["OR"]], lo_given_motif = b[["lo"]], hi_given_motif = b[["hi"]],
               p_given_motif = b[["p"]], LR_p_both_vs_motif = lr$`Pr(>Chi)`[2],
               cvAUC_base = cv_auc(B), cvAUC_motif = cv_auc(paste(B, "+", MOT)), cvAUC_chip = cv_auc(paste(B, "+", chip)),
               cvAUC_both = cv_auc(paste(B, "+", MOT, "+", chip)))
  }))
}), idcol = "base")
sb[, motif_tertile := cut(sox_motif_margin, quantile(sox_motif_margin, 0:3 / 3), include.lowest = TRUE,
                          labels = c("low", "mid", "high"))]
r2s <- sb[, .(n = .N, lost_D4 = mean(lost_D4)), by = .(motif_tertile, sox_fam)][order(motif_tertile, sox_fam)]
r2c <- data.table(spearman_chipexp_vs_motif = cor(sb$sox_fam_exp, sb$sox_motif_margin, method = "spearman"),
                  share_sox_fam = mean(sb$sox_fam), n = nrow(sb), lost = sum(sb$lost_D4))
fwrite(r2, file.path(out, "R2_sox_chip_vs_motif.tsv"), sep = "\t")
fwrite(r2s, file.path(out, "R2_rate_by_motif_tertile.tsv"), sep = "\t")
fwrite(r2c, file.path(out, "R2_descriptive.tsv"), sep = "\t")

# ---- R3 ----
r3 <- rbindlist(lapply(c(B0 = B0, B1 = B1), function(B) rbindlist(lapply(c("smarcc1_ht29", "pma_baf"), function(x) {
  m <- fit(paste(B, "+", MOT, "+", x)); v <- coef_or(m, x)
  data.table(predictor = x, OR = v[["OR"]], lo = v[["lo"]], hi = v[["hi"]], p = v[["p"]])
}))), idcol = "base")
fwrite(r3, file.path(out, "R3_baf_models.tsv"), sep = "\t")
fwrite(sb[, .(region, lost_D4, sox_fam, sox_fam_exp, sox_motif_margin, sox_motif_hits, sox9_dmso_log2cpm)],
       file.path(out, "R2_sox9_bound_regions.tsv.gz"), sep = "\t")
print(r1s); print(r1r); print(r2); print(r2s); print(r2c); print(r3)
writeLines(capture.output(sessionInfo()), file.path(out, "sessionInfo.51.txt"))
