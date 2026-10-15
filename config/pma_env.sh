# PMA path config. Source from scripts; never hard-code mount paths elsewhere.
# Requires the workspace setup_env.sh (BIOWORKSPACE_ROOT, BIO_DATA, BIO_SOFTWARES).
if [[ -z "${BIO_DATA:-}" ]]; then
  _ws="${BIOWORKSPACE_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)}"
  source "$_ws/setup_env.sh" > /dev/null
fi
export PMA_DATA="${BIO_DATA}/2.PROJECTS/PMA"
export PMA_MOTIF="${PMA_DATA}/motif_reference"
export PMA_MOTIF_RAW="${PMA_MOTIF}/raw"
export PMA_MOTIF_PROCESSED="${PMA_MOTIF}/processed"
export PMA_MOTIF_RESULT="${PMA_MOTIF}/result"
export PMA_MEME_BIN="${BIO_SOFTWARES}/tools/meme-5.5.9/bin"
export PMA_HGNC_MAP="${BIO_DATA}/1.Databases/HGNC_gene_id_mapping/processed/v0.1/hgnc_symbol_ensembl_map.tsv"
