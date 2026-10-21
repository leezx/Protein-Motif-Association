# PRINT (Hu et al. 2025, buenrostrolab/PRINT) bulk footprinting with the upstream functions, unmodified.
# Precomputed hg38 Tn5 bias + pretrained dispersion models; one pseudobulk ("all").
# usage: Rscript run_print.R <print_repo> <shared_dir> <regions.bed> <frags.tsv.gz> <outdir> <nCores> <radius,...>
# Output: <outdir>/print_r<radius>.bedgraph.gz  chrom, start, end, -log10 p (PRINT aggregateScores) per bp
#         <outdir>/print_timing.tsv, <outdir>/print_nan.tsv
suppressPackageStartupMessages({ library(GenomicRanges); library(data.table); library(hdf5r) })
a <- commandArgs(trailingOnly = TRUE)
repo <- normalizePath(a[1]); shared <- normalizePath(a[2]); bed <- a[3]; frags <- a[4]; out <- a[5]
nCores <- as.integer(a[6]); radii <- as.integer(strsplit(a[7], ",")[[1]])
for (f in c("utils.R", "getCounts.R", "getBias.R", "getFootprints.R")) source(file.path(repo, "code", f))
main <- file.path(normalizePath(out), "print_project/")
dir.create(file.path(main, "data/shared"), recursive = TRUE, showWarnings = FALSE)
file.symlink(file.path(shared, "precomputedTn5Bias"), file.path(main, "data/shared/precomputedTn5Bias"))
tic <- function() proc.time()[["elapsed"]]; timing <- list()

r <- fread(bed, header = FALSE)
regions <- GRanges(r$V1, IRanges(r$V2 + 1, r$V3))
project <- footprintingProject(projectName = "k562", refGenome = "hg38")
mainDir(project) <- main
dataDir(project) <- file.path(main, "data/")
regionRanges(project) <- regions

t0 <- tic()
project <- getPrecomputedBias(project, nCores = nCores)
timing$bias <- tic() - t0; t0 <- tic()
barcodeGroups <- data.frame(barcode = "K562", group = "all")
project <- getCountTensor(project, frags, barcodeGroups, returnCombined = TRUE, chunkSize = 2000, nCores = nCores)
groups(project) <- "all"
groupCellType(project) <- "all"
timing$counts <- tic() - t0

nan <- list()
for (rad in radii) {
  t0 <- tic()
  dispModel(project, as.character(rad)) <- readRDS(sprintf("%s/dispModel/dispersionModel%dbp.rds", shared, rad))
  project <- getFootprints(project, mode = as.character(rad), footprintRadius = rad, flankRadius = rad, nCores = nCores)
  timing[[paste0("footprint_r", rad)]] <- tic() - t0
  fp <- footprints(project, as.character(rad))
  tracks <- rbindlist(lapply(seq_along(fp), function(i) {
    s <- fp[[i]]$aggregateScores
    if (is.null(s)) return(NULL)
    p0 <- start(regions)[i] - 1L
    data.table(chrom = as.character(seqnames(regions)[i]), start = p0 + seq_along(s) - 1L,
               end = p0 + seq_along(s), score = s)
  }))
  nan[[as.character(rad)]] <- data.table(radius = rad, regions = length(fp),
    regions_with_scores = sum(!vapply(fp, function(x) is.null(x$aggregateScores), logical(1))),
    bp = nrow(tracks), nonfinite_bp = sum(!is.finite(tracks$score)))
  fwrite(tracks, file.path(out, sprintf("print_r%d.bedgraph.gz", rad)), sep = "\t", col.names = FALSE)
}
fwrite(rbindlist(nan), file.path(out, "print_nan.tsv"), sep = "\t")
fwrite(data.table(stage = names(timing), seconds = unlist(timing)), file.path(out, "print_timing.tsv"), sep = "\t")
cat("done\n")
