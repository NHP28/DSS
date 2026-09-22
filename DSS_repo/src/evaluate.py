"""Precision@K / Recall@K (K = 5, 10, 20, 50) nhu Muc 5.1 cua paper.

Chi goi y POI user CHUA ghe trong train (V_u = V \\ P_u, Muc 4.2); trung binh tren cac user co ground truth.
"""
import numpy as np

KS = (5, 10, 20, 50)


def evaluate_scores(score_rows, Y, truth, ks=KS, chunk=1024):
    """score_rows(i0, i1) -> ma tran diem (i1-i0, n). Tra ve {K: (P, R)}."""
    m = Y.shape[0]
    users = np.array(sorted(truth))
    kmax = max(ks)
    acc = {k: np.zeros(2) for k in ks}
    for i0 in range(0, m, chunk):
        i1 = min(i0 + chunk, m)
        sel = users[(users >= i0) & (users < i1)]
        if len(sel) == 0:
            continue
        S = np.array(score_rows(i0, i1), dtype=np.float32, copy=True)[sel - i0]
        S[Y[sel].toarray() > 0] = -np.inf
        idx = np.argpartition(-S, kmax, axis=1)[:, :kmax]
        top = np.take_along_axis(idx, np.argsort(-np.take_along_axis(S, idx, axis=1), axis=1, kind="stable"), axis=1)
        for row, u in zip(top, sel):
            gt = truth[int(u)]
            hit = np.fromiter((p in gt for p in row), bool, kmax)
            for k in ks:
                h = hit[:k].sum()
                acc[k] += (h / k, h / len(gt))
    return {k: tuple(v / len(users)) for k, v in acc.items()}


def fmt(res):
    return "  ".join(f"P@{k}={p:.4f} R@{k}={r:.4f}" for k, (p, r) in res.items())
