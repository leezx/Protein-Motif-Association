#!/bin/bash
# Step 4b-1 setup on Argos: unpack PRINT shared resources, index hg38, point RGT (HINT-ATAC) at the genome.
# usage: 00_setup.sh <raw_dir> <work_dir> <env_prefix> <chrom.sizes>
set -euo pipefail
RAW=$1; W=$2; ENV=$3; SIZES=$4
mkdir -p $W/print_shared
cd $W/print_shared
if [ ! -d dispModel ]; then mkdir -p dispModel && tar -xzf $RAW/print_zenodo/dispModel.tar.gz -C dispModel --strip-components=0; fi
find dispModel -name "dispersionModel10bp.rds" | head -1
D10=$(dirname $(find dispModel -name "dispersionModel10bp.rds" | head -1)); [ "$D10" != "dispModel" ] && { mv $D10/* dispModel/ 2>/dev/null || true; }
if [ ! -s precomputedTn5Bias/hg38Tn5Bias.h5 ]; then
  mkdir -p precomputedTn5Bias && tar -xzf $RAW/print_zenodo/hg38Tn5Bias.tar.gz -C precomputedTn5Bias
  H=$(find precomputedTn5Bias -name "*.h5" | head -1); [ "$H" != "precomputedTn5Bias/hg38Tn5Bias.h5" ] && mv "$H" precomputedTn5Bias/hg38Tn5Bias.h5
fi
cp -n $RAW/print_zenodo/Tn5_NN_model.h5 .
ls -ld precomputedTn5Bias dispModel
cp -n $SIZES $W/hg38.chrom.sizes
FA=$RAW/reference/hg38.fa
if [ ! -s "$FA.fai" ]; then
  # Preserve an unindexed file from an interrupted extraction, then rebuild from the immutable gzip source.
  if [ -s "$FA" ]; then
    mkdir -p "$W/setup_interrupted"
    mv "$FA" "$W/setup_interrupted/hg38.fa.no_fai.$(date +%Y%m%dT%H%M%S)"
  fi
  TMP=$RAW/reference/.hg38.fa.tmp.$$
  gunzip -c "$RAW/reference/hg38.fa.gz" > "$TMP"
  [ -s "$TMP" ]
  mv "$TMP" "$FA"
  $ENV/bin/samtools faidx "$FA"
fi
# RGT: genome path for hg38 (data.config.user overrides data.config)
CFG=$HOME/rgtdata/data.config.user
grep -q "^\[hg38\]" $CFG 2>/dev/null || printf "\n[hg38]\ngenome: %s\nchromosome_sizes: %s\n" $RAW/reference/hg38.fa $W/hg38.chrom.sizes >> $CFG
echo SETUP_OK
