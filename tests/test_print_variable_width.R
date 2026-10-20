source(file.path("scripts", "04b_footprint", "print_variable_width.R"))
library(data.table)

# Direct HDF5 slice helper contract: one-based inclusive coordinates, exact
# length and exact source values must be preserved for the independent oracle.
mock_chromosome_bias <- as.numeric(seq_len(100L)) / 10
stopifnot(identical(read_bias_slice(mock_chromosome_bias, 13L, 17L),
                    mock_chromosome_bias[13:17]),
          inherits(try(read_bias_slice(mock_chromosome_bias, 0L, 2L), silent = TRUE),
                   "try-error"))

for (n in c(1L, 99L, 100L, 101L, 128L)) {
  groups <- group_peak_indices(rep("chr1", n), rep(37L, n))
  stopifnot(length(groups) == 1L, length(groups[[1L]]$index) == n)
  vectors <- lapply(seq_len(n), function(i) as.numeric(i * 1000L + seq_len(37L)))
  bias <- build_bias_matrix(vectors, seq_len(n), 37L, global_index = seq_len(n))
  stopifnot(identical(dim(bias), c(n, 37L)),
            identical(unname(bias[1L, ]), vectors[[1L]]),
            identical(unname(bias[n, ]), vectors[[n]]))
}

# Reproduce the reviewed 8-row shuffled 3/2/2/1 grouping. split()/vapply()
# retain group names; the shape check must compare the sizes, not those names.
smoke_chrom <- c("chr9", "chr9", "chr9", "chr22", "chr22", "chr9", "chr22", "chr9")
smoke_width <- c(1042L, 1234L, 1042L, 1777L, 1977L, 1234L, 1777L, 1042L)
smoke_groups <- group_peak_indices(smoke_chrom, smoke_width)
smoke_group_sizes <- vapply(smoke_groups, function(g) length(g$index), integer(1))
stopifnot(length(smoke_groups) == 4L, !is.null(names(smoke_group_sizes)),
          identical(sort(unname(smoke_group_sizes)), c(1L, 2L, 2L, 3L)),
          has_reviewed_direct_compare_group_sizes(smoke_groups),
          any(vapply(smoke_groups, function(g) length(g$index) > 1L &&
                       any(diff(g$index) != 1L), logical(1))))
bad_smoke_groups <- smoke_groups
bad_smoke_groups[[1L]]$index <- c(bad_smoke_groups[[1L]]$index, 2L)
stopifnot(!has_reviewed_direct_compare_group_sizes(bad_smoke_groups))

# Bounded scorer chunks preserve original row order and stop at either the
# peak-count or cumulative-bases limit; a single oversized peak stays whole.
chunks_by_bases <- make_bounded_region_chunks(1:6, c(400000L, 400000L, 300000L,
                                                       1200000L, 100L, 100L),
                                              max_peaks = 500L, max_bases = 1000000L)
stopifnot(identical(chunks_by_bases, list(1:2, 3L, 4L, 5:6)))
chunks_by_count <- make_bounded_region_chunks(1:7, rep(1L, 7L),
                                              max_peaks = 3L, max_bases = 100L)
stopifnot(identical(chunks_by_count, list(1:3, 4:6, 7L)))
stopifnot(inherits(try(make_bounded_region_chunks(1:2, c(10L, 10L), max_peaks = NA),
                       silent = TRUE), "try-error"))

# The bulk-safe wrapper retains PRINT's exact function body/formulas while
# repairing only sapply() dimension dropping for a singleton group. The
# multi-group path must remain byte-for-byte structurally identical.
native_sapply_fixture <- function(regionATAC, cellTypeLabels) {
  group_values <- sapply(seq_len(ncol(regionATAC)), function(i) regionATAC[, i])
  cell_types <- unique(cellTypeLabels)
  cell_values <- sapply(cell_types, function(cell) {
    rowSums(regionATAC[, cellTypeLabels %in% cell, drop = FALSE])
  })
  list(group_values = group_values, cell_values = cell_values)
}
safe_sapply_fixture <- make_bulk_safe_region_scorer(native_sapply_fixture)
single_group <- matrix(c(1, 3, 5, 7), ncol = 1L,
                       dimnames = list(NULL, "all"))
single_result <- safe_sapply_fixture(single_group, "all")
stopifnot(identical(dim(single_result$group_values), c(4L, 1L)),
          identical(dim(single_result$cell_values), c(4L, 1L)),
          identical(colnames(single_result$cell_values), "all"),
          identical(as.numeric(single_result$cell_values), as.numeric(single_group)))
multi_group <- cbind(c(1, 3, 5, 7), c(2, 4, 6, 8))
multi_native <- native_sapply_fixture(multi_group, c("a", "b"))
multi_safe <- safe_sapply_fixture(multi_group, c("a", "b"))
stopifnot(identical(multi_safe, multi_native))

# The PRINT legacy oracle is an S4 generic -> method -> get_footprints helper.
# Keep generic, method, helper and scorer in different environments so this
# fixture catches assumptions about environment(getFootprints).
oracle_generic_env <- new.env(parent = .GlobalEnv)
methods::setClass("PmaOracleProbe", representation(value = "character"),
                  where = oracle_generic_env)
methods::setGeneric("pmaOracleGetFootprints",
                    function(project) standardGeneric("pmaOracleGetFootprints"),
                    where = oracle_generic_env)
oracle_scorer_env <- new.env(parent = oracle_generic_env)
oracle_scorer_env$native_regionFootprintScoring <- function(x) paste0("native:", x)
oracle_scorer_env$regionFootprintScoring <- function(x) paste0("safe:", x)
oracle_helper_env <- new.env(parent = oracle_scorer_env)
oracle_helper_env$error_mode <- FALSE
oracle_helper_env$get_footprints <- eval(quote(function(x) {
  if (error_mode) stop("expected native oracle error")
  regionFootprintScoring(x)
}), envir = oracle_helper_env)
oracle_method_env <- new.env(parent = oracle_helper_env)
oracle_method_definition <- eval(quote(function(project) get_footprints("oracle")),
                                envir = oracle_method_env)
methods::setMethod("pmaOracleGetFootprints", signature = c(project = "PmaOracleProbe"),
                   definition = oracle_method_definition, where = oracle_generic_env)
oracle_project <- methods::new("PmaOracleProbe", value = "test")
oracle_generic <- methods::getGeneric("pmaOracleGetFootprints", where = oracle_generic_env)
oracle_owner <- resolve_print_oracle_scorer_owner(
  oracle_project, oracle_generic, oracle_scorer_env$regionFootprintScoring)
stopifnot(identical(oracle_owner, oracle_scorer_env),
          !exists("regionFootprintScoring", envir = oracle_helper_env, inherits = FALSE),
          !exists("get_footprints", envir = oracle_method_env, inherits = FALSE))
oracle_call <- function() with_print_region_scorer(
  oracle_scorer_env$native_regionFootprintScoring,
  oracle_generic(oracle_project), envir = oracle_owner,
  expected_current = oracle_scorer_env$regionFootprintScoring)
stopifnot(identical(oracle_call(), "native:oracle"),
          identical(oracle_scorer_env$regionFootprintScoring("after"), "safe:after"))
oracle_helper_env$error_mode <- TRUE
stopifnot(inherits(try(oracle_call(), silent = TRUE), "try-error"),
          identical(oracle_scorer_env$regionFootprintScoring("restored"), "safe:restored"))

# Never unlock namespace/import environments or replace a locked/active scorer.
locked_scorer_env <- new.env(parent = emptyenv())
locked_scorer_env$regionFootprintScoring <- oracle_scorer_env$regionFootprintScoring
lockBinding("regionFootprintScoring", locked_scorer_env)
stopifnot(inherits(try(with_print_region_scorer(
  oracle_scorer_env$native_regionFootprintScoring, TRUE,
  envir = locked_scorer_env,
  expected_current = oracle_scorer_env$regionFootprintScoring), silent = TRUE), "try-error"))
active_scorer_env <- new.env(parent = emptyenv())
makeActiveBinding("regionFootprintScoring",
                  function(value) oracle_scorer_env$regionFootprintScoring,
                  active_scorer_env)
stopifnot(inherits(try(with_print_region_scorer(
  oracle_scorer_env$native_regionFootprintScoring, TRUE,
  envir = active_scorer_env,
  expected_current = oracle_scorer_env$regionFootprintScoring), silent = TRUE), "try-error"))
locked_environment <- new.env(parent = emptyenv())
locked_environment$regionFootprintScoring <- oracle_scorer_env$regionFootprintScoring
lockEnvironment(locked_environment, bindings = FALSE)
stopifnot(inherits(try(with_print_region_scorer(
  oracle_scorer_env$native_regionFootprintScoring, TRUE,
  envir = locked_environment,
  expected_current = oracle_scorer_env$regionFootprintScoring), silent = TRUE), "try-error"),
  inherits(try(find_print_lexical_binding_owner("missing_scorer", oracle_method_env),
               silent = TRUE), "try-error"),
  inherits(try(resolve_print_oracle_scorer_owner(
    oracle_project, oracle_generic, function(x) paste0("wrong:", x)),
    silent = TRUE), "try-error"))

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

assert_numeric_close(c(1, NA_real_, Inf), c(1 + 1e-12, NA_real_, Inf), "tolerance fixture")
stopifnot(inherits(try(assert_numeric_close(c(1, NA_real_), c(1, 2), "NA mask fixture"),
                       silent = TRUE), "try-error"))
stopifnot(inherits(try(assert_numeric_close(c(1, 2), c(1, 2, 3), "length fixture"),
                       silent = TRUE), "try-error"))
range_a <- GenomicRanges::GRanges("summit:20-20", IRanges::IRanges(11, 30))
S4Vectors::mcols(range_a)$score <- 2
S4Vectors::mcols(range_a)$cellType <- "all"
range_b <- GenomicRanges::GRanges("summit:20-20", IRanges::IRanges(11, 30))
S4Vectors::mcols(range_b)$score <- 2 + 1e-12
S4Vectors::mcols(range_b)$cellType <- "all"
region_a <- list(regionID = "chr1:100-150", summitPvalscores = matrix(c(1, 2)),
                 aggregateATAC = c(2, 3), footprintRanges = range_a,
                 aggregateScores = c(4, 5), summits = 2L, bias = c(0.5, 0.7),
                 summitCellTypeScores = matrix(2))
region_b <- region_a
region_b$footprintRanges <- range_b
region_b$aggregateScores <- c(4, 5 + 1e-12)
assert_print_region_equal(region_a, region_b, "region comparison fixture")
region_bad <- region_b
region_bad$footprintRanges <- GenomicRanges::shift(range_b, 1L)
stopifnot(inherits(try(assert_print_region_equal(region_a, region_bad, "range fixture"),
                       silent = TRUE), "try-error"))

# Chunk parts are immutable; final tracks/events publish only after both scales
# pass row-count, compression, and SHA-256 checks. Zero events are a valid empty
# BED, while duplicate peak rows remain represented in the track.
publish_tmp <- tempfile("print-publish-contract-")
dir.create(publish_tmp)
publish_out <- file.path(publish_tmp, "print")
parts_dir <- paste0(publish_out, ".stream_parts")
dir.create(parts_dir)
track_parts <- list(
  r10 = list(data.table(chrom = c("chr1", "chr1"), pos = 10:11, score = c(1, 2)),
             data.table(chrom = c("chr1", "chr1"), pos = 10:11, score = c(1, 2))),
  r20 = list(data.table(chrom = c("chr1", "chr1"), pos = 10:11, score = c(3, 4)),
             data.table(chrom = c("chr1", "chr1"), pos = 10:11, score = c(3, 4)))
)
event_parts <- list(
  r10 = list(data.table(chrom = "chr1", start = 10L, end = 11L, score = 2), NULL),
  r20 = list(NULL, NULL)
)
publish_manifest <- data.table(chunk_id = 1:2,
  r10_track_rows = c(2L, 2L), r10_event_rows = c(1L, 0L),
  r20_track_rows = c(2L, 2L), r20_event_rows = c(0L, 0L))
for (rad in c("10", "20")) {
  for (i in 1:2) {
    track_path <- file.path(parts_dir, sprintf("r%s.track.%06d.tsv", rad, i))
    event_path <- file.path(parts_dir, sprintf("r%s.events.%06d.bed", rad, i))
    atomic_write_print_part(track_parts[[paste0("r", rad)]][[i]], track_path,
                            c("chrom", "pos", "score"))
    atomic_write_print_part(event_parts[[paste0("r", rad)]][[i]], event_path,
                            c("chrom", "start", "end", "score"))
    publish_manifest[[paste0("r", rad, "_track_sha256")]][i] <- sha256_file(track_path)
    publish_manifest[[paste0("r", rad, "_events_sha256")]][i] <- sha256_file(event_path)
  }
}
header_manifest_path <- file.path(parts_dir, "header_fixture.tsv")
atomic_write_print_part(data.table(global_row = 1L, start0 = 10L, end0 = 11L),
                        header_manifest_path, c("global_row", "start0", "end0"),
                        header = TRUE)
stopifnot(identical(names(fread(header_manifest_path)),
                    c("global_row", "start0", "end0")))
publish_streamed_print_outputs(
  list(parts_dir = parts_dir, manifest = publish_manifest,
       expected_track_rows = 4L), publish_out, c(10L, 20L))
stopifnot(file.exists(paste0(publish_out, ".complete.tsv")),
          count_gzip_text_lines(sprintf("%s.r10.track.tsv.gz", publish_out)) == 5,
          count_text_lines(sprintf("%s.r10.native_events.bed", publish_out)) == 1,
          count_text_lines(sprintf("%s.r20.native_events.bed", publish_out)) == 0,
          inherits(try(atomic_write_print_part(NULL,
                       file.path(parts_dir, "r10.events.000001.bed"),
                       c("chrom", "start", "end", "score")), silent = TRUE), "try-error"))
unlink(publish_tmp, recursive = TRUE)

cat("PRINT variable-width contract checks passed\n")
