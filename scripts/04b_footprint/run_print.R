# Step 4b-1: PRINT (Hu et al. 2025) native R implementation, CPU (mclapply/doParallel), precomputed hg38 Tn5 bias.
# usage: Rscript run_print.R <print_repo> <shared_dir> <regions.bed> <frags.tsv.gz> <out_prefix> <nCores> <radius,...>
# Set PRINT_DIRECT_COMPARE=1 only for the reviewed 8-region streaming equivalence run.
#   shared_dir holds precomputedTn5Bias/hg38Tn5Bias.h5 and dispModel/dispersionModel<k>bp.rds (Zenodo 7121026)
# Output: <out_prefix>.r<radius>.track.tsv.gz  chrom, pos (0-based), score = PRINT -log10(p) smoothed track
#         <out_prefix>.timing.tsv              stage, seconds
suppressPackageStartupMessages({ library(GenomicRanges); library(data.table) })
# Preserve each warning at the point it is raised so the supervised run can be triaged.
options(warn = 1)
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
# Keep the exact sourced scorer for the grouped legacy oracle. The streamed
# worker uses a wrapper that only repairs base::sapply()'s singleton dimension
# drop (position x 1 group); the oracle must never inherit that wrapper.
native_regionFootprintScoring <- regionFootprintScoring
regionFootprintScoring <- make_bulk_safe_region_scorer(native_regionFootprintScoring)
timing <- list(); tic <- function() proc.time()[["elapsed"]]
caller_started <- tic()
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
direct_compare <- identical(Sys.getenv("PRINT_DIRECT_COMPARE"), "1")
if (direct_compare &&
    (length(regions) != 8L || nCores != 16L || !identical(sort(radii), c(10L, 20L)) ||
     !has_reviewed_direct_compare_group_sizes(width_groups) ||
     length(unique(chromosomes)) < 2L || length(unique(widths)) < 3L ||
     !any(vapply(width_groups, function(g) length(g$index) > 1L && any(diff(g$index) != 1L), logical(1))))) {
  stop("direct comparison mode requires the reviewed 8-region, 16-worker, shuffled 3/2/2/1 smoke")
}
timing$input_and_grouping <- tic() - t0; t0 <- tic()

bias_path <- file.path(shared, "precomputedTn5Bias", "hg38Tn5Bias.h5")
bias_groups <- NULL
if (direct_compare) {
  # Retain the current grouped caller on the fixed 8 rows as the equivalence oracle.
  bias_dir <- file.path(main, "bias_groups")
  if (dir.exists(bias_dir) && length(list.files(bias_dir, all.files = TRUE, no.. = TRUE)) > 0L)
    stop("bias scratch directory is not empty; refusing to reuse cached groups")
  dir.create(bias_dir, recursive = TRUE, showWarnings = FALSE)
  h5file <- hdf5r::H5File$new(filename = bias_path, mode = "r")
  available_chromosomes <- names(h5file)
  if (!all(unique(chromosomes) %in% available_chromosomes)) stop("input BED chromosome missing from bias HDF5")
  bias_groups <- vector("list", length(width_groups))
  names(bias_groups) <- sprintf("group_%06d", seq_along(width_groups))
  for (g in seq_along(width_groups)) {
    item <- width_groups[[g]]
    chr_handle <- h5file[[item$chromosome]]
    vectors <- lapply(item$index, function(i) {
      read_bias_slice(chr_handle, start(regions)[i], end(regions)[i])
    })
    matrix <- build_bias_matrix(vectors, seq_along(vectors), item$width,
                                global_index = item$index)
    group_path <- file.path(bias_dir, paste0(names(bias_groups)[g], ".rds"))
    saveRDS(matrix, group_path, version = 2)
    bias_groups[[g]] <- list(index = item$index, width = item$width,
                             chromosome = item$chromosome, bias_path = group_path)
  }
  h5file$close_all()
  rm(h5file)
  if (any(vapply(bias_groups, is.null, logical(1)))) stop("one or more bias groups were not materialized")
  timing$bias <- tic() - t0
} else {
  # Production mode reads bias only for the current bounded scoring chunk.
  timing$bias <- 0
}
t0 <- tic()

project <- footprintingProject(projectName = basename(out), refGenome = "hg38")
mainDir(project) <- main
dataDir(project) <- paste0(main, "data/"); dir.create(dataDir(project), showWarnings = FALSE)
regionRanges(project) <- regions
bc <- fread(cmd = paste("zcat", frags, "| head -1"), header = FALSE)$V4[1]
barcodeGroups <- data.frame(barcode = bc, group = "all")
barcodeGrouping(project) <- barcodeGroups
groups(project) <- "all"
groupCellType(project) <- "all"
count_tensor_dir <- file.path(dataDir(project), "chunkedCountTensor")
if (dir.exists(count_tensor_dir) && length(list.files(count_tensor_dir, all.files = TRUE, no.. = TRUE)) > 0L)
  stop("count-tensor scratch directory is not empty; refusing cached counts")
project <- getCountTensor(project, frags, barcodeGroups,
                          chunkSize = 2000L,
                          returnCombined = direct_compare, nCores = nCores)
timing$counts <- tic() - t0
# The fixed PRINT scorer requires a global `project` binding for some fields.
# Group calls overwrite that binding, so freeze the full count source and shared
# labels before the first group is bound; never derive a later group's rows
# from `.GlobalEnv$project`.
full_count_tensor <- if (direct_compare) countTensor(project) else NULL
full_group_labels <- groups(project)
full_cell_type_labels <- groupCellType(project)
if (!direct_compare && length(countTensor(project)) != 0L) {
  stop("production PRINT must keep the native count tensor disk-backed")
}

# Keep the legacy grouped getFootprints() path only for the fixed 8-row oracle.
# Production uses one persistent scoring cluster, native disk-backed count chunks,
# bounded original-order region batches, and atomic per-chunk output parts.
t0 <- tic()
model_started <- tic()
dispersion_models <- lapply(radii, function(rad) readRDS(sprintf("%s/dispModel/dispersionModel%dbp.rds", shared, rad)))
names(dispersion_models) <- as.character(radii)
timing$model_load <- tic() - model_started
if (direct_compare) {
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
    groups(project_group) <- full_group_labels
    groupCellType(project_group) <- full_cell_type_labels
    countTensor(project_group) <- validate_count_group(full_count_tensor, idx, widths)
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
      project_group <- with_print_region_scorer(
        native_regionFootprintScoring,
        getFootprints(project_group, mode = as.character(rad),
                      footprintRadius = rad, flankRadius = rad, nCores = nCores),
        envir = environment(getFootprints))
      footprint_seconds[[as.character(rad)]] <- footprint_seconds[[as.character(rad)]] + tic() - footprint_started
      group_footprints[[as.character(rad)]][[g]] <- footprints(project_group, as.character(rad))
      bind_active_print_project(project_group)
    }
  }
  footprints_by_radius <- lapply(group_footprints, function(result_groups) {
    restore_group_results(length(regions), group_indices, result_groups)
  })
  timing$legacy_oracle_wall <- tic() - t0
  for (rad in radii) timing[[paste0("legacy_oracle_r", rad)]] <- footprint_seconds[[as.character(rad)]]
} else {
  footprints_by_radius <- NULL
}

direct_reference <- NULL
if (direct_compare) {
  direct_started <- tic()
  direct_reference <- lapply(radii, function(rad) vector("list", length(regions)))
  names(direct_reference) <- as.character(radii)
  direct_rows <- list()
  direct_h5 <- hdf5r::H5File$new(filename = bias_path, mode = "r")
  for (g in seq_along(bias_groups)) {
    item <- bias_groups[[g]]
    idx <- item$index
    group_count <- full_count_tensor[idx]
    names(group_count) <- as.character(seq_along(idx))
    group_ids <- gtools::mixedsort(full_group_labels)
    group_bias <- readRDS(item$bias_path)
    for (j in seq_along(idx)) {
      global_row <- idx[[j]]
      direct_bias <- read_bias_slice(direct_h5[[as.character(seqnames(regions)[global_row])]],
                                     start(regions)[global_row], end(regions)[global_row])
      if (!identical(direct_bias, as.numeric(group_bias[j, ]))) {
        stop("independent HDF5 bias slice differs from grouped bias row for region ", global_row)
      }
      region_atac <- direct_region_atac(group_count, j, group_ids, item$width)
      for (rad in radii) {
        expected <- regionFootprintScoring(
          regionATAC = region_atac,
          Tn5Bias = direct_bias,
          dispersionModel = dispersion_models[[as.character(rad)]],
          footprintRadius = rad, flankRadius = rad,
          regionID = as.character(regions[idx[[j]]]),
          scoreType = "pval", cellTypeLabels = full_cell_type_labels,
          returnCellTypeScores = FALSE)
        actual <- group_footprints[[as.character(rad)]][[g]][[j]]
        assert_print_region_equal(actual, expected,
                                  sprintf("direct comparison region %d radius %d", idx[[j]], rad))
        direct_reference[[as.character(rad)]][[idx[[j]]]] <- expected
        direct_rows[[length(direct_rows) + 1L]] <- data.table(
          radius = rad, global_row = global_row, group_id = g, bias_exact_match = TRUE,
          width = item$width, compared_fields = paste(names(expected), collapse = ","),
          event_count = if (is.null(expected$footprintRanges)) 0L else length(expected$footprintRanges))
      }
    }
  }
  direct_h5$close_all()
  fwrite(rbindlist(direct_rows), paste0(out, ".direct-comparison.tsv"), sep = "\t")
  timing$direct_compare <- tic() - direct_started
}

validate_direct_exports <- function(track_path, event_path, radius, expected_by_region) {
  expected_tracks <- rbindlist(lapply(seq_along(expected_by_region), function(i) {
    x <- expected_by_region[[i]]; rg <- regions[i]
    data.table(chrom = as.character(seqnames(rg)),
               pos = track_positions0(start(rg) - 1L, length(x$aggregateScores)),
               score = x$aggregateScores)
  }))
  observed_tracks <- fread(track_path)
  if (!identical(names(observed_tracks), c("chrom", "pos", "score")) ||
      nrow(observed_tracks) != nrow(expected_tracks) ||
      !identical(as.character(observed_tracks$chrom), as.character(expected_tracks$chrom)) ||
      !identical(as.integer(observed_tracks$pos), as.integer(expected_tracks$pos))) {
    stop("re-read PRINT track coordinates differ from direct per-region reference at radius ", radius)
  }
  assert_numeric_close(observed_tracks$score, expected_tracks$score,
                       paste("re-read track scores radius", radius))
  expected_events <- rbindlist(lapply(seq_along(expected_by_region), function(i) {
    x <- expected_by_region[[i]]; rg <- regions[i]
    if (is.null(x$footprintRanges) || length(x$footprintRanges) == 0L) return(NULL)
    coords <- lapply(seq_along(x$footprintRanges), function(j) {
      event_interval0(start(rg) - 1L, IRanges::start(x$footprintRanges)[j],
                      IRanges::end(x$footprintRanges)[j])
    })
    data.table(chrom = as.character(seqnames(rg)),
               start = vapply(coords, `[[`, integer(1), 1L),
               end = vapply(coords, `[[`, integer(1), 2L),
               score = x$aggregateScores[x$summits])
  }))
  if (is.null(expected_events)) {
    expected_events <- data.table(chrom = character(), start = integer(), end = integer(), score = numeric())
  }
  observed_events <- if (file.info(event_path)$size == 0L) {
    data.table(chrom = character(), start = integer(), end = integer(), score = numeric())
  } else fread(event_path, header = FALSE,
               col.names = c("chrom", "start", "end", "score"))
  if (nrow(observed_events) != nrow(expected_events) ||
      !identical(as.character(observed_events$chrom), as.character(expected_events$chrom)) ||
      !identical(as.integer(observed_events$start), as.integer(expected_events$start)) ||
      !identical(as.integer(observed_events$end), as.integer(expected_events$end))) {
    stop("re-read PRINT event coordinates differ from direct per-region reference at radius ", radius)
  }
  assert_numeric_close(observed_events$score, expected_events$score,
                       paste("re-read event scores radius", radius))
  invisible(c(track_rows = nrow(observed_tracks), event_rows = nrow(observed_events)))
}

stream_result <- run_streamed_print_scoring(
  regions = regions, widths = widths, radii = radii,
  dispersion_models = dispersion_models,
  cell_type_labels = full_cell_type_labels,
  count_tensor = full_count_tensor,
  count_chunk_dir = file.path(dataDir(project), "chunkedCountTensor"),
  native_chunk_size = 2000L,
  h5_path = bias_path, out = out, n_cores = nCores,
  direct_compare = direct_compare,
  direct_expected = direct_reference,
  max_chunk_peaks = 500L,
  max_chunk_bases = 1000000L,
  direct_chunk_peaks = 3L
)
timing$bias <- timing$bias + stream_result$bias_seconds
timing$score_dispatch_r10_r20 <- stream_result$score_dispatch_seconds
for (rad in radii) {
  timing[[paste0("output_materialization_r", rad)]] <-
    stream_result$output_materialization_by_radius[[as.character(rad)]]
}
t0 <- tic()
publish_streamed_print_outputs(stream_result, out, radii)
timing$output_publish <- tic() - t0
if (direct_compare) {
  t0 <- tic()
  for (rad in radii) {
    track_path <- sprintf("%s.r%d.track.tsv.gz", out, rad)
    event_path <- sprintf("%s.r%d.native_events.bed", out, rad)
    validate_direct_exports(track_path, event_path, rad,
                            direct_reference[[as.character(rad)]])
  }
  timing$direct_export_validation <- tic() - t0
}
timing[[if (direct_compare) {
  "pipeline_wall_through_validation_including_legacy_oracle"
} else {
  "pipeline_wall_through_validation"
}]] <- tic() - caller_started
fwrite(data.table(stage = names(timing), seconds = unlist(timing)), paste0(out, ".timing.tsv"), sep = "\t")
cat("done\n")
