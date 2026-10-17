#!/bin/bash
# Step 3b on Argos rcapps3 (x86, 72 cores, 1 TB). Stages in frozen order:
#   post_tomtom  v0.2.1 TOMTOM finalize -> edges (Step 3 03_build_edges) -> tau calibration
#   import       ENCODE raw manifests -> raw layer v0.3 -> evidence annotation v2
#   nodes_pca    nodes (exact + near-dedup with stop rule) -> features / balanced PCA
#   grid         12 parallel jobs: part x rep x dims (Seurat, r4p3)
#   gates        12 parallel jobs -> deterministic gates -> candidates + G6 strata
#   stability    G5/G6 runs for candidates (16 parallel) -> selection
#   strict       strict-tau (0.95) sensitivity on the selected configs (§13)
#   annotate     clusters, one PWM per cluster
#   align        §15: alignment graph (recall check, K 100/200), Louvain scan, coverage hubs, QC
#   tiers        §14: tier choice, hubs, QC, stability, SNN degree, annotation per tier
#   all          import .. annotate (post_tomtom must have finished)
# usage: bash run_v03.sh <stage>   (from the repo clone; logs in result/step3b_v03/logs)
set -euo pipefail
cd "$(dirname "$0")"
HERE=$PWD
M=${PMA_MOTIF:-/home/zz950/DATA/2.PROJECTS/PMA/motif_reference}
export PMA_MOTIF_RAW=$M/raw PMA_MOTIF_PROCESSED=$M/processed PMA_MOTIF_RESULT=$M/result
export PMA_HGNC_MAP=${PMA_HGNC_MAP:-/home/zz950/DATA/1.Databases/HGNC_gene_id_mapping/processed/v0.1/hgnc_symbol_ensembl_map.tsv}
PY=${PY:-/mnt/storage/apps/anaconda3-2024.06-1/bin/python}
RS=${RS:-/home/zz950/softwares/miniconda3/envs/r4p3/bin/Rscript}
export R_LIBS_USER=${R_LIBS_USER:-/home/zz950/softwares/R_lib_4}
R3=$PMA_MOTIF_RESULT/step3b_v03
LOG=$R3/logs
mkdir -p "$LOG" "$R3/grid"
JOBS="composite A 20
composite A 30
composite A 50
composite B 20
composite B 30
composite B 50
monomer A 20
monomer A 30
monomer A 50
monomer B 20
monomer B 30
monomer B 50"

stage_post_tomtom() {
  local S=$PMA_MOTIF_RESULT/step3_motif_clustering
  bash "$S/tomtom/02_run_tomtom.sh" "$S/tomtom" finalize
  (cd ../03_motif_clustering && "$PY" -I 03_build_edges.py)
  NUMBA_NUM_THREADS=64 "$PY" -I 01_tau_calibration.py
}

stage_import() {
  local E=$PMA_MOTIF_RAW/encode_grammar/2026-10-16
  [[ -f $E/checksums.md5 ]] || "$PY" -I ../02c_denovo_sources/write_raw_manifests.py encode "$E"
  "$PY" -I ../02c_denovo_sources/import_v03.py
  "$PY" -I ../02c_denovo_sources/evidence_v2.py "$PMA_MOTIF_PROCESSED/annotations/evidence_v2"
}

stage_nodes_pca() {
  NUMBA_NUM_THREADS=64 "$PY" -I 02_build_nodes.py
  OMP_NUM_THREADS=16 "$PY" -I 03_features_pca.py 56
}

par() {  # par <max_jobs>: run stdin lines (shell commands) with at most N in flight
  local n=$1 line
  while read -r line; do
    while (( $(jobs -rp | wc -l) >= n )); do wait -n || true; done
    bash -c "$line" &
  done
  wait || true
}

check() {  # check <printf pattern part rep dims>: every job output exists, else abort
  local p r d f bad=0
  while read -r p r d; do
    f=$(printf "$1" "$p" "$r" "$d")
    [[ -s $f ]] || { echo "missing $f"; bad=1; }
  done <<< "$JOBS"
  (( bad == 0 )) || exit 1
}

stage_grid() {
  echo "$JOBS" | while read -r p r d; do
    echo "OMP_NUM_THREADS=4 $RS $HERE/04_seurat_grid.R $R3/pca $R3/grid grid $p $r $d > $LOG/grid_${p}_${r}_d${d}.log 2>&1"
  done | par 12
  check "$R3/grid/grid_%s_%s_d%s.tsv.gz"
}

stage_gates() {
  echo "$JOBS" | while read -r p r d; do
    echo "NUMBA_NUM_THREADS=6 $PY -I $HERE/05_gates.py $p $r $d > $LOG/gates_${p}_${r}_d${d}.log 2>&1"
  done | par 12
  check "$R3/gates/gates_%s_%s_d%s.tsv"
  "$PY" -I 06_select.py candidates
}

stage_stability() {
  # candidates.tsv columns: part rep dims config K_final k res
  tail -n +2 "$R3/gates/candidates.tsv" | while IFS=$'\t' read -r p r d c kf k res; do
    echo "OMP_NUM_THREADS=4 $RS $HERE/04_seurat_grid.R $R3/pca $R3/grid stability $p $r $d $k $res > $LOG/stability_${p}_${r}_d${d}_k${k}_r${res}.log 2>&1"
  done | par 16
  "$PY" -I 06_select.py select
}

stage_strict() {  # §13 strict-tau sensitivity on the selected config of each partition
  "$PY" -c "import json,sys; d=json.load(open(sys.argv[1]))
[print(p, s['rep'], s['dims'], s['config']) for p, s in d.items() if s.get('status') == 'selected']" \
    "$R3/gates/selection.json" | while read -r p r d c; do
    NUMBA_NUM_THREADS=32 "$PY" -I 05_gates.py "$p" "$r" "$d" "$c" 0.95 > "$LOG/strict_${p}.log" 2>&1
  done
}

stage_tiers() {  # §14 three-tier reference (after 08_tiers.R scan)
  "$PY" -I 09_tiers.py choose
  NUMBA_NUM_THREADS=32 "$PY" -I 09_tiers.py build
  "$PY" -c "import json,sys; [print(t['res']) for t in json.load(open(sys.argv[1]))['tiers'].values()]" \
    "$R3/tiers/tier_choice.json" | while read -r res; do
    for p in composite monomer; do
      echo "OMP_NUM_THREADS=4 $RS $HERE/04_seurat_grid.R $R3/pca $R3/grid stability $p A 30 20 $res > $LOG/tier_stability_${p}_r${res}.log 2>&1"
    done
  done | par 6
  "$PY" -I 09_tiers.py stability
  OMP_NUM_THREADS=8 "$RS" 08_tiers.R "$R3/pca" "$R3/tiers" degree > "$LOG/tiers_degree.log" 2>&1
  for t in LOW MEDIUM HIGH; do "$PY" -I 07_annotate_clusters.py "$R3/reference_tiers/$t" "$t"; done
}

stage_align() {  # §15 post-QC rescue: alignment-weighted graph + coverage-maximising hubs
  local K=100 A=$R3/align
  [[ -s $A/align_summary_k100.json ]] || NUMBA_NUM_THREADS=48 OMP_NUM_THREADS=16 "$PY" -I 10_align_graph.py 100
  if ! "$PY" -c "import json,sys; sys.exit(0 if json.load(open(sys.argv[1]))['recall_pass_all'] else 1)" "$A/align_summary_k100.json"; then
    K=200
    [[ -s $A/align_summary_k200.json ]] || NUMBA_NUM_THREADS=48 OMP_NUM_THREADS=16 "$PY" -I 10_align_graph.py 200
    "$PY" -c "import json,sys; sys.exit(0 if json.load(open(sys.argv[1]))['recall_pass_all'] else 1)" \
      "$A/align_summary_k200.json" || { echo "candidate_graph_incomplete"; exit 1; }
  fi
  echo "candidate graph K=$K"
  for p in composite monomer; do
    echo "OMP_NUM_THREADS=8 $RS $HERE/11_align_louvain.R $A $R3/pca $K scan $p > $LOG/align_scan_${p}.log 2>&1"
  done | par 2
  export PMA_TIER_GRAPH=align
  "$PY" -I 09_tiers.py choose
  NUMBA_NUM_THREADS=48 "$PY" -I 09_tiers.py build
  "$PY" -c "import json,sys; [print(t['res']) for t in json.load(open(sys.argv[1]))['tiers'].values()]" \
    "$R3/align_tiers/tier_choice.json" | while read -r res; do
    for p in composite monomer; do
      echo "OMP_NUM_THREADS=4 $RS $HERE/11_align_louvain.R $A $R3/pca $K stability $p $res $R3/grid/strata_${p}.tsv > $LOG/align_stability_${p}_r${res}.log 2>&1"
    done
  done | par 6
  "$PY" -I 09_tiers.py stability
  for t in LOW MEDIUM HIGH; do "$PY" -I 07_annotate_clusters.py "$R3/reference_align/$t" "$t"; done
}

stage_annotate() {
  "$PY" -I 07_annotate_clusters.py "$R3/reference"
}

case "$1" in
  all) for s in import nodes_pca grid gates stability strict annotate; do echo "== $s $(date)"; "stage_$s"; done ;;
  *) "stage_$1" ;;
esac
echo "== done $1 $(date)"
