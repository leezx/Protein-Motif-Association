# TraceBIND 0.1.0 (Lin et al. 2026) with the pretrained PRINT Tn5 CNN bias (no mtDNA fine-tuning, no mito-FDR).
# Native multiscale NB test (center sizes 2-100) per region; we keep both the native events and a per-bp score.
# usage: Rscript run_tracebind.R <python> <model_dir> <regions.bed> <frags.tsv.gz> <outdir> <nCores>
#   <outdir>/tb_work/regionSeqs.txt must already exist (written by run_tracebind.sh from the indexed FASTA).
# Output: tracebind_tf.bedgraph.gz  per bp max -log10(BH p) over footprint widths 10-40 bp (TF scale)
#         tracebind_events.bed      native binding_sites_pval(p<0.05, width>=10) events
#         tracebind_timing.tsv
suppressPackageStartupMessages({
  library(tracebind); library(data.table); library(parallel)
  library(GenomicRanges); library(dplyr); library(tibble); library(tidyr); library(foreach)  # used unqualified inside tracebind
})
a <- commandArgs(trailingOnly = TRUE)
reticulate::use_python(a[1], required = TRUE)
model_dir <- normalizePath(a[2]); bed <- a[3]; frags <- a[4]; out <- normalizePath(a[5]); nCores <- as.integer(a[6])
tic <- function() proc.time()[["elapsed"]]; timing <- list()
work <- file.path(out, "tb_work/")
old <- setwd(work)
r <- fread(bed, header = FALSE)
regionsBed <- data.frame(chr = r$V1, start = r$V2 + 1, end = r$V3)
t0 <- tic()
get_bias(regionsBed, referenceGenome = "hg38", nCores = nCores, model_path = paste0(model_dir, "/"),
         model_use = "Tn5_NN_model.h5", save_path = work)
pred_bias <- read.table(paste0(work, "pred_bias.txt"))
timing$bias <- tic() - t0; t0 <- tic()
counts <- get_count(frags, regionsBed, nCores = nCores)
timing$counts <- tic() - t0; t0 <- tic()
tf_cols <- as.character(10:40)
res <- mclapply(seq_len(nrow(regionsBed)), function(i) {
  bd <- tryCatch(get_bardata(counts, regionsBed, bias = pred_bias[i, 1:length(regionsBed$start[i]:regionsBed$end[i])],
                             i = i, groupIDs = 1), error = function(e) NULL)
  if (is.null(bd) || sum(bd$Tn5Insertion) == 0) return(NULL)
  fr <- NB_footprintings(Tn5Insertion = bd$Tn5Insertion, pred_bias = bd$pred_bias, positions = bd$position,
                         p.adjust.method = "BH", nCores = 1)
  p <- fr[["pval"]]
  cols <- intersect(colnames(p), tf_cols)
  pos <- as.numeric(rownames(p))
  tr <- data.table(chrom = regionsBed$chr[i], start = pos - 1, end = pos,
                   score = apply(-log10(p[, cols, drop = FALSE]), 1, max))
  bs <- binding_sites_pval(p, pval_threshold = 0.05, width_threshold = 10)
  ev <- if (nrow(bs) == 0) NULL else
    data.table(chrom = regionsBed$chr[i], start = bs$position - bs$width / 2 - 1, end = bs$position + bs$width / 2 - 1,
               width = bs$width, mlog10p = bs$minus_log_p_value)
  list(tr = tr, ev = ev)
}, mc.cores = nCores)
timing$footprint <- tic() - t0
setwd(old)
ok <- !vapply(res, function(x) is.null(x) || inherits(x, "try-error"), logical(1))
fwrite(rbindlist(lapply(res[ok], `[[`, "tr")), file.path(out, "tracebind_tf.bedgraph.gz"), sep = "\t", col.names = FALSE)
fwrite(rbindlist(lapply(res[ok], `[[`, "ev")), file.path(out, "tracebind_events.bed"), sep = "\t", col.names = FALSE)
fwrite(data.table(stage = c(names(timing), "regions_scored", "regions_failed"),
                  value = c(unlist(timing), sum(ok), sum(vapply(res, inherits, logical(1), "try-error")))),
       file.path(out, "tracebind_timing.tsv"), sep = "\t")
cat("done\n")
