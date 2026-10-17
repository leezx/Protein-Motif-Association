# Step 3b §14: three-tier reference on the fixed graph (A, PCs 1:30, k 20).
# usage: Rscript 08_tiers.R <pca_dir> <tier_dir> scan
#          -> tiers_scan_<part>.tsv.gz : Louvain at the frozen grid resolutions + 16..64,
#             all from ONE graph per partition (so tiers share an identical graph)
#        Rscript 08_tiers.R <pca_dir> <tier_dir> degree
#          -> snn_degree_<tier>.tsv.gz : weighted intra-cluster SNN degree per node
#             for every final_tier_<tier>.tsv.gz in <tier_dir>
# Seurat via r4p3 + R_LIBS_USER=R_lib_4.
suppressPackageStartupMessages({ library(Seurat); library(Matrix) })
args <- commandArgs(trailingOnly = TRUE)
pd <- args[1]; td <- args[2]; mode <- args[3]
SEED <- 20261016; D <- 30; K <- 20
SCAN <- c(0.8, 1.2, 2.0, 3.0, 4.0, 6.0, 8.0, 12.0, 16, 24, 32, 48, 64)
dir.create(td, showWarnings = FALSE, recursive = TRUE)

graph_of <- function(part) {
  e <- data.table::fread(file.path(pd, paste0("pca_", part, ".tsv.gz")), data.table = FALSE)
  emb <- as.matrix(e[, 2:(D + 1)]); rownames(emb) <- e$node_id
  FindNeighbors(emb, k.param = K, compute.SNN = TRUE, nn.method = "annoy", verbose = FALSE)$snn
}

if (mode == "scan") {
  for (part in c("composite", "monomer")) {
    g <- graph_of(part)
    cl <- FindClusters(g, resolution = SCAN, algorithm = 1, random.seed = SEED, verbose = FALSE)
    out <- data.frame(node_id = rownames(g))
    for (j in seq_along(SCAN)) out[[sprintf("A_d%d_k%d_r%s", D, K, SCAN[j])]] <- as.character(cl[[j]])
    cat(part, sapply(cl, function(x) length(unique(x))), "\n")
    data.table::fwrite(out, file.path(td, sprintf("tiers_scan_%s.tsv.gz", part)), sep = "\t")
  }
} else if (mode == "degree") {
  g <- list(composite = graph_of("composite"), monomer = graph_of("monomer"))
  for (f in list.files(td, pattern = "^final_tier_.*\\.tsv\\.gz$", full.names = TRUE)) {
    a <- data.table::fread(f, data.table = FALSE)
    res <- list()
    for (part in names(g)) {
      s <- g[[part]]
      lab <- a$cluster[match(rownames(s), a$node_id)]
      tr <- summary(s)
      same <- lab[tr$i] == lab[tr$j] & tr$i != tr$j
      deg <- tapply(tr$x[same], factor(tr$i[same], levels = seq_len(nrow(s))), sum)
      deg[is.na(deg)] <- 0
      res[[part]] <- data.frame(node_id = rownames(s), snn_degree = as.numeric(deg))
    }
    out <- sub("final_tier_", "snn_degree_", f)
    data.table::fwrite(do.call(rbind, res), out, sep = "\t")
    cat(basename(f), "\n")
  }
}
