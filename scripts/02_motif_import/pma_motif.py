"""Shared motif utilities for the Step 2 raw layer.

Design: docs/STEP2_MOTIF_IMPORT_DESIGN.md §3 (identity, hashes, gap mask)
and §4 (evidence model). Pure functions only; no paths.
"""
import hashlib
import re
import struct

import numpy as np
import pandas as pd

NT = "ACGT"


# ---- matrices -------------------------------------------------------------

def matrix_bytes(m):
    """§3 serialisation: uint32-LE row count, then rows in motif order,
    columns A,C,G,T, little-endian float64, C order."""
    m = np.ascontiguousarray(np.asarray(m, dtype="<f8"))
    assert m.ndim == 2 and m.shape[1] == 4
    return struct.pack("<I", m.shape[0]) + m.tobytes(order="C")


def sha1(m):
    return hashlib.sha1(matrix_bytes(m)).hexdigest()


def normalise(m):
    """Row-normalise. All-zero rows become uniform; their 0-based positions
    are returned as the gap mask. Genuinely uniform rows are not masked."""
    m = np.asarray(m, dtype=float)
    rs = m.sum(axis=1, keepdims=True)
    zero = rs[:, 0] == 0
    out = np.where(zero[:, None], 0.25, m / np.where(rs == 0, 1, rs))
    return out, [int(i) for i in np.flatnonzero(zero)]


def revcomp(m):
    return np.asarray(m)[::-1, ::-1]


def rounded_key(m, decimals=4):
    """Orientation-free key for the rounded-equivalence group.
    Returns (key, orientation) where orientation says which strand of
    this motif was used as the canonical form."""
    r = np.round(np.asarray(m, dtype=float), decimals) + 0.0  # drop -0.0
    f, rc = sha1(r), sha1(np.round(revcomp(r), decimals) + 0.0)
    return (f, "fwd") if f <= rc else (rc, "rc")


def info_content(p):
    p = np.clip(np.asarray(p, dtype=float), 1e-9, 1)
    return float((2 + (p * np.log2(p)).sum(axis=1)).sum())


def check_matrix(m):
    """Format QC (§7). Returns '' or a reason string for qc_fail_format."""
    m = np.asarray(m, dtype=float)
    if m.ndim != 2 or m.shape[0] == 0 or m.shape[1] != 4:
        return "shape"
    if not np.isfinite(m).all():
        return "non_finite"
    if (m < 0).any():
        return "negative"
    return ""


# ---- file formats ---------------------------------------------------------

_ROW = re.compile(r"^\s*-?[0-9.eE+-]+\s+-?[0-9.eE+-]+\s+-?[0-9.eE+-]+\s+-?[0-9.eE+-]+\s*$")


def read_meme(path):
    """[(motif_id, alt_name, matrix)] in file order."""
    motifs, cur, mat = [], None, []
    with open(path) as fh:
        for line in fh:
            if line.startswith("MOTIF"):
                if cur:
                    motifs.append((*cur, np.array(mat, dtype=float)))
                parts = line.split()
                cur, mat = (parts[1], parts[2] if len(parts) > 2 else ""), []
            elif cur and _ROW.match(line):
                mat.append([float(x) for x in line.split()])
    if cur:
        motifs.append((*cur, np.array(mat, dtype=float)))
    return motifs


def read_fasta_pcm(path):
    """HOCOMOCO pcms.txt: '>name' then rows of 4 counts."""
    out, name, mat = {}, None, []
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if line.startswith(">"):
                if name:
                    out[name] = np.array(mat, dtype=float)
                name, mat = line[1:].split()[0], []
            elif line:
                mat.append([float(x) for x in line.split()])
    if name:
        out[name] = np.array(mat, dtype=float)
    return out


def write_meme(motifs, path):
    """motifs: [(motif_id, alt_name, prob matrix)]."""
    with open(path, "w") as fh:
        fh.write("MEME version 4\n\nALPHABET= ACGT\n\nstrands: + -\n\n"
                 "Background letter frequencies\nA 0.25 C 0.25 G 0.25 T 0.25\n\n")
        for mid, alt, m in motifs:
            fh.write(f"MOTIF {mid} {alt}\nletter-probability matrix: "
                     f"alength= 4 w= {len(m)} nsites= 20 E= 0\n")
            for row in m:
                fh.write(" ".join(f"{x:.6f}" for x in row) + "\n")
            fh.write("\n")


# ---- evidence model (§4) --------------------------------------------------

_ASSAY = {
    "in_vitro_selection": ["ht-selex", "selex", "methyl-ht-selex", "ght-selex", "cap-selex", "ncap-selex",
                           "smile-seq", "mesmile-seq", "b1h", "bacterial 1-hybrid",
                           "yeast 1-hybrid", "dap-seq", "ht-selex, methyl-ht-selex"],
    "in_vitro_array": ["pbm"],
    "in_vivo_occupancy": ["chip-seq", "chip-exo", "chip-seq+chip-exo", "chip-seq_and_chip-exo",
                          "chip-chip", "chec-seq", "cut&run", "rcade"],
    "literature_compiled": ["transfac", "misc", "compiled"],
}
ASSAY_CLASS = {a: k for k, v in _ASSAY.items() for a in v}
HOCOMOCO_DATATYPE = {"P": "ChIP-seq", "S": "HT-SELEX", "M": "Methyl-HT-SELEX",
                     "G": "GHT-SELEX", "I": "SMiLE-seq", "B": "PBM", "H": "HOCOMOCO-v11"}
BASIS = {"in_vitro_selection": "in_vitro_binding", "in_vitro_array": "in_vitro_binding",
         "in_vivo_occupancy": "occupancy_derived", "literature_compiled": "literature",
         "unknown": "unknown"}
DIRECT = {"in_vitro_binding": "supported", "occupancy_derived": "not_established",
          "literature": "not_established", "homology_transfer": "transferred",
          "unknown": "unknown"}


def assay_class(raw):
    """Map a source assay label to §4 assay_class; parenthesised
    sub-types (e.g. 'GHT-SELEX (GFPIVT)') are ignored."""
    if raw is None or (isinstance(raw, float) and np.isnan(raw)):
        return "unknown"
    key = re.sub(r"\s*\(.*\)\s*$", "", str(raw)).strip().lower()
    return ASSAY_CLASS.get(key, "unknown")


def evidence(assay_cls, homology=False):
    basis = "homology_transfer" if homology else BASIS[assay_cls]
    return basis, DIRECT[basis]


# ---- HGNC -----------------------------------------------------------------

def hgnc_resolver(path):
    """Upper-cased name -> (current HGNC symbol, how). how is one of
    symbol / previous / alias / *_ambiguous / unmapped."""
    h = pd.read_csv(path, sep="\t", dtype=str).fillna("")
    sym = {s.upper(): s for s in h.symbol}
    prev, alias = {}, {}
    for s, p, a in zip(h.symbol, h.previous_symbols, h.alias_symbols):
        for x in filter(None, (t.strip() for t in p.split(","))):
            prev.setdefault(x.upper(), set()).add(s)
        for x in filter(None, (t.strip() for t in a.split(","))):
            alias.setdefault(x.upper(), set()).add(s)

    def resolve(name):
        u = str(name).strip().upper()
        if u in sym:
            return sym[u], "symbol"
        for table, how in ((prev, "previous"), (alias, "alias")):
            hits = table.get(u, set())
            if len(hits) == 1:
                return next(iter(hits)), how
            if len(hits) > 1:
                return "", f"{how}_ambiguous"
        return "", "unmapped"
    return resolve
