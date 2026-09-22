"""Xay do thi tuong dong user / POI (Muc 4.3) + Laplacian chuan hoa (Muc 3.2) + spectral clustering (Muc 4.2).

User:  S^ST_ij  = cos(f_i, f_j),  f_i in R^{24 x n} = so check-in cua user i tai moi POI trong moi gio      (Eq. 7)
       S^user   = (alpha_user + S^SR) ⊙ S^ST / (1 + alpha_user),  S^SR_ij = 1 neu la ban be               (Eq. 8)
POI:   S^TE_ij  = cos(g_i, g_j),  g_i in R^24 = so luot ghe POI i trong moi gio                           (Eq. 9)
       S^GE_ij  = exp(-||x_i - x_j||^2 / (2 sigma^2))
       S^poi    = (alpha_poi + S^TE) ⊙ S^GE / (1 + alpha_poi)                                             (Eq. 10)
G_user, G_poi = do thi k-lang-gieng-gan-nhat (k-NN) cua S^user, S^poi.
L = I - D^{-1/2} W D^{-1/2}.
"""
import numpy as np
import scipy.sparse as sp
from scipy.sparse.linalg import eigsh
from sklearn.cluster import KMeans
from sklearn.neighbors import BallTree
from sklearn.preprocessing import normalize

EARTH_R = 6371.0


def local_hour(ts, lon, use_local=True):
    """Gio trong ngay. SNAP luu gio UTC -> uoc luong gio dia phuong bang mui gio = round(kinh do / 15)."""
    offset = np.round(lon / 15.0) * 3600 if use_local else 0
    return (((ts + offset) // 3600) % 24).astype(np.int64)


def _knn_sym(rows, cols, vals, size, k, mode="union"):
    """Giu k lang gieng lon nhat moi hang (da duoc chon san), roi doi xung hoa."""
    W = sp.csr_matrix((vals, (rows, cols)), shape=(size, size))
    if mode == "union":
        W = W.maximum(W.T)
    else:  # mutual
        W = W.minimum(W.T)
    W.eliminate_zeros()
    return W.tocsr()


def user_graph(train, m, n, social, coords, k=50, alpha=0.5, chunk=1500, use_local=True):
    hour = local_hour(train.ts.values, coords[train.l.values, 1], use_local)
    F = sp.csr_matrix((np.ones(len(train), dtype=np.float32), (train.u.values, hour * n + train.l.values)),
                      shape=(m, 24 * n))
    F.sum_duplicates()
    Fn = normalize(F, norm="l2", axis=1).astype(np.float32)
    FnT = Fn.T.tocsr()
    SR = sp.csr_matrix((np.ones(2 * len(social), dtype=np.float32),
                        (np.r_[social[:, 0], social[:, 1]], np.r_[social[:, 1], social[:, 0]])), shape=(m, m))
    rows, cols, vals = [], [], []
    for s in range(0, m, chunk):
        e = min(s + chunk, m)
        S = (Fn[s:e] @ FnT).toarray()                                   # S^ST (Eq. 7)
        S = (alpha + SR[s:e].toarray()) * S / (1 + alpha)               # Eq. 8
        S[np.arange(e - s), np.arange(s, e)] = 0.0                      # bo self-loop
        kk = min(k, m - 1)
        idx = np.argpartition(-S, kk, axis=1)[:, :kk]
        v = np.take_along_axis(S, idx, axis=1)
        keep = v > 0
        rows.append(np.repeat(np.arange(s, e), kk)[keep.ravel()])
        cols.append(idx[keep]); vals.append(v[keep])
    return _knn_sym(np.concatenate(rows), np.concatenate(cols), np.concatenate(vals), m, k)


def poi_graph(train, n, coords, k=50, alpha=0.5, sigma=1.0, n_cand=300, use_local=True):
    """sigma tinh bang km. Vi S^GE giam rat nhanh theo khoang cach, lang gieng k-NN cua S^poi nam trong
    n_cand POI gan nhat ve dia ly -> chi xet cac ung vien nay (tim bang BallTree haversine)."""
    hour = local_hour(train.ts.values, coords[train.l.values, 1], use_local)
    G = sp.csr_matrix((np.ones(len(train), dtype=np.float32), (train.l.values, hour)), shape=(n, 24)).toarray()
    Gn = normalize(G, norm="l2", axis=1)
    tree = BallTree(np.radians(coords), metric="haversine")
    dist, cand = tree.query(np.radians(coords), k=min(n_cand + 1, n))
    dist = dist * EARTH_R
    ste = np.einsum("id,ijd->ij", Gn, Gn[cand])                         # S^TE (Eq. 9)
    sge = np.exp(-dist ** 2 / (2 * sigma ** 2))                         # S^GE
    S = (alpha + ste) * sge / (1 + alpha)                               # Eq. 10
    S[cand == np.arange(n)[:, None]] = 0.0
    kk = min(k, cand.shape[1] - 1)
    idx = np.argpartition(-S, kk, axis=1)[:, :kk]
    v = np.take_along_axis(S, idx, axis=1)
    c = np.take_along_axis(cand, idx, axis=1)
    keep = v > 0
    return _knn_sym(np.repeat(np.arange(n), kk)[keep.ravel()], c[keep], v[keep], n, k)


def normalized_laplacian(W):
    d = np.asarray(W.sum(axis=1)).ravel()
    dinv = np.where(d > 0, 1.0 / np.sqrt(np.maximum(d, 1e-12)), 0.0)
    A = sp.diags(dinv) @ W @ sp.diags(dinv)
    # Nut co lap (bac 0): D^{-1/2} khong xac dinh -> dat hang/cot Laplacian = 0 (nut do khong bi rang buoc)
    I = sp.diags((d > 0).astype(np.float32))
    return (I - A).tocsr().astype(np.float32), A.tocsr()


def spectral_clusters(A, G, seed=0):
    """Spectral clustering (Ng-Jordan-Weiss): G vector rieng ung voi tri rieng NHO nhat cua L = I - A
    (= lon nhat cua A), chuan hoa tung hang, roi k-means."""
    _, vecs = eigsh(A.astype(np.float64), k=G, which="LA", tol=1e-4, maxiter=5000)
    X = normalize(vecs, axis=1)
    return KMeans(n_clusters=G, n_init=4, random_state=seed).fit_predict(X)
