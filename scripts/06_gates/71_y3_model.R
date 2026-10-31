# Y3 (contract UDE/design/paper_ideas_v2_y3_contract_v0.2.md): do PMA-predicted SOX9-dependent regulatory elements add
# information about gene expression responses to SOX9 degradation? Two-stage, nested cross-fitting.
# usage: Rscript 71_y3_model.R <gateB out_root> <y3 out_root> <rna TPM.csv> [cores=4] [n_nc1=200] [n_nc2=20]
# Regions (primary): Gate B's 4,424 evaluable SOX9-bound regions; upstream B2 / B3 exactly as Gate B (ridge logistic,
# lambda.min by chromosome-grouped inner CV; B3 TF-IDF/SVD fitted on the baseline regions of the fitting chromosomes).
# Outer folds: Gate B fold_assignments.tsv. Outer fold k: test genes use region predictions from upstream models fitted
# on folds != k; training genes use cross-fitted predictions (fit on folds not in {k, j}, predict fold j).
# Genes (primary): testable protein-coding / lncRNA genes (70) on chr1-22/X with >= 1 primary region whose midpoint is
# within 50 kb of the TSS. Links: weight exp(-d / 25 kb); promoter = TSS +-2 kb. GA: baseline gene / linked-region
# summaries; GB2 / GB3: GA + region P(loss) from B2 / B3 summarised as weighted mean, max, promoter max (+ flag) and
# distal weighted mean. Outcomes: Y3a |D4 apeglm log2FC| (ridge gaussian; pooled out-of-fold Spearman; primary GB3 vs
# GB2), Y3a' responder = padj < 0.05 & |shrunken| >= 0.585 (ridge logistic; AP), Y3b direction among responders (AUROC).
# Controls: NC1 link specificity (cross-fitted predictions of both arms permuted with one permutation within chromosome x
# ATAC tertile x SOX9 tertile x promoter strata; aggregation and gene models redone; n_nc1); NC2 occupancy identity
# (occupancy rows permuted among primary regions within ATAC tertile x degree quintile x promoter, B3 cross-fits and gene
# stage redone; n_nc2). Sensitivities: nearest-TSS links, promoter-only / distal-only summaries, top-1% genes removed,
# leave-one-chromosome-out; secondary: all testable baseline regions upstream and all linked genes.
suppressPackageStartupMessages({library(data.table); library(glmnet); library(parallel); library(jsonlite); library(Matrix)
  library(irlba)})
a <- commandArgs(trailingOnly = TRUE)
gb <- a[1]; yr <- a[2]; tpm_csv <- a[3]
cores <- if (length(a) >= 4) as.integer(a[4]) else 4L
n_nc1 <- if (length(a) >= 5) as.integer(a[5]) else 200L
n_nc2 <- if (length(a) >= 6) as.integer(a[6]) else 20L
SMOKE <- Sys.getenv("SMOKE") == "1"  # code test: RNA outcomes shuffled across genes
out <- file.path(yr, if (SMOKE) "model_smoke" else "model"); dir.create(out, showWarnings = FALSE, recursive = TRUE)
CH <- c(paste0("chr", 1:22), "chrX")

# ---- regions (as 64_gateB_model.R) ----
f <- fread(file.path(gb, "features/features.tsv.gz"))
de <- fread(file.path(gb, "counts/de_ATAC_alpha05.tsv.gz"))[contrast == "D4_vs_DMSO"]
reg_all <- fread(file.path(gb, "counts/regions.bed"), header = FALSE)
f[, ridx := match(region, reg_all$V4)]
f <- merge(f, de[, .(region, log2FC, padj)], by = "region", all.x = TRUE)
setorder(f, ridx); stopifnot(all(f$ridx == seq_len(nrow(f))))
f[, y := as.integer(!is.na(padj) & padj < 0.05 & log2FC < 0)]
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
SVD <- paste0("svd_", 1:20)
Bm <- as(readMM(file.path(gb, "features/pma_binary.mtx")), "CsparseMatrix")
stopifnot(nrow(Bm) == nrow(f))
FOLD <- with(fread(file.path(gb, "model/fold_assignments.tsv")), setNames(fold, chrom))
f[, fold := FOLD[chrom]]
f[, prim := sox9_dmso_both == TRUE & blacklist == FALSE & !is.na(padj)]
f[, alltest := blacklist == FALSE & !is.na(padj) & !is.na(fold)]
stopifnot(sum(f$prim) == 4424L)
XB2 <- as.matrix(f[, ..B2])

ISO <- file.path(out, "crossfit_isolation.tsv")
cat("stage\trun\touter_k\tinner_j\tfit_folds\tn_fit_regions\tn_train_labelled\tn_train_genes\tn_test_genes\tviolations\n", file = ISO)
logiso <- function(...) cat(paste(..., sep = "\t"), "\n", file = ISO, append = TRUE, sep = "")
embed <- function(M, fit_rows) {
  Mt <- M[fit_rows, , drop = FALSE]
  idf <- log1p(nrow(Mt) / pmax(colSums(Mt), 1))
  rn <- function(X) { X <- X %*% Diagonal(x = idf); X / pmax(sqrt(rowSums(X^2)), 1e-12) }
  set.seed(20261030)
  V <- irlba(rn(Mt), nv = 20, nu = 0, maxit = 1000)$v
  as.matrix(rn(M) %*% V)
}
# upstream: fit on labelled rows of `train_set` in folds fit_f; predict rows `pred`
region_pred <- function(arm, fit_f, pred, M, train_set, tag, k, j) {
  emb_rows <- which(f$fold %in% fit_f)                       # all baseline regions on the fitting chromosomes
  tr <- which(train_set & f$fold %in% fit_f)
  viol <- sum(!f$fold[emb_rows] %in% fit_f) + sum(!f$fold[tr] %in% fit_f) + sum(f$fold[pred] %in% fit_f)
  logiso("region", tag, k, j, paste(fit_f, collapse = ","), length(emb_rows), length(tr), NA, NA, viol)
  stopifnot(viol == 0)
  X <- XB2
  if (arm == "B3") { E <- embed(M, emb_rows); colnames(E) <- SVD; X <- cbind(X, E) }
  inner <- as.integer(factor(f$chrom[tr])) %% 5L + 1L
  cv <- cv.glmnet(X[tr, ], f$y[tr], family = "binomial", alpha = 0, foldid = inner)
  as.numeric(predict(cv, X[pred, , drop = FALSE], s = "lambda.min", type = "response"))
}
crossfit <- function(arm, M, train_set, pred_set, tag) {
  lapply(1:5, function(k) {
    p <- rep(NA_real_, nrow(f))
    tk <- which(pred_set & f$fold == k); p[tk] <- region_pred(arm, setdiff(1:5, k), tk, M, train_set, tag, k, NA)
    for (j in setdiff(1:5, k)) { tj <- which(pred_set & f$fold == j)
      p[tj] <- region_pred(arm, setdiff(1:5, c(k, j)), tj, M, train_set, tag, k, j) }
    p })
}

# ---- genes, links, features ----
g0 <- fread(file.path(yr, "rna/rna_de.tsv.gz"))[!is.na(padj) & chrom %in% CH]
tpm <- fread(tpm_csv); setnames(tpm, 1, "gene"); tpm[, gene_id := sub("_.*", "", gene)]
g0[, l_tpm := log2(1 + rowMeans(tpm[match(g0$gene_id, gene_id), .(DMSO_1, DMSO_2)]))]
g0[is.na(l_tpm), l_tpm := 0]
g0[, `:=`(y3 = abs(log2FC_shrunk), resp = as.integer(padj < 0.05 & abs(log2FC_shrunk) >= 0.585), up = as.integer(log2FC > 0))]
if (SMOKE) { set.seed(1); g0[, c("y3", "resp", "up") := .SD[sample(.N)], .SDcols = c("y3", "resp", "up")] }
mid <- (f$start + f$end) %/% 2
make_links <- function(gg, rset) rbindlist(lapply(CH, function(ch) {
  gi <- which(gg$chrom == ch); ri <- which(rset & f$chrom == ch)
  if (!length(gi) || !length(ri)) return(NULL)
  rs <- ri[order(mid[ri])]; m <- mid[rs]
  rbindlist(lapply(gi, function(i) { lo <- findInterval(gg$tss[i] - 50000, m) + 1; hi <- findInterval(gg$tss[i] + 50000, m)
    if (hi < lo) return(NULL); r <- rs[lo:hi]; data.table(gene = i, region = r, d = abs(mid[r] - gg$tss[i])) }))
}))
g0[, n_baseline_links := 0L]
Lall <- make_links(g0, f$alltest); nb <- Lall[, .N, by = gene]; g0[nb$gene, n_baseline_links := nb$N]
# universe: genes with >= 1 linked region of `rset`; gene re-indexed 1..G
universe <- function(rset) {
  L <- make_links(g0, rset); keep <- sort(unique(L$gene))
  L[, gene := match(gene, keep)]; L[, `:=`(w = exp(-d / 25000), prom = d <= 2000)]
  gg <- g0[keep]; gg[, fold := FOLD[chrom]]
  list(g = gg, L = L)
}
nearest_links <- function(L) L[order(region, d)][!duplicated(region)]
summ <- function(L, G, v, fun) { r <- numeric(G); if (!nrow(L)) return(r); x <- L[, .(s = fun(v[region], w)), by = gene]; r[x$gene] <- x$s; r }
wmean <- function(v, w) sum(v * w) / sum(w)
one <- rep(1, 1e6)
gene_base <- function(U, L = U$L) {
  G <- nrow(U$g); pos <- function(v) pmax(v + 1, 0)
  lp <- L[prom == TRUE]; ld <- L[prom == FALSE]
  dmin <- numeric(G); x <- L[, .(m = min(d)), by = gene]; dmin[x$gene] <- x$m
  data.table(l_tpm = U$g$l_tpm, lnc = as.numeric(U$g$gene_type == "lncRNA"),
             n_links = log1p(summ(L, G, one, function(v, w) length(v))),
             n_prom = summ(lp, G, one, function(v, w) length(v)), n_dist = summ(ld, G, one, function(v, w) length(v)),
             n_baseline = log1p(U$g$n_baseline_links),
             atac = summ(L, G, pos(f$atac_log2cpm), wmean), sox9 = summ(L, G, pos(f$sox9_log2cpm), wmean),
             motif = summ(L, G, pmax(f$sox_motif_margin, 0), wmean), k27 = summ(L, G, pos(f$h3k27ac_log2cpm), wmean),
             k4 = summ(L, G, pos(f$h3k4me3_log2cpm), wmean), w_sum = summ(L, G, one, function(v, w) sum(w)),
             d_min = log1p(dmin))
}
dep_feats <- function(U, p, L = U$L, parts = "all") {
  G <- nrow(U$g); lp <- L[prom == TRUE]; ld <- L[prom == FALSE]
  o <- data.table(dep_wmean = summ(L, G, p, wmean), dep_max = summ(L, G, p, function(v, w) max(v)),
                  dep_prom = summ(lp, G, p, function(v, w) max(v)), has_prom = as.numeric(summ(lp, G, one, function(v, w) 1) > 0),
                  dep_dist = summ(ld, G, p, wmean))
  if (parts == "prom") o[, .(dep_prom, has_prom)] else if (parts == "dist") o[, .(dep_dist)] else o
}
gene_stage <- function(U, base, P, family = "gaussian", yv = "y3", rows = seq_len(nrow(U$g)), L = U$L, parts = "all",
                       tag = "") {
  G <- nrow(U$g); pred <- rep(NA_real_, G)
  for (k in 1:5) {
    X <- as.matrix(base)
    if (!is.null(P)) X <- cbind(X, as.matrix(dep_feats(U, P[[k]], L, parts)))
    tr <- intersect(which(U$g$fold != k), rows); te <- intersect(which(U$g$fold == k), rows)
    if (nzchar(tag)) logiso("gene", tag, k, NA, NA, NA, NA, length(tr), length(te), sum(U$g$fold[tr] == k))
    inner <- as.integer(factor(U$g$chrom[tr])) %% 5L + 1L
    cv <- cv.glmnet(X[tr, ], U$g[[yv]][tr], family = family, alpha = 0, foldid = inner)
    pred[te] <- as.numeric(predict(cv, X[te, , drop = FALSE], s = "lambda.min"))
  }
  pred
}
ap <- function(s, y) { o <- order(-s); y <- y[o]; mean(cumsum(y)[y == 1] / which(y == 1)) }
auroc <- function(s, y) { r <- rank(s); n1 <- sum(y == 1); n0 <- sum(y == 0); (sum(r[y == 1]) - n1 * (n1 + 1) / 2) / (n1 * n0) }
rho <- function(p, y) cor(p, y, method = "spearman")
r2 <- function(p, y) 1 - sum((y - p)^2) / sum((y - mean(y))^2)

# ---- primary ----
U <- universe(f$prim)
fwrite(U$g[, .(gene_id, symbol, gene_type, chrom, tss, fold, n_baseline_links, y3, resp, up)], file.path(out, "gene_universe.tsv"), sep = "\t")
fwrite(U$L[, .(gene_id = U$g$gene_id[gene], region = f$region[region], d, w, prom)], file.path(out, "region_gene_links.tsv.gz"), sep = "\t")
base <- gene_base(U)
fwrite(data.table(feature = c(names(base), names(dep_feats(U, rep(0, nrow(f))))),
                  group = c(rep("GA", ncol(base)), rep("GB2/GB3 dependency (B2 or B3)", 5))), file.path(out, "feature_dictionary.tsv"), sep = "\t")
cat("primary universe: genes", nrow(U$g), "responders", sum(U$g$resp), "links", nrow(U$L), "\n")
CF <- mclapply(c(B2 = "B2", B3 = "B3"), function(arm) crossfit(arm, Bm, f$prim, f$prim, paste0("main_", arm)), mc.cores = 2)
saveRDS(CF, file.path(out, "region_crossfit.rds"))
O <- U$g[, .(gene_id, symbol, chrom, fold, y3, resp, up)]
O[, GA := gene_stage(U, base, NULL, tag = "GA")]
O[, GB2 := gene_stage(U, base, CF$B2, tag = "GB2")]
O[, GB3 := gene_stage(U, base, CF$B3, tag = "GB3")]
O[, `:=`(rGA = gene_stage(U, base, NULL, "binomial", "resp"), rGB2 = gene_stage(U, base, CF$B2, "binomial", "resp"),
         rGB3 = gene_stage(U, base, CF$B3, "binomial", "resp"))]
rr <- which(U$g$resp == 1L)
O[, `:=`(dGB2 = gene_stage(U, base, CF$B2, "binomial", "up", rr), dGB3 = gene_stage(U, base, CF$B3, "binomial", "up", rr))]
Ln <- nearest_links(U$L); bn <- gene_base(U, Ln)
O[, `:=`(nGB2 = gene_stage(U, bn, CF$B2, L = Ln), nGB3 = gene_stage(U, bn, CF$B3, L = Ln))]
O[, `:=`(pGB2 = gene_stage(U, base, CF$B2, parts = "prom"), pGB3 = gene_stage(U, base, CF$B3, parts = "prom"),
         xGB2 = gene_stage(U, base, CF$B2, parts = "dist"), xGB3 = gene_stage(U, base, CF$B3, parts = "dist"))]
fwrite(O, file.path(out, "oof_gene_predictions.tsv.gz"), sep = "\t")

d_main <- function(s) rho(s$GB3, s$y3) - rho(s$GB2, s$y3)
bootc <- function(D, fun, B = 2000L) { sp <- split(D, D$chrom); ch <- names(sp)
  replicate(B, { s <- rbindlist(sp[sample(ch, replace = TRUE)]); fun(s) }) }
set.seed(20261030)
bt <- bootc(O, d_main); b2 <- bootc(O, function(s) rho(s$GB2, s$y3) - rho(s$GA, s$y3))
top <- O$y3 >= quantile(O$y3, 0.99)
cmpt <- data.table(n_genes = nrow(O), n_resp = sum(O$resp), n_regions = sum(f$prim),
  rho_GA = rho(O$GA, O$y3), rho_GB2 = rho(O$GB2, O$y3), rho_GB3 = rho(O$GB3, O$y3),
  d_rho = d_main(O), ci_lo = quantile(bt, 0.025), ci_hi = quantile(bt, 0.975),
  d_rho_GB2_GA = rho(O$GB2, O$y3) - rho(O$GA, O$y3), ci_lo_GB2_GA = quantile(b2, 0.025), ci_hi_GB2_GA = quantile(b2, 0.975),
  R2_GB2 = r2(O$GB2, O$y3), R2_GB3 = r2(O$GB3, O$y3), MAE_GB2 = mean(abs(O$GB2 - O$y3)), MAE_GB3 = mean(abs(O$GB3 - O$y3)),
  d_rho_no_top1pct = d_main(O[!top]))
fwrite(cmpt, file.path(out, "model_comparison.tsv"), sep = "\t")
sens <- data.table(analysis = c("responder_AP_GA", "responder_AP_GB2", "responder_AP_GB3", "responder_AUROC_GB2", "responder_AUROC_GB3",
                                "direction_AUROC_GB2", "direction_AUROC_GB3", "nearest_TSS_d_rho", "promoter_only_d_rho", "distal_only_d_rho"),
                   value = c(ap(O$rGA, O$resp), ap(O$rGB2, O$resp), ap(O$rGB3, O$resp), auroc(O$rGB2, O$resp), auroc(O$rGB3, O$resp),
                             auroc(O$dGB2[rr], O$up[rr]), auroc(O$dGB3[rr], O$up[rr]),
                             rho(O$nGB3, O$y3) - rho(O$nGB2, O$y3), rho(O$pGB3, O$y3) - rho(O$pGB2, O$y3), rho(O$xGB3, O$y3) - rho(O$xGB2, O$y3)))
loco <- rbindlist(lapply(unique(O$chrom), function(ch) data.table(dropped = ch, d_rho = d_main(O[chrom != ch]))))
pc <- O[, .(n = .N, d_rho = if (.N >= 30) rho(GB3, y3) - rho(GB2, y3) else NA_real_), by = chrom]
fwrite(loco, file.path(out, "chromosome_influence.tsv"), sep = "\t"); fwrite(pc, file.path(out, "per_chromosome.tsv"), sep = "\t")

# ---- NC1: link specificity (both arms' cross-fitted predictions permuted with the same permutation) ----
f[, s_atac := cut(atac_log2cpm, unique(quantile(atac_log2cpm[prim], 0:3 / 3)), include.lowest = TRUE, labels = FALSE)]
f[, s_sox9 := cut(sox9_log2cpm, unique(quantile(sox9_log2cpm[prim], 0:3 / 3)), include.lowest = TRUE, labels = FALSE)]
f[, nc1_strat := paste(chrom, s_atac, s_sox9, tss_dist <= 2000)]
pr_idx <- which(f$prim)
nc1 <- rbindlist(mclapply(seq_len(n_nc1), function(k) {
  set.seed(20261030 + k); perm <- seq_len(nrow(f))
  st <- f$nc1_strat[pr_idx]; for (s in unique(st)) { ii <- pr_idx[st == s]; perm[ii] <- ii[sample.int(length(ii))] }
  P2 <- lapply(CF$B2, function(v) v[perm]); P3 <- lapply(CF$B3, function(v) v[perm])
  e2 <- gene_stage(U, base, P2); e3 <- gene_stage(U, base, P3)
  data.table(perm = k, d_rho = rho(e3, O$y3) - rho(e2, O$y3), rho_GB2_perm = rho(e2, O$y3), rho_GB3_perm = rho(e3, O$y3),
             moved = mean(perm[pr_idx] != pr_idx))
}, mc.cores = cores))
# ---- NC2: occupancy identity (B3 cross-fits redone on permuted occupancy rows) ----
f[, nc2_strat := paste(cut(atac_log2cpm, unique(quantile(atac_log2cpm[prim], 0:3 / 3)), include.lowest = TRUE, labels = FALSE),
                       cut(l_deg, unique(quantile(l_deg[prim], 0:5 / 5)), include.lowest = TRUE, labels = FALSE), tss_dist <= 1000)]
nc2 <- unlist(mclapply(seq_len(n_nc2), function(k) {
  set.seed(20261030 + 5000 + k); rm_ <- seq_len(nrow(f))
  st <- f$nc2_strat[pr_idx]; for (s in unique(st)) { ii <- pr_idx[st == s]; rm_[ii] <- ii[sample.int(length(ii))] }
  P3 <- crossfit("B3", Bm[rm_, ], f$prim, f$prim, paste0("NC2_", k))
  rho(gene_stage(U, base, P3), O$y3) - rho(O$GB2, O$y3)
}, mc.cores = cores))
# QA-1 (Y3 preflight review): how much of the primary region set NC1 can actually rearrange
sz <- table(f$nc1_strat[pr_idx])
fwrite(data.table(n_regions = length(pr_idx), n_strata = length(sz), singleton_strata = sum(sz == 1),
                  share_in_rearrangeable_strata = sum(sz[sz >= 2]) / length(pr_idx), share_in_strata_ge5 = sum(sz[sz >= 5]) / length(pr_idx),
                  mean_share_moved = mean(nc1$moved), min_share_moved = min(nc1$moved)), file.path(out, "nc1_qa.tsv"), sep = "\t")
negc <- rbind(nc1[, .(control = "NC1_link_specificity", k = perm, d_rho)], data.table(control = "NC2_occupancy_identity", k = seq_along(nc2), d_rho = nc2))
fwrite(negc, file.path(out, "negative_controls.tsv"), sep = "\t"); fwrite(nc1, file.path(out, "nc1_detail.tsv"), sep = "\t")

# ---- secondary: all testable baseline regions upstream, all linked genes ----
U2 <- universe(f$alltest); base2 <- gene_base(U2)
CF2 <- mclapply(c(B2 = "B2", B3 = "B3"), function(arm) crossfit(arm, Bm, f$alltest, f$alltest, paste0("sec_", arm)), mc.cores = 2)
e2 <- gene_stage(U2, base2, CF2$B2); e3 <- gene_stage(U2, base2, CF2$B3)
sens <- rbind(sens, data.table(analysis = c("secondary_all_regions_n_genes", "secondary_all_regions_rho_GB2", "secondary_all_regions_rho_GB3",
                                            "secondary_all_regions_d_rho"),
                               value = c(nrow(U2$g), rho(e2, U2$g$y3), rho(e3, U2$g$y3), rho(e3, U2$g$y3) - rho(e2, U2$g$y3))))
fwrite(sens, file.path(out, "sensitivity_results.tsv"), sep = "\t")

# ---- decision (contract v0.2 section 9) ----
iso <- fread(ISO)
crit <- c(c1 = cmpt$d_rho >= 0.02, c2 = cmpt$ci_lo > 0, c3 = cmpt$d_rho > quantile(nc1$d_rho, 0.95), c4 = cmpt$d_rho > max(nc2),
          c5 = all(loco$d_rho > 0), c6 = cmpt$d_rho_no_top1pct > 0)
decision <- if (all(crit)) "GO" else if (cmpt$d_rho > 0 && cmpt$ci_lo > 0) "CONDITIONAL" else
  if (cmpt$ci_hi < 0.02 && (cmpt$ci_lo <= 0 || cmpt$d_rho <= quantile(nc1$d_rho, 0.95))) "NO-GO" else "INCONCLUSIVE"
write_json(list(comparison = cmpt, nc1_p95 = quantile(nc1$d_rho, 0.95), nc1_p = (1 + sum(nc1$d_rho >= cmpt$d_rho)) / (1 + nrow(nc1)),
                nc1_rho_GB2_perm_mean = mean(nc1$rho_GB2_perm), nc1_mean_share_moved = mean(nc1$moved), nc2_max = max(nc2),
                nc2_p = (1 + sum(nc2 >= cmpt$d_rho)) / (1 + length(nc2)), nc2_min_achievable_p = 1 / (1 + length(nc2)), isolation_rows = nrow(iso),
                isolation_violations = sum(iso$violations, na.rm = TRUE), criteria = as.list(crit), decision = decision,
                n_nc1 = n_nc1, n_nc2 = n_nc2), file.path(out, "decision.json"), auto_unbox = TRUE, pretty = TRUE, digits = 6)
print(cmpt); print(sens); print(crit); cat("DECISION:", decision, "\n")
writeLines(capture.output(sessionInfo()), file.path(out, "sessionInfo.txt"))
