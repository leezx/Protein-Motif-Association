# Step 3b §15: Louvain (algorithm 1, seed 20261016) on the alignment-weighted graph.
# usage: Rscript 11_align_louvain.R <align_dir> <pca_dir> <K> scan <part>
#          -> align_scan_<part>.tsv.gz (one column per resolution)
#        Rscript 11_align_louvain.R <align_dir> <pca_dir> <K> stability <part> <res> <strata.tsv>
#          -> align_stability_<part>_r<res>.tsv.gz (10 seeds; 10 x 80 % stratified induced subgraphs)
suppressPackageStartupMessages({ library(Seurat); library(Matrix) })
args <- commandArgs(trailingOnly = TRUE)
ad <- args[1]; pd <- args[2]; K <- args[3]; mode <- args[4]; part <- args[5]
SEED <- 20261016
RES <- c(0.1, 0.2, 0.4, 0.8, 1.2, 2, 3, 4, 6, 8, 12, 16, 24, 32, 48, 64, 96, 128)

ids <- read.delim(file.path(pd, paste0("nodes_", part, ".tsv")))$node_id
e <- data.table::fread(file.path(ad, sprintf("edges_%s_k%s.tsv.gz", part, K)), data.table = FALSE)
n <- length(ids)
m <- sparseMatrix(i = c(e$i, e$j) + 1, j = c(e$j, e$i) + 1, x = c(e$s, e$s), dims = c(n, n),
                  dimnames = list(ids, ids))
g <- as.Graph(m)

if (mode == "scan") {
  cl <- FindClusters(g, resolution = RES, algorithm = 1, random.seed = SEED, verbose = FALSE)
  out <- data.frame(node_id = ids)
  for (j in seq_along(RES)) out[[sprintf("align_r%s", RES[j])]] <- as.character(cl[[j]])
  cat(part, sapply(cl, function(x) length(unique(x))), "\n")
  data.table::fwrite(out, file.path(ad, sprintf("align_scan_%s.tsv.gz", part)), sep = "\t")
} else if (mode == "stability") {
  res <- as.numeric(args[6])
  strata <- read.delim(args[7])
  strata <- strata$stratum[match(ids, strata$node_id)]
  stopifnot(!anyNA(strata))
  out <- data.frame(node_id = ids)
  for (s in 0:9) out[[paste0("seed", SEED + s)]] <-
    as.character(FindClusters(g, resolution = res, algorithm = 1, random.seed = SEED + s, verbose = FALSE)[[1]])
  for (b in 1:10) {
    set.seed(SEED + 100 + b)
    keep <- sort(unlist(lapply(split(seq_along(strata), strata),
                               function(ix) ix[sample.int(length(ix), ceiling(0.8 * length(ix)))])))
    lab <- rep(NA_character_, n)
    lab[keep] <- as.character(FindClusters(as.Graph(m[keep, keep]), resolution = res, algorithm = 1,
                                           random.seed = SEED, verbose = FALSE)[[1]])
    out[[paste0("sub", b)]] <- lab
  }
  data.table::fwrite(out, file.path(ad, sprintf("align_stability_%s_r%s.tsv.gz", part, res)), sep = "\t")
}
