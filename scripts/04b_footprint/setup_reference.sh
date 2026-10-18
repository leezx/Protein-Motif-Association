#!/bin/bash
# Rebuild hg38 FASTA + FAI as a validated pair. The marker is installed last.
pma_prepare_reference() {
  local fa=$1 source_gz=$2 work_dir=$3 samtools=$4
  local ref_dir marker marker_tmp stamp interrupted tmp
  ref_dir=$(dirname "$fa")
  marker="$fa.setup.sha256"

  # Reuse only a pair installed by this helper whose two files still match the
  # checksums recorded after a successful faidx. A non-empty FAI alone is not
  # evidence that indexing finished.
  if [ -s "$fa" ] && [ -s "$fa.fai" ] && [ -s "$marker" ] \
      && (cd "$ref_dir" && sha256sum -c "$(basename "$marker")" >/dev/null 2>&1); then
    return 0
  fi

  stamp=$(date +%Y%m%dT%H%M%S).$$
  interrupted="$work_dir/setup_interrupted/$stamp"
  if [ -e "$fa" ] || [ -e "$fa.fai" ] || [ -e "$marker" ]; then
    mkdir -p "$interrupted"
    [ ! -e "$fa" ] || mv "$fa" "$interrupted/hg38.fa"
    [ ! -e "$fa.fai" ] || mv "$fa.fai" "$interrupted/hg38.fa.fai"
    [ ! -e "$marker" ] || mv "$marker" "$interrupted/hg38.fa.setup.sha256"
  fi

  tmp="$ref_dir/.hg38.fa.tmp.$stamp"
  marker_tmp="$ref_dir/.hg38.fa.setup.sha256.tmp.$stamp"
  if ! gunzip -c "$source_gz" > "$tmp" || [ ! -s "$tmp" ]; then
    mkdir -p "$interrupted"
    [ ! -e "$tmp" ] || mv "$tmp" "$interrupted/hg38.fa.tmp"
    return 1
  fi
  if ! "$samtools" faidx "$tmp" || [ ! -s "$tmp.fai" ]; then
    mkdir -p "$interrupted"
    [ ! -e "$tmp" ] || mv "$tmp" "$interrupted/hg38.fa.tmp"
    [ ! -e "$tmp.fai" ] || mv "$tmp.fai" "$interrupted/hg38.fa.tmp.fai"
    return 1
  fi

  # Both are staged in the reference directory so each rename stays on the
  # same filesystem. The checksum marker is the final commit record.
  mv "$tmp" "$fa"
  mv "$tmp.fai" "$fa.fai"
  (cd "$ref_dir" && sha256sum hg38.fa hg38.fa.fai > "$(basename "$marker_tmp")")
  mv "$marker_tmp" "$marker"
}
