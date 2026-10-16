# Step 3 §9.2: frozen clustering grid on the saved PCA embeddings.
# usage: Rscript 12_seurat_grid.R <seurat_dir> [mode]
#   mode = grid (default): 90 configs x representation A (PCs 1:d) and B
#          (PCs 2:(d+1)), both partitions, seed 20261016 -> grid_labels_<part>.tsv.gz
#   mode = stability <part> <rep> <dims> <k> <res>: 10 seeds and 10 x 80 %
#          subsamples (stratified by source x GC quintile) -> stability_*.tsv
# Seurat via r4p3 + R_LIBS_USER=R_lib_4 on Argos.
options(Seurat.object.assay.version = "v3")
suppressPackageStartupMessages({ library(Seurat); library(Matrix) })
args <- commandArgs(trailingOnly = TRUE)
sd <- args[1]; mode <- if (length(args) > 1) args[2] else "grid"
SEED <- 20261016
DIMS <- c(20, 30, 50); KS <- c(15, 20, 30)
RES <- c(0.8, 1.2, 1.6, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0, 8.0)

emb_of <- function(part) {
  f <- file.path(sd, paste0("pca_", part, ".tsv.gz"))
  if (!file.exists(f)) {
    obj <- readRDS(file.path(sd, paste0("seurat_", part, ".rds")))
    e <- Embeddings(obj, "pca")
    write.table(data.frame(node_id = rownames(e), e, check.names = FALSE), gzfile(f), sep = "\t",
                quote = FALSE, row.names = FALSE)
    rm(obj); invisible(gc())
  }
  e <- read.delim(f, check.names = FALSE)
  m <- as.matrix(e[, -1]); rownames(m) <- e$node_id
  m
}

cluster_once <- function(emb, k, res, seed) {
  g <- FindNeighbors(emb, k.param = k, compute.SNN = TRUE, verbose = FALSE)
  FindClusters(g$snn, resolution = res, algorithm = 1, random.seed = seed, verbose = FALSE)
}

if (mode == "grid") {
  for (part in c("composite", "monomer")) {
    emb <- emb_of(part)
    out <- data.frame(node_id = rownames(emb))
    for (rep in c("A", "B")) for (d in DIMS) for (k in KS) {
      cols <- if (rep == "A") 1:d else 2:min(d + 1, ncol(emb))  # only 50 PCs exist: B at d=50 uses 2:50
      g <- FindNeighbors(emb[, cols], k.param = k, compute.SNN = TRUE, verbose = FALSE)
      cl <- FindClusters(g$snn, resolution = RES, algorithm = 1, random.seed = SEED, verbose = FALSE)
      for (j in seq_along(RES)) out[[sprintf("%s_d%d_k%d_r%s", rep, d, k, RES[j])]] <- as.character(cl[[j]])
      cat(part, rep, d, k, sapply(cl, function(x) length(unique(x))), "\n")
    }
    write.table(out, gzfile(file.path(sd, paste0("grid_labels_", part, ".tsv.gz"))), sep = "\t",
                quote = FALSE, row.names = FALSE)
  }
} else if (mode == "stability") {
  part <- args[3]; rep <- args[4]; d <- as.integer(args[5]); k <- as.integer(args[6]); res <- as.numeric(args[7])
  emb <- emb_of(part)
  emb <- emb[, if (rep == "A") 1:d else 2:min(d + 1, ncol(emb))]
  strata <- read.delim(file.path(sd, paste0("strata_", part, ".tsv")))  # node_id, stratum
  strata <- strata$stratum[match(rownames(emb), strata$node_id)]
  out <- data.frame(node_id = rownames(emb))
  for (s in 0:9) out[[paste0("seed", SEED + s)]] <- as.character(cluster_once(emb, k, res, SEED + s)[[1]])
  for (b in 1:10) {
    set.seed(SEED + 100 + b)
    keep <- unlist(lapply(split(seq_along(strata), strata), function(ix) ix[sample.int(length(ix), ceiling(0.8 * length(ix)))]))
    lab <- rep(NA_character_, nrow(emb))
    lab[keep] <- as.character(cluster_once(emb[keep, ], k, res, SEED)[[1]])
    out[[paste0("sub", b)]] <- lab
  }
  tag <- sprintf("%s_%s_d%d_k%d_r%s", part, rep, d, k, res)
  write.table(out, gzfile(file.path(sd, paste0("stability_", tag, ".tsv.gz"))), sep = "\t", quote = FALSE,
              row.names = FALSE)
}
