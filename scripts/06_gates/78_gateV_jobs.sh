#!/bin/bash
# Gate V feature preparation on Argos SGE (no model): regions -> 46 chrom (PMA_EXCL_CELL=K-562) -> 46 annotate ->
# 50 GATA motifs -> 78 features (ATAC prior, K562 histone, PMA matrices without K-562); 76 rerun for peak_table.
# usage: bash 78_gateV_jobs.sh <code_dir (04a_chipatlas/, 06_gates/)> <gateV root>      (run on argos-qsub1)
set -euo pipefail
CODE=$1; OUT=$2
PMA=/home/zz950/DATA/2.PROJECTS/PMA
P=$PMA/occupancy_chipatlas
E=/home/zz950/softwares/miniforge3/envs/pmafp/bin
RS="/home/zz950/softwares/miniconda3/envs/r4p3/bin/Rscript"
FA=/home/zz950/reference/bwa_wgs/resources_broad_hg38_v0_Homo_sapiens_assembly38.fasta
MEME=$PMA/motif_reference/processed/v0.3_raw_layer/PMA_motifs_raw.meme
RAW=$P/raw/2026-10-30_gse168851/GSE168851_scATAC_K562_LargeScreen_Peak_Matrix_SE.rds.gz
C4=$CODE/04a_chipatlas; C6=$CODE/06_gates
set +u; source /opt/sge/default/common/settings.sh; set -u
mkdir -p $OUT/pma $OUT/logs
ENV="export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PMA_EXCL_CELL=K-562 PATH=$E:\$PATH"
$E/python $C6/78_gateV_features.py regions $OUT/inventory/peaks.bed.gz $OUT
js=""
for c in $(seq 1 22) X; do
  j=$(echo "$ENV; $E/python $C4/46_ht29_pma_evidence.py chrom $OUT/counts/regions.bed $P/processed/v1/PMA_chipatlas_hg38_occupancy.bed.gz $OUT/pma chr$c" | \
    qsub -terse -q all.q -pe smp 1 -l h_vmem=16G -N gv46_$c -o $OUT/logs/46.chr$c.log -j y -cwd)
  js="$js,$j"
done
R=$P/result
j46=$(echo "$ENV; $E/python $C4/46_ht29_pma_evidence.py annotate $OUT/counts/regions.bed $R/hotspot_thresholds_v1/bins500.npz \
$R/hotspot_annotation_v1/bins_annotation.npz $MEME HO14_GATA1.H14CORE.1.PSM.A $FA $OUT/pma 1e-4" | \
  qsub -terse -q all.q -pe smp 1 -l h_vmem=24G -hold_jid ${js#,} -N gv46a -o $OUT/logs/46.annotate.log -j y -cwd)
j50=$(echo "$ENV PMA_MOTIF_LABEL=gata PMA_MOTIFS=GATA1a=HO14_GATA1.H14CORE.0.P.B,GATA1b=HO14_GATA1.H14CORE.1.PSM.A,GATA2a=HO14_GATA2.H14CORE.0.PSM.A,GATA2b=HO14_GATA2.H14CORE.1.P.B; \
$E/python $C4/50_sox_motif_scan.py $OUT/counts/regions.bed $MEME $FA $OUT/pma/gata_motifs.tsv.gz 1e-4" | \
  qsub -terse -q all.q -pe smp 1 -l h_vmem=16G -N gv50 -o $OUT/logs/50.log -j y -cwd)
j78=$(echo "$ENV; $E/python $C6/78_gateV_features.py features $OUT $P/processed/atac_v1/PMA_chipatlas_hg38_atac_occupancy.bed.gz \
$P/processed/histone_v1/PMA_chipatlas_hg38_histone_occupancy.bed.gz $P/processed/v1/PMA_chipatlas_hg38_experiments.tsv.gz 4" | \
  qsub -terse -q all.q -pe smp 4 -l h_vmem=12G -hold_jid $j46 -N gv78 -o $OUT/logs/78.log -j y -cwd)
j76=$(echo "export OMP_NUM_THREADS=1; T=\$TMPDIR/k562.rds; gunzip -c $RAW > \$T && R_LIBS_USER=/home/zz950/softwares/R_lib_4 $RS \
$C6/76_gateV_outcome.R \$T $OUT/inventory/gata1_chip.tsv.gz $OUT/outcome; rm -f \$T" | \
  qsub -terse -q all.q -l h_vmem=40G -N gv76 -o $OUT/logs/76.log -j y -cwd)
echo "jobs: 46=${js#,} 46a=$j46 50=$j50 78=$j78 76=$j76"
