# Gate B (Paper-ideas v2.0 plan v0.2 + impl addendum): does PMA protein identity add to measured chromatin in predicting
# SOX9-degradation ATAC loss in HT29?
# usage: Rscript 64_gateB_model.R <gateB out_root> [cores=8] [n_perm=200]
# Universe (primary): baseline-only consensus regions (62) bound by SOX9 in both DMSO replicates, not blacklisted, with
# a D4 padj (preflight fix 1: NA padj excluded; NA -> 0 is a sensitivity). Y1 = D4 vs DMSO ATAC padj < 0.05 and
# log2FC < 0 (66: DESeq2 ~ time, median-of-ratios, results(alpha = 0.05)). Y2 = D4 log2FC. Arms (same ridge logistic /
# gaussian, glmnet alpha = 0, lambda.min by inner chromosome-grouped CV): B0 RNA/ATAC-only, B1 + SOX9 CUT&RUN,
# B2 + SMARCC1 / H3K27ac / H3K4me3 / IgG + PMA degree and coverage, B3 = B2 + PMA SVD (20), GUT = B2 + gut-only PMA
# SVD (20). Embedding (preflight fix 2): binary occupancy -> TF-IDF -> row L2 -> truncated SVD (irlba, 20), fitted in
# each outer fold on the baseline regions of the training chromosomes only (idf and V from training rows), applied to
# the test rows; isolation is asserted and logged. Outer CV: 5 chromosome folds balanced on regions and positives
# (frozen; fold_assignments.tsv). CI: paired chromosome bootstrap (2,000). NC2: raw occupancy rows permuted among
# primary regions within ATAC tertile x degree quintile x promoter, embedding and B3 refitted per fold (n_perm).
# NC3: 20 references with each protein's occupancy shuffled within degree deciles, re-embedded per fold.
# NC4: near-duplicate regions (< 2 kb apart) thinned; 5 alternative chromosome groupings.
suppressPackageStartupMessages({library(data.table); library(glmnet); library(parallel); library(jsonlite); library(Matrix)
  library(irlba)})
args <- commandArgs(trailingOnly = TRUE)
root <- args[1]
cores <- if (length(args) >= 2) as.integer(args[2]) else 8L
n_perm <- if (length(args) >= 3) as.integer(args[3]) else 200L
na_rule <- if (length(args) >= 4) args[4] else "exclude"  # D4 padj NA (independent filtering): exclude | zero
SMOKE <- Sys.getenv("SMOKE") == "1"  # code test: outcomes shuffled, nothing interpretable is produced
out <- file.path(root, if (SMOKE) "model_smoke" else "model"); dir.create(out, showWarnings = FALSE)
f <- fread(file.path(root, "features/features.tsv.gz"))
de <- fread(file.path(root, "counts/de_ATAC_alpha05.tsv.gz"))[contrast == "D4_vs_DMSO"]
reg_all <- fread(file.path(root, "counts/regions.bed"), header = FALSE)
f[, ridx := match(region, reg_all$V4)]
reg_chrom <- reg_all$V1
Bm <- as(readMM(file.path(root, "features/pma_binary.mtx")), "CsparseMatrix")
Bg <- as(readMM(file.path(root, "features/pma_binary_gut.mtx")), "CsparseMatrix")
stopifnot(nrow(Bm) == nrow(reg_all), nrow(Bg) == nrow(reg_all))
f <- merge(f, de[, .(region, log2FC, padj)], by = "region", all.x = TRUE)
f[, y := as.integer(!is.na(padj) & padj < 0.05 & log2FC < 0)]
f[, y2 := fifelse(is.na(log2FC), 0, log2FC)]
if (SMOKE) { set.seed(1); f[, `:=`(y = sample(y), y2 = sample(y2))] }
f[, `:=`(tss_cls = fifelse(tss_dist <= 1000, "promoter", fifelse(tss_dist <= 5000, "proximal", "distal")),
         ccre_cls = fifelse(ccre %in% c("PLS", "pELS", "dELS", "CA-CTCF"), ccre, "other"))]
f[, `:=`(prox = as.numeric(tss_cls == "proximal"), dist = as.numeric(tss_cls == "distal"),
         c_PLS = as.numeric(ccre_cls == "PLS"), c_pELS = as.numeric(ccre_cls == "pELS"),
         c_dELS = as.numeric(ccre_cls == "dELS"), c_CTCF = as.numeric(ccre_cls == "CA-CTCF"),
         l_tss = log1p(tss_dist), l_gene = log1p(near_gene_dist), cpg = as.numeric(cpg),
         l_sox9sig = log1p(sox9_peak_signal), l_deg = log1p(pma_degree), smarcc1_b = as.numeric(smarcc1_dmso_both))]
motif <- grep("_(hits|margin)$", names(f), value = TRUE)
B0 <- c("atac_log2cpm", "ext_atac_frac", "gc", "cpg", "l_tss", "prox", "dist", "c_PLS", "c_pELS", "c_dELS", "c_CTCF",
        motif, "near_gene_log2tpm", "l_gene")
B1 <- c(B0, "sox9_log2cpm", "l_sox9sig", "igg_log2cpm")
B2 <- c(B1, "smarcc1_log2cpm", "smarcc1_b", "h3k27ac_log2cpm", "h3k4me3_log2cpm", "l_deg", "pma_coverage")
SVD <- paste0("svd_", 1:20); GUT <- paste0("gut_", 1:20)
ARMS <- list(B0 = B0, B1 = B1, B2 = B2, B3 = c(B2, SVD), GUT = c(B2, GUT))
EMB <- list(B3 = list(m = "all", cols = SVD), GUT = list(m = "gut", cols = GUT))
fwrite(data.table(feature = unique(unlist(ARMS)), first_arm = sapply(unique(unlist(ARMS)), function(v)
  names(ARMS)[which(sapply(ARMS, function(a) v %in% a))[1]])), file.path(out, "feature_dictionary.tsv"), sep = "\t")

U_all <- f[sox9_dmso_both == TRUE & blacklist == FALSE]
U <- if (na_rule == "exclude") U_all[!is.na(padj)] else U_all
CH <- c(paste0("chr", 1:22), "chrX")
assign_folds <- function(d, k = 5L, seed = NULL) {
  s <- d[, .(n = .N, pos = sum(y)), by = chrom][match(CH, chrom)][!is.na(chrom)]
  if (is.null(seed)) s <- s[order(-n)] else { set.seed(seed); s <- s[sample(.N)] }
  load <- numeric(k); pl <- numeric(k); fo <- integer(nrow(s))
  for (i in seq_len(nrow(s))) { j <- which.min(load / sum(s$n) + pl / max(1, sum(s$pos))); fo[i] <- j
    load[j] <- load[j] + s$n[i]; pl[j] <- pl[j] + s$pos[i] }
  setNames(fo, s$chrom)
}
FOLD <- assign_folds(U)
fwrite(data.table(chrom = names(FOLD), fold = FOLD, n = U[, .N, by = chrom][match(names(FOLD), chrom), N],
                  pos = U[, sum(y), by = chrom][match(names(FOLD), chrom), V1]), file.path(out, "fold_assignments.tsv"), sep = "\t")

ap <- function(s, y) { o <- order(-s); y <- y[o]; if (!any(y == 1)) return(NA_real_); mean(cumsum(y)[y == 1] / which(y == 1)) }
auroc <- function(s, y) { r <- rank(s); n1 <- sum(y == 1); n0 <- sum(y == 0); (sum(r[y == 1]) - n1 * (n1 + 1) / 2) / (n1 * n0) }
iso_log <- new.env(); iso_log$rows <- list()
embed_fold <- function(M, fit_rows, apply_rows) {
  Mt <- M[fit_rows, , drop = FALSE]
  idf <- log1p(nrow(Mt) / pmax(colSums(Mt), 1))
  rn <- function(X) { X <- X %*% Diagonal(x = idf); X / pmax(sqrt(rowSums(X^2)), 1e-12) }
  set.seed(20261030)
  V <- irlba(rn(Mt), nv = 20, nu = 0, maxit = 1000)$v
  as.matrix(rn(M[apply_rows, , drop = FALSE]) %*% V)
}
# M: named list of occupancy matrices (rows = regions.bed order); feats may include the embedding columns of an arm
oof <- function(d, feats, fold, family = "binomial", yv = "y", M = list(all = Bm, gut = Bg), arm = NULL) {
  p <- numeric(nrow(d)); fo <- fold[d$chrom]
  X <- as.matrix(d[, setdiff(feats, c(SVD, GUT)), with = FALSE])
  for (k in sort(unique(fo))) {
    tr <- fo != k
    Xk <- X
    if (!is.null(arm) && arm %in% names(EMB)) {
      test_ch <- names(fold)[fold == k]
      fit_rows <- which(reg_chrom %in% names(fold)[fold != k])
      stopifnot(!any(reg_chrom[fit_rows] %in% test_ch))  # fold isolation
      iso_log$rows[[length(iso_log$rows) + 1]] <- data.table(arm = arm, fold = k, n_fit = length(fit_rows),
                                                             test_chrom_rows_in_fit = sum(reg_chrom[fit_rows] %in% test_ch))
      E <- embed_fold(M[[EMB[[arm]]$m]], fit_rows, d$ridx)
      colnames(E) <- EMB[[arm]]$cols
      Xk <- cbind(X, E)
    }
    inner <- as.integer(factor(d$chrom[tr])) %% 5L + 1L
    cv <- cv.glmnet(Xk[tr, , drop = FALSE], d[[yv]][tr], family = family, alpha = 0, foldid = inner)
    p[!tr] <- as.numeric(predict(cv, Xk[!tr, , drop = FALSE], s = "lambda.min"))
  }
  p
}
P <- U[, .(region, chrom, y, y2, tss_cls, atac_log2cpm, l_deg, sox_motif_margin)]
for (a in names(ARMS)) P[, (a) := oof(U, ARMS[[a]], FOLD, arm = a)]
for (a in c("B2", "B3")) P[, (paste0(a, "_y2")) := oof(U, ARMS[[a]], FOLD, "gaussian", "y2", arm = a)]
fwrite(rbindlist(iso_log$rows), file.path(out, "embedding_isolation.tsv"), sep = "\t")
fwrite(P, file.path(out, "oof_predictions.tsv.gz"), sep = "\t")

bootc <- function(d, pairs, B = 2000L) {
  sp <- split(d, d$chrom); ch <- names(sp)
  t(replicate(B, { s <- rbindlist(sp[sample(ch, replace = TRUE)])
    sapply(pairs, function(pq) ap(s[[pq[2]]], s$y) - ap(s[[pq[1]]], s$y)) }))
}
CMP <- list(B3_B2 = c("B2", "B3"), B1_B0 = c("B0", "B1"), B2_B1 = c("B1", "B2"), B3_B1 = c("B1", "B3"), GUT_B2 = c("B2", "GUT"))
set.seed(20261030)
bt <- bootc(P, CMP)
cmp <- rbindlist(lapply(names(CMP), function(nm) { pq <- CMP[[nm]]
  data.table(comparison = nm, AP_base = ap(P[[pq[1]]], P$y), AP_new = ap(P[[pq[2]]], P$y),
             AUROC_base = auroc(P[[pq[1]]], P$y), AUROC_new = auroc(P[[pq[2]]], P$y),
             dAP = ap(P[[pq[2]]], P$y) - ap(P[[pq[1]]], P$y),
             ci_lo = quantile(bt[, nm], 0.025), ci_hi = quantile(bt[, nm], 0.975)) }))
cmp[, `:=`(n = nrow(P), n_pos = sum(P$y), prevalence = mean(P$y))]
# per-chromosome and per-fold consistency of the primary comparison
pc <- P[, .(n = .N, pos = sum(y), dAP = if (sum(y) >= 5) ap(B3, y) - ap(B2, y) else NA_real_), by = chrom]
pc[, fold := FOLD[chrom]]
fwrite(pc, file.path(out, "per_chromosome.tsv"), sep = "\t")
loco <- rbindlist(lapply(unique(P$chrom), function(ch) { s <- P[chrom != ch]
  data.table(dropped = ch, dAP = ap(s$B3, s$y) - ap(s$B2, s$y)) }))
fwrite(loco, file.path(out, "chromosome_influence.tsv"), sep = "\t")
# Y2 (supportive)
r2 <- function(p, y) 1 - sum((y - p)^2) / sum((y - mean(y))^2)
y2 <- data.table(arm = c("B2", "B3"), R2 = c(r2(P$B2_y2, P$y2), r2(P$B3_y2, P$y2)),
                 spearman = c(cor(P$B2_y2, P$y2, method = "spearman"), cor(P$B3_y2, P$y2, method = "spearman")),
                 MAE = c(mean(abs(P$B2_y2 - P$y2)), mean(abs(P$B3_y2 - P$y2))))
fwrite(y2, file.path(out, "y2_continuous.tsv"), sep = "\t")
# subgroups (pre-specified secondary): promoter vs distal, SOX motif margin tertiles
P[, mtert := cut(sox_motif_margin, unique(quantile(sox_motif_margin, 0:3 / 3)), include.lowest = TRUE, labels = c("low", "mid", "high"))]
sub <- rbind(P[, .(group = "tss", level = tss_cls, n = .N, pos = sum(y), AP_B2 = ap(B2, y), AP_B3 = ap(B3, y)), by = tss_cls][, -1],
             P[, .(group = "sox_motif", level = mtert, n = .N, pos = sum(y), AP_B2 = ap(B2, y), AP_B3 = ap(B3, y)), by = mtert][, -1])
sub[, dAP := AP_B3 - AP_B2]
fwrite(sub, file.path(out, "subgroups.tsv"), sep = "\t")

# NC2: raw occupancy rows permuted among primary regions within strata; embedding and B3 refitted per fold
U[, strat := paste(cut(atac_log2cpm, quantile(atac_log2cpm, 0:3 / 3), include.lowest = TRUE, labels = FALSE),
                   cut(l_deg, unique(quantile(l_deg, 0:5 / 5)), include.lowest = TRUE, labels = FALSE),
                   tss_dist <= 1000)]
nc2 <- unlist(mclapply(seq_len(n_perm), function(k) {
  set.seed(20261030 + k)
  rm_ <- seq_len(nrow(Bm))
  U[, pr := ridx[sample(.N)], by = strat]
  rm_[U$ridx] <- U$pr
  ap(oof(U, ARMS$B3, FOLD, M = list(all = Bm[rm_, ], gut = Bg), arm = "B3"), U$y) - ap(P$B2, P$y)
}, mc.cores = cores))
# NC3: each protein's occupancy shuffled within degree deciles (all baseline regions), re-embedded per fold
deg <- rowSums(Bm); dec <- cut(deg, unique(quantile(deg, 0:10 / 10)), include.lowest = TRUE, labels = FALSE)
grp <- split(seq_along(dec), dec)
shuffle_ref <- function(seed) {
  # per column: keep the number of occupied regions in each degree decile, redraw which regions
  set.seed(seed); ii <- integer(length(Bm@i)); pos <- 0L
  for (j in seq_len(ncol(Bm))) {
    if (Bm@p[j + 1] == Bm@p[j]) next
    r <- Bm@i[(Bm@p[j] + 1):Bm@p[j + 1]] + 1L
    tb <- table(dec[r])
    for (g in names(tb)) { G <- grp[[g]]; n <- tb[[g]]
      ii[pos + seq_len(n)] <- G[sample.int(length(G), n)]; pos <- pos + n }
  }
  jj <- rep(seq_len(ncol(Bm)), diff(Bm@p))
  sparseMatrix(ii, jj, x = 1, dims = dim(Bm))
}
nc3 <- unlist(mclapply(1:20, function(k)
  ap(oof(U, ARMS$B3, FOLD, M = list(all = shuffle_ref(20261030 + 1000 + k), gut = Bg), arm = "B3"), U$y) - ap(P$B2, P$y),
  mc.cores = cores))
# NC4a: thin near-duplicates (keep the first region of any run with gaps < 2 kb); NC4b: alternative chromosome groupings
U[, gap := start - shift(end), by = chrom]
Ut <- U[is.na(gap) | gap >= 2000]
nc4 <- data.table(test = "thinned_2kb", n = nrow(Ut), dAP = ap(oof(Ut, ARMS$B3, FOLD, arm = "B3"), Ut$y) - ap(oof(Ut, ARMS$B2, FOLD), Ut$y))
for (s in 1:5) { fo <- assign_folds(U, seed = 20261030 + s)
  nc4 <- rbind(nc4, data.table(test = paste0("regroup_", s), n = nrow(U),
                               dAP = ap(oof(U, ARMS$B3, fo, arm = "B3"), U$y) - ap(oof(U, ARMS$B2, fo), U$y))) }
neg <- rbind(data.table(control = "NC2_identity_permutation", k = seq_along(nc2), dAP = nc2),
             data.table(control = "NC3_coverage_shuffled_reference", k = seq_along(nc3), dAP = nc3))
fwrite(neg, file.path(out, "negative_controls.tsv"), sep = "\t")
fwrite(nc4, file.path(out, "nc4_sensitivity.tsv"), sep = "\t")

# secondary universe: all baseline regions (no SOX9 restriction), B3 vs B2
Fa <- f[blacklist == FALSE]; FA <- assign_folds(Fa)
sec <- data.table(universe = "all_baseline_ATAC", n = nrow(Fa), n_pos = sum(Fa$y),
                  AP_B2 = ap(oof(Fa, ARMS$B2, FA), Fa$y), AP_B3 = ap(oof(Fa, ARMS$B3, FA, arm = "B3"), Fa$y))
sec[, dAP := AP_B3 - AP_B2]
# sensitivity: the other NA-padj rule on the primary SOX9 universe
Uo <- if (na_rule == "exclude") U_all else U_all[!is.na(padj)]; FO <- assign_folds(Uo)
sec <- rbind(sec, data.table(universe = paste0("sox9_bound_na_", ifelse(na_rule == "exclude", "zero", "exclude")),
                             n = nrow(Uo), n_pos = sum(Uo$y), AP_B2 = ap(oof(Uo, ARMS$B2, FO), Uo$y),
                             AP_B3 = ap(oof(Uo, ARMS$B3, FO, arm = "B3"), Uo$y)), fill = TRUE)
sec[, dAP := AP_B3 - AP_B2]
fwrite(sec, file.path(out, "secondary_universe.tsv"), sep = "\t")

# exploratory: per-protein ridge on top of B2 (interpretation only)
pn <- fread(file.path(root, "features/proteins.tsv"))$protein
Xp <- as.matrix(Bm[U$ridx, , drop = FALSE]); colnames(Xp) <- pn
keep <- colSums(Xp) >= 30
Xe <- cbind(scale(as.matrix(U[, ..B2])), Xp[, keep])
cvp <- cv.glmnet(Xe, U$y, family = "binomial", alpha = 0.5, foldid = FOLD[U$chrom],
                 penalty.factor = c(rep(0, length(B2)), rep(1, sum(keep))))
cf <- as.matrix(coef(cvp, s = "lambda.1se"))[-1, 1]
fwrite(data.table(protein = names(cf)[-(1:length(B2))], coef = cf[-(1:length(B2))],
                  regions = colSums(Xp[, keep]))[order(-abs(coef))], file.path(out, "exploratory_per_protein.tsv"), sep = "\t")

# decision (plan v0.2 B9)
r <- cmp[comparison == "B3_B2"]
p95 <- quantile(nc2, 0.95)
consistent <- all(sign(nc4$dAP) == sign(r$dAP))
crit <- c(c1 = r$dAP >= 0.02, c2 = r$ci_lo > 0, c3 = r$dAP > p95, c4 = consistent,
          c5 = y2[arm == "B3", spearman] >= y2[arm == "B2", spearman], c6 = all(loco$dAP > 0))
decision <- if (all(crit)) "GO" else if (r$dAP > 0 && r$ci_lo > 0) "CONDITIONAL" else
  if (r$ci_hi < 0.02 && (r$ci_lo <= 0 || r$dAP <= p95)) "NO-GO" else "INCONCLUSIVE"
res <- list(na_rule = na_rule, n = nrow(P), n_pos = sum(P$y), comparisons = cmp, nc2_p95 = p95, nc2_p = (1 + sum(nc2 >= r$dAP)) / (1 + length(nc2)),
            nc3_max = max(nc3), criteria = as.list(crit), decision = decision, n_perm = n_perm)
fwrite(cmp, file.path(out, "baseline_comparison.tsv"), sep = "\t")
write_json(res, file.path(out, "decision.json"), auto_unbox = TRUE, pretty = TRUE, digits = 6)
print(cmp); print(y2); print(sub); print(nc4); print(sec); print(crit); cat("DECISION:", decision, "\n")
writeLines(capture.output(sessionInfo()), file.path(out, "sessionInfo.txt"))
