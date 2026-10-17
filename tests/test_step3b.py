"""Step 3b: universe-independent similarity s and MoDISco end-trimming."""
import os
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "03b_v03_clustering"))
pa = pytest.importorskip("pma_align")

for k in ("PMA_MOTIF_RAW", "PMA_MOTIF_PROCESSED"):
    os.environ.setdefault(k, "/nonexistent")
sys.path.insert(0, str(ROOT / "scripts" / "02c_denovo_sources"))
import import_v03 as iv  # noqa: E402

E = np.eye(4) * 0.97 + 0.01  # near-one-hot columns A, C, G, T


def motif(seq):
    return np.array([E["ACGT".index(c)] for c in seq])


def s_of(a, b):
    Z, Zrc, st, ln = pa.pack([a, b])
    return float(pa.s_pairs(Z, Zrc, st, ln, np.array([0]), np.array([1]))[0])


def test_identity_and_reverse_complement():
    m = motif("ACGTTGCAAG")
    assert s_of(m, m) == pytest.approx(1.0)
    assert s_of(m, m[::-1, ::-1]) == pytest.approx(1.0)


def test_shorter_partner_scaled_by_overlap():
    a = motif("ACGTTGCAAG")
    b = motif("TTGCAA")  # exact sub-motif, overlap 6 of max length 10
    assert s_of(a, b) == pytest.approx(0.6, abs=1e-6)


def test_min_overlap_and_symmetry():
    a, b = motif("AAAACCCCGG"), motif("TTGACT")
    assert s_of(a, b) == pytest.approx(s_of(b, a))
    assert s_of(motif("ACGT"), motif("ACGTA")) == 0.0  # overlap < 5 possible only


def test_uniform_columns_count_as_zero():
    a = motif("ACGTA")
    u = np.full((5, 4), 0.25)
    assert s_of(a, u) == 0.0


def test_trim_only_contiguous_low_ic_ends():
    u = np.full((1, 4), 0.25)
    core = motif("ACG")
    m = np.vstack([u, u, core[:1], u, core[1:], u])
    t, lo, hi = iv.trim(m)
    assert (lo, hi) == (2, 1)
    assert len(t) == 4  # internal uniform column kept
    t2, lo2, hi2 = iv.trim(np.vstack([u, u]))
    assert len(t2) == 0 and lo2 == 2


def test_near_dup_requires_overlap_of_longer():
    a, b = motif("ACGTTGCAAG"), motif("CGTTGCAAG")  # 9 of 10 columns = 90 %
    Z, Zrc, st, ln = pa.pack([a, b, motif("TTGCAA")])
    r = pa.near_dup_r(Z, Zrc, st, ln, np.array([0, 0]), np.array([1, 2]), 0.9)
    assert r[0] == pytest.approx(1.0)
    assert r[1] == -1.0  # 6 of 10 < 90 %: no admissible alignment
