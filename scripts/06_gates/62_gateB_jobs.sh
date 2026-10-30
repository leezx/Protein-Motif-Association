#!/bin/bash
# Gate B (plan v0.2): baseline-only universe, counts, PMA evidence, SOX motifs and DESeq2 on Argos SGE.
# Reuses 45/46/47/50 of Context Query v0.1 unchanged; only the consensus step differs (62_gateB_counts.py).
# usage: bash 62_gateB_jobs.sh <code_dir (holds 04a_chipatlas/ and 06_gates/)> <out_root>   (run on argos-qsub1)
set -euo pipefail
CODE=$1; OUT=$2
B=/home/zz950/projects/BAF_SOX9/data
PMA=/home/zz950/DATA/2.PROJECTS/PMA
E=/home/zz950/softwares/miniforge3/envs/pmafp/bin
RS="/home/zz950/softwares/miniconda3/envs/r4p3/bin/Rscript"
FA=/home/zz950/reference/bwa_wgs/resources_broad_hg38_v0_Homo_sapiens_assembly38.fasta
MEME=$PMA/motif_reference/processed/v0.3_raw_layer/PMA_motifs_raw.meme
C4=$CODE/04a_chipatlas
set +u; source /opt/sge/default/common/settings.sh; set -u
mkdir -p $OUT/counts $OUT/pma $OUT/logs
M=$OUT/counts/manifest.tsv
printf "sample\tassay\ttime\trep\tbam\tpeaks\n" > $M
for t in DMSO D2 D4 D7 D10 D13; do for r in 1 2; do
  printf "%s\tATAC\t%s\t%s\t%s\t%s\n" ${t}_$r $t $r $B/atac_pipeline/3.bam/${t}_$r.sorted.mapped.bam \
    $B/atac_pipeline/6.peak/macs_tag_peak/${t}_$r.tagAlign_peaks.narrowPeak >> $M
  for a in SOX9 SMARCC1 IgG H3K27Ac H3K4me3; do
    case $a in H3K*) [ $t = DMSO ] || continue;; esac
    s=${t}_${a}_$r; bam=$B/cutrun_pipeline/3.bam/$s.sorted.mapped.bam
    [ -f $bam ] || continue
    pk=$B/cutrun_pipeline/6.peak/macs_no_IgG_bam/$s.sorted.mapped.bam_peaks.narrowPeak; [ -f $pk ] || pk=.
    case $a in H3K*) pk=.;; esac
    printf "%s\t%s\t%s\t%s\t%s\t%s\n" $s $a $t $r $bam $pk >> $M
  done
done; done
ENV="export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PATH=$E:\$PATH"
rm -f $OUT/logs/*.log
j62=$(echo "$ENV; $E/python $CODE/06_gates/62_gateB_counts.py $M $OUT/counts 8" | \
  qsub -terse -q all.q -pe smp 8 -l h_vmem=5G -N gb62 -o $OUT/logs/62.log -j y -cwd)
js=""
for c in $(seq 1 22) X; do
  j=$(echo "$ENV; $E/python $C4/46_ht29_pma_evidence.py chrom $OUT/counts/regions.bed \
$PMA/occupancy_chipatlas/processed/v1/PMA_chipatlas_hg38_occupancy.bed.gz $OUT/pma chr$c" | \
    qsub -terse -q all.q -pe smp 1 -l h_vmem=16G -hold_jid $j62 -N gb46_$c -o $OUT/logs/46.chr$c.log -j y -cwd)
  js="$js,$j"
done
R=$PMA/occupancy_chipatlas/result
j46=$(echo "$ENV; $E/python $C4/46_ht29_pma_evidence.py annotate $OUT/counts/regions.bed \
$R/hotspot_thresholds_v1/bins500.npz $R/hotspot_annotation_v1/bins_annotation.npz $MEME HO14_SOX9.H14CORE.0.PS.A \
$FA $OUT/pma 1e-4" | \
  qsub -terse -q all.q -pe smp 1 -l h_vmem=24G -hold_jid ${js#,} -N gb46a -o $OUT/logs/46.annotate.log -j y -cwd)
j50=$(echo "$ENV; $E/python $C4/50_sox_motif_scan.py $OUT/counts/regions.bed $MEME $FA $OUT/pma/sox_motifs.tsv.gz 1e-4" | \
  qsub -terse -q all.q -pe smp 1 -l h_vmem=16G -hold_jid $j62 -N gb50 -o $OUT/logs/50.log -j y -cwd)
j47=$(echo "$ENV; R_LIBS_USER=/home/zz950/softwares/R_lib_4 $RS $C4/47_ht29_dtag_deseq.R $OUT/counts $B/cutrun_pipeline" | \
  qsub -terse -q all.q -pe smp 1 -l h_vmem=24G -hold_jid $j62 -N gb47 -o $OUT/logs/47.log -j y -cwd)
echo "jobs: 62=$j62 46=${js#,} 46a=$j46 50=$j50 47=$j47"
