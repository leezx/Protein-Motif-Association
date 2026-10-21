# PMA — links between this repo and its data

This repo holds code, design docs, result write-ups and small summary tables. The data lives outside it:

| | Location |
|---|---|
| Repo (GitHub) | https://github.com/leezx/Protein-Motif-Association (local `PR/Protein–Motif-Association`) |
| Data root (Mac) | `$BIO_DATA/2.PROJECTS/PMA/` = `DATA/2.PROJECTS/PMA/` in the workspace; see [README](../../DATA/2.PROJECTS/PMA/README.md) |
| Data root (Argos) | `/home/zz950/DATA/2.PROJECTS/PMA/` (the full-size datasets; the Mac holds copies of what is needed locally) |
| Path variables | `config/pma_env.sh` (`PMA_DATA`, `PMA_MOTIF*`, `PMA_OCC*`); never hard-code mount paths in scripts |
| Local shortcut (not in git) | `DATA` → `../../DATA/2.PROJECTS/PMA`, a relative symlink excluded via `.git/info/exclude` |

Relative links in this file assume the workspace layout (`<workspace>/PR/Protein–Motif-Association`,
`<workspace>/DATA/...`).

## Datasets ↔ code ↔ docs

| Dataset (DATA) | Where | Code (`scripts/`) | Design / results docs | Result write-up | Branch |
|---|---|---|---|---|---|
| [`motif_reference`](../../DATA/2.PROJECTS/PMA/motif_reference/link.md) | Mac + Argos | `01_motif_pilot`, `02_motif_import`, `02c_denovo_sources`, `03_motif_clustering`, `03b_v03_clustering` | `docs/STEP1…STEP3B_*.md` | `Figures/Figure1/Figure1.motif_reference.result.md` (Figure 1C) | `main`; Step 3 branches |
| [`occupancy_chipatlas`](../../DATA/2.PROJECTS/PMA/occupancy_chipatlas/link.md) | Argos (full); Mac (`processed/light_v1/`, `result/`) | `04a_chipatlas` | `docs/STEP4A_CHIPATLAS_OCCUPANCY_DESIGN.md` §1–§17; `docs/reports/STEP4A_CHIPATLAS_*` | `Figures/Figure1/Figure1.chipatlas_occupancy.result.md` (1D); `Figure1.protein_cooccupancy` (1E), `Figure1.experiment_clustering` (1F), `Figure1.region_classes` (1G) `.result.md`; panels in `result/figure1_clustering_v1_2/` | `step4a-chipatlas-occupancy` → `task_20261020_chipatlas_light_bed` |
| `atac_footprint` | Argos only (`/home/zz950/DATA/2.PROJECTS/PMA/atac_footprint`) | `04b_footprint` | `docs/STEP4B_ATAC_FOOTPRINT_BENCHMARK_DESIGN.md` | — | `step4b-atac-footprinting`, `task_20261018_step4b_setup_fix` |
| `footprint/` (Mac) | Mac | — | reference PDF only | — | — |

## Within each dataset

`raw/` is append-only, dated per source, with checksums. `processed/<version>/` holds the reusable data assets.
`result/<analysis_id>/` holds the analysis outputs. The dataset's `link.md` lists versions, the code commit for
each version, and its status.

## Keeping the links current

- New dataset: add a row here, a row in `DATA/2.PROJECTS/PMA/README.md`, a row in `DATA/dataset.index.md`, and a
  `link.md` in the dataset that points back to this repo.
- New analysis round: update the dataset `link.md` and the matching `Figures/FigureN/FigureN.<key>.result.md`.
