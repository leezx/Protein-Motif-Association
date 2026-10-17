"""Step 3b §19 closure items (ChatGPT final review F49-F52): QC supplements for the coverage-greedy tiers.

usage (PMA_TIER_SET=greedy):
  21_greedy_qc.py marginal    -> align_tiers_greedy/hub_marginal.tsv, hub_marginal_summary.tsv
       per hub: core motifs it covers at s >= tau and how many of them no other hub of the tier covers
       (Delta_i = coverage lost when the hub is removed); reported next to the pairwise s >= 0.85 metric.
  21_greedy_qc.py composite   -> align_tiers_greedy/composite_supplement.tsv, PMA_composite_supplement.meme
       optional supplement: greedy over connected composite core motifs alone, until >= 90 % coverage.
  21_greedy_qc.py stability   -> align_tiers_greedy/stability.tsv
       10 x 80 % experiment-stratified subsamples (seed 20261016 + b): draw 80 % of independent experiments
       (a core motif without a resolved experiment is its own experiment); a motif is retained if any of
       its experiments is drawn. Greedy is rerun on retained connected core motifs (core definition fixed).
       Per tier: in-sample coverage, held-out coverage (non-retained motifs covered by subsample hubs),
       full coverage, hub ID Jaccard, and the share of reference hubs with a subsample hub at s >= tau.
  21_greedy_qc.py freeze      -> align_tiers_greedy/MANIFEST.json (sha256 of every output, tau, commit)
"""
import hashlib
import importlib
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "02_motif_import"))
ut = importlib.import_module("17_unique_tiers")
import pma_motif as pm  # noqa: E402

assert ut.SET == "greedy", "run with PMA_TIER_SET=greedy"
T, R = ut.T, ut.R
SEED, N_SUB, FRAC = 20261016, 10, 0.8


def setup():
    _, x, meta = ut.unique_meta()
    nd, g, rank = ut.load_core_tau_graph(meta)
    elig = ~nd.isolated.to_numpy()
    go = pd.read_csv(T / "greedy_order.tsv", sep="\t")
    gid = dict(zip(nd.unique_id, nd.gid))
    return x, nd, g, rank, elig, go, np.array([gid[u] for u in go.unique_id])


def covered_by(g, hubs, n):
    c = np.zeros(n, bool)
    for h in hubs:
        c[g.indices[g.indptr[h]:g.indptr[h + 1]]] = True
    return c


def marginal():
    _, nd, g, _, elig, go, hub_gid = setup()
    rows, summ = [], []
    for name, k in ut.TARGETS.items():
        H = hub_gid[:k]
        cnt = np.asarray(g[:, H].sum(1)).ravel()  # hubs of the tier covering each motif (g symmetric)
        only = (cnt == 1) & elig
        for r, h in enumerate(H):
            nb = g.indices[g.indptr[h]:g.indptr[h + 1]]
            rows.append(dict(tier=name, rank=r + 1, unique_id=nd.unique_id[h], partition=nd.part[h],
                             covered_n=int(elig[nb].sum()), unique_covered_n=int(only[nb].sum())))
        d = pd.DataFrame(rows[-k:])
        summ.append(dict(tier=name, hubs=k, fraction_zero_marginal_hubs=float((d.unique_covered_n == 0).mean()),
                         median_unique_coverage_per_hub=float(d.unique_covered_n.median()),
                         median_covered_per_hub=float(d.covered_n.median()),
                         coverage=float(((cnt > 0) & elig).sum() / elig.sum())))
    pd.DataFrame(rows).to_csv(T / "hub_marginal.tsv", sep="\t", index=False)
    s = pd.DataFrame(summ)
    s.to_csv(T / "hub_marginal_summary.tsv", sep="\t", index=False, float_format="%.4f")
    print(s.to_string(index=False))


def composite():
    _, nd, g, rank, elig, _, _ = setup()
    el = elig & (nd.part.to_numpy() == "composite")
    out = ut.greedy_core(g, el, rank, int(el.sum()))
    stop = next(k for k, (_, _, c) in enumerate(out) if c >= 0.90) + 1
    d = pd.DataFrame([dict(rank=k + 1, unique_id=nd.unique_id[i], node_id=nd.node_id[i], gain=gn, cum_coverage=c)
                      for k, (i, gn, c) in enumerate(out[:stop])])
    d.to_csv(T / "composite_supplement.tsv", sep="\t", index=False, float_format="%.5f")
    mats = {n: m for n, _, m in pm.read_meme(R / "nodes" / "nodes.meme")}
    pm.write_meme([(f"PMS_C{r:04d}", u, mats[n]) for r, u, n in zip(d["rank"], d.unique_id, d.node_id)],
                  T / "PMA_composite_supplement.meme")
    print(f"composite supplement: {stop} hubs, coverage {d.cum_coverage.iloc[-1]:.4f} of {int(el.sum())} connected composite core")


def stability():
    x, nd, g, rank, elig, go, hub_gid = setup()
    n = len(nd)
    core_ids = set(nd.unique_id)
    e = x[x.unique_id.isin(core_ids)]
    exp = e.exp.where(e.exp.notna(), "solo:" + e.unique_id)
    pairs = pd.DataFrame({"unique_id": e.unique_id, "exp": exp}).drop_duplicates()
    gid = dict(zip(nd.unique_id, nd.gid))
    pairs["gid"] = pairs.unique_id.map(gid)
    exps = np.sort(pairs.exp.unique())
    kmax = max(ut.TARGETS.values())
    rows = []
    for b in range(N_SUB):
        rng = np.random.default_rng(SEED + b)
        drawn = set(rng.choice(exps, size=int(round(FRAC * len(exps))), replace=False))
        keep = np.zeros(n, bool)
        keep[pairs.gid[pairs.exp.isin(drawn)].to_numpy()] = True
        el = elig & keep
        out = ut.greedy_core(g, el, rank, kmax)
        sub = np.array([i for i, _, _ in out])
        held = elig & ~keep
        for name, k in ut.TARGETS.items():
            S, H = sub[:k], hub_gid[:k]
            cs = covered_by(g, S, n)
            ch = covered_by(g, H, n)
            match = covered_by(g, S, n)[H].mean()  # reference hub within tau of (or equal to) a subsample hub
            rows.append(dict(subsample=b, tier=name, hubs=len(S), retained=int(el.sum()), held_out=int(held.sum()),
                             coverage_in_sample=float(cs[el].mean()), coverage_held_out=float(cs[held].mean()),
                             coverage_held_out_reference_hubs=float(ch[held].mean()),
                             coverage_full=float(cs[elig].mean()), coverage_full_reference=float(ch[elig].mean()),
                             hub_jaccard=float(len(set(S) & set(H)) / len(set(S) | set(H))),
                             reference_hubs_matched_tau=float(match)))
        print(rows[-3:], flush=True)
    d = pd.DataFrame(rows)
    d.to_csv(T / "stability.tsv", sep="\t", index=False, float_format="%.4f")
    print(d.groupby("tier").agg(["median", "min", "max"]).round(4).T.to_string())


def freeze():
    commit = subprocess.run(["git", "-C", str(HERE), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    files = {str(p.relative_to(T)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(T.rglob("*"))
             if p.is_file() and p.name != "MANIFEST.json"}  # F53: recursive, relative paths
    need = ["greedy_order.tsv", "tier_qc.tsv", "tier_mapping.tsv", "stability.tsv", "hub_marginal.tsv",
            "PMA_composite_supplement.meme"] + [f"final_tier_{t}.tsv.gz" for t in ut.TARGETS] + \
        [f"reference_{t}/{f}" for t in ut.TARGETS for f in ("PMA_representatives.meme", "PMA_cluster_summary.tsv",
                                                             "PMA_motif_to_cluster.tsv", "PMA_unrepresented_motifs.tsv",
                                                             "reference_summary.json")]
    missing = [f for f in need if f not in files]
    assert not missing, missing
    integrity = {}
    for t, k in ut.TARGETS.items():  # integrity: MEME = summary = target; every reference_cluster_id is summarised
        d = T / f"reference_{t}"
        cs = pd.read_csv(d / "PMA_cluster_summary.tsv", sep="\t", usecols=["cluster_id"])
        n_meme = sum(1 for line in open(d / "PMA_representatives.meme") if line.startswith("MOTIF"))
        mc = pd.read_csv(d / "PMA_motif_to_cluster.tsv", sep="\t", usecols=["reference_cluster_id"]).reference_cluster_id
        orphan = int((~mc.dropna().isin(set(cs.cluster_id))).sum())
        assert n_meme == len(cs) == k and orphan == 0, (t, n_meme, len(cs), orphan)
        integrity[t] = dict(meme_motifs=n_meme, summary_rows=len(cs), orphan_reference_ids=orphan,
                            records_in_reference=int(mc.notna().sum()))
    man = dict(tier_set="greedy", design="STEP3B_V03_INTEGRATION_DESIGN.md §19", code_commit=commit, tau=ut.tau(),
               strict=ut.STRICT, s_edge=0.65, s_redundancy=ut.S_RED, targets=ut.TARGETS,
               core_definition=json.loads((ut.U / "core_definition.json").read_text())["definition"],
               dedup="t = 0.99 greedy (§16)", integrity=integrity, sha256=files)
    (T / "MANIFEST.json").write_text(json.dumps(man, indent=2) + "\n")
    print(json.dumps({k: v for k, v in man.items() if k != "sha256"}, indent=2), len(files), "files")


if __name__ == "__main__":
    {"marginal": marginal, "composite": composite, "stability": stability, "freeze": freeze}[sys.argv[1]]()
