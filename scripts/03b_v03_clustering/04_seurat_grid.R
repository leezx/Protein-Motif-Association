# Step 3b §5.3-5.4: frozen v0.3 grid on the projected PCA scores (51 PCs).
# usage: Rscript 04_seurat_grid.R <pca_dir> <out_dir> grid <part> <rep A|B> <dims>
#          -> grid_<part>_<rep>_d<dims>.tsv.gz (k in {15,20,30} x 8 resolutions)
#        Rscript 04_seurat_grid.R <pca_dir> <out_dir> stability <part> <rep> <dims> <k> <res>
#          -> stability_<part>_<rep>_d<dims>_k<k>_r<res>.tsv.gz (10 seeds, 10 x 80 % subsamples)
# kNN/SNN over all nodes (Annoy), Louvain (algorithm 1), seed 20261016.
# Seurat via r4p3 + R_LIBS_USER=R_lib_4 on Argos.
suppressPackageStartupMessages({ library(Seurat); library(Matrix) })
args <- commandArgs(trailingOnly = TRUE)
pd <- args[1]; od <- args[2]; mode <- args[3]; part <- args[4]; rep <- args[5]; d <- as.integer(args[6])
SEED <- 20261016
KS <- c(15, 20, 30)
RES <- c(0.8, 1.2, 2.0, 3.0, 4.0, 6.0, 8.0, 12.0)
dir.create(od, showWarnings = FALSE, recursive = TRUE)

e <- data.table::fread(file.path(pd, paste0("pca_", part, ".tsv.gz")), data.table = FALSE)
emb <- as.matrix(e[, -1]); rownames(emb) <- e$node_id; rm(e)
stopifnot(ncol(emb) == 51)
emb <- emb[, if (rep == "A") 1:d else 2:(d + 1)]

cluster_once <- function(x, k, res, seed) {
  g <- FindNeighbors(x, k.param = k, compute.SNN = TRUE, nn.method = "annoy", verbose = FALSE)
  FindClusters(g$snn, resolution = res, algorithm = 1, random.seed = seed, verbose = FALSE)
}

if (mode == "grid") {
  out <- data.frame(node_id = rownames(emb))
  for (k in KS) {
    t0 <- Sys.time()
    g <- FindNeighbors(emb, k.param = k, compute.SNN = TRUE, nn.method = "annoy", verbose = FALSE)
    cl <- FindClusters(g$snn, resolution = RES, algorithm = 1, random.seed = SEED, verbose = FALSE)
    for (j in seq_along(RES)) out[[sprintf("%s_d%d_k%d_r%s", rep, d, k, RES[j])]] <- as.character(cl[[j]])
    cat(part, rep, d, k, sapply(cl, function(x) length(unique(x))), format(Sys.time() - t0), "\n")
    rm(g); invisible(gc())
  }
  data.table::fwrite(out, file.path(od, sprintf("grid_%s_%s_d%d.tsv.gz", part, rep, d)), sep = "\t")
} else if (mode == "stability") {
  k <- as.integer(args[7]); res <- as.numeric(args[8])
  strata <- read.delim(file.path(od, paste0("strata_", part, ".tsv")))  # node_id, stratum
  strata <- strata$stratum[match(rownames(emb), strata$node_id)]
  stopifnot(!anyNA(strata))
  out <- data.frame(node_id = rownames(emb))
  for (s in 0:9) out[[paste0("seed", SEED + s)]] <- as.character(cluster_once(emb, k, res, SEED + s)[[1]])
  for (b in 1:10) {
    set.seed(SEED + 100 + b)
    keep <- unlist(lapply(split(seq_along(strata), strata),
                          function(ix) ix[sample.int(length(ix), ceiling(0.8 * length(ix)))]))
    lab <- rep(NA_character_, nrow(emb))
    lab[keep] <- as.character(cluster_once(emb[keep, ], k, res, SEED)[[1]])
    out[[paste0("sub", b)]] <- lab
  }
  data.table::fwrite(out, file.path(od, sprintf("stability_%s_%s_d%d_k%d_r%s.tsv.gz", part, rep, d, k, res)),
                     sep = "\t")
}
