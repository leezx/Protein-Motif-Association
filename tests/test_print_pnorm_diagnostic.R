source(file.path("scripts", "04b_footprint", "diagnose_print_pnorm.R"))
run_self_test()

call_row <- data.frame(
  warning_count = 1L, unclassified_warning_count = 0L,
  anomaly_positions = 1L
)
masked_position <- data.frame(anomaly_position = TRUE,
                              native_zero_coverage_mask = TRUE)
gate <- summarize_diagnostic_gate(call_row, masked_position)
stopifnot(gate$current_replay_anomaly_gate == "PASS_CURRENT_REPLAY_ANOMALIES_ALL_MASKED",
          gate$scale_up_warning_gate == "BLOCKED_HISTORICAL_CONTEXT_NOT_REPRODUCED")

unknown_mask <- data.frame(anomaly_position = TRUE,
                           native_zero_coverage_mask = NA)
stopifnot(summarize_diagnostic_gate(call_row, unknown_mask)$current_replay_anomaly_gate ==
            "BLOCKED_UNKNOWN_MASK")
unmasked_position <- data.frame(anomaly_position = TRUE,
                                native_zero_coverage_mask = FALSE)
stopifnot(summarize_diagnostic_gate(call_row, unmasked_position)$current_replay_anomaly_gate ==
            "BLOCKED_UNMASKED_ANOMALY")

unlocated_warning <- transform(call_row, anomaly_positions = 0L)
stopifnot(summarize_diagnostic_gate(unlocated_warning, data.frame())$current_replay_anomaly_gate ==
            "BLOCKED_UNLOCATED_WARNING")

unknown_warning <- transform(call_row, unclassified_warning_count = 1L)
stopifnot(summarize_diagnostic_gate(unknown_warning, masked_position)$current_replay_anomaly_gate ==
            "BLOCKED_UNCLASSIFIED_WARNING")

historical_28 <- transform(call_row, warning_count = 28L)
stopifnot(summarize_diagnostic_gate(historical_28, masked_position)$scale_up_warning_gate ==
            "BLOCKED_HISTORICAL_CONTEXT_NOT_REPRODUCED")

existing_dir <- tempfile("print-diagnostic-existing-")
dir.create(existing_dir)
output_guard_error <- tryCatch({
  assert_new_output_path(existing_dir)
  NULL
}, error = identity)
stopifnot(inherits(output_guard_error, "error"),
          grepl("already exists", conditionMessage(output_guard_error)))
unlink(existing_dir, recursive = TRUE)

guard_dir <- tempfile("print-diagnostic-integrity-")
dir.create(guard_dir)
guard_file <- file.path(guard_dir, "cache.rds")
writeLines("frozen", guard_file)
guard_path <- normalizePath(guard_file)
guard_audit <- new.env(parent = emptyenv())
guard_audit$paths <- guard_path
guard_audit$before_hashes <- setNames(sha256_file(guard_path), guard_path)
primary_failure <- tryCatch(run_with_integrity_guard(
  function() stop("simulated primary failure"), guard_audit
), error = identity)
stopifnot(inherits(primary_failure, "error"),
          identical(conditionMessage(primary_failure), "simulated primary failure"))

writeLines("changed", guard_file)
dual_failure <- tryCatch(run_with_integrity_guard(
  function() stop("simulated primary failure"), guard_audit
), error = identity)
stopifnot(inherits(dual_failure, "error"),
          grepl("simulated primary failure", conditionMessage(dual_failure)),
          grepl("post-error integrity verification also failed", conditionMessage(dual_failure)))
unlink(guard_dir, recursive = TRUE)

cat("PRINT pnorm diagnostic gate/hash/output-guard tests PASS\n")
