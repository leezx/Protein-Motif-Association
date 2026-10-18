#!/bin/bash
# Build a BAM into a temporary path, validate its index, and only then publish it as a reusable cache.
set -euo pipefail
PYTHON=$1; SAMTOOLS=$2; CONVERTER=$3; FRAGS=$4; SIZES=$5; REGIONS=$6; BAM=$7
validate_bam() {
  "$SAMTOOLS" quickcheck "$1" >/dev/null 2>&1 &&
    "$PYTHON" -c 'import pysam,sys; f=pysam.AlignmentFile(sys.argv[1],"rb"); f.check_index(); f.close()' "$1" \
      >/dev/null 2>&1 && { [ -s "$1.bai" ] || [ -s "${1%.bam}.bai" ]; }
}

if validate_bam "$BAM"; then
  exit 0
fi

bam_dir=$(dirname "$BAM")
mkdir -p "$bam_dir"
if [ -e "$BAM" ] || [ -e "$BAM.bai" ] || [ -e "${BAM%.bam}.bai" ]; then
  archive="$bam_dir/invalid_cache_archive/$(date -u +%Y%m%dT%H%M%SZ)_$$/$(basename "$BAM")"
  mkdir -p "$archive"
  for path in "$BAM" "$BAM.bai" "${BAM%.bam}.bai"; do
    [ ! -e "$path" ] || mv "$path" "$archive/"
  done
fi

tmp="$bam_dir/.building_$(basename "$BAM" .bam)_$$.bam"
cleanup() {
  rm -f "$tmp" "$tmp.bai" "${tmp%.bam}.bai" "$tmp.unsorted.bam"
}
trap cleanup EXIT
  "$PYTHON" "$CONVERTER" "$FRAGS" "$SIZES" "$REGIONS" "$tmp" \
  || { echo "BAM_CONVERSION_FAIL $BAM" >&2; exit 1; }
validate_bam "$tmp" || { echo "BAM_VALIDATION_FAIL $BAM" >&2; exit 1; }
mv "$tmp" "$BAM"
if [ -e "$tmp.bai" ]; then
  mv "$tmp.bai" "$BAM.bai"
else
  mv "${tmp%.bam}.bai" "${BAM%.bam}.bai"
fi
