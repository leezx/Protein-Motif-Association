"""Step 3b §17: three PI tiers on the 101,228 unique motifs (t = 0.99 dedup).

usage: 17_unique_tiers.py choose   -> unique/tier_choice.json
       17_unique_tiers.py build    -> align_tiers/final_tier_<T>.tsv.gz (node level, for
                                      07_annotate_clusters.py with PMA_TIER_GRAPH=align),
                                      align_tiers/tier_qc.tsv, align_tiers/tier_mapping.tsv
Graph: connected unique motifs, s >= 0.65, weight s (16_unique_louvain.R scan).
Isolated unique motifs (no partner at s >= 0.65) are NOT in the tier budgets; each is
its own entry in the separate `isolated` partition (PI 2026-10-17).
Tier choice: per target (500 / 1,000 / 2,000) the scanned resolution whose
K_monomer + K_composite (connected motifs) is closest; ties -> smaller resolution.
Hub (coverage-maximising, §15/§15b): within a cluster, the unique motif with the most
cluster members at s >= tau (exact edges), each unique motif weighted 1 (each is a
distinct pattern after dedup); ties within 1 % of cluster size: higher mean s to
members (s < 0.65 counted as 0), evidence v2 tier <= 2, more independent experiments,
unique ID.
QC (reported, never tunes resolution): coverage of unique motifs and of source
records by their hub at tau and at 0.95, coverage per source, hub redundancy
(s >= 0.85 across clusters), N-challenge co-clustering, AMI vs Codebook T10 /
HOCOMOCO, cross-tier mapping.
"""
import importlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
gt = importlib.import_module("05_gates")

R = gt.R
U = R / "unique"
T = R / "align_tiers"
TARGETS = {"LOW": 500, "MEDIUM": 1000, "HIGH": 2000}
PARTS = ("composite", "monomer")
STRICT, S_RED = 0.95, 0.85


def tau():
    return float(json.loads((R / "tau_calibration" / "tau.json").read_text())["tau"])


def scan(part):
    return pd.read_csv(U / f"scan_{part}.tsv.gz", sep="\t", dtype=str).set_index("unique_id")


def choose():
    T.mkdir(parents=True, exist_ok=True)
    k = {p: scan(p).nunique() for p in PARTS}
    res = sorted(set(k["monomer"].index) & set(k["composite"].index), key=lambda c: float(c[1:]))
    tab = pd.DataFrame({"res": [float(c[1:]) for c in res], "K_monomer": [int(k["monomer"][c]) for c in res],
                        "K_composite": [int(k["composite"][c]) for c in res]})
    tab["K_total"] = tab.K_monomer + tab.K_composite
    out = {"scan": tab.to_dict("records"), "tiers": {}}
    for name, tgt in TARGETS.items():
        d = (tab.K_total - tgt).abs()
        b = tab.loc[d[d == d.min()].index].sort_values("res").iloc[0]
        out["tiers"][name] = dict(target=tgt, res=float(b.res), K_total=int(b.K_total), K_monomer=int(b.K_monomer),
                                  K_composite=int(b.K_composite), deviation=round(float(b.K_total / tgt - 1), 4))
    (U / "tier_choice.json").write_text(json.dumps(out, indent=2) + "\n")
    (T / "tier_choice.json").write_text(json.dumps(out, indent=2) + "\n")  # read by 07_annotate_clusters.py
    print(tab.to_string(index=False))
    print(json.dumps(out["tiers"], indent=2))


def unique_meta():
    """Per unique motif: high evidence (any record tier <= 2), independent experiments."""
    m = pd.read_csv(R / "dedup" / "PMA_motif_to_unique_t0.99.tsv.gz", sep="\t",
                    usecols=["pma_id", "node_id", "unique_id", "partition"])
    ev = pd.read_csv(gt.EVID, sep="\t", usecols=["pma_id", "evidence_tier", "independent_experiment_id",
                                                  "independence_status", "source_db"])
    x = m.merge(ev, on="pma_id", how="left")
    ok = ~x.independence_status.isin(["unresolved", "independence_unresolved"]) & x.independent_experiment_id.notna()
    x["exp"] = x.independent_experiment_id.where(ok)
    g = x.groupby("unique_id")
    meta = pd.DataFrame({"high": g.evidence_tier.min().le(2), "n_exp": g.exp.nunique()})
    return m, x, meta


def build():
    tv = tau()
    choice = json.loads((U / "tier_choice.json").read_text())["tiers"]
    m, x, meta = unique_meta()
    qc, finals = [], {t: [] for t in TARGETS}
    for part in PARTS:
        gn = pd.read_csv(U / f"graph_nodes_{part}.tsv", sep="\t")
        n = len(gn)
        conn_ids = gn.unique_id[~gn.isolated].to_numpy()
        row = {u: i for i, u in enumerate(gn.unique_id)}
        z = np.load(U / f"tau_edges_{part}.npz")
        tq, tt, ts = z["q"].astype(np.int64), z["t"].astype(np.int64), z["s"]
        key = np.minimum(tq, tt) * n + np.maximum(tq, tt)
        o = np.argsort(key)
        key, ks = key[o], ts[o]
        ge = pd.read_csv(U / f"graph_edges_{part}.tsv", sep="\t")
        conn_rows = np.flatnonzero(~gn.isolated.to_numpy())
        gi, gj, gs = conn_rows[ge.i.to_numpy()], conn_rows[ge.j.to_numpy()], ge.s.to_numpy()
        del ge
        sc = scan(part).reindex(conn_ids)
        hm = meta.reindex(gn.unique_id)

        def s_lookup(a, b):
            k = np.minimum(a, b) * n + np.maximum(a, b)
            p = np.clip(np.searchsorted(key, k), 0, len(key) - 1)
            hit = key[p] == k
            return np.where(a == b, 1.0, np.where(hit, ks[p], 0.0))

        for name, t in choice.items():
            lab = np.full(n, -1, dtype=np.int64)
            lab[conn_rows] = pd.factorize(sc[f"r{t['res']:g}"])[0]
            nc = lab.max() + 1
            same = (lab[tq] == lab[tt]) & (lab[tq] >= 0)
            cov = np.bincount(tq[same], minlength=n) + np.bincount(tt[same], minlength=n) + 1
            sameg = lab[gi] == lab[gj]
            ssum = np.bincount(gi[sameg], weights=gs[sameg], minlength=n) + \
                np.bincount(gj[sameg], weights=gs[sameg], minlength=n)
            size = np.bincount(lab[conn_rows], minlength=nc)
            mean_s = ssum / np.maximum(size[np.maximum(lab, 0)] - 1, 1)
            key_df = pd.DataFrame({"lab": lab, "cov": cov, "ms": mean_s, "h": ~hm.high.fillna(False).to_numpy(),
                                   "e": -hm.n_exp.fillna(0).to_numpy(), "u": gn.unique_id.to_numpy()})
            key_df = key_df[key_df.lab >= 0]
            best = key_df.groupby("lab").cov.transform("max")
            cand = key_df[key_df.cov >= best - 0.01 * size[key_df.lab]]
            hub = cand.sort_values(["lab", "ms", "h", "e", "u"], ascending=[True, False, True, True, True]) \
                .drop_duplicates("lab").set_index("lab")
            hub_row = np.array([row[u] for u in hub.reindex(range(nc)).u])
            members = conn_rows
            s_hub = s_lookup(hub_row[lab[members]], members)
            covered_u = np.zeros(n, bool)
            covered_u[members] = s_hub >= tv
            strict_u = np.zeros(n, bool)
            strict_u[members] = s_hub >= STRICT
            hr = np.sort(hub_row)
            hpair = np.isin(tq, hr) & np.isin(tt, hr) & (ts >= S_RED) & (lab[tq] != lab[tt])
            red = np.zeros(n, bool)
            red[tq[hpair]] = red[tt[hpair]] = True
            # node-level output: every source node -> its unique motif's cluster
            part_nodes = m[m.partition == part]
            r = part_nodes.unique_id.map(row).to_numpy()
            iso = gn.isolated.to_numpy()[r]
            hub_node = gn.node_id.to_numpy()[hub_row]
            f = pd.DataFrame({
                "node_id": part_nodes.node_id.to_numpy(), "unique_id": part_nodes.unique_id.to_numpy(),
                "partition": np.where(iso, "isolated", part),
                "cluster": np.where(iso, "I" + part[0].upper() + pd.Series(r).astype(str).to_numpy(),
                                    part[0].upper() + pd.Series(lab[r]).astype(str).to_numpy()),
                "rep_node": np.where(iso, gn.node_id.to_numpy()[r], hub_node[np.maximum(lab[r], 0)]),
                "covered": np.where(iso, 1, covered_u[r].astype(int)),
                "covered_strict": np.where(iso, 1, strict_u[r].astype(int))}).drop_duplicates("node_id")
            finals[name].append(f)
            rec = x[x.partition == part].assign(cov=lambda d: covered_u[d.unique_id.map(row).to_numpy()],
                                                iso=lambda d: gn.isolated.to_numpy()[d.unique_id.map(row).to_numpy()])
            rec = rec[~rec.iso]
            qc.append(dict(tier=name, part=part, res=t["res"], K=int(nc), unique_connected=int(len(members)),
                           unique_isolated=int(gn.isolated.sum()),
                           coverage_unique_tau=float(covered_u[members].mean()),
                           coverage_unique_strict=float(strict_u[members].mean()),
                           coverage_records_tau=float(rec["cov"].mean()),
                           clusters_cov90=float((np.bincount(lab[members], weights=covered_u[members], minlength=nc)
                                                 / size >= 0.9).mean()),
                           hub_redundancy=float(red[hub_row].mean()),
                           coverage_by_source=json.dumps(rec.groupby("source_db")["cov"].mean().round(3).to_dict())))
            print({k: v for k, v in qc[-1].items() if k != "coverage_by_source"}, flush=True)
    q = pd.DataFrame(qc)
    nodes_all = pd.read_csv(R / "nodes" / "motif_nodes.tsv", sep="\t")
    node_of = dict(zip(nodes_all.pma_id, nodes_all.node_id))
    bp = pd.read_csv(gt.RESULT / "step2_motif_import" / "benchmark" / "benchmark_pairs.tsv", sep="\t", dtype=str)
    nch = bp[bp["set"] == "N_challenge"]
    md = pd.read_csv(gt.PROC / "PMA_motif_metadata.tsv", sep="\t", low_memory=False, usecols=["pma_id", "codebook_cluster"])
    hc = pd.read_csv(gt.RAW / "hocomoco_v14" / "2026-10-14" / "H14CORE-CLUSTERED_cluster_list.tsv", sep="\t")
    h14 = {f"HO14_{mm.strip()}": rr for rr, ms in zip(hc.Representative_Motif, hc.Clustered_Motifs) for mm in ms.split(";")}
    refs = {"codebook": md.dropna(subset=["codebook_cluster"]).set_index("pma_id").codebook_cluster.astype(str),
            "hocomoco": pd.Series(h14)}
    rng = np.random.default_rng(gt.SEED)
    tot = []
    for name in TARGETS:
        f = pd.concat(finals[name], ignore_index=True)
        f.to_csv(T / f"final_tier_{name}.tsv.gz", sep="\t", index=False)
        finals[name] = f
        cl = dict(zip(f.node_id, f.partition + ":" + f.cluster))
        a, b = nch.m1.map(node_of).map(cl), nch.m2.map(node_of).map(cl)
        ok = a.notna() & b.notna()
        g = q[q.tier == name]
        row = dict(tier=name, part="ALL", res=g.res.iloc[0], K=int(g.K.sum()),
                   unique_connected=int(g.unique_connected.sum()), unique_isolated=int(g.unique_isolated.sum()),
                   coverage_unique_tau=float((g.coverage_unique_tau * g.unique_connected).sum() / g.unique_connected.sum()),
                   coverage_unique_strict=float((g.coverage_unique_strict * g.unique_connected).sum() / g.unique_connected.sum()),
                   hub_redundancy=float((g.hub_redundancy * g.K).sum() / g.K.sum()),
                   n_challenge=float((a[ok] == b[ok]).mean()), n_challenge_pairs=int(ok.sum()))
        for rname, ref in refs.items():
            lab = ref.index.map(node_of).map(cl)
            k = pd.notna(lab)
            row[f"AMI_{rname}"], row[f"AMI_{rname}_se"] = gt.ami_boot(ref.to_numpy()[k], np.asarray(lab[k]).astype(str), rng)
        row["flags"] = ";".join(x for x, bad in (("low_fidelity", row["coverage_unique_tau"] < 0.90),
                                                 ("possible_overmerging", row["n_challenge"] > 0.05),
                                                 ("residual_redundancy", row["hub_redundancy"] > 0.15)) if bad)
        tot.append(row)
    q = pd.concat([q, pd.DataFrame(tot)], ignore_index=True)
    q.to_csv(T / "tier_qc.tsv", sep="\t", index=False, float_format="%.4f")
    rows = []
    for child, parent in (("HIGH", "MEDIUM"), ("MEDIUM", "LOW")):
        c = finals[child][["node_id", "cluster", "partition"]].merge(
            finals[parent][["node_id", "cluster"]], on="node_id", suffixes=("_child", "_parent"))
        c = c[c.partition != "isolated"]
        ct = c.groupby(["cluster_child", "cluster_parent"]).size().rename("n").reset_index()
        best = ct.sort_values(["cluster_child", "n"], ascending=[True, False]).drop_duplicates("cluster_child")
        best["purity"] = best.n.to_numpy() / c.groupby("cluster_child").size().reindex(best.cluster_child).to_numpy()
        best["child_tier"], best["parent_tier"] = child, parent
        rows.append(best)
    mp = pd.concat(rows, ignore_index=True)
    mp.to_csv(T / "tier_mapping.tsv", sep="\t", index=False, float_format="%.4f")
    print(q[q.part == "ALL"].drop(columns=["coverage_by_source"], errors="ignore").to_string(index=False))
    print(mp.groupby(["child_tier", "parent_tier"]).purity.describe().round(3).to_string())


if __name__ == "__main__":
    {"choose": choose, "build": build}[sys.argv[1]]()
