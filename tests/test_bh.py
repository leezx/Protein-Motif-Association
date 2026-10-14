"""Unit tests for per-query BH (scripts/01_motif_pilot/03_pilot_analysis.py)."""
import importlib.util
import os
from pathlib import Path

import numpy as np
import pandas as pd
from statsmodels.stats.multitest import multipletests

os.environ.setdefault("PMA_MOTIF_PROCESSED", "/nonexistent")
os.environ.setdefault("PMA_MOTIF_RESULT", "/nonexistent")
_p = Path(__file__).resolve().parents[1] / "scripts" / "01_motif_pilot" / "03_pilot_analysis.py"
_spec = importlib.util.spec_from_file_location("pilot", _p)
pilot = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pilot)


def _frame(pvals_by_query):
    rows = [(q, f"T{i}", p) for q, ps in pvals_by_query.items() for i, p in enumerate(ps)]
    return pd.DataFrame(rows, columns=["Query_ID", "Target_ID", "p-value"]).assign(**{"q-value": np.nan})


def test_matches_statsmodels_per_query():
    rng = np.random.default_rng(0)
    data = {"A": rng.uniform(size=200) ** 3, "B": rng.uniform(size=200)}
    out = pilot.bh_per_query(_frame(data))
    for q, ps in data.items():
        ref = multipletests(ps, method="fdr_bh")[1]
        np.testing.assert_allclose(out.loc[out.Query_ID == q, "q-value"].to_numpy(), ref, rtol=1e-12)


def test_ties_and_zeros():
    data = {"A": [0.0, 0.0, 0.01, 0.01, 0.01, 1.0]}
    out = pilot.bh_per_query(_frame(data))["q-value"].to_numpy()
    np.testing.assert_allclose(out, multipletests(data["A"], method="fdr_bh")[1])
    assert out[0] == 0.0 and out[2] == out[3] == out[4]


def test_queries_are_independent_families():
    a = pilot.bh_per_query(_frame({"A": [0.001, 0.5]}))
    ab = pilot.bh_per_query(_frame({"A": [0.001, 0.5], "B": [0.9] * 50}))
    np.testing.assert_allclose(a["q-value"], ab.loc[ab.Query_ID == "A", "q-value"])
