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
script_arg <- sub("^--file=", "", grep("^--file=", commandArgs(FALSE), value = TRUE)[1])
source(file.path(dirname(normalizePath(script_arg)), "print_variable_width.R"))
timing <- list(); tic <- function() proc.time()[["elapsed"]]
t0 <- tic()
r <- fread(bed, header = FALSE)
if (ncol(r) < 3L || anyNA(r$V1) || anyNA(r$V2) || anyNA(r$V3) || any(r$V2 < 0) || any(r$V3 <= r$V2))
  stop("input BED has invalid intervals")
regions <- GRanges(r$V1, IRanges(r$V2 + 1, r$V3))
widths <- as.integer(width(regions))
chromosomes <- as.character(seqnames(regions))
width_groups <- group_peak_indices(chromosomes, widths)
if (sum(vapply(width_groups, function(g) length(g$index), integer(1))) != length(regions))
  stop("width grouping does not cover every input region")
timing$input_and_grouping <- tic() - t0; t0 <- tic()

# PRINT's native S4 slot is a rectangular matrix, while the frozen input peaks
# have variable widths. Read one chromosome of precomputed bias at a time,
# construct exact-width matrices without padding, and persist each group in a
# unique scratch directory. The upstream get_footprints() helper also resolves
# `project` from .GlobalEnv; the active group is explicitly bound there before
# setting regionBias or calling getFootprints().
bias_dir <- file.path(main, "bias_groups")
if (dir.exists(bias_dir) && length(list.files(bias_dir, all.files = TRUE, no.. = TRUE)) > 0L)
  stop("bias scratch directory is not empty; refusing to reuse cached groups")
dir.create(bias_dir, recursive = TRUE, showWarnings = FALSE)
bias_path <- file.path(shared, "precomputedTn5Bias", "hg38Tn5Bias.h5")
h5file <- hdf5r::H5File$new(filename = bias_path, mode = "r")
available_chromosomes <- names(h5file)
if (!all(unique(chromosomes) %in% available_chromosomes)) stop("input BED chromosome missing from bias HDF5")
bias_groups <- vector("list", length(width_groups))
names(bias_groups) <- sprintf("group_%06d", seq_along(width_groups))
for (chr in unique(chromosomes)) {
  chr_handle <- h5file[[chr]]
  chr_bias <- chr_handle[1:chr_handle$dims]
  for (g in seq_along(width_groups)) {
    item <- width_groups[[g]]
    if (!identical(item$chromosome, chr)) next
    vectors <- lapply(item$index, function(i) chr_bias[start(regions)[i]:end(regions)[i]])
    matrix <- build_bias_matrix(vectors, seq_along(vectors), item$width,
                                global_index = item$index)
    group_path <- file.path(bias_dir, paste0(names(bias_groups)[g], ".rds"))
    saveRDS(matrix, group_path, version = 2)
    bias_groups[[g]] <- list(index = item$index, width = item$width,
                             chromosome = item$chromosome, bias_path = group_path)
  }
  rm(chr_bias, chr_handle)
  gc()
}
h5file$close_all()
rm(h5file)
if (any(vapply(bias_groups, is.null, logical(1)))) stop("one or more bias groups were not materialized")
timing$bias <- tic() - t0; t0 <- tic()

project <- footprintingProject(projectName = basename(out), refGenome = "hg38")
mainDir(project) <- main
dataDir(project) <- paste0(main, "data/"); dir.create(dataDir(project), showWarnings = FALSE)
regionRanges(project) <- regions
bc <- fread(cmd = paste("zcat", frags, "| head -1"), header = FALSE)$V4[1]
barcodeGroups <- data.frame(barcode = bc, group = "all")
barcodeGrouping(project) <- barcodeGroups
groups(project) <- "all"
groupCellType(project) <- "all"
project <- getCountTensor(project, frags, barcodeGroups, returnCombined = TRUE, nCores = nCores)
timing$counts <- tic() - t0

# Footprint each exact-width group using the unchanged native per-region caller.
# The global index map, not region coordinates, restores duplicates and original
# order. Every group receives its own empty scratch directory so chunk_1.rds
# cannot be mistaken for another group's result.
t0 <- tic()
model_started <- tic()
dispersion_models <- lapply(radii, function(rad) readRDS(sprintf("%s/dispModel/dispersionModel%dbp.rds", shared, rad)))
names(dispersion_models) <- as.character(radii)
timing$model_load <- tic() - model_started
group_indices <- lapply(bias_groups, `[[`, "index")
group_footprints <- lapply(radii, function(x) vector("list", length(bias_groups)))
names(group_footprints) <- as.character(radii)
footprint_seconds <- setNames(as.list(rep(0, length(radii))), as.character(radii))
for (g in seq_along(bias_groups)) {
  item <- bias_groups[[g]]
  idx <- item$index
  project_group <- footprintingProject(projectName = paste0(basename(out), "_", names(bias_groups)[g]),
                                       refGenome = "hg38", mainDir = main,
                                       dataDir = paste0(main, "groups/"))
  group_data_dir <- print_group_scratch_dir(main, g)
  if (dir.exists(group_data_dir) && length(list.files(group_data_dir, all.files = TRUE, no.. = TRUE)) > 0L)
    stop("PRINT group scratch directory is not empty; refusing cached output")
  dir.create(group_data_dir, recursive = TRUE, showWarnings = FALSE)
  dataDir(project_group) <- paste0(group_data_dir, "/")
  mainDir(project_group) <- main
  regionRanges(project_group) <- regions[idx]
  groups(project_group) <- groups(project)
  groupCellType(project_group) <- groupCellType(project)
  countTensor(project_group) <- validate_count_group(countTensor(project), idx, widths)
  bind_active_print_project(project_group)
  assert_active_print_project(project_group)
  regionBias(project_group) <- readRDS(item$bias_path)
  bind_active_print_project(project_group)
  assert_active_print_project(project_group)
  if (nrow(regionBias(project_group)) != length(idx) || ncol(regionBias(project_group)) != item$width)
    stop("group bias matrix dimensions disagree with regions")
  for (rad in radii) {
    dispModel(project_group, as.character(rad)) <- dispersion_models[[as.character(rad)]]
    bind_active_print_project(project_group)
    assert_active_print_project(project_group)
    footprint_started <- tic()
    project_group <- getFootprints(project_group, mode = as.character(rad),
                                   footprintRadius = rad, flankRadius = rad,
                                   nCores = nCores)
    footprint_seconds[[as.character(rad)]] <- footprint_seconds[[as.character(rad)]] + tic() - footprint_started
    group_footprints[[as.character(rad)]][[g]] <- footprints(project_group, as.character(rad))
    bind_active_print_project(project_group)
  }
}
footprints_by_radius <- lapply(group_footprints, function(result_groups) {
  restore_group_results(length(regions), group_indices, result_groups)
})
timing$footprint_groups <- tic() - t0
for (rad in radii) timing[[paste0("footprint_r", rad)]] <- footprint_seconds[[as.character(rad)]]

for (rad in radii) {
  t0 <- tic()
  fp <- footprints_by_radius[[as.character(rad)]]
  tr <- rbindlist(lapply(seq_along(fp), function(i) {
    x <- fp[[i]]
    if (is.null(x$aggregateScores)) return(NULL)
    rg <- regions[i]
    if (length(x$aggregateScores) != width(rg) || length(x$bias) != width(rg) ||
        length(x$aggregateATAC) != width(rg))
      stop("PRINT region track, bias, or count length differs from original peak width")
    data.table(chrom = as.character(seqnames(rg)), pos = track_positions0(start(rg) - 1L, length(x$aggregateScores)),
               score = x$aggregateScores)
  }))
  track_path <- sprintf("%s.r%d.track.tsv.gz", out, rad)
  if (is.null(tr)) tr <- data.table(chrom = character(), pos = integer(), score = numeric())
  fwrite(tr, track_path, sep = "\t")
  ev <- rbindlist(lapply(seq_along(fp), function(i) {  # PRINT's own footprint calls (findSummits on the track)
    x <- fp[[i]]
    if (is.null(x$footprintRanges) || length(x$footprintRanges) == 0) return(NULL)
    rg <- regions[i]
    if (length(x$footprintRanges) != length(x$summits) ||
        length(x$aggregateScores) != width(rg))
      stop("PRINT native event and summit/score lengths are inconsistent")
    event_coordinates <- lapply(seq_along(x$footprintRanges), function(j) {
      event_interval0(start(rg) - 1L, start(x$footprintRanges)[j], end(x$footprintRanges)[j])
    })
    data.table(chrom = as.character(seqnames(rg)),
               start = vapply(event_coordinates, `[[`, integer(1), 1L),
               end = vapply(event_coordinates, `[[`, integer(1), 2L),
               score = x$aggregateScores[x$summits])
  }))
  event_path <- sprintf("%s.r%d.native_events.bed", out, rad)
  if (is.null(ev)) {
    if (!file.create(event_path)) stop("could not create empty native event file")
  } else {
    fwrite(ev, event_path, sep = "\t", col.names = FALSE)
  }
  timing[[paste0("write_r", rad)]] <- tic() - t0
}
fwrite(data.table(stage = names(timing), seconds = unlist(timing)), paste0(out, ".timing.tsv"), sep = "\t")
cat("done\n")
