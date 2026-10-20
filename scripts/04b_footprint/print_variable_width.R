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
