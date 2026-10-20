source(file.path("scripts", "04b_footprint", "print_variable_width.R"))

for (n in c(1L, 99L, 100L, 101L, 128L)) {
  groups <- group_peak_indices(rep("chr1", n), rep(37L, n))
  stopifnot(length(groups) == 1L, length(groups[[1L]]$index) == n)
  vectors <- lapply(seq_len(n), function(i) as.numeric(i * 1000L + seq_len(37L)))
  bias <- build_bias_matrix(vectors, seq_len(n), 37L, global_index = seq_len(n))
  stopifnot(identical(dim(bias), c(n, 37L)),
            identical(unname(bias[1L, ]), vectors[[1L]]),
            identical(unname(bias[n, ]), vectors[[n]]))
}

# Mixed widths, repeated width groups, interleaved chromosomes, and repeated
# coordinates represented by separate input rows must preserve each global ID.
chrom <- c("chr2", "chr1", "chr2", "chr1", "chr1", "chr2", "chr1")
widths <- c(51L, 80L, 51L, 51L, 80L, 51L, 51L)
starts <- c(100L, 200L, 300L, 400L, 500L, 600L, 400L)
ends <- starts + widths - 1L
groups <- group_peak_indices(chrom, widths)
flat <- unlist(lapply(groups, `[[`, "index"), use.names = FALSE)
stopifnot(length(flat) == length(chrom), !anyDuplicated(flat),
          identical(sort(flat), seq_along(chrom)),
          chrom[[4L]] == chrom[[7L]], starts[[4L]] == starts[[7L]], ends[[4L]] == ends[[7L]])
stopifnot(!identical(print_group_scratch_dir("/tmp/run", 1L),
                     print_group_scratch_dir("/tmp/run", 2L)))
project <- list(id = "group-a")
bind_active_print_project(project)
stopifnot(isTRUE(assert_active_print_project(project)))
wrong_project <- list(id = "group-b")
stopifnot(inherits(try(assert_active_print_project(wrong_project), silent = TRUE), "try-error"))

bias_vectors <- lapply(seq_along(widths), function(i) as.numeric(i * 100L + seq_len(widths[i])))
matrices <- lapply(groups, function(g) {
  build_bias_matrix(bias_vectors[g$index], seq_along(g$index), g$width,
                    global_index = g$index)
})
for (g in seq_along(groups)) {
  stopifnot(identical(dim(matrices[[g]]), c(length(groups[[g]]$index), groups[[g]]$width)))
  for (row in seq_along(groups[[g]]$index)) {
    original <- groups[[g]]$index[[row]]
    stopifnot(identical(unname(matrices[[g]][row, ]), bias_vectors[[original]]),
              rownames(matrices[[g]])[[row]] == as.character(original))
  }
}

counts <- lapply(seq_along(widths), function(i) {
  if (i == 3L) return(data.frame())
  data.frame(position = c(1L, widths[[i]]), group = "all", count = c(i, i + 1L))
})
for (g in groups) {
  selected <- validate_count_group(counts, g$index, widths)
  stopifnot(length(selected) == length(g$index))
  for (j in seq_along(g$index)) stopifnot(identical(selected[[j]], counts[[g$index[[j]]]]))
}
# Simulate the runner's top-level binding across consecutive groups. The
# immutable full source must survive replacing .GlobalEnv$project with a
# previous group's project/countTensor.
full_count_source <- counts
for (g in groups[seq_len(min(2L, length(groups)))]) {
  group_project <- list(countTensor = validate_count_group(full_count_source, g$index, widths))
  bind_active_print_project(group_project)
  next_group_counts <- validate_count_group(full_count_source, g$index, widths)
  stopifnot(identical(next_group_counts, counts[g$index]))
}
bad_counts <- counts
bad_counts[[2L]]$position[[1L]] <- widths[[2L]] + 1L
stopifnot(inherits(try(validate_count_group(bad_counts, 2L, widths), silent = TRUE), "try-error"))

# Group execution order is deliberately different from BED order. Restoration
# must return the exact per-row object, including NULLs and duplicate records.
index_groups <- list(c(2L, 4L), c(1L, 3L))
result_groups <- list(list(list(id = 2L), NULL), list(list(id = 1L), list(id = 3L)))
restored <- restore_group_results(4L, index_groups, result_groups)
stopifnot(identical(restored[[1L]], list(id = 1L)),
          identical(restored[[2L]], list(id = 2L)),
          identical(restored[[3L]], list(id = 3L)),
          is.null(restored[[4L]]))
stopifnot(inherits(try(restore_group_results(4L, list(c(1L, 2L), c(2L, 3L)),
                                               list(list(1, 2), list(2, 3))), silent = TRUE), "try-error"))
stopifnot(inherits(try(restore_group_results(4L, list(1:2), list(list(1, 2))), silent = TRUE), "try-error"))

# BED is 0-based half-open; PRINT local vectors/ranges are 1-based. Preserve a
# native event that extends beyond the peak interval instead of clipping it.
stopifnot(identical(track_positions0(100L, 4L), 100:103),
          identical(unname(event_interval0(100L, 1L, 20L)), c(100L, 120L)),
          identical(unname(event_interval0(100L, 95L, 114L)), c(194L, 214L)),
          identical(unname(event_interval0(100L, -9L, 10L)), c(90L, 110L)))
stopifnot(inherits(try(event_interval0(0L, -9L, 10L), silent = TRUE), "try-error"))

cat("PRINT variable-width contract checks passed\n")
