"""Unit tests for scripts/02_motif_import/pma_motif.py (design §3, §4)."""
import struct
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "02_motif_import"))
import pma_motif as pm  # noqa: E402

M = np.array([[0.7, 0.1, 0.1, 0.1],
              [0.0, 0.0, 0.0, 0.0],
              [0.25, 0.25, 0.25, 0.25],
              [0.1, 0.2, 0.3, 0.4]])


def test_hash_pinned():
    # §3 serialisation: uint32-LE length + float64-LE rows (A,C,G,T).
    assert pm.matrix_bytes(M)[:4] == struct.pack("<I", 4)
    assert len(pm.matrix_bytes(M)) == 4 + 4 * 4 * 8
    assert pm.sha1(M) == "283f223b4fcc286b94d66c28f4dcb47b596f5b83"


def test_hash_dtype_independent():
    assert pm.sha1(M.astype(np.float32).astype(float).round(2)) == pm.sha1(M)
    assert pm.sha1(M.tolist()) == pm.sha1(M)


def test_gap_mask_only_all_zero_rows():
    m, gaps = pm.normalise(M * 10)
    assert gaps == [1]                       # uniform row 2 is not a gap
    assert np.allclose(m.sum(axis=1), 1)
    assert np.allclose(m[1], 0.25)


def test_rounded_key_orientation_free():
    k1, o1 = pm.rounded_key(M)
    k2, o2 = pm.rounded_key(pm.revcomp(M))
    assert k1 == k2 and {o1, o2} == {"fwd", "rc"}
    # differences beyond 4 decimals do not change the group
    assert pm.rounded_key(M + 1e-6)[0] == k1


def test_check_matrix():
    assert pm.check_matrix(M) == ""
    assert pm.check_matrix(-M) == "negative"
    assert pm.check_matrix(M[:, :3]) == "shape"
    assert pm.check_matrix(np.full((2, 4), np.nan)) == "non_finite"


def test_assay_and_evidence():
    assert pm.assay_class("GHT-SELEX (GFPIVT)") == "in_vitro_selection"
    assert pm.assay_class("ChIP-seq") == "in_vivo_occupancy"
    assert pm.assay_class("PBM") == "in_vitro_array"
    assert pm.assay_class(None) == "unknown"
    assert pm.evidence("in_vivo_occupancy") == ("occupancy_derived", "not_established")
    assert pm.evidence("in_vitro_selection") == ("in_vitro_binding", "supported")
    assert pm.evidence("in_vitro_selection", homology=True) == ("homology_transfer", "transferred")
