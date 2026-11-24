"""Item-based k-nearest-neighbour collaborative filtering (cosine on the binary visit matrix)."""
import numpy as np
from sklearn.preprocessing import normalize


class ItemKNN:
    def __init__(self, k=50):
        self.k = k

    def fit(self, C):
        self.B = (C.tocsr() > 0).astype(np.float32)
        columns = normalize(self.B.T.tocsr(), norm="l2", axis=1)
        sim = (columns @ columns.T).toarray()
        np.fill_diagonal(sim, 0.0)
        if self.k < sim.shape[0] - 1:
            # Keep each item's k strongest neighbours; weak similarities are mostly noise.
            threshold = np.partition(sim, -self.k, axis=1)[:, -self.k][:, None]
            sim = np.where(sim >= threshold, sim, 0.0)
        self.sim = sim.astype(np.float32)
        return self

    def predict(self, users):
        """Scores (len(users), n_items): summed similarity to the items each user visited."""
        return np.asarray(self.B[users] @ self.sim)
