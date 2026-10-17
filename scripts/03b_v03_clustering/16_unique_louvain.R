# Step 3b §17: Louvain (algorithm 1, seed 20261016) on the unique-motif alignment graph
# (connected representatives, s >= 0.65, weight s).
# usage: Rscript 16_unique_louvain.R <unique_dir> scan <part> <res,res,...>
#          -> unique/scan_<part>.tsv.gz (one column per resolution; rows = connected nodes)
#        Rscript 16_unique_louvain.R <unique_dir> stability <part> <res> <n_seeds> <n_sub>
#          -> unique/stability_<part>_r<res>.tsv.gz
# Memory: one partition per process (monomer ~41.5M edges).
suppressPackageStartupMessages({ library(Seurat); library(Matrix) })
args <- commandArgs(trailingOnly = TRUE)
ud <- args[1]; mode <- args[2]; part <- args[3]
SEED <- 20261016
nodes <- read.delim(file.path(ud, paste0("graph_nodes_", part, ".tsv")))
ids <- nodes$unique_id[!as.logical(nodes$isolated)]
e <- data.table::fread(file.path(ud, paste0("graph_edges_", part, ".tsv")))
n <- length(ids)
g <- as.Graph(sparseMatrix(i = c(e$i, e$j) + 1, j = c(e$j, e$i) + 1, x = c(e$s, e$s), dims = c(n, n),
                           dimnames = list(ids, ids)))
rm(e); invisible(gc())
louvain <- function(gr, res, seed) FindClusters(gr, resolution = res, algorithm = 1, random.seed = seed,
                                                verbose = FALSE)
if (mode == "scan") {
  res <- as.numeric(strsplit(args[4], ",")[[1]])
  out <- data.frame(unique_id = ids)
  for (r in res) {
    t0 <- Sys.time()
    out[[sprintf("r%s", r)]] <- as.character(louvain(g, r, SEED)[[1]])
    cat(part, r, length(unique(out[[ncol(out)]])), format(Sys.time() - t0), "\n")
    data.table::fwrite(out, file.path(ud, sprintf("scan_%s.tsv.gz", part)), sep = "\t")
  }
} else if (mode == "stability") {
  r <- as.numeric(args[4]); ns <- as.integer(args[5]); nb <- as.integer(args[6])
  out <- data.frame(unique_id = ids)
  for (s in seq_len(ns) - 1) out[[paste0("seed", SEED + s)]] <- as.character(louvain(g, r, SEED + s)[[1]])
  for (b in seq_len(nb)) {
    set.seed(SEED + 100 + b)
    keep <- sort(sample.int(n, ceiling(0.8 * n)))
    lab <- rep(NA_character_, n)
    lab[keep] <- as.character(louvain(as.Graph(g[keep, keep]), r, SEED)[[1]])
    out[[paste0("sub", b)]] <- lab
  }
  data.table::fwrite(out, file.path(ud, sprintf("stability_%s_r%s.tsv.gz", part, r)), sep = "\t")
}
