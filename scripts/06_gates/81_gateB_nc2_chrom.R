# Gate B NC2 post-audit correction (GPT Gate V final review, UDE/design/paper_ideas_v2_gateV_final_review.md section 3).
# The frozen 64_gateB_model.R (md5 5507a62f) permuted occupancy rows within ATAC tertile x degree quintile x promoter
# without chromosome, so a test-chromosome profile could enter a training-fold embedding. This reruns only NC2 with
# strata chrom x ATAC tertile x degree quintile x promoter (n_perm, B3 refitted per permutation with fold-specific
# embedding), against the frozen primary estimate. Setup (features, universe, arms, folds, embed_fold, oof) is copied
# from 64 unchanged except that oof takes an audit file. Frozen folds and the B2 / B3 OOF predictions are read from
# model/ and asserted identical. Original NC2 and model outputs are not touched; output model/nc2_chrom_correction/.
# usage: Rscript 81_gateB_nc2_chrom.R <gateB out_root> [cores=4] [n_perm=200]
suppressPackageStartupMessages({library(data.table); library(glmnet); library(parallel); library(jsonlite); library(Matrix)
  library(irlba)})
args <- commandArgs(trailingOnly = TRUE)
root <- args[1]
cores <- if (length(args) >= 2) as.integer(args[2]) else 8L
n_perm <- if (length(args) >= 3) as.integer(args[3]) else 200L
na_rule <- "exclude"
SMOKE <- Sys.getenv("SMOKE") == "1"  # code test: outcomes shuffled, nothing interpretable is produced
HGNC_ONLY <- FALSE
frozen <- file.path(root, "model")
out <- file.path(frozen, if (SMOKE) "nc2_chrom_correction_smoke" else "nc2_chrom_correction"); dir.create(out, showWarnings = FALSE)
f <- fread(file.path(root, "features/features.tsv.gz"))
de <- fread(file.path(root, "counts/de_ATAC_alpha05.tsv.gz"))[contrast == "D4_vs_DMSO"]
reg_all <- fread(file.path(root, "counts/regions.bed"), header = FALSE)
f[, ridx := match(region, reg_all$V4)]
reg_chrom <- reg_all$V1
Bm <- as(readMM(file.path(root, "features/pma_binary.mtx")), "CsparseMatrix")
Bg <- as(readMM(file.path(root, "features/pma_binary_gut.mtx")), "CsparseMatrix")
stopifnot(nrow(Bm) == nrow(reg_all), nrow(Bg) == nrow(reg_all))
if (HGNC_ONLY) {
  hg <- readLines(file.path(root, "features/hgnc_symbols.txt"))
  Bm <- Bm[, fread(file.path(root, "features/proteins.tsv"))$protein %in% hg]
  Bg <- Bg[, fread(file.path(root, "features/proteins_gut.tsv"))$protein %in% hg]
}
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

ap <- function(s, y) { o <- order(-s); y <- y[o]; if (!any(y == 1)) return(NA_real_); mean(cumsum(y)[y == 1] / which(y == 1)) }
auroc <- function(s, y) { r <- rank(s); n1 <- sum(y == 1); n0 <- sum(y == 0); (sum(r[y == 1]) - n1 * (n1 + 1) / 2) / (n1 * n0) }
embed_fold <- function(M, fit_rows, apply_rows) {
  Mt <- M[fit_rows, , drop = FALSE]
  idf <- log1p(nrow(Mt) / pmax(colSums(Mt), 1))
  rn <- function(X) { X <- X %*% Diagonal(x = idf); X / pmax(sqrt(rowSums(X^2)), 1e-12) }
  set.seed(20261030)
  V <- irlba(rn(Mt), nv = 20, nu = 0, maxit = 1000)$v
  as.matrix(rn(M[apply_rows, , drop = FALSE]) %*% V)
}
# M: named list of occupancy matrices (rows = regions.bed order); feats may include the embedding columns of an arm
AUDIT <- file.path(out, "embedding_isolation.tsv")
cat("run\tarm\tfold\tpid\tn_fit\ttest_chrom_rows_in_fit\n", file = AUDIT)
oof <- function(d, feats, fold, family = "binomial", yv = "y", M = list(all = Bm, gut = Bg), arm = NULL, tag = "main", audit = AUDIT) {
  p <- numeric(nrow(d)); fo <- fold[d$chrom]
  X <- as.matrix(d[, setdiff(feats, c(SVD, GUT)), with = FALSE])
  for (k in sort(unique(fo))) {
    tr <- fo != k
    Xk <- X
    if (!is.null(arm) && arm %in% names(EMB)) {
      test_ch <- names(fold)[fold == k]
      fit_rows <- which(reg_chrom %in% names(fold)[fold != k])
      stopifnot(!any(reg_chrom[fit_rows] %in% test_ch))  # fold isolation
      # every fit (incl. forked NC2 / NC3 workers) appends one audit line
      cat(sprintf("%s\t%s\t%d\t%d\t%d\t%d\n", tag, arm, k, Sys.getpid(), length(fit_rows), sum(reg_chrom[fit_rows] %in% test_ch)),
          file = audit, append = TRUE)
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
# ---- frozen primary estimate and fold check ----
P <- fread(file.path(frozen, "oof_predictions.tsv.gz"))
ff <- fread(file.path(frozen, "fold_assignments.tsv"))
stopifnot(identical(P$region, U$region))
# SMOKE: labels already shuffled above (which changes the balanced folds), so the frozen folds are used as given
if (SMOKE) { FOLD <- setNames(ff$fold, ff$chrom); P[, y := U$y] } else
  stopifnot(identical(FOLD[ff$chrom], setNames(ff$fold, ff$chrom)), identical(P$y, U$y))
obs <- ap(P$B3, P$y) - ap(P$B2, P$y)
cat("frozen B3 - B2 dAP", obs, "\n")

# ---- NC2, chromosome-preserving ----
U[, strat := paste(chrom, cut(atac_log2cpm, quantile(atac_log2cpm, 0:3 / 3), include.lowest = TRUE, labels = FALSE),
                   cut(l_deg, unique(quantile(l_deg, 0:5 / 5)), include.lowest = TRUE, labels = FALSE), tss_dist <= 1000)]
ss <- U[, .N, by = strat]
AUD2 <- file.path(out, "nc2_audit"); dir.create(AUD2, showWarnings = FALSE)
runs <- mclapply(seq_len(n_perm), function(k) {
  set.seed(20261030 + k)
  ro <- seq_len(nrow(Bm)); pr <- U[, .(ridx, pr = ridx[sample(.N)]), by = strat]
  stopifnot(all(reg_chrom[pr$ridx] == reg_chrom[pr$pr]))
  ro[pr$ridx] <- pr$pr
  af <- file.path(AUD2, sprintf("NC2_%03d.tsv", k))
  cat("run\tarm\tfold\tpid\tn_fit\ttest_chrom_rows_in_fit\n", file = af)
  d <- ap(oof(U, ARMS$B3, FOLD, M = list(all = Bm[ro, ], gut = Bg), arm = "B3", tag = paste0("NC2chr_", k), audit = af), U$y) -
    ap(P$B2, P$y)
  data.table(k = k, dAP = d, n_changed = sum(pr$ridx != pr$pr), share_changed = mean(pr$ridx != pr$pr),
             cross_chrom_swaps = sum(reg_chrom[pr$ridx] != reg_chrom[pr$pr]))
}, mc.cores = cores)
ok <- vapply(runs, function(x) is.data.table(x) && is.finite(x$dAP), logical(1))
if (!all(ok)) { print(runs[!ok]); stop("NC2 tasks failed: ", sum(!ok)) }
tab <- rbindlist(runs); stopifnot(nrow(tab) == n_perm, all(tab$cross_chrom_swaps == 0))
fwrite(tab, file.path(out, "nc2_permutation.tsv"), sep = "\t")
na <- list.files(AUD2, full.names = TRUE); stopifnot(length(na) == n_perm)
aud <- rbindlist(c(list(fread(AUDIT, colClasses = "character")), lapply(na, fread, colClasses = "character")))
aud[, `:=`(fold = as.integer(fold), test_chrom_rows_in_fit = as.integer(test_chrom_rows_in_fit))]
stopifnot(all(aud[, uniqueN(fold), by = run]$V1 == length(unique(FOLD))))
fwrite(aud, AUDIT, sep = "\t")
qa <- data.table(strata = nrow(ss), singleton_strata = sum(ss$N == 1), median_stratum_size = median(ss$N),
                 median_share_changed = median(tab$share_changed), min_share_changed = min(tab$share_changed),
                 cross_chrom_swaps = sum(tab$cross_chrom_swaps), isolation_fits = nrow(aud),
                 isolation_violations = sum(aud$test_chrom_rows_in_fit > 0))
fwrite(qa, file.path(out, "nc2_qa.tsv"), sep = "\t")
old <- fread(file.path(frozen, "negative_controls.tsv"))[control == "NC2_identity_permutation", dAP]
p95 <- unname(quantile(tab$dAP, 0.95)); p <- (1 + sum(tab$dAP >= obs)) / (1 + n_perm)
verdict <- if (qa$isolation_violations > 0) "NOT EVALUABLE" else if (obs > p95) "GO confirmed" else "CONDITIONAL"
res <- list(smoke = SMOKE, frozen_dAP = obs, n_perm = n_perm, nc2_chrom_p95 = p95, nc2_chrom_max = max(tab$dAP), nc2_chrom_p = p,
            nc2_original_p95 = unname(quantile(old, 0.95)), nc2_original_max = max(old), qa = qa, verdict = verdict)
write_json(res, file.path(out, "correction.json"), auto_unbox = TRUE, pretty = TRUE, digits = 6)
print(qa); str(res[c("frozen_dAP", "nc2_chrom_p95", "nc2_chrom_max", "nc2_chrom_p", "nc2_original_p95", "verdict")])
writeLines(capture.output(sessionInfo()), file.path(out, "sessionInfo.txt"))
