"""Step 3b §6.1: universe-independent motif similarity s(A, B).

s(A, B) = max over offsets and both orientations of B with overlap >= 5 of
clip(mean column Pearson over the aligned columns, 0, 1) * L_overlap / max(L_A, L_B).

Column Pearson uses population-standardised probability columns; a column
with zero variance (uniform) contributes Pearson 0. Matrices are packed
into one array with offsets so numba can run pairs in parallel.
"""
import numpy as np
from numba import njit, prange

MIN_OVERLAP = 5


def standardise(m):
    m = np.asarray(m, dtype=np.float64)
    c = m - m.mean(axis=1, keepdims=True)
    sd = np.sqrt((c ** 2).mean(axis=1, keepdims=True))
    return np.where(sd > 0, c / np.where(sd > 0, sd, 1), 0.0)


def pack(mats):
    """mats: list of (L x 4) probability matrices -> (Z, Zrc, start, length)."""
    z = [standardise(m) for m in mats]
    lens = np.array([len(x) for x in z], dtype=np.int64)
    start = np.concatenate([[0], np.cumsum(lens)[:-1]]).astype(np.int64)
    Z = np.concatenate(z).astype(np.float64)
    Zrc = np.concatenate([x[::-1, ::-1] for x in z]).astype(np.float64)
    return Z, Zrc, start, lens


@njit(cache=True)
def _best(Za, la, Zb, lb):
    best = 0.0
    mx = max(la, lb)
    for off in range(-(lb - MIN_OVERLAP), la - MIN_OVERLAP + 1):
        i0 = max(0, off)
        i1 = min(la, off + lb)
        ov = i1 - i0
        if ov < MIN_OVERLAP:
            continue
        acc = 0.0
        for i in range(i0, i1):
            j = i - off
            acc += (Za[i, 0] * Zb[j, 0] + Za[i, 1] * Zb[j, 1] + Za[i, 2] * Zb[j, 2] + Za[i, 3] * Zb[j, 3]) / 4.0
        r = acc / ov
        if r < 0.0:
            r = 0.0
        elif r > 1.0:
            r = 1.0
        s = r * ov / mx
        if s > best:
            best = s
    return best


@njit(parallel=True, cache=True)
def s_pairs(Z, Zrc, start, lens, qa, qb):
    """s for each pair (qa[k], qb[k]) of packed indices."""
    out = np.empty(len(qa))
    for k in prange(len(qa)):
        a, b = qa[k], qb[k]
        Za = Z[start[a]:start[a] + lens[a]]
        f = _best(Za, lens[a], Z[start[b]:start[b] + lens[b]], lens[b])
        r = _best(Za, lens[a], Zrc[start[b]:start[b] + lens[b]], lens[b])
        out[k] = f if f > r else r
    return out


@njit(parallel=True, cache=True)
def s_one_vs_all(Z, Zrc, start, lens, a, targets):
    out = np.empty(len(targets))
    Za = Z[start[a]:start[a] + lens[a]]
    for k in prange(len(targets)):
        b = targets[k]
        f = _best(Za, lens[a], Z[start[b]:start[b] + lens[b]], lens[b])
        r = _best(Za, lens[a], Zrc[start[b]:start[b] + lens[b]], lens[b])
        out[k] = f if f > r else r
    return out
