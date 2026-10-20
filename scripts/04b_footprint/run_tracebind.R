# Step 4b-1: TraceBIND (Lin et al. 2026) native R/Rcpp, CPU. Round 1 runs PRINT-bias mode: the pretrained PRINT
# Tn5 CNN (no mtDNA fine-tuning, no mito FDR), fixed adjusted-p threshold; labelled as such in every output.
# usage: Rscript run_tracebind.R <python> <model_dir> <regions.bed> <frags.tsv.gz> <out_prefix> <nCores> [p_threshold]
# Output: <out_prefix>.events.bed  chrom, start, end, width, -log10 adj p (BH per bp), region id; mode = PRINT-bias
#         <out_prefix>.timing.tsv
suppressPackageStartupMessages({
  library(tracebind); library(data.table); library(GenomicRanges); library(dplyr); library(tibble); library(tidyr)
  library(parallel); library(foreach)
})
a <- commandArgs(trailingOnly = TRUE)
reticulate::use_python(a[1], required = TRUE)
model_dir <- normalizePath(a[2]); bed <- a[3]; frags <- a[4]; out <- a[5]; nCores <- as.integer(a[6])
pthr <- if (length(a) >= 7) as.numeric(a[7]) else 0.05
tic <- function() proc.time()[["elapsed"]]; timing <- list()
work <- paste0(dirname(out), "/tb_", basename(out), "/"); dir.create(work, showWarnings = FALSE, recursive = TRUE)
old <- setwd(work)
r <- fread(bed, header = FALSE)
regionsBed <- data.frame(chr = r$V1, start = r$V2 + 1, end = r$V3)  # 1-based inclusive positions
t0 <- tic()
get_bias(regionsBed, referenceGenome = "hg38", nCores = nCores, model_path = paste0(model_dir, "/"),
         model_use = "Tn5_NN_model.h5", save_path = work)
pred_bias <- read.table(paste0(work, "pred_bias.txt"))
timing$bias <- tic() - t0; t0 <- tic()
counts <- get_count(frags, regionsBed, nCores = nCores)
timing$counts <- tic() - t0; t0 <- tic()
grp <- 1
res <- mclapply(seq_len(nrow(regionsBed)), function(i) {
  bd <- tryCatch(get_bardata(counts, regionsBed, bias = pred_bias[i, 1:length(regionsBed$start[i]:regionsBed$end[i])],
                             i = i, groupIDs = grp), error = function(e) NULL)
  if (is.null(bd) || sum(bd$Tn5Insertion) == 0) return(NULL)
  fr <- NB_footprintings(Tn5Insertion = bd$Tn5Insertion, pred_bias = bd$pred_bias, positions = bd$position,
                         p.adjust.method = "BH", nCores = 1)
  bs <- binding_sites_pval(fr[["pval"]], pval_threshold = pthr, width_threshold = 10)
  if (nrow(bs) == 0) return(NULL)
  data.table(chrom = regionsBed$chr[i], start = bs$position - bs$width / 2 - 1, end = bs$position + bs$width / 2 - 1,
             width = bs$width, mlog10p = bs$minus_log_p_value, region = r$V4[i])
}, mc.cores = nCores)
ev <- rbindlist(res)
timing$footprint <- tic() - t0
setwd(old)
fwrite(ev, paste0(out, ".events.bed"), sep = "\t", col.names = FALSE)
fwrite(data.table(stage = c(names(timing), "mode"), seconds = c(unlist(timing), NA),
                  note = c(rep("", length(timing)), "PRINT-bias mode (no mtDNA fine-tuning, no mito FDR)")),
       paste0(out, ".timing.tsv"), sep = "\t")
cat("done", nrow(ev), "events\n")
