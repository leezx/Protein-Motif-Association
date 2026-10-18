#!/bin/bash
# Source this file, then call prepare_bams with dataset, fragments, and regions triplets.
select_bam_cache_dir() {
  local work_dir=$1 smoke_mode=${2:-0}
  if [ "$smoke_mode" = 1 ]; then
    printf '%s/bam/smoke\n' "$work_dir"
  else
    printf '%s/bam/full\n' "$work_dir"
  fi
}

prepare_bams() {
  local python=$1 samtools=$2 converter=$3 sizes=$4 bam_dir=$5 d frags regions
  shift 5
  while [ "$#" -ge 3 ]; do
    d=$1; frags=$2; regions=$3
    bash "$(dirname "${BASH_SOURCE[0]}")/ensure_bam_cache.sh" \
      "$python" "$samtools" "$converter" "$frags" "$sizes" "$regions" "$bam_dir/$d.bam" \
      || { echo "BAM_PREP_FAIL $d" >&2; return 1; }
    shift 3
  done
  [ "$#" -eq 0 ]
}
