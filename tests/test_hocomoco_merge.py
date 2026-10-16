"""Tests for the HOCOMOCO collection merge rule (design §12, review F10/F15)."""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "02_motif_import"))
import pma_motif as pm  # noqa: E402

PCM = [[10, 0, 0, 0], [0, 10, 0, 0], [0, 0, 5, 5]]


def ann(name, tf="TFA", origin="PEAKS1", dtype="P", om=None, quality="A"):
    return dict(name=name, tf=tf, datatype=dtype, quality=quality,
                original_motif=dict(name=om or f"{tf}@{origin}", origin=origin, motif_datatype=dtype))


def test_same_pcm_same_experiment_merges_and_keeps_provenance():
    rc = np.asarray(PCM)[::-1, ::-1].tolist()  # reverse complement counts
    recs, mem = pm.merge_hocomoco([("H14CORE", ann("TFA.CORE"), PCM),
                                   ("H14INVITRO", ann("TFA.INVITRO", quality="B"), rc)])
    assert len(recs) == 1 and recs[0][2] == ["H14CORE", "H14INVITRO"]
    assert recs[0][3] == ["TFA.INVITRO"]
    assert [m["quality"] for m in mem] == ["A", "B"]  # per-entry quality kept
    assert {m["pma_id"] for m in mem} == {"HO14_TFA.CORE"}


def test_same_pcm_different_tf_or_experiment_stays_separate():
    recs, mem = pm.merge_hocomoco([("H14CORE", ann("TFA.CORE"), PCM),
                                   ("H14INVITRO", ann("TFB.INVITRO", tf="TFB"), PCM),
                                   ("H14INVIVO", ann("TFA.INVIVO", origin="PEAKS2"), PCM),
                                   ("H14INVIVO", ann("TFA.INVIVO.S", dtype="S"), PCM)])
    assert len(recs) == 4
    assert all(m["match"] == "representative" for m in mem)


def test_same_experiment_other_original_motif_is_labelled():
    _, mem = pm.merge_hocomoco([("H14CORE", ann("R.CORE", om="R@score"), PCM),
                                ("H14INVIVO", ann("R.INVIVO", om="R@pvalue"), PCM)])
    assert mem[1]["match"] == "same_experiment_other_original_motif"
