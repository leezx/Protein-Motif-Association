# Gate V (contract v0.1 + preflight amendment v0.2): does the non-K562 PMA reference add to measured chromatin in
# predicting GATA1-CRISPRi accessibility loss in K562 (Spear-ATAC GSE168851)? Same framework as Gate B (64), retrained
# on K562 labels; not a zero-shot transfer of the HT29 model.
# usage: Rscript 79_gateV_model.R <gateV root> [cores=8] [n_perm=200]
# Universe (primary): NT-accessible subset of pooled-called ArchR peaks (77: NT CPM >= 1 after author NT-guide QC)
# bound by >= 2 unperturbed K562 GATA1 ChIP-Atlas experiments (75), main chromosomes, not blacklisted, pooled padj
# not NA. Y1 = GATA1 vs NT padj < 0.05 and log2FC < 0 (77); Y2 = pooled log2FC. Arms (ridge, glmnet alpha = 0,
# lambda.min by inner chromosome-grouped CV): B0 NT ATAC + external non-K562 ATAC prior + sequence/annotation + GATA
# motifs; B1 + GATA1 ChIP support; B2 + K562 H3K27ac / H3K4me3 support + PMA degree / coverage (non-K562); B3 = B2 +
# PMA SVD20. Embedding: binary non-K562 occupancy -> TF-IDF -> row L2 -> irlba (20), fitted per outer fold on the NT
# universe peaks of the training chromosomes only, applied to test rows; every fit is logged (isolation audit).
# Validation: 5 chromosome folds balanced on regions and positives (frozen before fitting); paired chromosome bootstrap
# (2,000); NC2 occupancy rows permuted within NT-ATAC tertile x degree quintile x promoter, embedding + B3 refitted
# (n_perm); leave-one-chromosome-out; per-guide Delta AP from the pooled OOF predictions on each guide's own testable
# rows (guide NA never counted as negative); universe sensitivity restricted to peaks with >= 2 ChIP-Atlas K-562 ATAC
# experiments (independent of the screen; reported, not used for the decision).
suppressPackageStartupMessages({library(data.table); library(glmnet); library(parallel); library(jsonlite); library(Matrix)
  library(irlba)})
args <- commandArgs(trailingOnly = TRUE)
root <- args[1]
cores <- if (length(args) >= 2) as.integer(args[2]) else 8L
n_perm <- if (length(args) >= 3) as.integer(args[3]) else 200L
SMOKE <- Sys.getenv("SMOKE") == "1"  # code test: outcomes shuffled, nothing interpretable is produced
out <- file.path(root, if (SMOKE) "model_smoke" else "model"); dir.create(out, showWarnings = FALSE)
CH <- c(paste0("chr", 1:22), "chrX")

reg <- fread(file.path(root, "counts/regions.bed"), header = FALSE, col.names = c("chrom", "start", "end", "region", "n"))
reg[, peak := .I - 1L]
f <- fread(file.path(root, "features/features.tsv.gz"))
ann <- fread(file.path(root, "pma/annotation.tsv.gz"), select = c("region", "blacklist", "ccre", "tss_dist", "cpg", "gc"))
mot <- fread(file.path(root, "pma/gata_motifs.tsv.gz"))
chip <- fread(file.path(root, "inventory/gata1_chip.tsv.gz"))
pt <- fread(file.path(root, "outcome_v2/peak_table.tsv.gz"))
f <- Reduce(function(a, b) merge(a, b, by = "region", all.x = TRUE), list(reg[, .(region, peak)], f, ann, mot))
f <- merge(f, chip, by = "peak", all.x = TRUE)
f <- merge(f, pt, by = "peak", all.x = TRUE)
setorder(f, peak); f[, ridx := peak + 1L]
stopifnot(nrow(f) == nrow(reg), identical(f$region, reg$region))

Bm <- as(readMM(file.path(root, "features/pma_binary.mtx")), "CsparseMatrix")
stopifnot(nrow(Bm) == nrow(reg))
pairs <- fread(file.path(root, "pma/pairs.tsv.gz"), select = c("region", "n_exp", "n_exp_ht29"))  # last col = K-562 here
cov <- pairs[, .(cov = sum(n_exp - n_exp_ht29)), by = region]; rm(pairs); invisible(gc())
f[, pma_degree := rowSums(Bm)]
f[, pma_coverage := log1p(fcoalesce(as.numeric(cov$cov[match(region, cov$region)]), 0))]

guides <- sub("^lfc_", "", grep("^lfc_", names(f), value = TRUE))
f[, `:=`(y = as.integer(!is.na(padj) & padj < 0.05 & log2FC < 0), y2 = log2FC)]
for (g in guides) f[, (paste0("y_", g)) := fifelse(is.na(get(paste0("padj_", g))), NA_integer_,
                                                  as.integer(get(paste0("padj_", g)) < 0.05 & get(paste0("lfc_", g)) < 0))]
f[, `:=`(tss_cls = fifelse(tss_dist <= 1000, "promoter", fifelse(tss_dist <= 5000, "proximal", "distal")),
         ccre_cls = fifelse(ccre %in% c("PLS", "pELS", "dELS", "CA-CTCF"), ccre, "other"))]
f[, `:=`(prox = as.numeric(tss_cls == "proximal"), dist = as.numeric(tss_cls == "distal"),
         c_PLS = as.numeric(ccre_cls == "PLS"), c_pELS = as.numeric(ccre_cls == "pELS"),
         c_dELS = as.numeric(ccre_cls == "dELS"), c_CTCF = as.numeric(ccre_cls == "CA-CTCF"),
         l_tss = log1p(tss_dist), cpg = as.numeric(cpg), l_deg = log1p(pma_degree),
         gata1_chip_frac = gata1_n_exp / gata1_n_eligible)]
motif <- grep("_(hits|margin)$", names(mot), value = TRUE)
B0 <- c("nt_log2cpm", "ext_atac_frac", "gc", "cpg", "l_tss", "prox", "dist", "c_PLS", "c_pELS", "c_dELS", "c_CTCF", motif)
B1 <- c(B0, "gata1_chip_frac")
B2 <- c(B1, "k562_h3k27ac_frac", "k562_h3k4me3_frac", "l_deg", "pma_coverage")
SVD <- paste0("svd_", 1:20)
ARMS <- list(B0 = B0, B1 = B1, B2 = B2, B3 = c(B2, SVD))
fwrite(data.table(feature = unique(unlist(ARMS)), first_arm = sapply(unique(unlist(ARMS)), function(v)
  names(ARMS)[which(sapply(ARMS, function(a) v %in% a))[1]])), file.path(out, "feature_dictionary.tsv"), sep = "\t")

base <- f$universe %in% TRUE & f$chrom %in% CH            # embedding fit pool: NT universe peaks
U <- f[base & gata1_n_exp >= 2 & blacklist == FALSE & !is.na(padj)]
stopifnot(!anyNA(U[, ..B2]))
if (SMOKE) {
  set.seed(1); U[, `:=`(y = sample(y), y2 = sample(y2))]
  for (g in guides) { v <- paste0("y_", g); U[, (v) := sample(get(v))] }
}

assign_folds <- function(d, k = 5L) {
  s <- d[, .(n = .N, pos = sum(y)), by = chrom][order(-n)]
  load <- numeric(k); pl <- numeric(k); fo <- integer(nrow(s))
  for (i in seq_len(nrow(s))) { j <- which.min(load / sum(s$n) + pl / max(1, sum(s$pos))); fo[i] <- j
    load[j] <- load[j] + s$n[i]; pl[j] <- pl[j] + s$pos[i] }
  setNames(fo, s$chrom)
}
FOLD <- assign_folds(U)
fwrite(U[, .(n = .N, pos = sum(y)), by = chrom][, fold := FOLD[chrom]][order(fold, chrom)],
       file.path(out, "fold_assignments.tsv"), sep = "\t")

ap <- function(s, y) { o <- order(-s); y <- y[o]; if (!any(y == 1)) return(NA_real_); mean(cumsum(y)[y == 1] / which(y == 1)) }
auroc <- function(s, y) { r <- rank(s); n1 <- sum(y == 1); n0 <- sum(y == 0); (sum(r[y == 1]) - n1 * (n1 + 1) / 2) / (n1 * n0) }
embed_fold <- function(M, fit_rows, apply_rows) {
  Mt <- M[fit_rows, , drop = FALSE]
  idf <- log1p(nrow(Mt) / pmax(colSums(Mt), 1))
  rn <- function(X) { X <- X %*% Diagonal(x = idf); X / pmax(sqrt(rowSums(X^2)), 1e-12) }
  set.seed(20261031)
  V <- irlba(rn(Mt), nv = 20, nu = 0, maxit = 1000)$v
  as.matrix(rn(M[apply_rows, , drop = FALSE]) %*% V)
}
AUDIT <- file.path(out, "embedding_isolation.tsv")
cat("run\tfold\tpid\tn_fit\ttest_chrom_rows_in_fit\n", file = AUDIT)
oof <- function(d, feats, fold, family = "binomial", yv = "y", M = Bm, tag = "main", audit = AUDIT) {
  p <- numeric(nrow(d)); fo <- fold[d$chrom]
  X <- as.matrix(d[, setdiff(feats, SVD), with = FALSE])
  for (k in sort(unique(fo))) {
    tr <- fo != k; Xk <- X
    if (any(SVD %in% feats)) {
      test_ch <- names(fold)[fold == k]
      fit_rows <- which(base & f$chrom %in% names(fold)[fold != k])
      stopifnot(!any(f$chrom[fit_rows] %in% test_ch))
      cat(sprintf("%s\t%d\t%d\t%d\t%d\n", tag, k, Sys.getpid(), length(fit_rows), sum(f$chrom[fit_rows] %in% test_ch)),
          file = audit, append = TRUE)
      E <- embed_fold(M, fit_rows, d$ridx); colnames(E) <- SVD
      Xk <- cbind(X, E)
    }
    inner <- as.integer(factor(d$chrom[tr])) %% 5L + 1L
    cv <- cv.glmnet(Xk[tr, , drop = FALSE], d[[yv]][tr], family = family, alpha = 0, foldid = inner)
    p[!tr] <- as.numeric(predict(cv, Xk[!tr, , drop = FALSE], s = "lambda.min"))
  }
  p
}

P <- U[, c("region", "chrom", "y", "y2", "tss_cls", "nt_log2cpm", "l_deg", "gata_motif_margin", "ext_atac_k562_n",
           paste0("y_", guides)), with = FALSE]
for (a in names(ARMS)) P[, (a) := oof(U, ARMS[[a]], FOLD, tag = a)]
for (a in c("B2", "B3")) P[, (paste0(a, "_y2")) := oof(U, ARMS[[a]], FOLD, "gaussian", "y2", tag = paste0(a, "_y2"))]
fwrite(P, file.path(out, "oof_predictions.tsv.gz"), sep = "\t")

# paired chromosome bootstrap: one resample of chromosomes serves all comparisons and guides
CMP <- list(B3_B2 = c("B2", "B3"), B1_B0 = c("B0", "B1"), B2_B1 = c("B1", "B2"), B3_B1 = c("B1", "B3"))
dap_on <- function(s, yv, a, b) { k <- !is.na(s[[yv]]); ap(s[[b]][k], s[[yv]][k]) - ap(s[[a]][k], s[[yv]][k]) }
stats_of <- function(s) c(sapply(CMP, function(pq) dap_on(s, "y", pq[1], pq[2])),
                          setNames(sapply(guides, function(g) dap_on(s, paste0("y_", g), "B2", "B3")), paste0("guide_", guides)))
sp <- split(P, P$chrom); chs <- names(sp)
set.seed(20261031)
bt <- t(replicate(2000L, stats_of(rbindlist(sp[sample(chs, replace = TRUE)]))))
cmp <- rbindlist(lapply(names(CMP), function(nm) { pq <- CMP[[nm]]
  data.table(comparison = nm, AP_base = ap(P[[pq[1]]], P$y), AP_new = ap(P[[pq[2]]], P$y),
             AUROC_base = auroc(P[[pq[1]]], P$y), AUROC_new = auroc(P[[pq[2]]], P$y),
             dAP = dap_on(P, "y", pq[1], pq[2]), ci_lo = quantile(bt[, nm], 0.025, na.rm = TRUE),
             ci_hi = quantile(bt[, nm], 0.975, na.rm = TRUE)) }))
cmp[, `:=`(n = nrow(P), n_pos = sum(P$y), prevalence = mean(P$y))]
fwrite(cmp, file.path(out, "baseline_comparison.tsv"), sep = "\t")

# guides: pooled OOF predictions, each guide's own testable rows and labels
gd <- rbindlist(lapply(guides, function(g) { yv <- paste0("y_", g); k <- !is.na(P[[yv]]); nm <- paste0("guide_", g)
  data.table(guide = g, n_testable = sum(k), n_pos = sum(P[[yv]][k]), prevalence = mean(P[[yv]][k]),
             AP_B2 = ap(P$B2[k], P[[yv]][k]), AP_B3 = ap(P$B3[k], P[[yv]][k]), dAP = dap_on(P, yv, "B2", "B3"),
             ci_lo = quantile(bt[, nm], 0.025, na.rm = TRUE), ci_hi = quantile(bt[, nm], 0.975, na.rm = TRUE)) }))
fwrite(gd, file.path(out, "guide_validation.tsv"), sep = "\t")

pc <- P[, .(n = .N, pos = sum(y), dAP = if (sum(y) >= 5) ap(B3, y) - ap(B2, y) else NA_real_), by = chrom][, fold := FOLD[chrom]]
fwrite(pc, file.path(out, "per_chromosome.tsv"), sep = "\t")
loco <- rbindlist(lapply(unique(P$chrom), function(ch) { s <- P[chrom != ch]; data.table(dropped = ch, dAP = ap(s$B3, s$y) - ap(s$B2, s$y)) }))
fwrite(loco, file.path(out, "chromosome_influence.tsv"), sep = "\t")
r2 <- function(p, y) 1 - sum((y - p)^2) / sum((y - mean(y))^2)
y2 <- data.table(arm = c("B2", "B3"), R2 = c(r2(P$B2_y2, P$y2), r2(P$B3_y2, P$y2)),
                 spearman = c(cor(P$B2_y2, P$y2, method = "spearman"), cor(P$B3_y2, P$y2, method = "spearman")))
fwrite(y2, file.path(out, "y2_continuous.tsv"), sep = "\t")
P[, mtert := cut(gata_motif_margin, unique(quantile(gata_motif_margin, 0:3 / 3)), include.lowest = TRUE, labels = c("low", "mid", "high"))]
sub <- rbind(P[, .(group = "tss", n = .N, pos = sum(y), AP_B2 = ap(B2, y), AP_B3 = ap(B3, y)), by = .(level = tss_cls)],
             P[, .(group = "gata_motif", n = .N, pos = sum(y), AP_B2 = ap(B2, y), AP_B3 = ap(B3, y)), by = .(level = mtert)])
sub[, dAP := AP_B3 - AP_B2]
fwrite(sub, file.path(out, "subgroups.tsv"), sep = "\t")
# universe sensitivity (amendment P0-3): peaks also accessible in >= 2 independent ChIP-Atlas K-562 ATAC experiments
us <- rbindlist(lapply(list(primary = rep(TRUE, nrow(P)), k562_atac_ref = P$ext_atac_k562_n >= 2), function(k) {
  s <- P[k]; data.table(n = nrow(s), n_pos = sum(s$y), prevalence = mean(s$y), median_lfc = median(U$log2FC[k]),
                        AP_B2 = ap(s$B2, s$y), AP_B3 = ap(s$B3, s$y), dAP = ap(s$B3, s$y) - ap(s$B2, s$y)) }), idcol = "universe")
fwrite(us, file.path(out, "universe_sensitivity.tsv"), sep = "\t")

# NC2 (review 2: chromosome-preserving): occupancy rows permuted among primary regions within chromosome x NT-ATAC
# tertile x degree quintile x promoter, so no test-chromosome profile can enter an embedding fit; embedding and B3
# refitted per fold. Each permutation writes its own audit file (merged below); every task must return a finite value.
U[, strat := paste(chrom, cut(nt_log2cpm, quantile(nt_log2cpm, 0:3 / 3), include.lowest = TRUE, labels = FALSE),
                   cut(l_deg, unique(quantile(l_deg, 0:5 / 5)), include.lowest = TRUE, labels = FALSE), tss_dist <= 1000)]
ss <- U[, .N, by = strat]
AUD2 <- file.path(out, "nc2_audit"); dir.create(AUD2, showWarnings = FALSE)
nc2_runs <- mclapply(seq_len(n_perm), function(k) {
  set.seed(20261031 + k)
  ro <- seq_len(nrow(Bm)); pr <- U[, .(ridx, pr = ridx[sample(.N)]), by = strat]
  stopifnot(all(f$chrom[pr$ridx] == f$chrom[pr$pr]))
  ro[pr$ridx] <- pr$pr
  af <- file.path(AUD2, sprintf("NC2_%03d.tsv", k))
  cat("run\tfold\tpid\tn_fit\ttest_chrom_rows_in_fit\n", file = af)
  d <- ap(oof(U, ARMS$B3, FOLD, M = Bm[ro, ], tag = paste0("NC2_", k), audit = af), U$y) - ap(P$B2, P$y)
  data.table(k = k, dAP = d, n_changed = sum(pr$ridx != pr$pr), share_changed = mean(pr$ridx != pr$pr),
             cross_chrom_swaps = sum(f$chrom[pr$ridx] != f$chrom[pr$pr]))
}, mc.cores = cores)
ok <- vapply(nc2_runs, function(x) is.data.table(x) && is.finite(x$dAP), logical(1))
if (!all(ok)) { print(nc2_runs[!ok]); stop("NC2 tasks failed: ", sum(!ok)) }
nc2_tab <- rbindlist(nc2_runs); stopifnot(nrow(nc2_tab) == n_perm, all(nc2_tab$cross_chrom_swaps == 0))
nc2 <- nc2_tab$dAP
fwrite(nc2_tab, file.path(out, "nc2_permutation.tsv"), sep = "\t")
fwrite(data.table(strata = nrow(ss), singleton_strata = sum(ss$N == 1), regions_in_singletons = sum(ss[N == 1, N]),
                  median_stratum_size = median(ss$N), median_share_changed = median(nc2_tab$share_changed),
                  min_share_changed = min(nc2_tab$share_changed), cross_chrom_swaps = sum(nc2_tab$cross_chrom_swaps)),
       file.path(out, "nc2_qa.tsv"), sep = "\t")
na <- list.files(AUD2, full.names = TRUE); stopifnot(length(na) == n_perm)
fwrite(rbindlist(c(list(fread(AUDIT)), lapply(na, fread))), AUDIT, sep = "\t")

# decision (contract v0.1 section 5)
r <- cmp[comparison == "B3_B2"]; p95 <- unname(quantile(nc2, 0.95, na.rm = TRUE))
crit <- c(c1_dAP_ge_0.02 = r$dAP >= 0.02, c2_ci_lo_gt_0 = r$ci_lo > 0, c3_gt_nc2_p95 = r$dAP > p95,
          c4_loco_all_pos = all(loco$dAP > 0), c5_guides_pos_ge2 = sum(gd$dAP > 0) >= 2)
decision <- if (all(crit)) "GO" else if (r$dAP > 0 && r$ci_lo > 0) "CONDITIONAL" else
  if (r$ci_hi < 0.02 && (r$ci_lo <= 0 || r$dAP <= p95)) "NO-GO" else "INCONCLUSIVE"
aud <- fread(AUDIT)
stopifnot(all(aud[grepl("^NC2_", run), uniqueN(fold), by = run]$V1 == length(unique(FOLD))))
res <- list(smoke = SMOKE, n = nrow(P), n_pos = sum(P$y), isolation_fits = nrow(aud), nc2_qa = fread(file.path(out, "nc2_qa.tsv")),
            isolation_violations = sum(aud$test_chrom_rows_in_fit > 0), comparisons = cmp, guides = gd,
            nc2_p95 = p95, nc2_p = (1 + sum(nc2 >= r$dAP)) / (1 + length(nc2)), n_perm = n_perm,
            criteria = as.list(crit), decision = decision)
write_json(res, file.path(out, "decision.json"), auto_unbox = TRUE, pretty = TRUE, digits = 6)
print(cmp); print(gd); print(y2); print(sub); print(us); print(crit); cat("DECISION:", decision, "\n")
writeLines(capture.output(sessionInfo()), file.path(out, "sessionInfo.txt"))
