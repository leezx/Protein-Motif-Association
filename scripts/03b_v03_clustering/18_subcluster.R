# Step 3b §17 (implementation note): nested tiers by subclustering.
# LOW = Louvain at a base resolution on the unique-motif graph (scan_<part>.tsv.gz).
# MEDIUM / HIGH: every LOW cluster is re-clustered on its own induced subgraph
# (Louvain algorithm 1, seed 20261016) at a common sub-resolution; labels "<base>.<sub>".
# Reason: on the dense 41.5M-edge graph, whole-graph Louvain gains clusters very
# slowly with resolution (425 -> 472 for res 0.2 -> 2) and res 4 took > 60 min.
# usage: Rscript 18_subcluster.R <unique_dir> <part> <base_col> <subres,subres,...>
#          -> unique/subscan_<part>.tsv.gz (unique_id, base, sub_r<r>...)
suppressPackageStartupMessages({ library(Seurat); library(Matrix) })
args <- commandArgs(trailingOnly = TRUE)
ud <- args[1]; part <- args[2]; base_col <- args[3]; subres <- as.numeric(strsplit(args[4], ",")[[1]])
SEED <- 20261016
nodes <- read.delim(file.path(ud, paste0("graph_nodes_", part, ".tsv")))
ids <- nodes$unique_id[!as.logical(nodes$isolated)]
e <- data.table::fread(file.path(ud, paste0("graph_edges_", part, ".tsv")))
n <- length(ids)
m <- sparseMatrix(i = c(e$i, e$j) + 1, j = c(e$j, e$i) + 1, x = c(e$s, e$s), dims = c(n, n), dimnames = list(ids, ids))
rm(e); invisible(gc())
sc <- data.table::fread(file.path(ud, paste0("scan_", part, ".tsv.gz")), data.table = FALSE)
base <- as.character(sc[[base_col]][match(ids, sc$unique_id)])
stopifnot(!anyNA(base))
out <- data.frame(unique_id = ids, base = base)
for (r in subres) out[[sprintf("sub_r%s", r)]] <- NA_character_
groups <- split(seq_len(n), base)
t0 <- Sys.time()
for (b in names(groups)) {
  ix <- groups[[b]]
  if (length(ix) < 3) {
    for (r in subres) out[[sprintf("sub_r%s", r)]][ix] <- paste0(b, ".0")
    next
  }
  cl <- FindClusters(as.Graph(m[ix, ix]), resolution = subres, algorithm = 1, random.seed = SEED, verbose = FALSE)
  for (j in seq_along(subres)) out[[sprintf("sub_r%s", subres[j])]][ix] <- paste0(b, ".", as.character(cl[[j]]))
}
cat(part, base_col, "subres:", subres, "\nK:", sapply(subres, function(r) length(unique(out[[sprintf("sub_r%s", r)]]))),
    format(Sys.time() - t0), "\n")
data.table::fwrite(out, file.path(ud, sprintf("subscan_%s.tsv.gz", part)), sep = "\t")
