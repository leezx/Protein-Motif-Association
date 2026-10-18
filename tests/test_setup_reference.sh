#!/bin/bash
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
source "$ROOT/scripts/04b_footprint/setup_reference.sh"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

mkdir -p "$TMP/bin"
cat > "$TMP/bin/samtools" <<'MOCK'
#!/bin/bash
set -euo pipefail
[ "$1" = faidx ]
fa=$2
awk 'BEGIN{OFS="\t"} /^>/{if (name!="") print name,n,0,n,n+1; name=substr($0,2); n=0; next} {n+=length($0)} END{if (name!="") print name,n,0,n,n+1}' "$fa" > "$fa.fai"
MOCK
chmod +x "$TMP/bin/samtools"

new_case() {
  local name=$1
  mkdir -p "$TMP/$name/raw/reference" "$TMP/$name/work"
  printf '>chr1\nACGTACGT\n>chr2\nTTAA\n' | gzip -c > "$TMP/$name/raw/reference/hg38.fa.gz"
}
assert_rebuilt() {
  local name=$1
  cmp "$TMP/$name/raw/reference/hg38.fa" <(gzip -dc "$TMP/$name/raw/reference/hg38.fa.gz")
  [ -s "$TMP/$name/raw/reference/hg38.fa.fai" ]
  [ -s "$TMP/$name/raw/reference/hg38.fa.setup.sha256" ]
}

# Partial FASTA without an index.
new_case partial_fasta
printf '>chr1\nACG' > "$TMP/partial_fasta/raw/reference/hg38.fa"
pma_prepare_reference "$TMP/partial_fasta/raw/reference/hg38.fa" "$TMP/partial_fasta/raw/reference/hg38.fa.gz" "$TMP/partial_fasta/work" "$TMP/bin/samtools"
assert_rebuilt partial_fasta
test -n "$(find "$TMP/partial_fasta/work/setup_interrupted" -name hg38.fa -print -quit)"

# A non-empty but incomplete index cannot be trusted without a matching marker.
new_case partial_index
printf '>chr1\nACG' > "$TMP/partial_index/raw/reference/hg38.fa"
printf 'chr1\t999\t0\t999\t1000\n' > "$TMP/partial_index/raw/reference/hg38.fa.fai"
pma_prepare_reference "$TMP/partial_index/raw/reference/hg38.fa" "$TMP/partial_index/raw/reference/hg38.fa.gz" "$TMP/partial_index/work" "$TMP/bin/samtools"
assert_rebuilt partial_index
[ -s "$(find "$TMP/partial_index/work/setup_interrupted" -name 'hg38.fa.fai' -print -quit)" ]

# A valid installed pair is reused byte-for-byte and without reindexing.
new_case valid_pair
pma_prepare_reference "$TMP/valid_pair/raw/reference/hg38.fa" "$TMP/valid_pair/raw/reference/hg38.fa.gz" "$TMP/valid_pair/work" "$TMP/bin/samtools"
before=$(sha256sum "$TMP/valid_pair/raw/reference/hg38.fa" "$TMP/valid_pair/raw/reference/hg38.fa.fai")
pma_prepare_reference "$TMP/valid_pair/raw/reference/hg38.fa" "$TMP/valid_pair/raw/reference/hg38.fa.gz" "$TMP/valid_pair/work" "$TMP/bin/samtools"
after=$(sha256sum "$TMP/valid_pair/raw/reference/hg38.fa" "$TMP/valid_pair/raw/reference/hg38.fa.fai")
[ "$before" = "$after" ]
[ -z "$(find "$TMP/valid_pair/work/setup_interrupted" -type f -print -quit 2>/dev/null || true)" ]

# A stale index with a missing FASTA is archived and rebuilt.
new_case missing_fasta
printf 'chr1\t999\t0\t999\t1000\n' > "$TMP/missing_fasta/raw/reference/hg38.fa.fai"
pma_prepare_reference "$TMP/missing_fasta/raw/reference/hg38.fa" "$TMP/missing_fasta/raw/reference/hg38.fa.gz" "$TMP/missing_fasta/work" "$TMP/bin/samtools"
assert_rebuilt missing_fasta
[ -s "$(find "$TMP/missing_fasta/work/setup_interrupted" -name 'hg38.fa.fai' -print -quit)" ]

echo 'setup reference recovery fixtures: PASS (partial FASTA, partial FAI, valid pair reuse, missing FASTA + stale FAI)'
