# Helpers for processing the pinned PRINT implementation on variable-width
# regions without padding or changing the caller's genomic intervals.

group_peak_indices <- function(chromosomes, widths) {
  if (length(chromosomes) != length(widths) || length(widths) == 0L ||
      anyNA(chromosomes) || anyNA(widths) || any(widths <= 0L)) {
    stop("invalid chromosome/width vectors")
  }
  key <- paste(chromosomes, widths, sep = "\r")
  parts <- split(seq_along(widths), factor(key, levels = unique(key)))
  lapply(parts, function(index) {
    list(chromosome = chromosomes[index[[1L]]],
         width = as.integer(widths[index[[1L]]]),
         index = as.integer(index))
  })
}

has_reviewed_direct_compare_group_sizes <- function(width_groups) {
  group_sizes <- vapply(width_groups, function(g) length(g$index), integer(1))
  identical(sort(unname(group_sizes)), c(1L, 2L, 2L, 3L))
}

bind_active_print_project <- function(project_object, envir = .GlobalEnv) {
  assign("project", project_object, envir = envir)
  invisible(project_object)
}

assert_active_print_project <- function(project_object, envir = .GlobalEnv) {
  if (!exists("project", envir = envir, inherits = FALSE) ||
      !identical(get("project", envir = envir, inherits = FALSE), project_object)) {
    stop("PRINT helper would resolve a different active project object")
  }
  invisible(TRUE)
}

print_group_scratch_dir <- function(main_dir, group_number) {
  if (length(group_number) != 1L || is.na(group_number) || group_number < 1L) {
    stop("invalid PRINT group number")
  }
  file.path(main_dir, "groups", sprintf("group_%06d", as.integer(group_number)), "data")
}

build_bias_matrix <- function(bias_vectors, index, expected_width, global_index = index) {
  if (length(index) == 0L || anyNA(index) || anyDuplicated(index) ||
      any(index < 1L) || any(index > length(bias_vectors))) {
    stop("invalid global region index")
  }
  if (length(global_index) != length(index) || anyNA(global_index) ||
      anyDuplicated(global_index) || any(global_index < 1L)) {
    stop("invalid global region identity map")
  }
  rows <- lapply(index, function(i) bias_vectors[[i]])
  row_widths <- lengths(rows)
  if (any(row_widths != expected_width) || any(!vapply(rows, is.numeric, logical(1)))) {
    stop("bias vectors do not satisfy the group's exact-width contract")
  }
  values <- unlist(rows, recursive = FALSE, use.names = FALSE)
  if (length(values) != length(index) * expected_width || any(!is.finite(values))) {
    stop("bias vectors contain missing, non-finite, or mis-sized values")
  }
  matrix(values, nrow = length(index), ncol = expected_width, byrow = TRUE,
         dimnames = list(as.character(global_index), NULL))
}

read_bias_slice <- function(chromosome_dataset, start1, end1) {
  if (length(start1) != 1L || length(end1) != 1L || anyNA(c(start1, end1)) ||
      start1 < 1L || end1 < start1) {
    stop("invalid 1-based HDF5 bias slice")
  }
  values <- as.numeric(chromosome_dataset[as.integer(start1):as.integer(end1)])
  if (length(values) != end1 - start1 + 1L || any(!is.finite(values))) {
    stop("HDF5 bias slice has incorrect length or non-finite values")
  }
  values
}

validate_count_group <- function(count_tensor, index, widths) {
  if (length(count_tensor) != length(widths) || length(index) == 0L ||
      anyNA(index) || any(index < 1L) || any(index > length(widths))) {
    stop("count tensor and original region index map are inconsistent")
  }
  selected <- count_tensor[index]
  if (length(selected) != length(index)) stop("count tensor subset changed length")
  for (j in seq_along(selected)) {
    counts <- selected[[j]]
    if (is.null(counts) || nrow(counts) == 0L) next
    required <- c("position", "group", "count")
    if (!all(required %in% names(counts))) stop("count tensor element lacks required columns")
    position <- counts[["position"]]
    if (anyNA(position) || any(position < 1L) || any(position > widths[index[[j]]])) {
      stop("count tensor position falls outside its original region")
    }
  }
  selected
}

restore_group_results <- function(n_regions, index_groups, result_groups) {
  if (length(index_groups) != length(result_groups) || n_regions < 1L) {
    stop("group result/map count mismatch")
  }
  output <- vector("list", n_regions)
  seen <- logical(n_regions)
  for (g in seq_along(index_groups)) {
    index <- index_groups[[g]]
    result <- result_groups[[g]]
    if (length(index) != length(result) || anyNA(index) || any(index < 1L) ||
        any(index > n_regions) || anyDuplicated(index) || any(seen[index])) {
      stop("group result indices are invalid or duplicated")
    }
    for (j in seq_along(index)) output[index[[j]]] <- list(result[[j]])
    seen[index] <- TRUE
  }
  if (!all(seen)) stop("group results do not cover every original region")
  output
}

track_positions0 <- function(bed_start0, score_length) {
  if (length(bed_start0) != 1L || is.na(bed_start0) || bed_start0 < 0L ||
      length(score_length) != 1L || is.na(score_length) || score_length < 0L) {
    stop("invalid track coordinate inputs")
  }
  as.integer(bed_start0) + seq_len(as.integer(score_length)) - 1L
}

event_interval0 <- function(bed_start0, local_start1, local_end1) {
  if (length(bed_start0) != 1L || length(local_start1) != 1L ||
      length(local_end1) != 1L ||
      anyNA(c(bed_start0, local_start1, local_end1)) ||
      bed_start0 < 0L || local_end1 < local_start1) {
    stop("invalid native event interval coordinates")
  }
  result <- c(start = as.integer(bed_start0) + as.integer(local_start1) - 1L,
              end = as.integer(bed_start0) + as.integer(local_end1))
  if (result[["start"]] < 0L || result[["end"]] <= result[["start"]]) {
    stop("native event maps outside valid BED coordinates")
  }
  result
}

assert_numeric_close <- function(actual, expected, label,
                                 atol = 1e-10, rtol = 1e-10) {
  if (!identical(dim(actual), dim(expected)) || length(actual) != length(expected)) {
    stop(label, ": dimensions or lengths differ")
  }
  actual <- as.numeric(actual)
  expected <- as.numeric(expected)
  if (!identical(is.na(actual), is.na(expected)) ||
      !identical(is.infinite(actual), is.infinite(expected)) ||
      !identical(sign(actual[is.infinite(actual)]), sign(expected[is.infinite(expected)]))) {
    stop(label, ": NA/Inf masks differ")
  }
  finite <- is.finite(actual) & is.finite(expected)
  allowed <- atol + rtol * abs(expected[finite])
  if (any(abs(actual[finite] - expected[finite]) > allowed)) {
    stop(label, ": numeric values exceed tolerance")
  }
  invisible(TRUE)
}

assert_print_region_equal <- function(actual, expected, label,
                                      atol = 1e-10, rtol = 1e-10) {
  exact_fields <- c("regionID", "summits")
  numeric_fields <- c("summitPvalscores", "aggregateATAC", "aggregateScores",
                      "bias", "summitCellTypeScores", "cellTypeScores")
  range_fields <- c("footprintRanges")
  fields <- unique(c(exact_fields, numeric_fields, range_fields))
  if (length(setdiff(names(expected), fields)) > 0L) {
    stop(label, ": unhandled result fields: ", paste(setdiff(names(expected), fields), collapse = ","))
  }
  if (!identical(names(actual), names(expected))) stop(label, ": result fields differ")
  for (field in intersect(exact_fields, names(expected))) {
    if (!identical(actual[[field]], expected[[field]])) {
      stop(label, ": exact field differs: ", field)
    }
  }
  for (field in intersect(numeric_fields, names(expected))) {
    if (is.null(actual[[field]]) || is.null(expected[[field]])) {
      if (!identical(actual[[field]], expected[[field]])) stop(label, ": null field differs: ", field)
    } else {
      assert_numeric_close(actual[[field]], expected[[field]], paste(label, field), atol, rtol)
    }
  }
  for (field in intersect(range_fields, names(expected))) {
    a <- actual[[field]]; e <- expected[[field]]
    if (is.null(a) || is.null(e)) {
      if (!identical(a, e)) stop(label, ": range null state differs")
      next
    }
    if (!identical(as.character(GenomicRanges::seqnames(a)),
                   as.character(GenomicRanges::seqnames(e))) ||
        !identical(as.integer(IRanges::start(a)), as.integer(IRanges::start(e))) ||
        !identical(as.integer(IRanges::end(a)), as.integer(IRanges::end(e))) ||
        !identical(names(a), names(e))) {
      stop(label, ": footprint range coordinates differ")
    }
    ma <- S4Vectors::mcols(a); me <- S4Vectors::mcols(e)
    if (!identical(names(ma), names(me)) || nrow(ma) != nrow(me)) {
      stop(label, ": footprint range metadata shape differs")
    }
    for (column in names(me)) {
      if (is.numeric(ma[[column]]) && is.numeric(me[[column]])) {
        assert_numeric_close(ma[[column]], me[[column]],
                             paste(label, "footprintRanges", column), atol, rtol)
      } else if (!identical(ma[[column]], me[[column]])) {
        stop(label, ": footprint range metadata differs: ", column)
      }
    }
  }
  invisible(TRUE)
}

direct_region_atac <- function(count_data, region_index, group_ids, width) {
  if (length(region_index) != 1L || region_index < 1L || region_index > length(count_data)) {
    stop("invalid direct-comparison region index")
  }
  per_group <- lapply(group_ids, function(group_id) {
    row <- count_data[[region_index]]
    if (is.null(row) || nrow(row) == 0L) return(numeric(width))
    keep <- row[["group"]] %in% group_id
    track <- numeric(width)
    if (any(keep)) track[row[["position"]][keep]] <- row[["count"]][keep]
    track
  })
  do.call(cbind, per_group)
}

# Build bounded, contiguous batches in original BED order. A single wide peak
# may exceed max_bases and is then emitted alone; coordinates are never changed.
make_bounded_region_chunks <- function(indices, widths, max_peaks = 500L,
                                       max_bases = 1000000L) {
  indices <- as.integer(indices)
  widths <- as.integer(widths)
  max_peaks <- as.integer(max_peaks)
  max_bases <- as.numeric(max_bases)
  if (!length(indices) || length(indices) != length(widths) ||
      anyNA(indices) || anyNA(widths) || any(indices < 1L) || any(widths < 1L) ||
      anyDuplicated(indices) || length(max_peaks) != 1L || is.na(max_peaks) ||
      max_peaks < 1L || length(max_bases) != 1L || is.na(max_bases) ||
      !is.finite(max_bases) || max_bases < 1) {
    stop("invalid bounded-region chunk inputs")
  }
  chunks <- list()
  first <- 1L
  running_bases <- 0
  for (i in seq_along(indices)) {
    would_exceed <- i > first &&
      ((i - first + 1L) > max_peaks || running_bases + widths[[i]] > max_bases)
    if (would_exceed) {
      chunks[[length(chunks) + 1L]] <- indices[first:(i - 1L)]
      first <- i
      running_bases <- 0
    }
    running_bases <- running_bases + widths[[i]]
  }
  chunks[[length(chunks) + 1L]] <- indices[first:length(indices)]
  chunks
}

assert_exact_chunk_cover <- function(chunks, expected_indices) {
  flattened <- unlist(chunks, use.names = FALSE)
  if (!identical(as.integer(flattened), as.integer(expected_indices))) {
    stop("scoring chunks do not exactly preserve original BED row order")
  }
  invisible(TRUE)
}

# PRINT's scorer uses sapply() for several position-by-group results. With one
# bulk pseudobulk, base::sapply() drops the singleton group dimension; later
# code indexes those results as matrices. Keep the native function body and
# formulas, changing only this dimension-dropping edge case.
make_bulk_safe_region_scorer <- function(native_scorer) {
  if (!is.function(native_scorer)) stop("native PRINT scorer must be a function")
  scorer_env <- new.env(parent = environment(native_scorer))
  scorer_env$sapply <- function(X, FUN, ..., simplify = TRUE, USE.NAMES = TRUE) {
    result <- base::sapply(X, FUN, ..., simplify = simplify, USE.NAMES = USE.NAMES)
    if (length(X) == 1L && is.atomic(result) && is.null(dim(result)) &&
        isTRUE(simplify)) {
      column_name <- if (!is.null(names(X))) names(X)[[1L]] else
        if (is.character(X)) as.character(X)[[1L]] else NULL
      result <- matrix(result, ncol = 1L,
                       dimnames = list(names(result), column_name))
    }
    result
  }
  patched <- native_scorer
  environment(patched) <- scorer_env
  patched
}

# Temporarily bind the pinned native scorer in the lexical environment used by
# PRINT's grouped caller. This keeps the equivalence oracle independent from
# the singleton-matrix compatibility wrapper used by streamed workers.
find_print_lexical_binding_owner <- function(symbol, envir) {
  if (length(symbol) != 1L || is.na(symbol) || !nzchar(symbol) ||
      !is.environment(envir)) {
    stop("PRINT lexical binding lookup requires a symbol and environment")
  }
  current <- envir
  repeat {
    if (exists(symbol, envir = current, inherits = FALSE)) return(current)
    if (identical(current, emptyenv())) break
    current <- parent.env(current)
  }
  stop("PRINT lexical binding not found: ", symbol)
}

assert_print_binding_replaceable <- function(symbol, envir) {
  if (!is.environment(envir) || !exists(symbol, envir = envir, inherits = FALSE)) {
    stop("PRINT override target is not a local binding: ", symbol)
  }
  if (environmentIsLocked(envir) || bindingIsLocked(symbol, envir) ||
      bindingIsActive(symbol, envir)) {
    stop("PRINT refuses to replace a locked or active binding: ", symbol)
  }
  invisible(TRUE)
}

# Resolve the concrete S4 getFootprints method and then follow its lexical
# get_footprints closure to the environment that owns the scorer binding. The
# generic's own environment is not necessarily part of that lookup path.
resolve_print_oracle_scorer_owner <- function(project, generic,
                                             expected_bulk_safe_scorer) {
  if (length(class(project)) < 1L || !methods::is(generic, "genericFunction") ||
      !is.function(expected_bulk_safe_scorer)) {
    stop("PRINT oracle resolution requires a project, S4 generic, and scorer")
  }
  signature_names <- methods::slot(generic, "signature")
  if (length(signature_names) < 1L) stop("PRINT S4 generic has no dispatch signature")
  signature <- rep("ANY", length(signature_names))
  names(signature) <- signature_names
  signature[[1L]] <- class(project)[[1L]]
  selected_method <- methods::selectMethod(generic, signature = signature,
                                            fdef = generic)
  method_environment <- environment(selected_method)
  helper_owner <- find_print_lexical_binding_owner("get_footprints",
                                                    method_environment)
  helper <- get("get_footprints", envir = helper_owner, inherits = FALSE)
  if (!is.function(helper)) stop("resolved PRINT get_footprints binding is not a function")
  scorer_owner <- find_print_lexical_binding_owner("regionFootprintScoring",
                                                    environment(helper))
  assert_print_binding_replaceable("regionFootprintScoring", scorer_owner)
  current_scorer <- get("regionFootprintScoring", envir = scorer_owner,
                        inherits = FALSE)
  if (!identical(current_scorer, expected_bulk_safe_scorer)) {
    stop("resolved PRINT scorer binding is not the expected bulk-safe wrapper")
  }
  scorer_owner
}

with_print_region_scorer <- function(scorer, expression, envir,
                                    expected_current) {
  symbol <- "regionFootprintScoring"
  if (!is.function(scorer) || !is.function(expected_current) ||
      !is.environment(envir)) {
    stop("PRINT scorer override requires functions and a binding-owner environment")
  }
  assert_print_binding_replaceable(symbol, envir)
  previous <- get(symbol, envir = envir, inherits = FALSE)
  if (!identical(previous, expected_current)) {
    stop("PRINT scorer binding changed after lexical-owner resolution")
  }
  assign(symbol, scorer, envir = envir)
  on.exit(assign(symbol, previous, envir = envir), add = TRUE)
  eval(substitute(expression), envir = parent.frame())
}

count_text_lines <- function(path) {
  result <- system2("wc", c("-l", shQuote(path)), stdout = TRUE, stderr = TRUE)
  status <- attr(result, "status")
  if (!is.null(status) && status != 0L) stop("could not count lines in ", path)
  as.numeric(strsplit(trimws(result[[1L]]), "[[:space:]]+")[[1L]][[1L]])
}

count_gzip_text_lines <- function(path) {
  command <- paste("gzip -dc --", shQuote(path), "| wc -l")
  result <- system2("sh", c("-c", shQuote(command)), stdout = TRUE, stderr = TRUE)
  status <- attr(result, "status")
  if (!is.null(status) && status != 0L) stop("could not count lines in gzip output ", path)
  as.numeric(strsplit(trimws(result[[1L]]), "[[:space:]]+")[[1L]][[1L]])
}

# Worker function for the persistent scoring cluster. It deliberately calls
# PRINT's pinned native regionFootprintScoring() once per region and scale.
# Keep scoreType='pval': get_footprints() uses that value explicitly.
score_print_region_job <- function(job) {
  region_count <- setNames(list(job$count), as.character(job$global_index))
  region_atac <- getRegionATAC(countData = region_count,
                               regionInd = as.character(job$global_index),
                               groupIDs = print_group_ids,
                               width = job$width)
  if (is.null(dim(region_atac)) || nrow(region_atac) != job$width ||
      ncol(region_atac) != length(print_group_ids)) {
    if (is.null(dim(region_atac)) && length(print_group_ids) == 1L &&
        length(region_atac) == job$width) {
      region_atac <- matrix(region_atac, ncol = 1L,
                            dimnames = list(names(region_atac), print_group_ids))
    } else {
      stop("PRINT regionATAC shape differs from native position-by-group contract at row ",
           job$global_index)
    }
  }
  result <- vector("list", length(print_radii))
  names(result) <- as.character(print_radii)
  for (radius in print_radii) {
    result[[as.character(radius)]] <- regionFootprintScoring(
      regionATAC = region_atac,
      Tn5Bias = job$bias,
      dispersionModel = print_dispersion_models[[as.character(radius)]],
      footprintRadius = radius,
      flankRadius = radius,
      regionID = job$region_id,
      scoreType = "pval",
      cellTypeLabels = print_cell_type_labels,
      returnCellTypeScores = FALSE
    )
  }
  result
}

print_chunk_tables <- function(results, indices, regions) {
  if (length(results) != length(indices)) stop("PRINT chunk result/row counts differ")
  tracks <- vector("list", length(results))
  events <- vector("list", length(results))
  event_counts <- integer(length(results))
  for (j in seq_along(results)) {
    x <- results[[j]]
    global_index <- indices[[j]]
    rg <- regions[global_index]
    if (is.null(x$aggregateScores) || length(x$aggregateScores) != width(rg) ||
        length(x$bias) != width(rg) || length(x$aggregateATAC) != width(rg)) {
      stop("PRINT region track, bias, or count length differs from original peak width at row ",
           global_index)
    }
    tracks[[j]] <- data.table(
      chrom = as.character(seqnames(rg)),
      pos = track_positions0(start(rg) - 1L, length(x$aggregateScores)),
      score = x$aggregateScores
    )
    if (is.null(x$footprintRanges) || length(x$footprintRanges) == 0L) {
      events[j] <- list(NULL)
      event_counts[[j]] <- 0L
    } else {
      if (length(x$footprintRanges) != length(x$summits)) {
        stop("PRINT native event and summit lengths differ at row ", global_index)
      }
      coordinates <- lapply(seq_along(x$footprintRanges), function(k) {
        event_interval0(start(rg) - 1L,
                        IRanges::start(x$footprintRanges)[[k]],
                        IRanges::end(x$footprintRanges)[[k]])
      })
      events[[j]] <- data.table(
        chrom = as.character(seqnames(rg)),
        start = vapply(coordinates, `[[`, integer(1), 1L),
        end = vapply(coordinates, `[[`, integer(1), 2L),
        score = x$aggregateScores[x$summits]
      )
      event_counts[[j]] <- nrow(events[[j]])
    }
  }
  list(track = rbindlist(tracks, use.names = TRUE),
       events = rbindlist(events, use.names = TRUE),
       region_event_counts = event_counts)
}

atomic_write_print_part <- function(table, path, columns, header = FALSE) {
  if (file.exists(path)) stop("refusing to overwrite PRINT part: ", path)
  partial <- paste0(path, ".partial")
  if (file.exists(partial)) stop("refusing to reuse PRINT partial: ", partial)
  if (is.null(table) || nrow(table) == 0L) {
    if (header) {
      con <- file(partial, open = "wt")
      writeLines(paste(columns, collapse = "\t"), con, sep = "\n")
      close(con)
    } else if (!file.create(partial)) {
      stop("could not create empty PRINT part: ", partial)
    }
  } else {
    fwrite(table[, ..columns], partial, sep = "\t", col.names = header)
  }
  if (!file.rename(partial, path)) stop("could not atomically commit PRINT part: ", path)
  invisible(path)
}

append_raw_file <- function(input_path, output_connection, buffer_bytes = 8L * 1024L * 1024L) {
  input_connection <- file(input_path, open = "rb")
  on.exit(close(input_connection), add = TRUE)
  repeat {
    block <- readBin(input_connection, what = "raw", n = buffer_bytes)
    if (!length(block)) break
    writeBin(block, output_connection)
  }
  invisible(TRUE)
}

sha256_file <- function(path) {
  result <- system2("sha256sum", path, stdout = TRUE, stderr = TRUE)
  status <- attr(result, "status")
  if (!is.null(status) && status != 0L) stop("sha256sum failed for ", path)
  digest <- strsplit(result[[1L]], "[[:space:]]+")[[1L]][[1L]]
  if (!grepl("^[0-9a-f]{64}$", digest)) stop("invalid SHA-256 result for ", path)
  digest
}

run_streamed_print_scoring <- function(regions, widths, radii, dispersion_models,
                                       cell_type_labels, count_tensor = NULL,
                                       count_chunk_dir = NULL, native_chunk_size = 2000L,
                                       h5_path, out, n_cores, direct_compare = FALSE,
                                       direct_expected = NULL, max_chunk_peaks = 500L,
                                       max_chunk_bases = 1000000L,
                                       direct_chunk_peaks = 3L) {
  if (n_cores < 1L || n_cores > 20L ||
      (direct_compare && (length(regions) != 8L || n_cores != 16L ||
                          !identical(sort(as.integer(radii)), c(10L, 20L)))) ||
      (!direct_compare && n_cores != 16L)) {
    stop("streamed PRINT requires 16 workers; direct validation is the reviewed 8-row, r10/r20 case")
  }
  if (direct_compare && (is.null(count_tensor) || is.null(direct_expected))) {
    stop("direct streamed comparison requires the native in-memory tensor and grouped oracle")
  }
  if (!direct_compare && (is.null(count_chunk_dir) || !dir.exists(count_chunk_dir))) {
    stop("production streamed scoring requires the native disk-backed count tensor")
  }
  parts_dir <- paste0(out, ".stream_parts")
  if (dir.exists(parts_dir) && length(list.files(parts_dir, all.files = TRUE, no.. = TRUE))) {
    stop("streamed PRINT part directory is not empty")
  }
  dir.create(parts_dir, recursive = TRUE, showWarnings = FALSE)
  manifest_rows <- list()
  region_manifest_rows <- list()
  comparison_rows <- list()
  output_materialization_by_radius <-
    setNames(as.list(rep(0, length(radii))), as.character(radii))
  score_dispatch_seconds <- 0
  indices_all <- seq_along(regions)
  chunks <- if (direct_compare) {
    make_bounded_region_chunks(indices_all, widths, max_peaks = direct_chunk_peaks,
                               max_bases = max_chunk_bases)
  } else {
    # Count chunks are native PRINT's 2,000-row on-disk partitions. Bound each
    # scoring dispatch again by both peak count and total interval width.
    native_ranges <- split(indices_all, ceiling(indices_all / native_chunk_size))
    unlist(lapply(native_ranges, function(ids) {
      make_bounded_region_chunks(ids, widths[ids], max_peaks = max_chunk_peaks,
                                 max_bases = max_chunk_bases)
    }), recursive = FALSE)
  }
  assert_exact_chunk_cover(chunks, indices_all)

  cl <- parallel::makeCluster(n_cores, type = "PSOCK", outfile = "")
  on.exit(try(parallel::stopCluster(cl), silent = TRUE), add = TRUE)
  parallel::clusterEvalQ(cl, {
    suppressPackageStartupMessages({
      library(GenomicRanges); library(IRanges); library(S4Vectors)
      library(dplyr); library(Matrix); library(caTools); library(survcomp)
    })
    options(warn = 1)
    TRUE
  })
  print_group_ids <- gtools::mixedsort(unique(as.character(cell_type_labels)))
  # The current bulk runner has a single pseudobulk and one cell-type label.
  # Fail closed if a later caller changes that contract without review.
  if (length(print_group_ids) != 1L || !identical(length(unique(cell_type_labels)), 1L)) {
    stop("streamed PRINT currently supports exactly one bulk pseudobulk")
  }
  # Export source functions from the runner's global environment, and bind the
  # small shared model/label objects once. Chunk data are sent one region-job
  # at a time by parLapplyLB; HDF5 handles never leave the parent process.
  assign("print_radii", as.integer(radii), envir = .GlobalEnv)
  assign("print_dispersion_models", dispersion_models, envir = .GlobalEnv)
  assign("print_cell_type_labels", as.character(cell_type_labels), envir = .GlobalEnv)
  assign("print_group_ids", print_group_ids, envir = .GlobalEnv)
  clusterExport(cl, c("getRegionATAC", "regionFootprintScoring", "footprintScoring",
                      "footprintWindowSum", "predictDispersion", "conv",
                      "findSummits", "mergeRegions", "score_print_region_job"),
                envir = .GlobalEnv)
  clusterExport(cl, c("print_group_ids", "print_radii", "print_dispersion_models",
                      "print_cell_type_labels"), envir = .GlobalEnv)
  bias_h5 <- hdf5r::H5File$new(filename = h5_path, mode = "r")
  on.exit(try(bias_h5$close_all(), silent = TRUE), add = TRUE)
  available_chromosomes <- names(bias_h5)
  chromosome_names <- as.character(seqnames(regions))
  if (!all(unique(chromosome_names) %in% available_chromosomes)) {
    stop("scoring regions contain a chromosome absent from the bias HDF5")
  }

  native_chunk_cache <- NULL
  native_chunk_cache_id <- NA_integer_
  bias_seconds <- 0
  for (chunk_id in seq_along(chunks)) {
    ids <- as.integer(chunks[[chunk_id]])
    count_rows <- if (direct_compare) {
      count_tensor[ids]
    } else {
      current_native_chunk <- ceiling(ids[[1L]] / native_chunk_size)
      if (any(ceiling(ids / native_chunk_size) != current_native_chunk)) {
        stop("scoring chunk crosses a native count-tensor chunk boundary")
      }
      if (is.na(native_chunk_cache_id) || native_chunk_cache_id != current_native_chunk) {
        native_chunk_cache <- readRDS(file.path(count_chunk_dir,
                                                paste0("chunk_", current_native_chunk, ".rds")))
        expected_length <- min(native_chunk_size,
                               length(regions) - (current_native_chunk - 1L) * native_chunk_size)
        if (length(native_chunk_cache) != expected_length) {
          stop("native count-tensor chunk row count differs from frozen BED")
        }
        native_chunk_cache_id <- current_native_chunk
      }
      local_ids <- ids - (current_native_chunk - 1L) * native_chunk_size
      native_chunk_cache[local_ids]
    }
    names(count_rows) <- as.character(ids)
    count_rows <- validate_count_group(count_rows, seq_along(ids), widths[ids])
    bias_started <- proc.time()[["elapsed"]]
    bias_vectors <- lapply(ids, function(i) {
      read_bias_slice(bias_h5[[chromosome_names[[i]]]], start(regions)[[i]], end(regions)[[i]])
    })
    bias_seconds <- bias_seconds + proc.time()[["elapsed"]] - bias_started
    jobs <- lapply(seq_along(ids), function(j) {
      list(global_index = ids[[j]], count = count_rows[[j]], bias = bias_vectors[[j]],
           width = widths[[ids[[j]]]], region_id = as.character(regions[ids[[j]]]))
    })
    dispatch_started <- proc.time()[["elapsed"]]
    results <- parallel::parLapplyLB(cl, jobs, score_print_region_job)
    score_dispatch_seconds <- score_dispatch_seconds +
      (proc.time()[["elapsed"]] - dispatch_started)
    result_by_radius <- lapply(as.character(radii), function(rad) {
      lapply(results, `[[`, rad)
    })
    names(result_by_radius) <- as.character(radii)

    chunk_record <- list(chunk_id = chunk_id, first_row = ids[[1L]], last_row = ids[[length(ids)]],
                         peak_count = length(ids), width_bases = sum(widths[ids]))
    region_event_counts_by_radius <- list()
    for (radius in radii) {
      rad <- as.character(radius)
      track_path <- file.path(parts_dir, sprintf("r%s.track.%06d.tsv", rad, chunk_id))
      event_path <- file.path(parts_dir, sprintf("r%s.events.%06d.bed", rad, chunk_id))
      stage_start <- proc.time()[["elapsed"]]
      tables <- print_chunk_tables(result_by_radius[[rad]], ids, regions)
      if (any(!is.finite(tables$track$score)) ||
          (!is.null(tables$events) && any(!is.finite(tables$events$score)))) {
        stop("non-finite PRINT output in scoring chunk ", chunk_id, " radius ", radius)
      }
      expected_positions <- unlist(lapply(ids, function(i) {
        track_positions0(start(regions)[[i]] - 1L, widths[[i]])
      }), use.names = FALSE)
      expected_chromosomes <- rep(chromosome_names[ids], widths[ids])
      if (nrow(tables$track) != sum(widths[ids]) ||
          !identical(as.character(tables$track$chrom), expected_chromosomes) ||
          !identical(as.integer(tables$track$pos), as.integer(expected_positions))) {
        stop("PRINT chunk track coordinates differ from original BED row order")
      }
      atomic_write_print_part(tables$track, track_path,
                              c("chrom", "pos", "score"))
      atomic_write_print_part(tables$events, event_path,
                              c("chrom", "start", "end", "score"))
      output_materialization_by_radius[[rad]] <- output_materialization_by_radius[[rad]] +
        (proc.time()[["elapsed"]] - stage_start)
      chunk_record[[paste0("r", rad, "_track_rows")]] <- nrow(tables$track)
      chunk_record[[paste0("r", rad, "_event_rows")]] <- if (is.null(tables$events)) 0L else nrow(tables$events)
      chunk_record[[paste0("r", rad, "_track_sha256")]] <- sha256_file(track_path)
      chunk_record[[paste0("r", rad, "_events_sha256")]] <- sha256_file(event_path)
      region_event_counts_by_radius[[rad]] <- tables$region_event_counts
      if (direct_compare) {
        for (j in seq_along(ids)) {
          assert_print_region_equal(result_by_radius[[rad]][[j]],
                                    direct_expected[[rad]][[ids[[j]]]],
                                    sprintf("streamed/native row %d radius %s", ids[[j]], rad))
          comparison_rows[[length(comparison_rows) + 1L]] <- data.table(
            global_row = ids[[j]], radius = as.integer(rad), fields_equal = TRUE)
        }
      }
    }
    region_manifest_chunk <- data.table(
      chunk_id = chunk_id,
      global_row = ids,
      chrom = as.character(seqnames(regions[ids])),
      start0 = as.integer(start(regions[ids]) - 1L),
      end0 = as.integer(end(regions[ids])),
      width = widths[ids],
      region_id = as.character(regions[ids])
    )
    for (radius in radii) {
      rad <- as.character(radius)
      region_manifest_chunk[[paste0("r", rad, "_track_rows")]] <- widths[ids]
      region_manifest_chunk[[paste0("r", rad, "_event_rows")]] <-
        region_event_counts_by_radius[[rad]]
      region_manifest_chunk[[paste0("r", rad, "_track_sha256")]] <-
        chunk_record[[paste0("r", rad, "_track_sha256")]]
      region_manifest_chunk[[paste0("r", rad, "_events_sha256")]] <-
        chunk_record[[paste0("r", rad, "_events_sha256")]]
    }
    chunk_map_path <- file.path(parts_dir, sprintf("chunk_manifest_%06d.tsv", chunk_id))
    atomic_write_print_part(region_manifest_chunk, chunk_map_path,
                            names(region_manifest_chunk), header = TRUE)
    region_manifest_rows[[chunk_id]] <- region_manifest_chunk
    manifest_rows[[chunk_id]] <- as.list(chunk_record)
    if ((chunk_id %% 10L) == 0L) gc()
  }
  manifest <- rbindlist(manifest_rows, fill = TRUE)
  fwrite(manifest, file.path(parts_dir, "chunk_manifest.tsv"), sep = "\t")
  fwrite(rbindlist(region_manifest_rows), file.path(parts_dir, "region_manifest.tsv"),
         sep = "\t")
  if (direct_compare) {
    fwrite(rbindlist(comparison_rows), paste0(out, ".stream-comparison.tsv"), sep = "\t")
  }
  expected_track_rows <- sum(widths)
  for (rad in radii) {
    if (sum(manifest[[paste0("r", rad, "_track_rows")]]) != expected_track_rows) {
      stop("streamed track rows do not equal the sum of original peak widths at radius ", rad)
    }
  }
  list(parts_dir = parts_dir, manifest = manifest,
       score_dispatch_seconds = score_dispatch_seconds,
       output_materialization_by_radius = output_materialization_by_radius,
       bias_seconds = bias_seconds,
       chunk_count = length(chunks), expected_track_rows = expected_track_rows)
}

publish_streamed_print_outputs <- function(stream_result, out, radii) {
  parts_dir <- stream_result$parts_dir
  manifest <- stream_result$manifest
  staged_paths <- character()
  final_paths <- character()
  for (radius in radii) {
    rad <- as.character(radius)
    track_path <- sprintf("%s.r%s.track.tsv.gz", out, rad)
    events_path <- sprintf("%s.r%s.native_events.bed", out, rad)
    if (file.exists(track_path) || file.exists(events_path)) {
      stop("refusing to overwrite a streamed PRINT final output")
    }
    plain_tmp <- paste0(track_path, ".partial")
    gzip_tmp <- paste0(track_path, ".partial.gz")
    events_tmp <- paste0(events_path, ".partial")
    if (any(file.exists(c(plain_tmp, gzip_tmp, events_tmp)))) {
      stop("refusing to reuse a partial streamed PRINT output")
    }
    con <- file(plain_tmp, open = "wb")
    writeBin(charToRaw("chrom\tpos\tscore\n"), con)
    for (chunk_id in seq_len(nrow(manifest))) {
      append_raw_file(file.path(parts_dir, sprintf("r%s.track.%06d.tsv", rad, chunk_id)), con)
    }
    close(con)
    gzip_status <- system2("gzip", c("-n", "-c", shQuote(plain_tmp)), stdout = gzip_tmp)
    if (!identical(as.integer(gzip_status), 0L) || !file.exists(gzip_tmp) ||
        file.info(gzip_tmp)$size <= 0) {
      stop("gzip failed to publish streamed PRINT radius ", rad)
    }
    event_con <- file(events_tmp, open = "wb")
    for (chunk_id in seq_len(nrow(manifest))) {
      append_raw_file(file.path(parts_dir, sprintf("r%s.events.%06d.bed", rad, chunk_id)), event_con)
    }
    close(event_con)
    gzip_check <- system2("gzip", c("-t", shQuote(gzip_tmp)))
    if (!identical(as.integer(gzip_check), 0L) ||
        count_gzip_text_lines(gzip_tmp) != stream_result$expected_track_rows + 1L ||
        count_text_lines(events_tmp) != sum(manifest[[paste0("r", rad, "_event_rows")]])) {
      stop("staged PRINT output failed row-count or gzip validation for radius ", rad)
    }
    track_part_paths <- file.path(parts_dir, sprintf("r%s.track.%06d.tsv", rad,
                                                       seq_len(nrow(manifest))))
    event_part_paths <- file.path(parts_dir, sprintf("r%s.events.%06d.bed", rad,
                                                       seq_len(nrow(manifest))))
    track_hashes <- vapply(track_part_paths, sha256_file, character(1))
    event_hashes <- vapply(event_part_paths, sha256_file, character(1))
    if (!identical(unname(track_hashes), manifest[[paste0("r", rad, "_track_sha256")]]) ||
        !identical(unname(event_hashes), manifest[[paste0("r", rad, "_events_sha256")]])) {
      stop("PRINT part hash changed before output publication at radius ", rad)
    }
    track_rows <- vapply(track_part_paths, count_text_lines, numeric(1))
    event_rows <- vapply(event_part_paths, count_text_lines, numeric(1))
    if (!identical(as.numeric(track_rows),
                   as.numeric(manifest[[paste0("r", rad, "_track_rows")]])) ||
        !identical(as.numeric(event_rows),
                   as.numeric(manifest[[paste0("r", rad, "_event_rows")]]))) {
      stop("PRINT part row count changed before publication at radius ", rad)
    }
    file.remove(plain_tmp)
    staged_paths <- c(staged_paths, gzip_tmp, events_tmp)
    final_paths <- c(final_paths, track_path, events_path)
  }
  if (any(file.exists(final_paths))) stop("PRINT final output appeared before atomic publication")
  for (i in seq_along(staged_paths)) {
    if (!file.rename(staged_paths[[i]], final_paths[[i]])) {
      stop("atomic rename failed while publishing PRINT outputs")
    }
  }
  completion_path <- paste0(out, ".complete.tsv")
  completion_tmp <- paste0(completion_path, ".partial")
  if (file.exists(completion_path) || file.exists(completion_tmp)) {
    stop("refusing to overwrite PRINT completion marker")
  }
  completion <- data.table(
    radius = as.integer(radii),
    track_path = sprintf("%s.r%s.track.tsv.gz", basename(out), radii),
    event_path = sprintf("%s.r%s.native_events.bed", basename(out), radii),
    track_sha256 = vapply(final_paths[seq(1L, length(final_paths), by = 2L)], sha256_file, character(1)),
    event_sha256 = vapply(final_paths[seq(2L, length(final_paths), by = 2L)], sha256_file, character(1)),
    track_rows = stream_result$expected_track_rows,
    event_rows = vapply(radii, function(rad) {
      sum(manifest[[paste0("r", rad, "_event_rows")]])
    }, numeric(1))
  )
  fwrite(completion, completion_tmp, sep = "\t")
  if (!file.rename(completion_tmp, completion_path)) {
    stop("could not atomically commit PRINT completion marker")
  }
  invisible(TRUE)
}
