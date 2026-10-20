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
