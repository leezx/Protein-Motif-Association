"""Targets, control pools and motif libraries for hotspot motif enrichment (§18.3).

usage: 26_motif_enrichment_prep.py <bins500.npz> <hotspot_regions_v2 dir> <blacklist.bed.gz> <genes.gtf>
                                    <motif_metadata.tsv> <motifs_raw.meme> <step3b reference_tiers dir> <chrom.sizes> <out_dir>
Env: PMA_MOTIF_CAP (10000), PMA_MOTIF_SEED (1), PMA_ATAC_N (18651), PMA_DNASE_N (2086).

Writes to out_dir:
  targets/<class>_<tier>[_<stratum>].bed   one 500 bp summit bin per region, sampled down to the cap
  pools/G_<class>_<tier>[_<stratum>].bed    candidate 500 bp bins for homer2 bg -bg, from blacklist-free bins outside the
                                            same-tier set of the class: every eligible promoter bin (so CpG-island
                                            targets have matches) plus PMA_G_POOL (500,000) random eligible distal bins
                                            (own RNG, seed + 100). Promoter stratum: promoter bins only; distal: distal only.
                                            Run 1 excluded all top20 bins: HOMER's equal-per-GC-bin rule then left
                                            40–920 control sequences for protein top1/top5 (§18.3).
  pools/A_protein_<tier>.bed                accessibility-stratified candidate bins outside the same-tier protein set
                                            (homer2 bg -bg); N for A = min(targets, pool // 2)
  motifs/{JASPAR2026_CORE_vert_nr,PMA_HIGH,PMA_MEDIUM,PMA_LOW}.meme and motif_annotation.tsv
  manifest.tsv (one row per comparison), prep_summary.json
"""
import gzip
import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

BIN = 500
TIERS = ["top20", "top10", "top5", "top1"]
CAP = int(os.environ.get("PMA_MOTIF_CAP", "10000")); SEED = int(os.environ.get("PMA_MOTIF_SEED", "1"))
NSTRATA = 20; POOL_PER_TARGET = 20; PROM_FLANK = 1000; G_POOL = int(os.environ.get("PMA_G_POOL", "500000"))


def ecdf_rank(v):
    pos = np.sort(v[v > 0])
    return np.searchsorted(pos, v, side="right") / pos.size


def interval_mask(df, offs, nb, chrom_idx, nbin, flank=0):
    """Boolean bin mask of bins overlapping [s - flank, e + flank) intervals in df (c, s, e)."""
    m = np.zeros(nbin, dtype=bool)
    df = df[df.c.isin(chrom_idx)]
    ci = df.c.map(chrom_idx).to_numpy()
    s = np.maximum(df.s.to_numpy() - flank, 0) // BIN; e = (df.e.to_numpy() + flank - 1) // BIN
    n = e - s + 1
    idx = np.repeat(offs[ci] + s, n) + (np.arange(n.sum()) - np.repeat(np.cumsum(n) - n, n))
    lim = np.repeat(offs[ci] + np.asarray(nb)[ci], n)
    m[idx[idx < lim]] = True
    return m


def bins_bed(path, idx, offs, chroms, sizes, names=None):
    ci = np.searchsorted(offs, idx, side="right") - 1
    st = (idx - offs[ci]) * BIN
    rows = [f"{chroms[c]}\t{s}\t{min(s + BIN, sizes[chroms[c]])}\t{(names[k] if names is not None else f'b{idx[k]}')}\t0\t+\n"
            for k, (c, s) in enumerate(zip(ci, st))]
    Path(path).write_text("".join(rows))


def read_regions(path):
    return pd.read_csv(path, sep="\t", header=None, usecols=[0, 1, 2], names=["c", "s", "e"])


def summit_bins(reg, offs, cidx, score):
    """Bin with the highest score inside each region (first one on ties)."""
    base = reg.c.map(cidx).map(lambda i: offs[i]).to_numpy(np.int64)
    b0 = base + reg.s.to_numpy() // BIN; n = (reg.e.to_numpy() - 1) // BIN - reg.s.to_numpy() // BIN + 1
    idx = np.repeat(b0, n) + (np.arange(n.sum()) - np.repeat(np.cumsum(n) - n, n))
    grp = np.repeat(np.arange(len(reg)), n)
    order = np.lexsort((-score[idx], grp))
    first = np.concatenate([[0], np.flatnonzero(np.diff(grp[order])) + 1])
    return idx[order][first]


def split_meme(meme, keep_ids, out):
    txt = Path(meme).read_text(); head, *blocks = txt.split("\nMOTIF ")
    kept = [b for b in blocks if b.split()[0] in keep_ids]
    Path(out).write_text(head.rstrip("\n") + "\n\n" + "".join("MOTIF " + b.rstrip("\n") + "\n\n" for b in kept))
    return len(kept)


def main(npz, hsdir, blpath, gtf, meta, rawmeme, tiersdir, sizes_path, out):
    out = Path(out)
    for d in ("targets", "pools", "motifs"):
        (out / d).mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(SEED); rng_g = np.random.default_rng(SEED + 100)
    z = np.load(npz); chroms = [str(c) for c in z["chrom"]]; offs = z["offset"]; NB = z["n_bins"]; nbin = int(sum(NB))
    cidx = {c: i for i, c in enumerate(chroms)}
    sizes = {l.split()[0]: int(l.split()[1]) for l in open(sizes_path) if l.strip()}
    P = z["proteins"].astype(np.int64)
    rA, rD = ecdf_rank(z["atac_experiments"]), ecdf_rank(z["dnase_experiments"]); openscore = (rA + rD) / 2
    bl = pd.read_csv(blpath, sep="\t", header=None, usecols=[0, 1, 2], names=["c", "s", "e"])
    black = interval_mask(bl, offs, NB, cidx, nbin)
    tss = []
    with open(gtf) as fh:
        for l in fh:
            if l.startswith("#"):
                continue
            f = l.split("\t", 8)
            if f[2] == "transcript":
                t = int(f[3]) - 1 if f[6] == "+" else int(f[4]) - 1
                tss.append((f[0] if f[0].startswith("chr") else "chr" + f[0], t, t + 1))
    prom = interval_mask(pd.DataFrame(tss, columns=["c", "s", "e"]), offs, NB, cidx, nbin, flank=PROM_FLANK)
    summ = {"cap": CAP, "seed": SEED, "blacklist_bins": int(black.sum()), "promoter_bins": int(prom.sum()), "targets": {}, "pools": {}}

    def hs_mask(cls, tier):
        m = np.zeros(nbin, dtype=bool); reg = read_regions(Path(hsdir) / f"PMA_hotspot_{cls}_{tier}.bed")
        base = reg.c.map(cidx).map(lambda i: offs[i]).to_numpy(np.int64)
        b0 = base + reg.s.to_numpy() // BIN; n = (reg.e.to_numpy() - 1) // BIN - reg.s.to_numpy() // BIN + 1
        m[np.repeat(b0, n) + (np.arange(n.sum()) - np.repeat(np.cumsum(n) - n, n))] = True
        return m

    manifest = []
    score = {"protein": P.astype(float), "open": openscore}
    for cls in ("protein", "open"):
        for tier in TIERS:
            reg = read_regions(Path(hsdir) / f"PMA_hotspot_{cls}_{tier}.bed")
            sb = summit_bins(reg, offs, cidx, score[cls])
            sb = np.sort(rng.choice(sb, CAP, replace=False)) if sb.size > CAP else sb
            tid = f"{cls}_{tier}"; bins_bed(out / "targets" / f"{tid}.bed", sb, offs, chroms, sizes)
            summ["targets"][tid] = {"regions": len(reg), "sequences": int(sb.size), "pct_promoter": float(100 * prom[sb].mean()),
                                    "median_proteins": float(np.median(P[sb])), "median_openscore": float(np.median(openscore[sb]))}
            nbg = min(2 * sb.size, 100000)
            same = hs_mask(cls, tier); elig = ~black & ~same
            pe, de = np.flatnonzero(elig & prom), np.flatnonzero(elig & ~prom)
            dsel = np.sort(rng_g.choice(de, G_POOL, replace=False)) if de.size > G_POOL else de
            for name, gp in (("", np.sort(np.concatenate([pe, dsel]))), ("_promoter", pe), ("_distal", dsel)):
                if name and tier != "top5":
                    continue
                bins_bed(out / "pools" / f"G_{tid}{name}.bed", gp, offs, chroms, sizes)
                summ["pools"][f"G_{tid}{name}"] = {"bins": int(gp.size), "pct_promoter": float(100 * prom[gp].mean())}
            manifest.append({"comparison": f"G_{tid}", "target": f"targets/{tid}.bed", "mode": "bg", "pool": f"pools/G_{tid}.bed", "N": nbg})
            if cls == "protein":  # accessibility-matched pool
                edges = np.unique(np.quantile(openscore[sb], np.linspace(0, 1, NSTRATA + 1)))
                st_t = np.clip(np.searchsorted(edges, openscore[sb], side="right") - 1, 0, len(edges) - 2)
                cand = np.flatnonzero(~black & ~same & (openscore >= edges[0]) & (openscore <= edges[-1]))
                st_c = np.clip(np.searchsorted(edges, openscore[cand], side="right") - 1, 0, len(edges) - 2)
                pool, short = [], 0
                for k in range(len(edges) - 1):
                    want = POOL_PER_TARGET * int((st_t == k).sum()); have = cand[st_c == k]
                    short += max(0, want - have.size)
                    pool.append(rng.choice(have, min(want, have.size), replace=False) if have.size else have)
                pool = np.sort(np.concatenate(pool)); bins_bed(out / "pools" / f"A_{tid}.bed", pool, offs, chroms, sizes)
                summ["pools"][f"A_{tid}"] = {"bins": int(pool.size), "wanted": int(POOL_PER_TARGET * sb.size), "shortfall": int(short),
                                             "median_openscore_target": float(np.median(openscore[sb])),
                                             "median_openscore_pool": float(np.median(openscore[pool])) if pool.size else None,
                                             "pct_promoter_pool": float(100 * prom[pool].mean()) if pool.size else None,
                                             "pct_promoter_target": float(100 * prom[sb].mean())}
                manifest.append({"comparison": f"A_{tid}", "target": f"targets/{tid}.bed", "mode": "bg", "pool": f"pools/A_{tid}.bed",
                                 "N": int(min(sb.size, pool.size // 2))})
            if tier == "top5":
                for name, m in (("promoter", prom), ("distal", ~prom)):
                    s2 = sb[m[sb]]; t2 = f"{tid}_{name}"; bins_bed(out / "targets" / f"{t2}.bed", s2, offs, chroms, sizes)
                    summ["targets"][t2] = {"sequences": int(s2.size)}
                    manifest.append({"comparison": f"S_{t2}", "target": f"targets/{t2}.bed", "mode": "bg",
                                     "pool": f"pools/G_{tid}_{name}.bed", "N": min(2 * s2.size, 100000)})
    pd.DataFrame(manifest).to_csv(out / "manifest.tsv", sep="\t", index=False)

    # motif libraries + annotation
    md = pd.read_csv(meta, sep="\t", dtype=str, usecols=["pma_id", "source_db", "source_version", "source_set", "motif_name", "assayed_target"])
    jas = md[(md.source_db == "JASPAR") & (md.source_set == "CORE_vertebrates_nr")]
    lib = {"JASPAR2026_CORE_vert_nr": split_meme(rawmeme, set(jas.pma_id), out / "motifs" / "JASPAR2026_CORE_vert_nr.meme")}
    ann = [jas.assign(library="JASPAR2026_CORE_vert_nr", motif_id=jas.pma_id, label=jas.motif_name, tf_family="", candidate_tfs=jas.assayed_target,
                      annotation_status="")[["library", "motif_id", "label", "tf_family", "candidate_tfs", "annotation_status"]]]
    for t in ("HIGH", "MEDIUM", "LOW"):
        src = Path(tiersdir) / t
        (out / "motifs" / f"PMA_{t}.meme").write_text((src / "PMA_representatives.meme").read_text())
        lib[f"PMA_{t}"] = sum(1 for l in open(src / "PMA_representatives.meme") if l.startswith("MOTIF"))
        cs = pd.read_csv(src / "PMA_cluster_summary.tsv", sep="\t", dtype=str)
        ann.append(pd.DataFrame({"library": f"PMA_{t}", "motif_id": cs.cluster_id, "label": cs.representative_id,
                                 "tf_family": cs.tf_family_primary, "candidate_tfs": cs.candidate_tf_ids,
                                 "annotation_status": cs.annotation_status}))
    pd.concat(ann).to_csv(out / "motifs" / "motif_annotation.tsv", sep="\t", index=False)
    summ["motif_libraries"] = lib
    (out / "prep_summary.json").write_text(json.dumps(summ, indent=1))
    print(json.dumps(summ, indent=1))


if __name__ == "__main__":
    main(*sys.argv[1:])
