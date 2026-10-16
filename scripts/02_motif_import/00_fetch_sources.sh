#!/usr/bin/env bash
# Step 2: fetch HOCOMOCO v14, CisBP 3.10 (human), Factorbook motif catalogs
# into DATA raw/<source>/<date>/. Append-only; writes source_manifest.tsv + checksums.md5.
set -euo pipefail
source "$(dirname "$0")/../../config/pma_env.sh"

DATE="${PMA_FETCH_DATE:-2026-10-14}"
UA="Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15 Safari/605.1.15"

fetch() {  # fetch <dir> <out_name> <url>
  local dir=$1 out=$2 url=$3
  if [[ ! -s "$dir/$out" ]]; then curl -sfL -A "$UA" -o "$dir/$out" "$url"; fi
  printf '%s\t%s\t%s\t%s\n' "$out" "$DATE" "$url" "$(wc -c < "$dir/$out" | tr -d ' ')" >> "$dir/source_manifest.tsv"
}
start() { mkdir -p "$1"; printf 'file\tfetch_date\turl\tbytes\n' > "$1/source_manifest.tsv"; }
finalize() {
  ( cd "$1"
    for z in *.zip; do [[ -e "$z" ]] || continue
      [[ -d "unpacked/${z%.zip}" ]] || { mkdir -p unpacked; unzip -q -o "$z" -d "unpacked/${z%.zip}"; }; done
    for g in *.gz; do [[ -e "$g" ]] || continue
      mkdir -p unpacked; [[ -s "unpacked/${g%.gz}" ]] || gunzip -c "$g" > "unpacked/${g%.gz}"; done
    find . -type f ! -name checksums.md5 ! -name source_manifest.tsv ! -path '*/__MACOSX/*' \
      | sort | xargs md5 -r > checksums.md5 )
}

# HOCOMOCO v14 (website final bundle; no versioned Zenodo record for v14 as of fetch date)
HB=https://hocomoco14.autosome.org/final_bundle/hocomoco14
HO="$PMA_MOTIF_RAW/hocomoco_v14/$DATE"; start "$HO"
fetch "$HO" H14CORE_meme_format.meme   "$HB/H14CORE/formatted_motifs/H14CORE_meme_format.meme"
fetch "$HO" H14CORE_pcms.txt           "$HB/H14CORE/formatted_motifs/H14CORE_pcms.txt"
fetch "$HO" H14CORE_annotation.jsonl   "$HB/H14CORE/H14CORE_annotation.jsonl"
fetch "$HO" H14INVITRO_annotation.jsonl "$HB/H14INVITRO/H14INVITRO_annotation.jsonl"
fetch "$HO" H14INVIVO_annotation.jsonl  "$HB/H14INVIVO/H14INVIVO_annotation.jsonl"
fetch "$HO" H14CORE-CLUSTERED_cluster_list.tsv "$HB/H14CORE-CLUSTERED/cluster_list.tsv"
fetch "$HO" H14CORE-CLUSTERED_annotation.jsonl "$HB/H14CORE-CLUSTERED/H14CORE-CLUSTERED_annotation.jsonl"
fetch "$HO" tf_masterlist.tsv           "$HB/tf_masterlist.tsv"
finalize "$HO"

# CisBP 3.10 human species archive (PWMs + TF_Information). The archive is generated
# on demand via POST bulk_archive.php and served from a temporary URL.
CI="$PMA_MOTIF_RAW/cisbp_3_10/$DATE"; mkdir -p "$CI"
if [[ ! -s "$CI/CisBP_3_10_Homo_sapiens_PWMs_TFinfo.zip" ]]; then
  jar=$(mktemp); curl -sL -A "$UA" -c "$jar" -b "$jar" https://cisbp.ccbr.utoronto.ca/bulk.php -o /dev/null
  tmpurl=$(curl -sL -A "$UA" -c "$jar" -b "$jar" -X POST https://cisbp.ccbr.utoronto.ca/bulk_archive.php \
    --data 'selSpec=Homo_sapiens&Spec[]=PWMs&Spec[]=TF_Information&submit=Download Species Archive!' \
    | grep -o 'tmp/[^"]*\.zip' | head -1)
  curl -sfL -A "$UA" -b "$jar" -o "$CI/CisBP_3_10_Homo_sapiens_PWMs_TFinfo.zip" "https://cisbp.ccbr.utoronto.ca/$tmpurl"
fi
printf 'file\tfetch_date\turl\tbytes\n%s\t%s\t%s\t%s\n' CisBP_3_10_Homo_sapiens_PWMs_TFinfo.zip "$DATE" \
  "https://cisbp.ccbr.utoronto.ca/bulk_archive.php (POST selSpec=Homo_sapiens, PWMs+TF_Information; build 3.10, updated 2026-04-26)" \
  "$(wc -c < "$CI/CisBP_3_10_Homo_sapiens_PWMs_TFinfo.zip" | tr -d ' ')" > "$CI/source_manifest.tsv"
# Matrices: the species archive's PWMs_all_motifs interleaves unzip log lines with matrices
# (ambiguous ID mapping), so per-motif files come from the entire-dataset PWMs.zip.
fetch "$CI" EntireDataset_PWMs.zip https://cisbp.ccbr.utoronto.ca/data/3_10/DataFiles/Bulk_downloads/EntireDataset/PWMs.zip
finalize "$CI"

# Factorbook (Weng lab) motif catalogs
FB="$PMA_MOTIF_RAW/factorbook/$DATE"; start "$FB"
fetch "$FB" factorbook_chip_seq_meme_motif_catalog.meme.gz https://downloads.wenglab.org/factorbook_chip_seq_meme_motif_catalog.meme.gz
fetch "$FB" factorbook_chip_seq_meme_motifs.tsv            https://downloads.wenglab.org/factorbook_chip_seq_meme_motifs.tsv
# HT-SELEX catalog: factorbook.org answers scripted requests with HTTP 429 (bot protection).
# If the file was placed here manually (browser download), it is recorded; otherwise skipped.
if [[ -s "$FB/all-selex-motifs.meme.gz" ]] || curl -sfL -A "$UA" -o "$FB/all-selex-motifs.meme.gz" https://www.factorbook.org/motifscatlog/all-selex-motifs.meme.gz; then
  printf '%s\t%s\t%s\t%s\n' all-selex-motifs.meme.gz "$DATE" https://www.factorbook.org/motifscatlog/all-selex-motifs.meme.gz \
    "$(wc -c < "$FB/all-selex-motifs.meme.gz" | tr -d ' ')" >> "$FB/source_manifest.tsv"
else
  rm -f "$FB/all-selex-motifs.meme.gz"; echo "WARN: Factorbook HT-SELEX catalog not fetched (HTTP 429); deferred" >&2
fi
finalize "$FB"
echo "fetched: $HO $CI $FB"
