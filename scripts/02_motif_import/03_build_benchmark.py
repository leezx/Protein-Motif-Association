"""Step 2: similarity calibration benchmark (design §8, §8.1).

Builds P-high, P-provisional and N-challenge pairs from metadata only
(never from similarity), assigns TFClass-family partitions, and writes
the blinded manual review sheet. No similarity is computed here.

Outputs: result/step2_motif_import/benchmark/
  benchmark_pairs.tsv, benchmark_queries.txt,
  review_sheet.html, review_key.tsv, review_labels_template.tsv
"""
import base64
import hashlib
import io
import os
import sys
from collections import defaultdict
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pma_motif as pm  # noqa: E402

PROC = Path(os.environ["PMA_MOTIF_PROCESSED"]) / "v0.2_raw_layer"
OUT = Path(os.environ["PMA_MOTIF_RESULT"]) / "step2_motif_import" / "benchmark"
MASTER = Path(os.environ["PMA_MOTIF_RAW"]) / "hocomoco_v14" / os.environ.get("PMA_FETCH_DATE", "2026-10-14") \
    / "tf_masterlist.tsv"
SEED = 20261015
BINS = [0, 8, 10, 12, 15, 1000]
LABELS = ["<=8", "9-10", "11-12", "13-15", ">15"]
PER_BIN, PER_TFPAIR, REVIEW_PER_BIN = 100, 3, 20
IUPAC2 = {frozenset("AC"): "M", frozenset("AG"): "R", frozenset("AT"): "W",
          frozenset("CG"): "S", frozenset("CT"): "Y", frozenset("GT"): "K"}
COMP = str.maketrans("ACGTMRWSYKN", "TGCAKYWSRMN")


def consensus(m):
    out = []
    for row in m:
        o = np.argsort(row)[::-1]
        if row[o[0]] >= 0.6:
            out.append(pm.NT[o[0]])
        elif row[o[0]] + row[o[1]] >= 0.75 and row[o[1]] >= 0.25:
            out.append(IUPAC2[frozenset(pm.NT[o[0]] + pm.NT[o[1]])])
        else:
            out.append("N")
    return "".join(out)


def kmers(cons, k=5):
    s = set()
    for c in (cons, cons.translate(COMP)[::-1]):
        s.update(c[i:i + k] for i in range(len(c) - k + 1) if "N" not in c[i:i + k])
    return s


def length_bin(n):
    return pd.cut(pd.Series(n), BINS, labels=LABELS).astype(str).to_numpy()


def tfclass(hgnc_by_id):
    t = pd.read_csv(MASTER, sep="\t", dtype=str).fillna("")
    t = t[t["curated:uniprot_id"].str.endswith("_HUMAN")]
    rows = {}
    for ids, sc, fam in zip(t["auto:hgnc"], t["tfclass:superclass"], t["tfclass:family"]):
        for h in filter(None, ids.split(";")):
            if h in hgnc_by_id:
                rows.setdefault(hgnc_by_id[h], (sc, fam))
    return rows


def sample(df, rng):
    """≤ PER_TFPAIR per TF pair, then ≤ PER_BIN per length bin (§8.1)."""
    df = df.sample(frac=1, random_state=rng).groupby("tf_pair", sort=True).head(PER_TFPAIR)
    return df.groupby("len_bin", sort=True).head(PER_BIN)


def main():  # noqa: C901
    OUT.mkdir(parents=True, exist_ok=True)
    md = pd.read_csv(PROC / "PMA_motif_metadata.tsv", sep="\t", low_memory=False)
    mats = {mid: m for mid, _a, m in pm.read_meme(PROC / "PMA_motifs_raw.meme")}
    md = md[md.pma_id.isin(mats)].set_index("pma_id")
    h = pd.read_csv(os.environ["PMA_HGNC_MAP"], sep="\t", dtype=str)
    tfc = tfclass(dict(zip(h.hgnc_id.str.replace("HGNC:", "", regex=False), h.symbol)))
    md["tf1"] = md.motif_tf_assignment.fillna("").str.split(";").str[0]
    md["superclass"] = md.tf1.map(lambda t: tfc.get(t, ("", ""))[0])
    md["family"] = md.tf1.map(lambda t: tfc.get(t, ("", ""))[1])
    md["partition"] = [("" if not f else
                        "calibration" if int(hashlib.sha1(f.encode()).hexdigest()[-1], 16) % 2 == 0
                        else "evaluation") for f in md.family]

    def pairs_frame(rows, setname, label_source):
        p = pd.DataFrame(rows, columns=["m1", "m2"])
        for i in (1, 2):
            p[f"tf{i}"] = p[f"m{i}"].map(md.tf1)
            p[f"len{i}"] = p[f"m{i}"].map(md.length).astype(int)
            p[f"src{i}"] = p[f"m{i}"].map(md.source_db)
            p[f"family{i}"] = p[f"m{i}"].map(md.family)
            p[f"part{i}"] = p[f"m{i}"].map(md.partition)
        p["len_bin"] = length_bin(np.minimum(p.len1, p.len2))
        p["tf_pair"] = [";".join(sorted(x)) for x in zip(p.tf1, p.tf2)]
        p["set"], p["label_source"] = setname, label_source
        return p

    # ---- P-high (a): Codebook Table 13 consistent/ok, mapped, x Codebook PWM of same TF
    cur = pd.read_csv(PROC / "codebook_table13_mapping.tsv", sep="\t")
    cur = cur[cur.consistent_ok & (cur.n_mapped > 0)]
    cb = md[md.source_db == "Codebook"]
    rows = []
    for tf, ids in zip(cur.tf, cur.pma_ids):
        ext = sorted(ids.split(";"))[0]
        for c in cb.index[cb.tf1 == tf]:
            rows.append((ext, c))
    ph = pairs_frame(rows, "P_high", "codebook_t13")

    # ---- eligible motifs for P-provisional / N-challenge
    fl = md.qc_flags.fillna("").str.replace("low_ic", "").str.strip(";")
    el = md[(md.direct_binding_evidence == "supported") & (md.species_basis == "human") &
            (md.is_composite.astype(str) == "False") & md.derived_from.isna() & (fl == "") &
            (md.tf1 != "")]
    print(f"eligible motifs: {len(el)} ({el.source_db.value_counts().to_dict()})")

    def same_group(a, b):
        for g in ("exact_dup_group", "rounded_equiv_group"):
            x, y = md.at[a, g], md.at[b, g]
            if isinstance(x, str) and x == y:
                return True
        ea, eb = md.at[a, "experiment_ids"], md.at[b, "experiment_ids"]
        return isinstance(ea, str) and isinstance(eb, str) and bool(set(ea.split(";")) & set(eb.split(";")))

    rows = [(a, b) for _tf, g in el.groupby("tf1") for a, b in combinations(sorted(g.index), 2)
            if md.at[a, "source_db"] != md.at[b, "source_db"] and not same_group(a, b)]
    pp_all = pairs_frame(rows, "P_provisional", "same_tf_metadata")

    # ---- N-challenge candidates via shared 5-mer index
    cons = {i: consensus(mats[i]) for i in el.index}
    idx = defaultdict(list)
    for i, c in cons.items():
        for k in kmers(c):
            idx[k].append(i)
    cand = set()
    sc, ln = el.superclass.to_dict(), el.length.to_dict()
    for ids in idx.values():
        for a, b in combinations(sorted(ids), 2):
            if sc[a] and sc[b] and sc[a] != sc[b] and abs(ln[a] - ln[b]) <= 2:
                cand.add((a, b))
    nc_all = pairs_frame(sorted(cand), "N_challenge", "metadata_challenge")

    pp, nc = sample(pp_all, SEED), sample(nc_all, SEED)
    bench = pd.concat([ph, pp, nc], ignore_index=True)
    bench["partition"] = np.where(
        (bench.part1 == "") | (bench.part2 == "") | bench.part1.isna() | bench.part2.isna(), "unassigned",
        np.where(bench.part1 == bench.part2, bench.part1, "cross_family"))
    bench.insert(0, "pair_id", [f"BP{i:05d}" for i in range(len(bench))])
    bench["consensus1"] = bench.m1.map(lambda x: consensus(mats[x]))
    bench["consensus2"] = bench.m2.map(lambda x: consensus(mats[x]))
    bench.to_csv(OUT / "benchmark_pairs.tsv", sep="\t", index=False)
    q = sorted(set(bench.m1) | set(bench.m2))
    (OUT / "benchmark_queries.txt").write_text("\n".join(q) + "\n")
    cand_counts = pd.concat([pp_all.assign(s="P_provisional"), nc_all.assign(s="N_challenge")]) \
        .groupby(["s", "len_bin"]).size().rename("n_candidates")
    cand_counts.to_csv(OUT / "candidate_counts.tsv", sep="\t")
    print(bench.groupby(["set", "len_bin"]).size().unstack(fill_value=0).to_string())
    print(bench.groupby(["set", "partition"]).size().unstack(fill_value=0).to_string())
    print(f"queries: {len(q)}")

    review_sheet(pp, nc, mats)


# ---- blinded review sheet -------------------------------------------------

def logo_png(m, title):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.font_manager import FontProperties
    from matplotlib.patches import PathPatch
    from matplotlib.textpath import TextPath
    from matplotlib.transforms import Affine2D
    colors = dict(A="#109648", C="#255C99", G="#F7B32B", T="#D62839")
    fp = FontProperties(family="DejaVu Sans", weight="bold")
    fig, ax = plt.subplots(figsize=(max(2.0, 0.32 * len(m)), 1.3), dpi=80)
    p = np.clip(m, 1e-9, 1)
    ic = 2 + (p * np.log2(p)).sum(axis=1)
    for x, (row, h) in enumerate(zip(m, ic)):
        y = 0.0
        for j in np.argsort(row):
            hh = row[j] * h
            if hh < 1e-3:
                continue
            tp = TextPath((0, 0), pm.NT[j], size=1, prop=fp)
            bb = tp.get_extents()
            t = Affine2D().translate(-bb.x0, -bb.y0).scale(0.9 / bb.width, hh / bb.height) \
                .translate(x + 0.05, y)
            ax.add_patch(PathPatch(t.transform_path(tp), color=colors[pm.NT[j]], lw=0))
            y += hh
    ax.set_xlim(0, len(m))
    ax.set_ylim(0, 2)
    ax.set_xticks([])
    ax.set_yticks([0, 1, 2])
    ax.set_title(title, fontsize=8, loc="left")
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode()


def review_sheet(pp, nc, mats):
    rng = np.random.default_rng(SEED)
    pick = pd.concat([d.groupby("len_bin", sort=True).head(REVIEW_PER_BIN) for d in (pp, nc)])
    pick = pick.iloc[rng.permutation(len(pick))].reset_index(drop=True)
    pick.insert(0, "review_id", [f"R{i + 1:03d}" for i in range(len(pick))])
    pick[["review_id", "m1", "m2", "set", "len_bin", "tf1", "tf2"]].to_csv(
        OUT / "review_key.tsv", sep="\t", index=False)
    pick[["review_id"]].assign(label="", note="").to_csv(
        OUT / "review_labels_template.tsv", sep="\t", index=False)
    html = ["<!doctype html><meta charset=utf-8><title>PMA motif pair review</title>",
            "<style>body{font-family:sans-serif;margin:16px}div.p{border-top:1px solid #ccc;"
            "padding:8px 0}img{margin-right:12px;vertical-align:top}</style>",
            "<h1>PMA motif pair review (blinded)</h1><p>For each pair: do motif 1 and motif 2 "
            "describe the <b>same sequence pattern</b>? Motif 2 is shown in both orientations. "
            "Record one label per review ID in <code>review_labels_template.tsv</code>: "
            "<code>same</code> / <code>different</code> / <code>partial_composite</code> / "
            "<code>unsure</code>. TF names and scores are hidden on purpose.</p>"]
    for r in pick.itertuples():
        a, b = mats[r.m1], mats[r.m2]
        html.append(f"<div class=p><b>{r.review_id}</b><br>"
                    f"<img src='data:image/png;base64,{logo_png(a, f'motif 1 ({len(a)} bp)')}'>"
                    f"<img src='data:image/png;base64,{logo_png(b, f'motif 2 ({len(b)} bp)')}'>"
                    f"<img src='data:image/png;base64,{logo_png(pm.revcomp(b), 'motif 2, reverse complement')}'>"
                    "</div>")
    (OUT / "review_sheet.html").write_text("\n".join(html))
    print(f"review sheet: {len(pick)} pairs")


if __name__ == "__main__":
    main()
