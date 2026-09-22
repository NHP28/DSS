"""Thanh phan U - User-based Collaborative Filtering (Eq. 1, 2, 14).

  w_ik  = cos(c_i, c_k)                                   (Eq. 2)
  p^u_ij = sum_k w_ik * c_kj / sum_k w_ik                  (Eq. 1 / 14)

Y tuong: hai user cung ghe nhieu POI giong nhau -> "giong nhau" -> POI ma user giong ban da ghe
la ung vien tot de goi y.
"""
import numpy as np
from sklearn.preprocessing import normalize


class UserCF:
    def fit(self, C):
        self.C = C.tocsr().astype(np.float32)
        Cn = normalize(self.C, norm="l2", axis=1)          # chia cho ||c_i||
        W = (Cn @ Cn.T).toarray()                          # cosine giua moi cap user
        np.fill_diagonal(W, 0.0)                           # bo chinh user do (w_ii)
        self.W = W
        self.W_sum = W.sum(axis=1)
        return self

    def predict(self, users):
        """Tra ve p^u cho batch user: (len(users), n_pois)."""
        num = np.asarray((self.C.T @ self.W[users].T).T)   # W[B] @ C  (C thua)
        den = self.W_sum[users][:, None]
        return np.divide(num, den, out=np.zeros_like(num), where=den > 0)
