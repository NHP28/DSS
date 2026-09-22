"""Thanh phan S - Friend-based Collaborative Filtering (Eq. 3, 4, 15).

  SI_ki = eta * |F_k ∩ F_i| / |F_k ∪ F_i|  +  (1 - eta) * |L_k ∩ L_i| / |L_k ∪ L_i|     (Eq. 4)
  p^s_ij = sum_{k in F_i} SI_ki * c_kj / sum_{k in F_i} SI_ki                            (Eq. 3 / 15)

F = tap ban be, L = tap POI da ghe (trong tap train).
"""
import numpy as np
import scipy.sparse as sp


class FriendCF:
    def __init__(self, eta=0.05):
        self.eta = eta

    def fit(self, C, friends):
        self.C = C.tocsr().astype(np.float32)
        n = C.shape[0]
        F = [set(f.tolist()) for f in friends]
        L = [set(self.C.indices[self.C.indptr[u]:self.C.indptr[u + 1]].tolist()) for u in range(n)]

        rows, cols, vals = [], [], []
        for i in range(n):
            for k in friends[i]:
                jf = len(F[k] & F[i]) / len(F[k] | F[i])
                uni = len(L[k] | L[i])
                jl = len(L[k] & L[i]) / uni if uni else 0.0
                si = self.eta * jf + (1 - self.eta) * jl
                if si > 0:
                    rows.append(i); cols.append(k); vals.append(si)
        self.SI = sp.csr_matrix((np.array(vals, dtype=np.float32), (rows, cols)), shape=(n, n))
        self.SI_sum = np.asarray(self.SI.sum(axis=1)).ravel()
        return self

    def predict(self, users):
        num = (self.SI[users] @ self.C).toarray()
        den = self.SI_sum[users][:, None]
        return np.divide(num, den, out=np.zeros_like(num), where=den > 0)
