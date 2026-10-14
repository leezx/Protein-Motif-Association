#!/usr/bin/env bash
# Step 1 pilot: fetch Codebook 2026 + JASPAR 2026 sources into DATA raw/.
# Idempotent: existing files are kept (raw is append-only); a new DATE
# creates a new raw folder. Writes source_manifest.tsv + checksums.md5.
set -euo pipefail
source "$(dirname "$0")/../../config/pma_env.sh"

DATE="${PMA_FETCH_DATE:-2026-10-14}"
UA="Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15 Safari/605.1.15"
NAT='https://media.springernature.com/original/springer-static/esm/art%3A10.1038%2Fs41586-026-10798-9/MediaObjects/41586_2026_10798_'
JAS='https://jaspar.elixir.no/download'

fetch() {  # fetch <dir> <out_name> <url>
  local dir=$1 out=$2 url=$3
  mkdir -p "$dir"
  if [[ ! -s "$dir/$out" ]]; then
    curl -sfL -A "$UA" -o "$dir/$out" "$url"
  fi
  printf '%s\t%s\t%s\t%s\n' "$out" "$DATE" "$url" "$(wc -c < "$dir/$out" | tr -d ' ')" >> "$dir/source_manifest.tsv"
}

finalize() {  # write checksums + unpack zips once
  local dir=$1
  ( cd "$dir"
    for z in *.zip; do [[ -e "$z" ]] || continue
      [[ -d "unpacked/${z%.zip}" ]] || { mkdir -p unpacked; unzip -q -o "$z" -d "unpacked/${z%.zip}"; }; done
    find . -type f ! -name checksums.md5 ! -name source_manifest.tsv ! -path '*/__MACOSX/*' \
      | sort | xargs md5 -r > checksums.md5 )
}

CB="$PMA_MOTIF_RAW/codebook_2026/$DATE"
mkdir -p "$CB"; printf 'file\tfetch_date\turl\tbytes\n' > "$CB/source_manifest.tsv"
fetch "$CB" Nature2026_SupplementaryTables_MOESM3.zip "${NAT}MOESM3_ESM.zip"
fetch "$CB" Nature2026_SupplementaryData1_MOESM4.zip  "${NAT}MOESM4_ESM.zip"
for f in representative_motifs.zip groups.json README; do
  fetch "$CB" "zenodo17307845_$f" "https://zenodo.org/records/17307845/files/$f"; done
for f in README MEX_top1.zip metadata_complete_dataset.tsv; do
  fetch "$CB" "zenodo15667805_$f" "https://zenodo.org/records/15667805/files/$f"; done
finalize "$CB"

JA="$PMA_MOTIF_RAW/jaspar_2026/$DATE"
mkdir -p "$JA"; printf 'file\tfetch_date\turl\tbytes\n' > "$JA/source_manifest.tsv"
for f in JASPAR2026_CORE_vertebrates_non-redundant_pfms_meme.txt JASPAR2026_CORE_vertebrates_redundant_pfms_meme.txt \
         JASPAR2026_CORE_vertebrates_non-redundant_pfms_jaspar.txt JASPAR2026_CORE_vertebrates_redundant_pfms_jaspar.txt; do
  fetch "$JA" "$f" "$JAS/data/2026/CORE/$f"; done
fetch "$JA" JASPAR2026_UNVALIDATED_non-redundant_pfms_meme.txt "$JAS/data/2026/collections/JASPAR2026_UNVALIDATED_non-redundant_pfms_meme.txt"
fetch "$JA" JASPAR2026.sqlite "$JAS/database/JASPAR2026.sqlite"
fetch "$JA" api_CORE_vertebrates_latest_p1.json \
  "https://jaspar.elixir.no/api/v1/matrix/?collection=CORE&tax_group=vertebrates&version=latest&page_size=1000&format=json"
finalize "$JA"
echo "fetched: $CB $JA"
