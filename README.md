# Protein-Motif-Association (PMA)

PMA builds a comprehensive, statistically calibrated reference of human
protein–motif genomic associations: for chromatin-associated proteins
with occupancy data (primarily reused from ChIP-Atlas), which DNA motifs
are associated with their occupied regions — against a matched genomic
background (*genomic association*) and relative to other proteins in the
same biosample (*protein-specific association*) — with HOT-region
control, independent-dataset replication and evidence grading.

PMA is an association reference, not a recruitment-mechanism study.

**Start here:**
- [`docs/PROJECT_CHARTER.md`](docs/PROJECT_CHARTER.md) — operating rules
  and Part 1 scope (founding question, 100% definition, non-goals).
- [`design/PMA_pseudo_figures_v0.2.md`](design/PMA_pseudo_figures_v0.2.md)
  — current frozen design (v0.1 kept for history).
- [`Worklog.md`](Worklog.md) — chronological log and progress tracker.
- [`UDE/CURRENT.md`](UDE/CURRENT.md) — indexed Understanding, Design and
  Execution state, with source authority and open discrepancies. The step
  contracts stay in their existing paths.

## Current status

v0.2 project scope is frozen. The integrated `step4b-atac-footprinting`
branch contains the motif reference, Step 4a and the Step 4b setup work;
additional BED6 and footprint work remains on separate branches and open
PRs. Check [`UDE/CURRENT.md`](UDE/CURRENT.md) and the current Git/PR state
before treating a later result as integrated or accepted.

## Data

**No data files live in this repo.** All data lives under
`/Volumes/Stelligen_SSD/Stelligen/DATA/<data_type>/<dataset_id>/`
(see `docs/PROJECT_CHARTER.md` §2.3). This repo holds code, manifests
and docs only. PMA data root: `$BIO_DATA/2.PROJECTS/PMA/` (paths set in
`config/pma_env.sh`).

## Layout

- `config/pma_env.sh`: data and tool paths, built on the workspace `setup_env.sh`
- `scripts/<NN>_<step>/`: code for each step
- `results/<NN>_<step>/`: small summary tables only
- `datasets/<id>/dataset.md`: manifest for each dataset

## Tools

- MEME Suite 5.5.9 (TOMTOM): `$BIO_SOFTWARES/tools/meme-5.5.9`, built from source
- Python: workspace `python-main` venv (numpy, pandas, openpyxl)
