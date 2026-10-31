# Gate A (Paper-ideas v2.0 plan v0.2 + impl addendum): does context-aware co-occupancy (M2) add to generic overlap (M1)?
# usage: Rscript 61_gateA_benchmark.R <features dir of 60> <signed_protein_modules_v1 dir> <bioplex dir or '-'> <out> [cores=8] [n_perm=200]
# Unit: unique protein pair (anchor TF x partner); anchors = sequence-specific TFs with >= 20 experiments and >= 3 cell
# types (coverage rule only); evaluable anchors have >= 3 Complex Portal partners in the 808-protein universe.
# Models (ridge logistic, glmnet alpha = 0; lambda by inner leave-anchor-out CV on training anchors):
#   M0 coverage/genomic covariates; M1 = M0 + Jaccard (Figure 1E, all bins); M2 = M1 + K-562 / Hep G2 / MCF-7
#   stratified MH log2 OR (signed modules PM1; 0 + availability flag when the pair is not measured in a context).
# Validation: leave-one-anchor-out; a test anchor's pairs never enter training. Primary set: positives + 5 matched
# unlabeled partners per positive (Mahalanobis on partner covariates, per anchor, greedy without replacement).
# Metrics: pooled out-of-fold AP, per-anchor AP, AUROC, precision@10; anchor-cluster paired bootstrap (2,000).
# Null: MH block permuted within partner-breadth deciles, whole procedure refitted (n_perm). BioPlex: models trained
# on Complex Portal, evaluated on BioPlex edges not in Complex Portal among pairs whose proteins are both in BioPlex.
suppressPackageStartupMessages({library(data.table); library(glmnet); library(parallel); library(jsonlite)})
args <- commandArgs(trailingOnly = TRUE)
fd <- args[1]; smd <- args[2]; bpd <- args[3]; out <- args[4]
cores <- if (length(args) >= 5) as.integer(args[5]) else 8L
n_perm <- if (length(args) >= 6) as.integer(args[6]) else 200L
SMOKE <- Sys.getenv("SMOKE") == "1"  # code test: Complex Portal labels shuffled across pairs
dir.create(out, showWarnings = FALSE, recursive = TRUE)
set.seed(20261030)

prot <- fread(file.path(fd, "proteins.tsv"))
pr <- fread(file.path(fd, "pairs.tsv.gz"))
pr[, same_complex := as.logical(same_complex)]
if (SMOKE) { set.seed(1); pr[, same_complex := sample(same_complex)] }
# per-context MH association (signed modules PM1); key on the unordered pair
key2 <- function(a, b) ifelse(a < b, paste(a, b), paste(b, a))
pr[, key := key2(protein_a, protein_b)]
for (ctx in c("K562", "Hep_G2", "MCF7")) {
  s <- fread(file.path(smd, ctx, "pairs.tsv.gz"), select = c("protein_a", "protein_b", "log2or_mh"))
  s[, key := key2(protein_a, protein_b)]
  v <- s$log2or_mh[match(pr$key, s$key)]
  pr[, (paste0("mh_", ctx)) := fifelse(is.na(v), 0, pmin(pmax(v, -6), 8))]
  pr[, (paste0("av_", ctx)) := as.numeric(!is.na(v))]
}
# symmetric pair covariates: min and max of per-protein features
P <- prot[, .(protein, l_exp = log(n_exp), l_breadth = log(breadth), prom_frac, hot_frac, acc_mean, ccre_frac, gc_mean,
              l_ct = log(n_celltypes), l_st = log(n_studies))]
pf <- setdiff(names(P), "protein")
A <- P[match(pr$protein_a, protein), ..pf]; B <- P[match(pr$protein_b, protein), ..pf]
for (v in pf) { pr[, (paste0(v, "_lo")) := pmin(A[[v]], B[[v]])]; pr[, (paste0(v, "_hi")) := pmax(A[[v]], B[[v]])] }
pr[, `:=`(l_shared_ct = log1p(shared_celltypes), l_shared_st = log1p(shared_studies), lj = log(jaccard + 1e-4))]
M0 <- c(as.vector(outer(pf, c("_lo", "_hi"), paste0)), "l_shared_ct", "celltype_jaccard", "l_shared_st",
        "av_K562", "av_Hep_G2", "av_MCF7")
M1 <- c(M0, "lj")
M2 <- c(M1, "mh_K562", "mh_Hep_G2", "mh_MCF7")
MODELS <- list(M0 = M0, M1 = M1, M2 = M2)

# anchors (coverage rule) and evaluability (frozen before any model is fitted)
cand <- prot[cls == "Sequence-specific TF" & n_exp >= 20 & n_celltypes >= 3, protein]
npos <- sapply(cand, function(a) pr[(protein_a == a | protein_b == a) & same_complex == TRUE, .N])
anchors <- data.table(anchor = cand, n_exp = prot[match(cand, protein), n_exp],
                      n_celltypes = prot[match(cand, protein), n_celltypes], cp_partners = npos)
anchors[, evaluable := cp_partners >= 3]
fwrite(anchors, file.path(out, "anchors.tsv"), sep = "\t")
AN <- anchors[evaluable == TRUE, anchor]
cat("anchor candidates", length(cand), "; evaluable", length(AN), "\n")
# long table: one row per (anchor, partner); anchor-anchor pairs appear twice (once per anchor), never in the same fold
L <- rbindlist(lapply(AN, function(a) {
  x <- pr[protein_a == a | protein_b == a]
  x[, `:=`(anchor = a, partner = fifelse(protein_a == a, protein_b, protein_a))]
}))
L[, y := as.integer(same_complex)]

# matched primary set: per anchor, 5 unlabeled partners per positive, nearest by Mahalanobis on partner-side covariates
mv <- c("l_exp", "l_breadth", "prom_frac", "hot_frac", "acc_mean", "l_ct", "l_st")
PM <- P[match(L$partner, protein), ..mv]
L <- cbind(L, setnames(copy(PM), paste0("p_", mv)))
mcols <- c(paste0("p_", mv), "l_shared_ct", "l_shared_st")
S <- cov(as.matrix(L[, ..mcols]))
L[, matched := y == 1L]
for (a in AN) {
  i_pos <- L[anchor == a & y == 1L, which = TRUE]; i_un <- L[anchor == a & y == 0L, which = TRUE]
  X <- as.matrix(L[, ..mcols])
  avail <- i_un
  for (i in i_pos) {
    d <- mahalanobis(X[avail, , drop = FALSE], X[i, ], S)
    pick <- avail[order(d)[seq_len(min(5, length(avail)))]]
    L[pick, matched := TRUE]; avail <- setdiff(avail, pick)
  }
}
smd_tab <- rbindlist(lapply(mcols, function(v) {
  m <- L[matched == TRUE]; p <- m[y == 1L][[v]]; u <- m[y == 0L][[v]]; ua <- L[y == 0L][[v]]
  data.table(covariate = v, smd_matched = (mean(p) - mean(u)) / sqrt((var(p) + var(u)) / 2),
             smd_all = (mean(p) - mean(ua)) / sqrt((var(p) + var(ua)) / 2))
}))
fwrite(smd_tab, file.path(out, "matching_balance.tsv"), sep = "\t")
# anchors whose matched set is unbalanced (any |SMD| > 0.5 within the anchor) leave the matched primary evaluation
bal <- L[matched == TRUE, .(max_abs_smd = max(sapply(mcols, function(v) {
  p <- get(v)[y == 1L]; u <- get(v)[y == 0L]; s <- sqrt((var(p) + var(u)) / 2)
  if (!is.finite(s) || s == 0) 0 else abs(mean(p) - mean(u)) / s }))), by = anchor]
bal[, in_primary := max_abs_smd <= 0.5]
fwrite(bal, file.path(out, "matching_by_anchor.tsv"), sep = "\t")

ap <- function(s, y) { o <- order(-s); y <- y[o]; if (!any(y == 1)) return(NA_real_); mean(cumsum(y)[y == 1] / which(y == 1)) }
auroc <- function(s, y) { r <- rank(s); n1 <- sum(y == 1); n0 <- sum(y == 0); (sum(r[y == 1]) - n1 * (n1 + 1) / 2) / (n1 * n0) }

fit_predict <- function(D, feats) {
  # leave-one-anchor-out; inner CV over training anchors chooses lambda
  rbindlist(lapply(AN, function(a) {
    te <- D[anchor == a]
    tr <- D[anchor != a & partner != a]
    tr <- tr[!duplicated(key)]
    folds <- as.integer(factor(tr$anchor)) %% 10L + 1L
    cv <- cv.glmnet(as.matrix(tr[, ..feats]), tr$y, family = "binomial", alpha = 0, foldid = folds,
                    type.measure = "deviance")
    o <- data.table(anchor = a, partner = te$partner, s = as.numeric(predict(cv, as.matrix(te[, ..feats]), s = "lambda.min")))
    o[, key := te$key][]
  }))
}

run_all <- function(D) {
  res <- lapply(MODELS, function(f) fit_predict(D, f))
  o <- res$M0[, .(anchor, partner, key, M0 = s)]
  o[, `:=`(M1 = res$M1$s, M2 = res$M2$s)]
  o
}
pred <- run_all(L)
pred <- merge(pred, L[, .(anchor, partner, y, matched)], by = c("anchor", "partner"))
fwrite(pred, file.path(out, "oof_predictions.tsv.gz"), sep = "\t")

PRIM <- bal[in_primary == TRUE, anchor]
summ <- function(d, lab) {
  # pooled over anchors; an anchor-anchor pair evaluated under both anchors keeps both (each is a held-out prediction)
  r <- data.table(set = lab, n_anchors = uniqueN(d$anchor), n = nrow(d), n_pos = sum(d$y), prevalence = mean(d$y))
  for (m in names(MODELS)) {
    r[, (paste0("AP_", m)) := ap(d[[m]], d$y)]; r[, (paste0("AUROC_", m)) := auroc(d[[m]], d$y)]
  }
  r
}
boot <- function(d, B = 2000L) {
  an <- unique(d$anchor); sp <- split(d, d$anchor)
  t(replicate(B, { s <- rbindlist(sp[sample(an, replace = TRUE)])
    c(d10 = ap(s$M1, s$y) - ap(s$M0, s$y), d21 = ap(s$M2, s$y) - ap(s$M1, s$y), d20 = ap(s$M2, s$y) - ap(s$M0, s$y)) }))
}
per_anchor <- function(d) d[, .(n = .N, n_pos = sum(y), AP_M0 = ap(M0, y), AP_M1 = ap(M1, y), AP_M2 = ap(M2, y),
                               prec10_M1 = mean(y[order(-M1)][1:10]), prec10_M2 = mean(y[order(-M2)][1:10])), by = anchor]
dm <- pred[matched == TRUE & anchor %in% PRIM]; da <- pred
res <- rbind(summ(dm, "matched_primary"), summ(da, "all_partners"))
bm <- boot(dm); ba <- boot(da)
ci <- function(b, k) quantile(b[, k], c(0.025, 0.975), na.rm = TRUE)
res[, `:=`(dAP_M2_M1 = AP_M2 - AP_M1, rel_M2_M1 = (AP_M2 - AP_M1) / AP_M1, dAP_M1_M0 = AP_M1 - AP_M0)]
res[, `:=`(ci_lo_M2_M1 = c(ci(bm, "d21")[1], ci(ba, "d21")[1]), ci_hi_M2_M1 = c(ci(bm, "d21")[2], ci(ba, "d21")[2]),
           ci_lo_M1_M0 = c(ci(bm, "d10")[1], ci(ba, "d10")[1]), ci_hi_M1_M0 = c(ci(bm, "d10")[2], ci(ba, "d10")[2]))]
pa <- per_anchor(dm)
res[set == "matched_primary", share_anchors_improved := mean(pa$AP_M2 > pa$AP_M1)]
fwrite(pa, file.path(out, "per_anchor.tsv"), sep = "\t")
fwrite(per_anchor(da), file.path(out, "per_anchor_all_partners.tsv"), sep = "\t")
# leave-one-anchor-out influence on the primary dAP
infl <- rbindlist(lapply(unique(dm$anchor), function(a) { s <- dm[anchor != a]
  data.table(dropped = a, dAP_M2_M1 = ap(s$M2, s$y) - ap(s$M1, s$y)) }))
fwrite(infl, file.path(out, "anchor_influence.tsv"), sep = "\t")
# pre-specified sensitivity: leave the bZIP family out (AP-1 / ATF / CREB / CEBP / DDIT3 / BATF / MAF anchors)
bzip <- grep("^(ATF|BATF|CEBP|CREB|DDIT3|FOS|JUN|MAF|NFE2|BACH)", unique(dm$anchor), value = TRUE)
for (lab in c("matched_no_bZIP", "all_no_bZIP")) {
  d <- if (lab == "matched_no_bZIP") dm[!anchor %in% bzip] else da[!anchor %in% bzip]
  if (uniqueN(d$anchor) >= 3) { r0 <- summ(d, lab); b0 <- boot(d)
    r0[, `:=`(dAP_M2_M1 = AP_M2 - AP_M1, rel_M2_M1 = (AP_M2 - AP_M1) / AP_M1, dAP_M1_M0 = AP_M1 - AP_M0,
              ci_lo_M2_M1 = ci(b0, "d21")[1], ci_hi_M2_M1 = ci(b0, "d21")[2],
              ci_lo_M1_M0 = ci(b0, "d10")[1], ci_hi_M1_M0 = ci(b0, "d10")[2])]
    res <- rbind(res, r0, fill = TRUE) }
}

# null: permute the MH block within partner-breadth deciles, refit M2 (and reuse the real M1)
L[, bdec := cut(p_l_breadth, unique(quantile(p_l_breadth, 0:10 / 10)), include.lowest = TRUE, labels = FALSE)]
mhb <- c("mh_K562", "mh_Hep_G2", "mh_MCF7", "av_K562", "av_Hep_G2", "av_MCF7")
null <- unlist(mclapply(seq_len(n_perm), function(k) {
  set.seed(20261030 + k)
  D <- copy(L)
  # permute at the unique-pair level so an anchor-anchor pair keeps one value
  u <- D[!duplicated(key), c("key", "bdec", mhb), with = FALSE]
  u[, (mhb) := .SD[sample(.N)], by = bdec, .SDcols = mhb]
  D[, (mhb) := NULL]; D <- merge(D, u[, c("key", mhb), with = FALSE], by = "key")
  p2 <- fit_predict(D, M2)
  x <- merge(pred[matched == TRUE & anchor %in% PRIM, .(anchor, partner, y, M1)], p2[, .(anchor, partner, s)],
             by = c("anchor", "partner"))
  ap(x$s, x$y) - ap(x$M1, x$y)
}, mc.cores = cores))
fwrite(data.table(perm = seq_along(null), dAP_M2_M1 = null), file.path(out, "null_mh_permutation.tsv"), sep = "\t")
res[set == "matched_primary", `:=`(null_p95 = quantile(null, 0.95), null_p = (1 + sum(null >= dAP_M2_M1)) / (1 + length(null)))]

# BioPlex (independent physical support), models frozen from the Complex Portal benchmark
bp_res <- data.table()
if (bpd != "-") {
  for (f in list.files(bpd, pattern = "\\.tsv$", full.names = TRUE)) {
    b <- fread(f)
    nm <- sub("\\.tsv$", "", basename(f))
    nodes <- unique(c(b$SymbolA, b$SymbolB))
    bk <- unique(key2(b$SymbolA, b$SymbolB))
    d <- pred[partner %in% nodes & anchor %in% nodes & y == 0L]
    d[, y := as.integer(key %in% bk)]
    if (sum(d$y) < 5) { bp_res <- rbind(bp_res, data.table(set = nm, n_pos = sum(d$y), status = "NOT EVALUABLE"), fill = TRUE); next }
    r <- summ(d, nm); bb <- boot(d)
    r[, `:=`(dAP_M2_M1 = AP_M2 - AP_M1, ci_lo_M2_M1 = ci(bb, "d21")[1], ci_hi_M2_M1 = ci(bb, "d21")[2],
             dAP_M1_M0 = AP_M1 - AP_M0, ci_lo_M1_M0 = ci(bb, "d10")[1], ci_hi_M1_M0 = ci(bb, "d10")[2],
             status = "enrichment_only: bait/prey assay eligibility not verifiable from the filtered network; absent edges are unlabeled, not negative")]
    bp_res <- rbind(bp_res, r, fill = TRUE)
  }
} else bp_res <- data.table(set = "BioPlex", status = "NOT EVALUABLE (input not provided)")
fwrite(res, file.path(out, "results_summary.tsv"), sep = "\t")
fwrite(bp_res, file.path(out, "bioplex_validation.tsv"), sep = "\t")

# full-candidate ranking (preflight fix 4): lift of the top-ranked pairs over prevalence, per model, pooled OOF
lift <- rbindlist(lapply(c(10L, 50L, 100L), function(k) rbindlist(lapply(names(MODELS), function(m) {
  o <- da[order(-da[[m]])]; data.table(model = m, top_k = k, precision = mean(o$y[1:k]), lift = mean(o$y[1:k]) / mean(da$y)) }))))
fwrite(lift, file.path(out, "full_candidate_topk.tsv"), sep = "\t")
# bZIP vs non-bZIP contribution (positives and per-anchor gain)
fam <- pa[, .(anchors = .N, positives = sum(n_pos), mean_dAP = mean(AP_M2 - AP_M1), improved = sum(AP_M2 > AP_M1)),
          by = .(family = fifelse(anchor %in% bzip, "bZIP", "non-bZIP"))]
fwrite(fam, file.path(out, "family_contribution.tsv"), sep = "\t")

# decision (plan v0.2 A8 + preflight review 1)
r <- res[set == "matched_primary"]
full <- res[set == "all_partners"]
# c3: BioPlex cannot support GO without assay eligibility (preflight P0-2) -> NOT EVALUABLE (NA)
crit <- c(c1 = r$dAP_M2_M1 >= 0.005 && r$rel_M2_M1 >= 0.15, c2 = r$ci_lo_M2_M1 > 0, c3 = NA,
          c4 = r$dAP_M2_M1 > r$null_p95, c5 = r$share_anchors_improved >= 0.7 && all(infl$dAP_M2_M1 > 0))
full_worse <- full$dAP_M2_M1 < 0 && full$ci_hi_M2_M1 < 0
decision <- if (length(PRIM) < 10) "INCONCLUSIVE (fewer than 10 evaluable anchors)" else
  if (isTRUE(all(crit)) && !full_worse) "GO" else
  if (r$dAP_M2_M1 > 0 && r$ci_lo_M2_M1 > 0) paste0("CONDITIONAL", if (is.na(crit[["c3"]])) " (BioPlex criterion NOT EVALUABLE)" else "",
                                                 if (full_worse) " (full-candidate ranking worse)" else "") else
  if (r$ci_hi_M2_M1 < 0.005) "NO-GO" else "INCONCLUSIVE"
write_json(list(anchors_candidates = length(cand), anchors_evaluable = length(AN), anchors_primary = length(PRIM),
                criteria = as.list(crit), full_candidate_worse = full_worse, decision = decision, n_perm = n_perm), file.path(out, "decision.json"),
           auto_unbox = TRUE, pretty = TRUE, digits = 6)
print(res); print(bp_res); print(crit); cat("DECISION:", decision, "\n")
writeLines(capture.output(sessionInfo()), file.path(out, "sessionInfo.txt"))
