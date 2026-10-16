# Step 3 §8.2: Seurat clustering + UMAP of 8-mer affinity profiles, run per
# partition (monomer, composite) on Argos.
# usage: Rscript 07_seurat_cluster.R <kmer_dir> <out_dir>
# kmer_dir holds features.f32 (nodes x 32,896 float32, row-major),
# nodes.tsv and kmers.txt from 06_kmer_features.py.
options(Seurat.object.assay.version = "v3")
suppressPackageStartupMessages({
  library(Seurat)
  library(Matrix)
  library(ggplot2)
})
args <- commandArgs(trailingOnly = TRUE)
kdir <- args[1]; out <- args[2]
dir.create(out, showWarnings = FALSE, recursive = TRUE)
SEED <- 20261016
RES <- c(0.4, 0.6, 0.8, 1.0, 1.5, 2.0)
PRIMARY_RES <- 0.8

nodes <- read.delim(file.path(kdir, "nodes.tsv"), stringsAsFactors = FALSE)
kmers <- readLines(file.path(kdir, "kmers.txt"))
nk <- length(kmers); nn <- nrow(nodes)
con <- file(file.path(kdir, "features.f32"), "rb")
x <- readBin(con, "numeric", n = as.double(nk) * nn, size = 4, endian = "little")
close(con)
stopifnot(length(x) == as.double(nk) * nn)
M <- matrix(x, nrow = nk, ncol = nn, dimnames = list(kmers, nodes$node_id))
rm(x); invisible(gc())

run_partition <- function(part) {
  keep <- nodes$partition == part
  m <- M[, keep, drop = FALSE]
  meta <- nodes[keep, ]
  rownames(meta) <- meta$node_id
  assay <- CreateAssayObject(data = m)
  obj <- CreateSeuratObject(assay, assay = "kmer", meta.data = meta)
  rm(m); invisible(gc())
  VariableFeatures(obj) <- kmers
  # §8.1: centred, not scaled per 8-mer
  obj <- ScaleData(obj, features = kmers, do.scale = FALSE, do.center = TRUE, verbose = FALSE)
  obj <- RunPCA(obj, features = kmers, npcs = 50, seed.use = SEED, verbose = FALSE)
  for (d in list(1:20, 1:50)) {  # dims sensitivity at the primary resolution
    tag <- paste0("dims1_", max(d))
    obj <- FindNeighbors(obj, dims = d, k.param = 20, graph.name = paste0(c("nn_", "snn_"), tag), verbose = FALSE)
    obj <- FindClusters(obj, graph.name = paste0("snn_", tag), resolution = PRIMARY_RES, algorithm = 1,
                        random.seed = SEED, verbose = FALSE)
    obj[[paste0("clust_", tag, "_res0.8")]] <- obj$seurat_clusters
  }
  obj <- FindNeighbors(obj, dims = 1:30, k.param = 20, verbose = FALSE)
  obj <- FindClusters(obj, resolution = RES, algorithm = 1, random.seed = SEED, verbose = FALSE)
  obj <- RunUMAP(obj, dims = 1:30, n.neighbors = 30, min.dist = 0.3, seed.use = SEED, verbose = FALSE)
  md <- obj@meta.data
  res_cols <- grep("^kmer_snn_res\\.", colnames(md), value = TRUE)
  um <- Embeddings(obj, "umap"); pcs <- Embeddings(obj, "pca")
  tab <- data.frame(node_id = rownames(md), partition = part,
                    cluster = as.character(md[[paste0("kmer_snn_res.", PRIMARY_RES)]]),
                    md[, c(res_cols, grep("^clust_dims", colnames(md), value = TRUE))],
                    UMAP_1 = um[, 1], UMAP_2 = um[, 2], pcs[, 1:10], check.names = FALSE)
  write.table(tab, file.path(out, paste0("seurat_", part, ".tsv")), sep = "\t", quote = FALSE, row.names = FALSE)
  write.table(data.frame(pc = 1:50, stdev = Stdev(obj, "pca")), file.path(out, paste0("pca_stdev_", part, ".tsv")),
              sep = "\t", quote = FALSE, row.names = FALSE)
  # length / GC / IC vs PCs (F29 diagnostics)
  diag <- sapply(c("length", "gc", "ic"), function(v) cor(pcs[, 1:10], md[[v]], method = "spearman"))
  write.table(data.frame(pc = paste0("PC_", 1:10), round(diag, 4)), file.path(out, paste0("pc_bias_", part, ".tsv")),
              sep = "\t", quote = FALSE, row.names = FALSE)
  saveRDS(obj, file.path(out, paste0("seurat_", part, ".rds")))
  p <- DimPlot(obj, reduction = "umap", group.by = paste0("kmer_snn_res.", PRIMARY_RES), raster = TRUE,
               label = TRUE, label.size = 2, repel = FALSE) + NoLegend() +
    ggtitle(sprintf("PMA motifs (%s): %d nodes, %d clusters (res 0.8)", part, ncol(obj),
                    length(unique(obj$seurat_clusters))))
  ggsave(file.path(out, paste0("umap_clusters_", part, ".png")), p, width = 9, height = 8, dpi = 200)
  for (v in c("length", "ic", "gc")) {
    p <- FeaturePlot(obj, v, raster = TRUE) + ggtitle(paste(part, v))
    ggsave(file.path(out, paste0("umap_", v, "_", part, ".png")), p, width = 7, height = 6, dpi = 150)
  }
  cat(part, ncol(obj), "nodes;", sapply(res_cols, function(r) length(unique(md[[r]]))), "\n")
}
for (part in c("composite", "monomer")) run_partition(part)
writeLines(capture.output(sessionInfo()), file.path(out, "session_info.txt"))
