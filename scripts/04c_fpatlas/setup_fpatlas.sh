#!/bin/bash
# PMA footprint atlas: alignment environment (chromap) + chromap hg38 index (primary assembly chr1-22, X, Y, M).
#$ -q all.q
#$ -pe smp 4
#$ -l h_vmem=100G,m_mem_free=12G
#$ -N fpatlas_setup
#$ -j y
#$ -cwd
set -eo pipefail
M=/home/zz950/softwares/miniforge3
REF=/home/zz950/DATA/2.PROJECTS/PMA/atac_footprint/processed/fpatlas_ref
FA=/home/zz950/DATA/2.PROJECTS/PMA/atac_footprint/raw/2026-10-17/reference/hg38.fa
date; hostname; df -h /tmp | tail -1; echo "TMPDIR=$TMPDIR"
[ -x $M/envs/pma_fpatlas/bin/aria2c ] || $M/bin/mamba create -y -n pma_fpatlas \
  --override-channels -c https://mirrors.tuna.tsinghua.edu.cn/anaconda/cloud/conda-forge \
  -c https://mirrors.tuna.tsinghua.edu.cn/anaconda/cloud/bioconda chromap=0.2.6 sra-tools=3.1.1 samtools=1.21 pigz aria2
E=$M/envs/pma_fpatlas/bin
$E/chromap --version 2>&1 | head -2; $E/aria2c --version | head -1; $E/fasterq-dump --version | head -2; $E/samtools --version | head -1
mkdir -p $REF && cd $REF
[ -s hg38_primary.fa.fai ] || { $E/samtools faidx $FA chr{1..22} chrX chrY chrM > hg38_primary.fa; $E/samtools faidx hg38_primary.fa; }
/usr/bin/time -v $E/chromap -i -r hg38_primary.fa -o hg38_primary.chromap.index > chromap_index.log 2>&1
cut -f1,2 hg38_primary.fa.fai > hg38_primary.chrom.sizes
cp /home/zz950/DATA/2.PROJECTS/PMA/atac_footprint/processed/round1/hg38-blacklist.v2.bed .
md5sum hg38_primary.fa > hg38_primary.fa.md5
$M/bin/conda list -n pma_fpatlas --explicit > pma_fpatlas.explicit.txt
grep -E "Elapsed|Maximum resident" chromap_index.log
ls -la; date; echo SETUP_DONE
