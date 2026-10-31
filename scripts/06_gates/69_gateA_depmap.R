# Gate A exploratory functional support (plan v0.2 A3.3): DepMap Chronos co-dependency of anchor-partner pairs.
# Does not enter the Gate A decision. Local; reads only the gene columns of the 808-protein universe.
# usage: Rscript 69_gateA_depmap.R <CRISPRGeneEffect.csv> <Model.csv> <61 out dir> <out dir>
# Residual correlation: gene effects (cell lines with >= 100 non-missing values per pair) after regressing out the
# top 5 principal components of the full matrix (overall dependency structure) and OncotreeLineage; Pearson and
# Spearman; BH FDR. Exploratory high co-dependency: |residual r| >= 0.30 and FDR < 0.05, split by sign.
# Pairs already in Complex Portal are excluded; AP of the out-of-fold M0/M1/M2 scores for these labels per sign.
suppressPackageStartupMessages(library(data.table))
a <- commandArgs(trailingOnly = TRUE)
ge <- fread(a[1]); setnames(ge, 1, "ModelID")
mod <- fread(a[2], select = c("ModelID", "OncotreeLineage"))
pred <- fread(file.path(a[3], "oof_predictions.tsv.gz"))
out <- a[4]; dir.create(out, showWarnings = FALSE, recursive = TRUE)
sym <- sub(" \\(.*\\)$", "", names(ge)[-1])
X <- as.matrix(ge[, -1]); colnames(X) <- sym; rownames(X) <- ge$ModelID
# overall dependency structure: top 5 PCs of the column-centred, mean-imputed full matrix
Xi <- apply(X, 2, function(v) { v[is.na(v)] <- mean(v, na.rm = TRUE); v - mean(v) })
Xi <- Xi[, colSums(is.na(Xi)) == 0 & apply(Xi, 2, sd) > 0]
pc <- prcomp(Xi, rank. = 5)$x
lin <- factor(mod$OncotreeLineage[match(rownames(X), mod$ModelID)])
genes <- unique(c(pred$anchor, pred$partner)); genes <- genes[genes %in% sym]
R <- sapply(genes, function(g) { v <- X[, g]; ok <- !is.na(v); r <- rep(NA_real_, length(v))
  r[ok] <- resid(lm(v[ok] ~ pc[ok, ] + lin[ok])); r })
d <- pred[y == 0L & anchor %in% genes & partner %in% genes]
d <- d[!duplicated(key)]
cc <- d[, {
  x <- R[, anchor]; z <- R[, partner]; ok <- !is.na(x) & !is.na(z); n <- sum(ok)
  if (n >= 100) { ct <- cor.test(x[ok], z[ok]); .(n = n, r = unname(ct$estimate), p = ct$p.value,
                   rho = cor(x[ok], z[ok], method = "spearman")) } else .(n = n, r = NA_real_, p = NA_real_, rho = NA_real_)
}, by = .(anchor, partner, key)]
cc[, fdr := p.adjust(p, "BH")]
d <- merge(d, cc[, .(key, n, r, rho, fdr)], by = "key")
d <- d[!is.na(r)]
d[, `:=`(pos = as.integer(r >= 0.3 & fdr < 0.05), neg = as.integer(r <= -0.3 & fdr < 0.05))]
ap <- function(s, y) { if (!any(y == 1)) return(NA_real_); o <- order(-s); y <- y[o]; mean(cumsum(y)[y == 1] / which(y == 1)) }
res <- rbindlist(lapply(c("pos", "neg"), function(l) data.table(label = l, n = nrow(d), n_label = sum(d[[l]]),
  prevalence = mean(d[[l]]), AP_M0 = ap(d$M0, d[[l]]), AP_M1 = ap(d$M1, d[[l]]), AP_M2 = ap(d$M2, d[[l]]),
  spearman_M2_r = cor(d$M2, d$r, method = "spearman"), spearman_M1_r = cor(d$M1, d$r, method = "spearman"))))
fwrite(d[, .(anchor, partner, n, r, rho, fdr, M0, M1, M2, pos, neg)], file.path(out, "depmap_codependency_pairs.tsv.gz"), sep = "\t")
fwrite(res, file.path(out, "depmap_codependency_summary.tsv"), sep = "\t")
print(res)
