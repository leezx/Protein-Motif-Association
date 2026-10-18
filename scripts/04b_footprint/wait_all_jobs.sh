#!/bin/bash
# Source this file after defining indexed arrays named pids and labels.
wait_all_jobs() {
  local i rc failed=0
  for i in "${!pids[@]}"; do
    if wait "${pids[$i]}"; then
      rc=0
    else
      rc=$?
      printf 'CALLER_FAILURE %s pid=%s status=%s\n' \
        "${labels[$i]}" "${pids[$i]}" "$rc" >&2
      failed=1
    fi
  done
  [ "$failed" -eq 0 ]
}
