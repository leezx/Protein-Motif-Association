#!/bin/bash
# Context Query v0.1 (HT29 dTAG-SOX9 x PMA): manifest + SGE jobs for 45 (counts), 46 (PMA evidence), 47 (DESeq2).
# usage: bash 45_47_context_query_jobs.sh <code_dir> <out_root>    (run on argos-qsub1; jobs go to all.q)
set -euo pipefail
CODE=$1; OUT=$2
B=/home/zz950/projects/BAF_SOX9/data
PMA=/home/zz950/DATA/2.PROJECTS/PMA
E=/home/zz950/softwares/miniforge3/envs/pmafp/bin
RS="/home/zz950/softwares/miniconda3/envs/r4p3/bin/Rscript"
set +u; source /opt/sge/default/common/settings.sh; set -u
mkdir -p $OUT/counts $OUT/pma $OUT/logs
M=$OUT/counts/manifest.tsv
printf "sample\tassay\ttime\trep\tbam\tpeaks\n" > $M
for t in DMSO D2 D4 D7 D10 D13; do for r in 1 2; do
  printf "%s\tATAC\t%s\t%s\t%s\t%s\n" ${t}_$r $t $r $B/atac_pipeline/3.bam/${t}_$r.sorted.mapped.bam \
    $B/atac_pipeline/6.peak/macs_tag_peak/${t}_$r.tagAlign_peaks.narrowPeak >> $M
  for a in SOX9 SMARCC1 IgG; do
    s=${t}_${a}_$r; bam=$B/cutrun_pipeline/3.bam/$s.sorted.mapped.bam
    [ -f $bam ] || continue
    pk=$B/cutrun_pipeline/6.peak/macs_no_IgG_bam/$s.sorted.mapped.bam_peaks.narrowPeak; [ -f $pk ] || pk=.
    printf "%s\t%s\t%s\t%s\t%s\t%s\n" $s $a $t $r $bam $pk >> $M
  done
done; done
ENV="export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PATH=$E:\$PATH"
j45=$(echo "$ENV; $E/python $CODE/45_ht29_dtag_counts.py $M $OUT/counts 8" | \
  qsub -terse -q all.q -pe smp 8 -l h_vmem=5G -N cq45 -o $OUT/logs/45.log -j y -cwd)
js=""
for c in $(seq 1 22) X; do
  j=$(echo "$ENV; $E/python $CODE/46_ht29_pma_evidence.py chrom $OUT/counts/regions.bed \
$PMA/occupancy_chipatlas/processed/v1/PMA_chipatlas_hg38_occupancy.bed.gz $OUT/pma chr$c" | \
    qsub -terse -q all.q -pe smp 1 -l h_vmem=16G -hold_jid $j45 -N cq46_$c -o $OUT/logs/46.chr$c.log -j y -cwd)
  js="$js,$j"
done
R=$PMA/occupancy_chipatlas/result
j46=$(echo "$ENV; $E/python $CODE/46_ht29_pma_evidence.py annotate $OUT/counts/regions.bed \
$R/hotspot_thresholds_v1/bins500.npz $R/hotspot_annotation_v1/bins_annotation.npz \
$PMA/motif_reference/processed/v0.3_raw_layer/PMA_motifs_raw.meme HO14_SOX9.H14CORE.0.PS.A \
/home/zz950/reference/bwa_wgs/resources_broad_hg38_v0_Homo_sapiens_assembly38.fasta $OUT/pma 1e-4" | \
  qsub -terse -q all.q -pe smp 1 -l h_vmem=24G -hold_jid ${js#,} -N cq46a -o $OUT/logs/46.annotate.log -j y -cwd)
j47=$(echo "$ENV; R_LIBS_USER=/home/zz950/softwares/R_lib_4 $RS $CODE/47_ht29_dtag_deseq.R $OUT/counts $B/cutrun_pipeline" | \
  qsub -terse -q all.q -pe smp 1 -l h_vmem=24G -hold_jid $j45 -N cq47 -o $OUT/logs/47.log -j y -cwd)
echo "jobs: 45=$j45 46=${js#,} 46a=$j46 47=$j47"
# Review round 1 (run separately): 50 (SOX motifs) then 51 (checks)
#   python 50_sox_motif_scan.py $OUT/counts/regions.bed <meme> <fasta> $OUT/pma/sox_motifs.tsv.gz 1e-4
#   Rscript 51_ht29_review_checks.R $OUT
