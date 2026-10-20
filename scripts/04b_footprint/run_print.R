# Step 4b-1: PRINT (Hu et al. 2025) native R implementation, CPU (mclapply/doParallel), precomputed hg38 Tn5 bias.
# usage: Rscript run_print.R <print_repo> <shared_dir> <regions.bed> <frags.tsv.gz> <out_prefix> <nCores> <radius,...>
#   shared_dir holds precomputedTn5Bias/hg38Tn5Bias.h5 and dispModel/dispersionModel<k>bp.rds (Zenodo 7121026)
# Output: <out_prefix>.r<radius>.track.tsv.gz  chrom, pos (0-based), score = PRINT -log10(p) smoothed track
#         <out_prefix>.timing.tsv              stage, seconds
suppressPackageStartupMessages({ library(GenomicRanges); library(data.table) })
a <- commandArgs(trailingOnly = TRUE)
repo <- normalizePath(a[1]); shared <- normalizePath(a[2]); bed <- a[3]; frags <- a[4]; out <- a[5]
nCores <- as.integer(a[6]); radii <- as.integer(strsplit(a[7], ",")[[1]])
main <- paste0(dirname(out), "/print_main_", basename(out), "/")
dir.create(paste0(main, "data/shared"), recursive = TRUE, showWarnings = FALSE)
if (!file.exists(paste0(main, "code"))) file.symlink(paste0(repo, "/code"), paste0(main, "code"))
if (!file.exists(paste0(main, "data/shared/precomputedTn5Bias")))
  file.symlink(paste0(shared, "/precomputedTn5Bias"), paste0(main, "data/shared/precomputedTn5Bias"))
for (f in c("utils.R", "getCounts.R", "getBias.R", "getFootprints.R")) source(paste0(repo, "/code/", f))
timing <- list(); tic <- function() proc.time()[["elapsed"]]
t0 <- tic()
r <- fread(bed, header = FALSE)
regions <- GRanges(r$V1, IRanges(r$V2 + 1, r$V3))
project <- footprintingProject(projectName = basename(out), refGenome = "hg38")
mainDir(project) <- main
dataDir(project) <- paste0(main, "data/"); dir.create(dataDir(project), showWarnings = FALSE)
regionRanges(project) <- regions
project <- getPrecomputedBias(project, nCores = nCores)
timing$bias <- tic() - t0; t0 <- tic()
bc <- fread(cmd = paste("zcat", frags, "| head -1"), header = FALSE)$V4[1]
barcodeGroups <- data.frame(barcode = bc, group = "all")
barcodeGrouping(project) <- barcodeGroups
groups(project) <- "all"
groupCellType(project) <- "all"
project <- getCountTensor(project, frags, barcodeGroups, returnCombined = TRUE, nCores = nCores)
timing$counts <- tic() - t0
for (rad in radii) {
  t0 <- tic()
  dispModel(project, as.character(rad)) <- readRDS(sprintf("%s/dispModel/dispersionModel%dbp.rds", shared, rad))
  project <- getFootprints(project, mode = as.character(rad), footprintRadius = rad, flankRadius = rad,
                           nCores = nCores)
  fp <- footprints(project, as.character(rad))
  tr <- rbindlist(lapply(seq_along(fp), function(i) {
    x <- fp[[i]]
    if (is.null(x$aggregateScores)) return(NULL)
    rg <- regions[i]
    data.table(chrom = as.character(seqnames(rg)), pos = start(rg) - 1 + seq_along(x$aggregateScores) - 1,
               score = x$aggregateScores)
  }))
  track_path <- sprintf("%s.r%d.track.tsv.gz", out, rad)
  if (is.null(tr)) tr <- data.table(chrom = character(), pos = integer(), score = numeric())
  fwrite(tr, track_path, sep = "\t")
  ev <- rbindlist(lapply(seq_along(fp), function(i) {  # PRINT's own footprint calls (findSummits on the track)
    x <- fp[[i]]
    if (is.null(x$footprintRanges) || length(x$footprintRanges) == 0) return(NULL)
    rg <- regions[i]
    data.table(chrom = as.character(seqnames(rg)), start = start(rg) - 1 + start(x$footprintRanges) - 1,
               end = start(rg) - 1 + end(x$footprintRanges), score = x$aggregateScores[x$summits])
  }))
  event_path <- sprintf("%s.r%d.native_events.bed", out, rad)
  if (is.null(ev)) {
    if (!file.create(event_path)) stop("could not create empty native event file")
  } else {
    fwrite(ev, event_path, sep = "\t", col.names = FALSE)
  }
  timing[[paste0("footprint_r", rad)]] <- tic() - t0
}
fwrite(data.table(stage = names(timing), seconds = unlist(timing)), paste0(out, ".timing.tsv"), sep = "\t")
cat("done\n")
