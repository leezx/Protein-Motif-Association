#!/usr/bin/env Rscript
# Read-only diagnosis of the pinned PRINT pnorm warnings on an existing
# eight-peak cache. This script never builds counts, changes PRINT, or rewrites
# score tracks/events. It writes only a new diagnostic directory.

sha256_file <- function(path) {
  result <- system2("sha256sum", shQuote(normalizePath(path, mustWork = TRUE)),
                    stdout = TRUE, stderr = TRUE)
  status <- attr(result, "status")
  if (!is.null(status) && status != 0L) stop("sha256sum failed: ", path)
  strsplit(result[[1L]], "[[:space:]]+")[[1L]][[1L]]
}

sha256_object <- function(object) {
  path <- tempfile("print-model-weights-")
  connection <- file(path, open = "wb")
  connection_open <- TRUE
  on.exit({
    if (connection_open) try(close(connection), silent = TRUE)
    unlink(path)
  }, add = TRUE)
  writeBin(serialize(object, NULL, version = 3L), connection)
  close(connection)
  connection_open <- FALSE
  sha256_file(path)
}

classify_pnorm_warning <- function(text) {
  if (identical(text, "NaNs produced")) return("PNORM_NANS_PRODUCED")
  "UNCLASSIFIED_WARNING"
}

summarize_diagnostic_gate <- function(calls, positions) {
  warning_count <- if (nrow(calls)) sum(calls$warning_count) else 0L
  unclassified <- if (nrow(calls))
    sum(calls$unclassified_warning_count) else 0L
  unlocated <- if (nrow(calls))
    sum(calls$warning_count[calls$anomaly_positions == 0L]) else 0L
  unknown_mask <- if (nrow(positions))
    sum(positions$anomaly_position & is.na(positions$native_zero_coverage_mask)) else 0L
  unmasked <- if (nrow(positions))
    sum(positions$anomaly_position & positions$native_zero_coverage_mask %in% FALSE) else 0L
  current_replay_gate <- if (unclassified > 0L) "BLOCKED_UNCLASSIFIED_WARNING" else
    if (unlocated > 0L) "BLOCKED_UNLOCATED_WARNING" else
      if (unknown_mask > 0L) "BLOCKED_UNKNOWN_MASK" else
        if (unmasked > 0L) "BLOCKED_UNMASKED_ANOMALY" else
          if (warning_count == 0L) "NO_REPLAY_WARNING" else
            "PASS_CURRENT_REPLAY_ANOMALIES_ALL_MASKED"
  list(
    diagnostic_warning_count = warning_count,
    unclassified_warning_count = unclassified,
    warnings_without_elementwise_anomaly = unlocated,
    anomaly_positions_with_unknown_mask = unknown_mask,
    anomaly_positions_not_masked = unmasked,
    current_replay_anomaly_gate = current_replay_gate,
    historical_v5_warning_count_reference = 28L,
    historical_v5_warning_comparability = "NOT_ESTABLISHED_CONTEXTS_DIFFER",
    scale_up_warning_gate = "BLOCKED_HISTORICAL_CONTEXT_NOT_REPRODUCED"
  )
}

assert_that <- function(ok, message) if (!isTRUE(ok)) stop(message, call. = FALSE)

assert_new_output_path <- function(path) {
  assert_that(!file.exists(path), "diagnostic output path already exists")
  invisible(path)
}

run_with_integrity_guard <- function(thunk, audit) {
  primary <- tryCatch(list(value = thunk(), error = NULL), error = function(e) {
    list(value = NULL, error = e)
  })
  integrity <- NULL
  if (length(audit$paths) && length(audit$before_hashes)) {
    integrity <- tryCatch({
      after <- vapply(audit$paths, sha256_file, character(1))
      names(after) <- audit$paths
      if (!identical(audit$before_hashes, after))
        stop("read-only input/output hashes changed during diagnostic")
      NULL
    }, error = identity)
  }
  if (!is.null(primary$error) && !is.null(integrity)) {
    stop(sprintf("diagnostic failed: %s; post-error integrity verification also failed: %s",
                 conditionMessage(primary$error), conditionMessage(integrity)), call. = FALSE)
  }
  if (!is.null(primary$error)) stop(primary$error)
  if (!is.null(integrity)) stop(integrity)
  primary$value
}

make_diagnostic_scorers <- function(native_region_scorer, native_footprint_scorer,
                                    native_window_sum, state,
                                    bulk_safe_wrapper = identity,
                                    capture_forward = FALSE) {
  assert_that(is.function(native_region_scorer) && is.function(native_footprint_scorer) &&
                is.function(native_window_sum), "native PRINT scoring functions are required")
  if (is.null(state$completed_calls)) state$completed_calls <- list()

  pnorm_wrapper <- function(q, mean = 0, sd = 1, ...) {
    current <- state$current_call
    assert_that(!is.null(current), "pnorm called outside a tracked PRINT scorer")
    current$flank_index <- current$flank_index + 1L
    assert_that(current$flank_index %in% 1:2, "unexpected PRINT pnorm call count")
    flank <- c("left", "right")[[current$flank_index]]
    warning_state <- new.env(parent = emptyenv())
    warning_state$text <- character()
    value <- withCallingHandlers(
      stats::pnorm(q, mean = mean, sd = sd, ...),
      warning = function(w) {
        warning_state$text <- c(warning_state$text, conditionMessage(w))
        # Deliberately do not invoke muffleWarning: preserve native behavior.
      }
    )
    lengths <- c(length(q), length(mean), length(sd), length(value),
                 length(current$left_total), length(current$right_total))
    assert_that(length(unique(lengths)) == 1L,
                "PRINT pnorm vectors or insertion-mask vectors differ in length")
    current$warnings[[flank]] <- warning_state$text
    current$inputs[[flank]] <- list(q = q, mean = mean, sd = sd, p = value)
    value
  }

  diagnostic_footprint_scorer <- native_footprint_scorer
  footprint_env <- new.env(parent = environment(native_footprint_scorer))
  footprint_env$pnorm <- pnorm_wrapper
  if (capture_forward) {
    native_predict_dispersion <- get("predictDispersion",
                                     envir = environment(native_footprint_scorer),
                                     inherits = TRUE)
    footprint_env$predictDispersion <- function(x, modelWeights) {
      value <- native_predict_dispersion(x, modelWeights)
      current <- state$current_call
      assert_that(!is.null(current), "dispersion predictor called outside tracked scorer")
      assert_that(is.matrix(x) && nrow(x) == length(current$left_total) && ncol(x) == 5L,
                  "captured PRINT predictor input has unexpected dimensions")
      assert_that(is.matrix(value) && nrow(value) == nrow(x) && ncol(value) == 4L,
                  "captured PRINT predictor output has unexpected dimensions")
      current$scaled_features <- x
      current$model_weights <- modelWeights
      current$standardized_output <- value
      value
    }
  }
  environment(diagnostic_footprint_scorer) <- footprint_env

  observed_footprint_scorer <- function(Tn5Insertion, Tn5Bias, dispersionModel,
                                        footprintRadius = 10, flankRadius = 10, ...) {
    state$path_index <- state$path_index + 1L
    path <- c("pseudobulk_matrix", "cell_type_score")[[state$path_index]]
    window <- native_window_sum(Tn5Insertion, footprintRadius, flankRadius)
    state$current_call <- new.env(parent = emptyenv())
    state$current_call$path <- path
    state$current_call$scorer_pass <- state$scorer_pass
    state$current_call$flank_index <- 0L
    state$current_call$left_total <- window$center + window$leftFlank
    state$current_call$right_total <- window$center + window$rightFlank
    state$current_call$dispersion_model <- dispersionModel
    if (capture_forward) {
      bias_window <- native_window_sum(Tn5Bias, footprintRadius, flankRadius)
      raw_features <- cbind(
        bias_window$leftFlank,
        bias_window$rightFlank,
        bias_window$center,
        log10(state$current_call$left_total),
        log10(state$current_call$right_total)
      )
      assert_that(nrow(raw_features) == length(Tn5Insertion) && ncol(raw_features) == 5L,
                  "independently reconstructed PRINT feature matrix has unexpected dimensions")
      state$current_call$raw_features <- raw_features
    }
    state$current_call$warnings <- list(left = character(), right = character())
    state$current_call$inputs <- list()
    on.exit(state$current_call <- NULL, add = TRUE)
    result <- diagnostic_footprint_scorer(
      Tn5Insertion = Tn5Insertion, Tn5Bias = Tn5Bias,
      dispersionModel = dispersionModel, footprintRadius = footprintRadius,
      flankRadius = flankRadius, ...
    )
    state$completed_calls[[length(state$completed_calls) + 1L]] <- state$current_call
    result
  }

  diagnostic_region_body <- native_region_scorer
  region_env <- new.env(parent = environment(native_region_scorer))
  region_env$footprintScoring <- observed_footprint_scorer
  environment(diagnostic_region_body) <- region_env
  diagnostic_region_scorer <- bulk_safe_wrapper(diagnostic_region_body)
  list(region = diagnostic_region_scorer, state = state)
}

collect_call_rows <- function(call, context) {
  call_rows <- list()
  position_rows <- list()
  forward_audit_rows <- list()
  for (flank in c("left", "right")) {
    values <- call$inputs[[flank]]
    if (is.null(values)) stop("missing native pnorm flank result")
    n <- length(values$p)
    mask <- call$left_total < 1 | call$right_total < 1
    anomaly <- !is.finite(values$q) | !is.finite(values$mean) |
      !is.finite(values$sd) | !is.finite(values$p) | values$sd <= 0
    call_warnings <- call$warnings[[flank]]
    call_rows[[length(call_rows) + 1L]] <- data.frame(
      peak_row = context$peak_row, chromosome = context$chromosome,
      bed_start0 = context$start0, bed_end0 = context$end0,
      radius = context$radius, scorer_pass = call$scorer_pass,
      scorer_path = call$path, flank = flank,
      vector_length = n, warning_count = length(call_warnings),
      warning_text = paste(call_warnings, collapse = " | "),
      warning_categories = paste(unique(vapply(call_warnings, classify_pnorm_warning,
                                               character(1))), collapse = " | "),
      unclassified_warning_count = sum(vapply(call_warnings, classify_pnorm_warning,
                                              character(1)) == "UNCLASSIFIED_WARNING"),
      nonfinite_q = sum(!is.finite(values$q)),
      nonfinite_mean = sum(!is.finite(values$mean)),
      nonfinite_sd = sum(!is.finite(values$sd)),
      nonpositive_sd = sum(values$sd <= 0, na.rm = TRUE),
      nonfinite_p = sum(!is.finite(values$p)),
      anomaly_positions = sum(anomaly),
      anomaly_positions_native_masked = sum(anomaly & mask, na.rm = TRUE),
      anomaly_positions_not_masked = sum(anomaly & mask %in% FALSE, na.rm = TRUE),
      anomaly_positions_unknown_mask = sum(anomaly & is.na(mask), na.rm = TRUE),
      stringsAsFactors = FALSE
    )
    indices <- which(anomaly)
    if (length(indices)) {
      position_rows[[length(position_rows) + 1L]] <- data.frame(
        peak_row = context$peak_row, chromosome = context$chromosome,
        bed_start0 = context$start0, bed_end0 = context$end0,
        radius = context$radius, scorer_pass = call$scorer_pass,
        scorer_path = call$path, flank = flank,
        local_position_1based = indices,
        anomaly_position = TRUE,
        genomic_position_0based = context$start0 + indices - 1L,
        q = values$q[indices], predicted_mean = values$mean[indices],
        predicted_sd = values$sd[indices], pnorm_result = values$p[indices],
        left_total_insertion = call$left_total[indices],
        right_total_insertion = call$right_total[indices],
        native_zero_coverage_mask = mask[indices],
        warning_text = paste(call_warnings, collapse = " | "),
        stringsAsFactors = FALSE
      )
      capture <- call$scaled_features
      weights <- call$model_weights
      model <- call$dispersion_model
      standardized_output <- call$standardized_output
      raw_features <- call$raw_features
      if (is.null(capture) || is.null(weights) || is.null(model) ||
          is.null(standardized_output) || is.null(raw_features)) {
        stop("missing forward-pass capture for a PRINT pnorm context with anomalies")
      }
      if (!is.null(capture) && !is.null(weights) && !is.null(model) &&
          !is.null(standardized_output) && !is.null(raw_features)) {
        if (nrow(capture) != n || ncol(capture) != 5L || nrow(standardized_output) != n ||
            ncol(standardized_output) != 4L || nrow(raw_features) != n ||
            ncol(raw_features) != 5L) {
          stop("captured PRINT dispersion matrices have unexpected dimensions")
        }
        # One anomalous location and the closest finite positive-SD comparator per pnorm call.
        negative_sd_indices <- which(is.finite(values$sd) & values$sd <= 0)
        if (!length(negative_sd_indices)) next
        anomaly_index <- negative_sd_indices[[1L]]
        valid <- which(is.finite(values$q) & is.finite(values$mean) &
                         is.finite(values$sd) & values$sd > 0 & is.finite(values$p) &
                         !is.na(mask) & !mask)
        comparator <- if (length(valid)) valid[which.min(abs(valid - anomaly_index))] else NA_integer_
        selected <- c(anomaly_index, comparator)
        selected <- selected[!is.na(selected)]
        weights_hash <- sha256_object(weights)
        model_hash <- sha256_object(model)
        for (idx in selected) {
          scaled <- as.numeric(capture[idx, , drop = TRUE])
          backcalculated_features <- scaled * as.numeric(model$featureSD) +
            as.numeric(model$featureMean)
          independently_recomputed_features <- as.numeric(raw_features[idx, , drop = TRUE])
          independently_recomputed_scaled <-
            (independently_recomputed_features - as.numeric(model$featureMean)) /
              as.numeric(model$featureSD)
          feature_reconstruction_error <-
            max(abs(independently_recomputed_scaled - scaled))
          layer1_linear <- as.numeric(scaled %*% weights[[1]]) + as.numeric(weights[[2]])
          layer1_relu <- pmax(layer1_linear, 0)
          reconstructed_standardized <- as.numeric(layer1_relu %*% weights[[3]]) +
            as.numeric(weights[[4]])
          reconstructed_unscaled <- reconstructed_standardized * as.numeric(model$targetSD) +
            as.numeric(model$targetMean)
          captured_unscaled <- as.numeric(standardized_output[idx, ]) *
            as.numeric(model$targetSD) + as.numeric(model$targetMean)
          comparison_error <- max(abs(reconstructed_unscaled - captured_unscaled))
          flank_output_columns <- if (identical(flank, "left")) 1:2 else 3:4
          scorer_error <- max(abs(reconstructed_unscaled[flank_output_columns] -
                                    c(values$mean[idx], values$sd[idx])))
          forward_audit_rows[[length(forward_audit_rows) + 1L]] <- data.frame(
          peak_row = context$peak_row, chromosome = context$chromosome,
          bed_start0 = context$start0, bed_end0 = context$end0,
          radius = context$radius, scorer_pass = call$scorer_pass,
          scorer_path = call$path, flank = flank,
          role = if (idx == anomaly_index) "negative_sd" else "nearest_valid_sd",
          local_position_1based = idx,
          genomic_position_0based = context$start0 + idx - 1L,
          distance_to_peak_left = idx - 1L,
          distance_to_peak_right = n - idx,
          left_total_insertion = call$left_total[idx],
          right_total_insertion = call$right_total[idx],
          native_zero_coverage_mask = mask[idx],
          feature_order = "left_bias_sum;right_bias_sum;center_bias_sum;log10_left_total;log10_right_total",
          target_order = "left_ratio_mean;left_ratio_sd;right_ratio_mean;right_ratio_sd",
          weight_shapes = paste(vapply(weights, function(w) paste(dim(w), collapse = "x"),
                                       character(1)), collapse = ";"),
          model_sha256 = model_hash,
          feature_left_bias_sum = independently_recomputed_features[[1L]],
          feature_right_bias_sum = independently_recomputed_features[[2L]],
          feature_center_bias_sum = independently_recomputed_features[[3L]],
          feature_log10_left_total = independently_recomputed_features[[4L]],
          feature_log10_right_total = independently_recomputed_features[[5L]],
          backcalculated_feature_values_from_scaled_input = paste(
            format(backcalculated_features, digits = 17), collapse = ";"),
          scaled_features = paste(format(scaled, digits = 17), collapse = ";"),
          independently_recomputed_scaled_features = paste(
            format(independently_recomputed_scaled, digits = 17), collapse = ";"),
          max_feature_reconstruction_abs_error = feature_reconstruction_error,
          feature_mean = paste(format(model$featureMean, digits = 17), collapse = ";"),
          feature_sd = paste(format(model$featureSD, digits = 17), collapse = ";"),
          weights_sha256 = weights_hash,
          layer1_linear = paste(format(layer1_linear, digits = 17), collapse = ";"),
          layer1_relu = paste(format(layer1_relu, digits = 17), collapse = ";"),
          standardized_output = paste(format(standardized_output[idx, ], digits = 17), collapse = ";"),
          reconstructed_standardized_output = paste(format(reconstructed_standardized, digits = 17), collapse = ";"),
          target_mean = paste(format(model$targetMean, digits = 17), collapse = ";"),
          target_sd = paste(format(model$targetSD, digits = 17), collapse = ";"),
          reconstructed_unscaled_output = paste(format(reconstructed_unscaled, digits = 17), collapse = ";"),
          captured_unscaled_output = paste(format(captured_unscaled, digits = 17), collapse = ";"),
          scorer_mean = values$mean[idx], scorer_sd = values$sd[idx],
          scorer_q = values$q[idx], scorer_p = values$p[idx],
          max_forward_reconstruction_abs_error = comparison_error,
          max_scorer_output_abs_error = scorer_error,
          comparator_finite_q_mean_sd_p = is.finite(values$q[idx]) &&
            is.finite(values$mean[idx]) && is.finite(values$sd[idx]) &&
            is.finite(values$p[idx]),
          stringsAsFactors = FALSE
          )
        }
      }
    }
    if (length(call_warnings) && !length(indices)) {
      # Preserve a warning with no elementwise anomaly as an explicit row.
      position_rows[[length(position_rows) + 1L]] <- data.frame(
        peak_row = context$peak_row, chromosome = context$chromosome,
        bed_start0 = context$start0, bed_end0 = context$end0,
        radius = context$radius, scorer_pass = call$scorer_pass,
        scorer_path = call$path, flank = flank,
        anomaly_position = FALSE,
        local_position_1based = NA_integer_, genomic_position_0based = NA_integer_,
        q = NA_real_, predicted_mean = NA_real_, predicted_sd = NA_real_,
        pnorm_result = NA_real_, left_total_insertion = NA_real_,
        right_total_insertion = NA_real_, native_zero_coverage_mask = NA,
        warning_text = paste(call_warnings, collapse = " | "),
        stringsAsFactors = FALSE
      )
    }
  }
  list(calls = call_rows, positions = position_rows,
       forward_audit = forward_audit_rows)
}

run_self_test <- function() {
  state <- new.env(parent = emptyenv())
  state$path_index <- 0L
  state$scorer_pass <- "synthetic_test"
  state$current_call <- NULL
  state$completed_calls <- list()
  native_fp <- function(Tn5Insertion, Tn5Bias, dispersionModel,
                        footprintRadius = 1, flankRadius = 1, ...) {
    left <- c(0.2, 0.4, NaN)
    right <- c(0.2, 0.4, NaN)
    pnorm(left, mean = c(0.1, 0.2, 0.3), sd = c(1, -1, 1))
    pnorm(right, mean = c(0.1, 0.2, 0.3), sd = c(1, -1, 1))
    invisible(NULL)
  }
  native_region <- function(regionATAC, Tn5Bias, dispersionModel, ...) {
    footprintScoring(regionATAC[, 1], Tn5Bias, dispersionModel, ...)
    footprintScoring(regionATAC[, 1], Tn5Bias, dispersionModel, ...)
    "unchanged-result"
  }
  window_sum <- function(x, footprintRadius, flankRadius) {
    list(center = c(0, 0, 0), leftFlank = c(0, 2, 0), rightFlank = c(0, 2, 0))
  }
  wrapped <- make_diagnostic_scorers(native_region, native_fp, window_sum, state)
  value <- wrapped$region(matrix(1:3, ncol = 1), 1:3, NULL)
  assert_that(identical(value, "unchanged-result"), "diagnostic changed scorer return value")
  assert_that(state$path_index == 2L, "expected both native scorer paths")
  assert_that(length(state$completed_calls) == 2L, "expected both captured native scorer paths")
  assert_that(is.null(state$current_call), "diagnostic context was not cleared")
  first <- state$completed_calls[[1L]]
  assert_that(any(vapply(first$warnings, length, integer(1)) > 0L),
              "diagnostic failed to record native pnorm warnings")
  expected <- c(stats::pnorm(0.2, mean = 0.1, sd = 1), NaN, NaN)
  assert_that(identical(first$inputs$left$p, expected),
              "diagnostic wrapper changed native pnorm return values")
  rows <- collect_call_rows(first, list(peak_row = 1L, chromosome = "chr1",
                                         start0 = 100L, end0 = 103L, radius = 1L))
  positions <- data.table::rbindlist(rows$positions)
  assert_that(any(positions$genomic_position_0based == 101L &
                    positions$native_zero_coverage_mask == FALSE) &&
                any(positions$genomic_position_0based == 102L &
                      positions$native_zero_coverage_mask == TRUE),
              "diagnostic did not distinguish masked from unmasked anomalous positions")
  cat("PRINT pnorm diagnostic self-test PASS\n")
}

if (identical(commandArgs(trailingOnly = TRUE), "--self-test")) {
  run_self_test()
  quit(status = 0L)
}

main_impl <- function(args, audit) {
  if (length(args) != 8L) {
    stop(paste(
      "usage: Rscript diagnose_print_pnorm.R PRINT_REPO V5_MAIN_DIR SELECTED_BED",
      "SELECTION_MAP V5_OUTPUT_PREFIX SHARED_DIR V5_EVIDENCE_ROOT NEW_DIAGNOSTIC_DIR"
    ), call. = FALSE)
  }
  print_repo <- normalizePath(args[[1]], mustWork = TRUE)
  main_dir <- normalizePath(args[[2]], mustWork = TRUE)
  selected_bed <- normalizePath(args[[3]], mustWork = TRUE)
  selection_map <- normalizePath(args[[4]], mustWork = TRUE)
  output_prefix <- file.path(normalizePath(dirname(args[[5]]), mustWork = TRUE), basename(args[[5]]))
  shared_dir <- normalizePath(args[[6]], mustWork = TRUE)
  evidence_dir <- normalizePath(args[[7]], mustWork = TRUE)
  diagnostic_dir <- args[[8]]
  assert_new_output_path(diagnostic_dir)
  repo_head <- system2("git", c("-C", shQuote(print_repo), "rev-parse", "HEAD"), stdout = TRUE)
  repo_status <- system2("git", c("-C", shQuote(print_repo), "status", "--porcelain"), stdout = TRUE)
  assert_that(length(repo_head) == 1L &&
                identical(trimws(repo_head[[1L]]), "8dad7317c3a640454a191dba2acd138e6edc54ac"),
              "PRINT repository is not at the pinned V5 source commit")
  assert_that(length(repo_status) == 0L, "pinned PRINT source worktree is dirty")

  script_dir <- dirname(normalizePath(sub("^--file=", "", grep("^--file=", commandArgs(FALSE),
                                                                  value = TRUE)[[1]])))
  diagnostic_script <- file.path(script_dir, "diagnose_print_pnorm.R")
  helper <- file.path(script_dir, "print_variable_width.R")
  required <- c("utils.R", "getCounts.R", "getBias.R", "getFootprints.R")
  for (file in required) {
    path <- file.path(print_repo, "code", file)
    assert_that(file.exists(path), paste("missing pinned PRINT source:", file))
  }
  count_path <- file.path(main_dir, "data", "chunkedCountTensor", "chunk_1.rds")
  bias_dir <- file.path(main_dir, "bias_groups")
  bias_paths <- sort(list.files(bias_dir, pattern = "^group_[0-9]{6}\\.rds$", full.names = TRUE))
  model_paths <- file.path(shared_dir, "dispModel", c("dispersionModel10bp.rds", "dispersionModel20bp.rds"))
  track_paths <- sprintf("%s.r%d.track.tsv.gz", output_prefix, c(10L, 20L))
  event_paths <- sprintf("%s.r%d.native_events.bed", output_prefix, c(10L, 20L))
  compare_path <- paste0(output_prefix, ".direct-comparison.tsv")
  evidence_paths <- file.path(evidence_dir, c("summary.json", "smoke_completion.json"))
  all_inputs <- c(selected_bed, selection_map, count_path, bias_paths, model_paths,
                  track_paths, event_paths, compare_path,
                  file.path(print_repo, "code", required), helper,
                  diagnostic_script, evidence_paths)
  assert_that(length(bias_paths) > 0L && all(file.exists(all_inputs)),
              "one or more reviewed V5 read-only inputs are missing")
  # Establish the immutable pre-read baseline before source(), readRDS(), fread(),
  # or any other operation that loads cache/evidence contents. Rscript has
  # necessarily loaded this diagnostic file to start the process; its bytes are
  # recorded here, while all other code/data inputs are pinned before loading.
  # Only the six published V5 evidence/track/event files have historical trusted
  # SHA pins; count/bias/model caches are frozen now, not asserted to be original
  # V5 bytes.
  before_hashes <- vapply(all_inputs, sha256_file, character(1))
  names(before_hashes) <- normalizePath(all_inputs)
  audit$paths <- normalizePath(all_inputs)
  audit$before_hashes <- before_hashes
  expected_hashes <- c(
    "51e7d2292b4baa7d2e4851d14b7acddb3ab0974f73ca4e88d11e1d79c51d71b5",
    "f6789a5d1f5ebc5c65467bf6d3287cbcac5172ce020eedfda2414d91035b7a0a",
    "4ee07f188d4c0b43ea813fa2930b3da9ea41e2e2b2f83cf0d1aa70ff2bfda72b",
    "b54254670978d006781af4fb228ff744c9fbac2b09afb2fc07e915801778c447",
    "30aedcd7843e947164290335cdfaff61b33338f7b44e7c6ebb887394d4fa66c8",
    "b18d8916b5df3ade276e1f6f50628a9b82bf34b6b4741acb6ae552dbf4b8ad72"
  )
  names(expected_hashes) <- c(basename(evidence_paths), basename(track_paths), basename(event_paths))
  for (name in names(expected_hashes)) {
    path <- c(evidence_paths, track_paths, event_paths)[match(name,
      basename(c(evidence_paths, track_paths, event_paths)))]
    assert_that(identical(unname(before_hashes[[normalizePath(path)]]), expected_hashes[[name]]),
                paste("V5 evidence/output SHA-256 mismatch:", name))
  }

  suppressPackageStartupMessages({
    library(GenomicRanges)
    library(data.table)
    library(IRanges)
    library(S4Vectors)
    library(dplyr)
    library(Matrix)
    library(caTools)
  })
  helper_env <- new.env(parent = globalenv())
  sys.source(helper, envir = helper_env)
  print_env <- new.env(parent = globalenv())
  for (file in required) sys.source(file.path(print_repo, "code", file), envir = print_env)
  native_region <- get("regionFootprintScoring", envir = print_env, inherits = FALSE)
  native_fp <- get("footprintScoring", envir = print_env, inherits = FALSE)
  native_window <- get("footprintWindowSum", envir = print_env, inherits = FALSE)

  bed <- data.table::fread(selected_bed, header = FALSE)
  map <- data.table::fread(selection_map)
  assert_that(nrow(bed) == 8L && nrow(map) == 8L,
              "diagnostic requires exactly the reviewed eight selected regions")
  assert_that(all(c("output_index", "source_row_1based", "chrom", "start", "end", "width") %in% names(map)),
              "selection map schema mismatch")
  bed_width <- as.integer(bed[[3]] - bed[[2]])
  assert_that(identical(as.integer(map$output_index), 1:8) &&
                identical(as.character(map$chrom), as.character(bed[[1]])) &&
                identical(as.integer(map$start), as.integer(bed[[2]])) &&
                identical(as.integer(map$end), as.integer(bed[[3]])) &&
                identical(as.integer(map$width), bed_width),
              "selection BED and map coordinates disagree")
  assert_that(length(unique(bed[[1]])) >= 2L && length(unique(bed_width)) >= 3L,
              "selected regions no longer meet the reviewed 8-peak design")
  count_data <- readRDS(count_path)
  assert_that(length(count_data) == 8L, "cached count tensor is not exactly eight rows")
  bias_by_row <- vector("list", 8L)
  for (path in bias_paths) {
    matrix <- readRDS(path)
    ids <- suppressWarnings(as.integer(rownames(matrix)))
    assert_that(!is.null(ids) && length(ids) == nrow(matrix) && all(ids %in% 1:8),
                paste("cached bias matrix lacks original row identities:", basename(path)))
    for (i in seq_along(ids)) {
      assert_that(is.null(bias_by_row[[ids[[i]]]]), "duplicate cached bias row identity")
      bias_by_row[[ids[[i]]]] <- as.numeric(matrix[i, ])
    }
  }
  assert_that(all(lengths(bias_by_row) == bed_width),
              "cached bias rows do not cover the eight selected BED widths")
  models <- lapply(model_paths, readRDS)
  names(models) <- c("10", "20")

  comparison <- data.table::fread(compare_path)
  assert_that(nrow(comparison) == 16L && all(comparison$bias_exact_match),
              "V5 direct-equivalence record is not the expected 16 exact bias matches")
  expected_pairs <- data.table::CJ(global_row = 1:8, radius = c(10L, 20L))
  observed_pairs <- unique(comparison[, .(global_row, radius)])
  assert_that(nrow(observed_pairs) == 16L &&
                nrow(data.table::fsetdiff(expected_pairs, observed_pairs)) == 0L,
              "V5 record does not preserve all 16 original peak-radius comparisons")
  track_data <- lapply(track_paths, data.table::fread)
  event_data <- lapply(event_paths, function(path) {
    if (file.info(path)$size == 0) return(data.table::data.table())
    data.table::fread(path, header = FALSE, col.names = c("chrom", "start", "end", "score"))
  })
  expected_event_counts <- c(14L, 17L)
  assert_that(identical(vapply(event_data, nrow, integer(1)), expected_event_counts),
              "V5 native event counts changed from 14/17")
  expected_track_rows <- sum(bed_width)
  assert_that(all(vapply(track_data, nrow, integer(1)) == expected_track_rows),
              "V5 track row count does not equal sum of eight BED widths")

  dir.create(diagnostic_dir, recursive = FALSE, showWarnings = FALSE)
  diagnostic_dir <- normalizePath(diagnostic_dir, mustWork = TRUE)
  state <- new.env(parent = emptyenv())
  state$path_index <- 0L
  state$scorer_pass <- NULL
  state$current_call <- NULL
  state$completed_calls <- list()
  wrapped <- make_diagnostic_scorers(
    native_region, native_fp, native_window, state,
    bulk_safe_wrapper = helper_env$make_bulk_safe_region_scorer,
    capture_forward = TRUE
  )
  call_rows <- list(); position_rows <- list(); forward_audit_rows <- list()
  event_rows <- vector("list", 2L)
  names(event_rows) <- c("10", "20")
  track_offsets <- cumsum(c(0L, head(bed_width, -1L)))

  for (peak in 1:8) {
    count <- count_data[[peak]]
    atac <- helper_env$direct_region_atac(list(count), 1L, "all", bed_width[[peak]])
    if (is.null(dim(atac))) atac <- matrix(atac, ncol = 1L)
    for (radius in c(10L, 20L)) {
      replay_results <- list()
      for (pass in c("native_replay_1", "native_replay_2")) {
        state$path_index <- 0L
        state$scorer_pass <- pass
        context <- list(peak_row = peak, chromosome = as.character(bed[[1]][peak]),
                        start0 = as.integer(bed[[2]][peak]), end0 = as.integer(bed[[3]][peak]),
                        radius = radius)
        result <- wrapped$region(
          regionATAC = atac, Tn5Bias = bias_by_row[[peak]],
          dispersionModel = models[[as.character(radius)]],
          footprintRadius = radius, flankRadius = radius,
          regionID = paste0(context$chromosome, ":", context$start0, "-", context$end0),
          scoreType = "pval", cellTypeLabels = "all", returnCellTypeScores = FALSE
        )
        assert_that(state$path_index == 2L, "pinned PRINT did not call both score paths")
        calls <- state$completed_calls
        assert_that(length(calls) == 2L,
                    "instrumented scorer did not preserve both path call records")
        state$completed_calls <- list()
        for (call in calls) {
          rows <- collect_call_rows(call, context)
          call_rows <- c(call_rows, rows$calls)
          position_rows <- c(position_rows, rows$positions)
          forward_audit_rows <- c(forward_audit_rows, rows$forward_audit)
        }
        track <- track_data[[if (radius == 10L) 1L else 2L]]
        offset <- track_offsets[[peak]]
        expected <- result$aggregateScores
        observed <- track$score[seq.int(offset + 1L, offset + length(expected))]
        helper_env$assert_numeric_close(observed, expected,
                                        paste("baseline V5 score track peak", peak, "radius", radius, pass))
        observed_coords <- track$pos[seq.int(offset + 1L, offset + length(expected))]
        expected_coords <- as.integer(bed[[2]][peak]) + seq_along(expected) - 1L
        assert_that(identical(as.integer(observed_coords), expected_coords),
                    "baseline track coordinates changed or row mapping differs")
        replay_results[[pass]] <- result
      }
      helper_env$assert_print_region_equal(
        replay_results$native_replay_1,
        replay_results$native_replay_2,
        paste("duplicate native scorer replay peak", peak, "radius", radius)
      )
      event_rows[[as.character(radius)]][[peak]] <- native_events_for_region(
        replay_results$native_replay_2,
        as.character(bed[[1]][peak]), as.integer(bed[[2]][peak])
      )
    }
  }
  for (i in seq_along(event_paths)) {
    reconstructed <- data.table::rbindlist(event_rows[[if (i == 1L) "10" else "20"]], fill = TRUE)
    observed <- event_data[[i]]
    assert_that(nrow(reconstructed) == nrow(observed), "native event count changed during diagnostic")
    if (nrow(observed)) {
      assert_that(identical(as.character(reconstructed$chrom), as.character(observed$chrom)) &&
                    identical(as.integer(reconstructed$start), as.integer(observed$start)) &&
                    identical(as.integer(reconstructed$end), as.integer(observed$end)),
                  "native event coordinates changed during diagnostic")
      helper_env$assert_numeric_close(reconstructed$score, observed$score,
                                      "native event score comparison")
    }
  }
  after_hashes <- vapply(all_inputs, sha256_file, character(1))
  names(after_hashes) <- normalizePath(all_inputs)
  assert_that(identical(before_hashes, after_hashes), "read-only V5 input/output hashes changed")

  calls_table <- data.table::rbindlist(call_rows, fill = TRUE)
  positions_table <- data.table::rbindlist(position_rows, fill = TRUE)
  forward_audit_table <- if (length(forward_audit_rows))
    data.table::rbindlist(forward_audit_rows, fill = TRUE) else data.table::data.table()
  gate_summary <- summarize_diagnostic_gate(calls_table, positions_table)
  forward_tolerance <- 1e-10
  affected_calls <- if (nrow(calls_table)) calls_table[nonpositive_sd > 0L] else calls_table
  context_key <- function(x) paste(x$peak_row, x$radius, x$scorer_pass,
                                   x$scorer_path, x$flank, sep = "\r")
  expected_contexts <- if (nrow(affected_calls)) unique(context_key(affected_calls)) else character()
  observed_contexts <- if (nrow(forward_audit_table)) unique(context_key(forward_audit_table)) else character()
  context_coverage_ok <- length(expected_contexts) > 0L &&
    setequal(expected_contexts, observed_contexts)
  role_coverage_ok <- context_coverage_ok && all(vapply(expected_contexts, function(key) {
    rows <- forward_audit_table[context_key(forward_audit_table) == key, , drop = FALSE]
    sum(rows$role == "negative_sd") == 1L &&
      sum(rows$role == "nearest_valid_sd") == 1L &&
      all(rows$native_zero_coverage_mask[rows$role == "nearest_valid_sd"] %in% FALSE) &&
      all(rows$comparator_finite_q_mean_sd_p[rows$role == "nearest_valid_sd"] %in% TRUE)
  }, logical(1)))
  feature_reconstruction_error <- if (nrow(forward_audit_table) > 0L)
    max(forward_audit_table$max_feature_reconstruction_abs_error) else Inf
  forward_reconstruction_error <- if (nrow(forward_audit_table) > 0L)
    max(forward_audit_table$max_forward_reconstruction_abs_error) else Inf
  scorer_reconstruction_error <- if (nrow(forward_audit_table) > 0L)
    max(forward_audit_table$max_scorer_output_abs_error) else Inf
  forward_reconstruction_gate <- if (role_coverage_ok &&
                                        is.finite(feature_reconstruction_error) &&
                                        feature_reconstruction_error <= forward_tolerance &&
                                        is.finite(forward_reconstruction_error) &&
                                        is.finite(scorer_reconstruction_error) &&
                                        forward_reconstruction_error <= forward_tolerance &&
                                        scorer_reconstruction_error <= forward_tolerance) {
    "PASS_RECONSTRUCTED_SELECTED_ROWS"
  } else {
    "BLOCKED_RECONSTRUCTION_MISMATCH_OR_NO_ROWS"
  }
  data.table::fwrite(calls_table, file.path(diagnostic_dir, "pnorm_calls.tsv"), sep = "\t", na = "NA")
  data.table::fwrite(positions_table, file.path(diagnostic_dir, "pnorm_positions.tsv"), sep = "\t", na = "NA")
  data.table::fwrite(forward_audit_table,
                     file.path(diagnostic_dir, "dispersion_forward_audit.tsv"),
                     sep = "\t", na = "NA")
  manifest <- list(
    diagnostic = "PRINT pnorm observational replay on existing V5 eight-peak cache",
    print_commit = "8dad7317c3a640454a191dba2acd138e6edc54ac",
    peak_rows = 8L, radii = c(10L, 20L),
    scorer_passes = c("native_replay_1", "native_replay_2"),
    warning_count_scope = "reported separately per replay/pass/path/peak/radius/flank in pnorm_calls.tsv",
    scorer_paths = c("pseudobulk_matrix", "cell_type_score"),
    warning_muffling = FALSE, score_or_event_outputs_rewritten = FALSE,
    input_hashes_before_after_identical = TRUE,
    inputs = as.list(before_hashes),
    diagnostic_outputs = list(calls = "pnorm_calls.tsv", positions = "pnorm_positions.tsv",
                              forward_audit = "dispersion_forward_audit.tsv"),
    forward_reconstruction_tolerance = forward_tolerance,
    forward_audit_expected_context_count = length(expected_contexts),
    forward_audit_observed_context_count = length(observed_contexts),
    forward_audit_context_coverage_pass = context_coverage_ok,
    forward_audit_role_coverage_pass = role_coverage_ok,
    forward_audit_feature_reconstruction_max_abs_error = feature_reconstruction_error,
    forward_reconstruction_gate = forward_reconstruction_gate,
    forward_reconstruction_max_abs_error = forward_reconstruction_error,
    scorer_reconstruction_max_abs_error = scorer_reconstruction_error,
    warning_counts_by_context_file = "pnorm_calls.tsv",
    warning_counts_are_not_claimed_to_reproduce_the_historical_v5_context = TRUE,
    historical_v5_warning_count_reference = 28L,
    historical_v5_warning_comparability = "NOT_ESTABLISHED_CONTEXTS_DIFFER",
    diagnostic_warning_count = gate_summary$diagnostic_warning_count,
    warnings_without_elementwise_anomaly = gate_summary$warnings_without_elementwise_anomaly,
    unclassified_warning_count = gate_summary$unclassified_warning_count,
    logged_anomaly_position_rows = sum(!is.na(positions_table$genomic_position_0based)),
    warning_only_call_rows_without_elementwise_anomaly = sum(is.na(positions_table$genomic_position_0based)),
    unique_peak_radius_path_flank_positions = if (nrow(positions_table))
      data.table::uniqueN(positions_table[!is.na(genomic_position_0based),
                                         .(peak_row, radius, scorer_pass, scorer_path,
                                           flank, genomic_position_0based)]) else 0L,
    anomalous_positions_native_masked = sum(positions_table$native_zero_coverage_mask %in% TRUE, na.rm = TRUE),
    anomalous_positions_not_masked = gate_summary$anomaly_positions_not_masked,
    anomaly_positions_with_unknown_mask = gate_summary$anomaly_positions_with_unknown_mask,
    current_replay_anomaly_gate = gate_summary$current_replay_anomaly_gate,
    scale_up_warning_gate = gate_summary$scale_up_warning_gate,
    input_hash_scope = "all input bytes hashed before diagnostic source/readRDS/fread; own script bytes recorded after Rscript launch; unpinned count/bias/model caches are frozen at diagnostic start, not asserted to match original V5 bytes",
    input_hashes_before = as.list(before_hashes),
    input_hashes_after = as.list(after_hashes),
    R_version = R.version.string,
    package_versions = as.list(vapply(c("GenomicRanges", "data.table", "dplyr", "Matrix",
                                        "caTools", "cladoRcpp"),
                                      function(pkg) as.character(utils::packageVersion(pkg)),
                                      character(1)))
  )
  jsonlite::write_json(manifest, file.path(diagnostic_dir, "manifest.json"),
                       auto_unbox = TRUE, pretty = TRUE, null = "null")
  cat(jsonlite::toJSON(manifest, auto_unbox = TRUE, pretty = TRUE), "\n")
}

main <- function(args) {
  audit <- new.env(parent = emptyenv())
  run_with_integrity_guard(function() main_impl(args, audit), audit)
}

native_events_for_region <- function(result, chromosome, start0) {
  if (is.null(result$footprintRanges) || !length(result$footprintRanges)) {
    return(data.table::data.table(chrom = character(), start = integer(), end = integer(), score = numeric()))
  }
  ranges <- result$footprintRanges
  coordinates <- lapply(seq_along(ranges), function(i) {
    c(start = start0 + IRanges::start(ranges)[i] - 1L,
      end = start0 + IRanges::end(ranges)[i])
  })
  data.table::data.table(
    chrom = chromosome,
    start = vapply(coordinates, `[[`, integer(1), "start"),
    end = vapply(coordinates, `[[`, integer(1), "end"),
    score = result$aggregateScores[result$summits]
  )
}

if (sys.nframe() == 0L) {
  trailing <- commandArgs(trailingOnly = TRUE)
  tryCatch(if (identical(trailing, "--self-test")) run_self_test() else main(trailing), error = function(e) {
    message("PRINT_PNORM_DIAGNOSTIC_FAIL: ", conditionMessage(e))
    quit(status = 2L)
  })
}
