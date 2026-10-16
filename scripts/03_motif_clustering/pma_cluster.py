"""Step 3 core functions: similarity score, floor-constrained clustering,
representative ranking. Design: docs/STEP3_MOTIF_CLUSTERING_DESIGN.md §3.2–3.4.
"""
import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import fcluster, linkage
from scipy.spatial.distance import squareform

V01_Q, V01_OV = 0.01, 0.6
FINE_FLOOR, ARCH_FLOOR = 0.50, 0.30

# ---- similarity (§3.2) ----------------------------------------------------


def column_unit(m):
    """Rows of m centred and scaled to unit norm, so that the Pearson
    correlation of two columns is their dot product. Uniform rows -> 0."""
    c = np.asarray(m, float) - np.asarray(m, float).mean(axis=1, keepdims=True)
    n = np.linalg.norm(c, axis=1, keepdims=True)
    return np.where(n > 1e-12, c / np.where(n > 1e-12, n, 1), 0.0)


def aligned_span(lq, lt, offset):
    """Query positions [i0, i1) aligned to target positions i + offset
    (TOMTOM: query column i <-> target column i + Optimal_offset, target
    reverse-complemented when Orientation is '-')."""
    i0 = max(0, -offset)
    i1 = min(lq, lt - offset)
    return i0, max(i0, i1)


def directed_r(uq, ut_fwd, offset, orientation):
    """Mean column Pearson at TOMTOM's alignment; returns (r, overlap)."""
    ut = ut_fwd if orientation == "+" else ut_fwd[::-1, ::-1]
    i0, i1 = aligned_span(len(uq), len(ut), offset)
    if i1 <= i0:
        return 0.0, 0
    d = (uq[i0:i1] * ut[i0 + offset:i1 + offset]).sum(axis=1)
    return float(d.mean()), i1 - i0


def s_directed(r, overlap, la, lb):
    return min(max(r, 0.0), 1.0) * overlap / max(la, lb)


def eligible_directed(q, overlap, la, lb):
    """statistical_match_v0.1 for one direction."""
    return (q < V01_Q) and (overlap >= V01_OV * min(la, lb))


# ---- clustering (§3.3) ----------------------------------------------------


def floor_split(S, members, floor):
    """Split one candidate group so every pair has S >= floor, by complete
    linkage at distance 1 - floor. Never merges outside `members`.
    Returns a list of index arrays."""
    members = np.asarray(members)
    if len(members) == 1:
        return [members]
    sub = S[np.ix_(members, members)]
    if sub[np.triu_indices(len(members), 1)].min() >= floor:
        return [members]
    D = 1.0 - sub
    np.fill_diagonal(D, 0.0)
    lab = fcluster(linkage(squareform(D, checks=False), "complete"), t=1.0 - floor + 1e-12,
                   criterion="distance")
    return [members[lab == k] for k in np.unique(lab)]


def cluster_component(S, c_fine, c_arch, fine_floor=FINE_FLOOR, arch_floor=ARCH_FLOOR):
    """S: dense symmetric similarity of one connected component (diag 1,
    non-edges 0). Returns (fine_label, arch_label) as int arrays.

    Average-linkage dendrogram over nodes; fine candidates = cut at 1 - c_fine,
    archetype candidates = cut at 1 - c_arch (dendrogram cuts are nested).
    Fine floor: complete linkage within each fine candidate. Archetype
    floor: complete linkage over the fine clusters of each archetype
    candidate, with inter-cluster distance = max member-pair distance."""
    n = len(S)
    if n == 1:
        return np.zeros(1, int), np.zeros(1, int)
    D = 1.0 - S
    np.fill_diagonal(D, 0.0)
    Z = linkage(squareform(D, checks=False), "average")
    fc = fcluster(Z, t=1.0 - c_fine + 1e-12, criterion="distance")
    ac = fcluster(Z, t=1.0 - c_arch + 1e-12, criterion="distance")
    fine = np.full(n, -1)
    nf = 0
    for k in np.unique(fc):
        for grp in floor_split(S, np.flatnonzero(fc == k), fine_floor):
            fine[grp] = nf
            nf += 1
    arch = np.full(n, -1)
    na = 0
    for k in np.unique(ac):
        idx = np.flatnonzero(ac == k)
        units = np.unique(fine[idx])
        assert np.isin(np.flatnonzero(np.isin(fine, units)), idx).all(), "fine not nested in archetype"
        if len(units) == 1:
            arch[idx] = na
            na += 1
            continue
        order = idx[np.argsort(fine[idx], kind="mergesort")]
        starts = np.flatnonzero(np.r_[True, np.diff(fine[order]) != 0])
        blk = np.minimum.reduceat(S[np.ix_(order, order)], starts, axis=0)
        mins = np.minimum.reduceat(blk, starts, axis=1)  # min member-pair s between units
        np.fill_diagonal(mins, 1.0)
        for grp in floor_split(mins, np.arange(len(units)), arch_floor):
            arch[np.isin(fine, units[grp])] = na
            na += 1
    assert (fine >= 0).all() and (arch >= 0).all()
    return fine, arch


def min_pair(S, idx):
    idx = np.asarray(idx)
    if len(idx) < 2:
        return 1.0
    sub = S[np.ix_(idx, idx)]
    return float(sub[np.triu_indices(len(idx), 1)].min())


# ---- representatives (§3.4) ----------------------------------------------

EVIDENCE_RANK = {"supported": 0, "transferred": 1, "not_established": 2, "unknown": 3}


def rank_representative(cands, delta=0.05):
    """cands: list of dicts with keys pma_id, eligible, mean_s, evidence,
    source_db, quality_rank (source-native, lower better), n_experiments,
    length_dev. Pattern fidelity first: eligible candidates within `delta`
    of the best mean similarity; then evidence; then source-native quality,
    used only when every remaining candidate is from the same source
    (grades are never compared across sources); then experiments, mean_s,
    length deviation, pma_id."""
    pool = [c for c in cands if c["eligible"]] or list(cands)
    best = max(c["mean_s"] for c in pool)
    pool = [c for c in pool if c["mean_s"] >= best - delta - 1e-12]
    top = min(EVIDENCE_RANK.get(c["evidence"], 3) for c in pool)
    pool = [c for c in pool if EVIDENCE_RANK.get(c["evidence"], 3) == top]
    same_src = len({c["source_db"] for c in pool}) == 1
    pool.sort(key=lambda c: (c["quality_rank"] if same_src else 0, -c["n_experiments"], -c["mean_s"],
                             c["length_dev"], c["pma_id"]))
    return pool[0]["pma_id"]


def n_independent_experiments(accessions):
    """F26: distinct experiment accessions, counted within one namespace
    only (max over namespaces), so the same experiment under two namespaces
    (e.g. an ENCODE ENCSR and a GTRD peak set) is never counted twice."""
    by_ns = {}
    for a in accessions:
        ns = a.split(":", 1)[0] if ":" in a else ""
        by_ns.setdefault(ns, set()).add(a)
    return max((len(v) for v in by_ns.values()), default=0)


def sequence_specific_tfs(md, links, masterlist):
    """§3.0 target class: HGNC symbols in the HOCOMOCO v14 masterlist (human
    entries) or with at least one direct_binding_evidence = supported motif."""
    human = masterlist[masterlist["curated:uniprot_id"].str.endswith("_HUMAN")]["auto:gene_symbol"]
    sup = links[links.pma_id.isin(md.pma_id[md.direct_binding_evidence == "supported"])].tf_hgnc
    return (set(human) | set(sup)) - {""}


def target_class(md, links, masterlist):
    tfs = sequence_specific_tfs(md, links, masterlist)
    seq = links[links.tf_hgnc.isin(tfs)].pma_id.unique()
    return pd.Series(np.where(md.pma_id.isin(seq), "sequence_specific_TF", "non_TF_target"), index=md.pma_id)
