"""Tests for Step 3 nodes, similarity, floors, representatives (design §3, F24–F27)."""
import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd

D = Path(__file__).resolve().parents[1] / "scripts" / "03_motif_clustering"
sys.path.insert(0, str(D))
sys.path.insert(0, str(D.parent / "02_motif_import"))
import pma_cluster as pc  # noqa: E402


def load(name):
    spec = importlib.util.spec_from_file_location(name.replace(".py", "").lstrip("0123456789_"), D / name)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


nodes_mod = load("01_build_nodes.py")
edges_mod = load("03_build_edges.py")
rng = np.random.default_rng(7)
T = rng.dirichlet([0.3] * 4, 14)


def test_rc_duplicates_share_node():  # F24
    k1, o1 = nodes_mod.node_key(T)
    k2, o2 = nodes_mod.node_key(T[::-1, ::-1].copy())
    assert k1 == k2 and {o1, o2} == {"fwd", "rc"}


def test_alignment_matches_tomtom_convention():
    # offsets/overlaps observed from TOMTOM 5.5.9 on these constructions
    uT = pc.column_unit(T)
    q1 = T[3:11]
    r, ov = pc.directed_r(pc.column_unit(q1), uT, 3, "+")
    assert ov == 8 and r > 0.999
    q2 = T[3:11][::-1, ::-1]
    r, ov = pc.directed_r(pc.column_unit(q2), uT, 3, "-")
    assert ov == 8 and r > 0.999
    q3 = np.vstack([rng.dirichlet([0.3] * 4, 3), T[0:6]])
    _, ov = pc.directed_r(pc.column_unit(q3), uT, -3, "+")
    assert ov == 6


def test_vectorised_r_equals_scalar():
    mats = [rng.dirichlet([0.5] * 4, n) for n in (8, 12, 15, 6)]
    U = [pc.column_unit(m) for m in mats]
    L = np.array([len(u) for u in U])
    start = np.r_[0, np.cumsum(L)[:-1]]
    fwd, rc = np.vstack(U), np.vstack([u[::-1, ::-1] for u in U])
    rows = [(0, 1, 2, "+"), (1, 2, -3, "-"), (2, 3, 4, "+"), (3, 0, 1, "-"), (2, 0, 5, "-")]
    df = pd.DataFrame(rows, columns=["qi", "ti", "offset", "orientation"])
    df["overlap"] = [pc.directed_r(U[q], U[t], o, s)[1] for q, t, o, s in rows]
    got = edges_mod.directed_r(df, L, start, fwd, rc)
    want = [pc.directed_r(U[q], U[t], o, s)[0] for q, t, o, s in rows]
    assert np.allclose(got, want)


def chain_S():
    # 0-1-2 chain: 0~1 and 1~2 strong, 0~2 weak -> average linkage can merge
    S = np.array([[1, .95, .40, 0], [.95, 1, .95, 0], [.40, .95, 1, 0], [0, 0, 0, 1]], float)
    return S


def test_fine_floor_split_and_nesting():  # F25
    S = chain_S()
    fine, arch = pc.cluster_component(S, 0.70, 0.30)
    for lab, floor in ((fine, pc.FINE_FLOOR), (arch, pc.ARCH_FLOOR)):
        for u in np.unique(lab):
            assert pc.min_pair(S, np.flatnonzero(lab == u)) >= floor
    assert len(np.unique(fine)) >= 3  # {0,1,2} violates 0.50 -> split; 3 alone
    for u in np.unique(fine):  # each fine cluster lies inside one archetype
        assert len(np.unique(arch[fine == u])) == 1
    assert arch[0] == arch[1] == arch[2] != arch[3]  # 0.40 >= archetype floor 0.30


def cand(pid, mean_s, ev="supported", src="CisBP", q=9, n=0, eligible=True):
    return dict(pma_id=pid, eligible=eligible, mean_s=mean_s, evidence=ev, source_db=src,
                quality_rank=q, n_experiments=n, length_dev=0)


def test_representative_fidelity_first():  # F21
    # supported but peripheral loses to a central occupancy-derived motif
    c = [cand("A", 0.60), cand("B", 0.90, ev="not_established")]
    assert pc.rank_representative(c) == "B"
    # within the fidelity window, evidence decides
    c = [cand("A", 0.88), cand("B", 0.90, ev="not_established")]
    assert pc.rank_representative(c) == "A"


def test_quality_never_compared_across_sources():
    c = [cand("A", 0.9, src="HOCOMOCO", q=0), cand("B", 0.9, src="JASPAR", q=1, n=3)]
    assert pc.rank_representative(c) == "B"  # grades ignored -> experiments decide
    c = [cand("A", 0.9, src="HOCOMOCO", q=1), cand("B", 0.9, src="HOCOMOCO", q=0)]
    assert pc.rank_representative(c) == "B"


def test_experiment_count_within_namespace():  # F26
    assert pc.n_independent_experiments(["ENCODE:E1", "ENCODE:E1", "GTRD:P1"]) == 1
    assert pc.n_independent_experiments(["ENCODE:E1", "ENCODE:E2", "GTRD:P1"]) == 2
    assert pc.n_independent_experiments([]) == 0
