"""Thanh phan G - Geographical Influence bang phan phoi luy thua (Muc 3, Eq. 5-12, 16).

Buoc 1 (hoc): voi moi user, tinh khoang cach giua MOI CAP POI user da ghe -> histogram
        xac suat theo khoang cach -> fit duong thang trong khong gian log-log:
            log2 y = w0 + w1 log2 x        (Eq. 6, 8)
        bang least squares + L2 (Eq. 9) -> a = 2^w0, b = w1 (Eq. 7).
Buoc 2 (du doan): Naive Bayes
            p^g_ij = Pr[l_j | L_i] = prod_{l_y in L_i} a * d(l_j, l_y)^b      (Eq. 12 / 16)
        Tich cua hang tram so < 1 se underflow ve 0, nen ta tinh trong khong gian log:
            log p^g_ij = sum_y [log a + b log d(l_j, l_y)]
Luu y: |L_i| log a la hang so theo j nen triet tieu khi chuan hoa Eq. 17 -> chi b anh huong thu hang.
"""
import numpy as np
import torch

EARTH_R = 6371.0


def haversine_np(a, b):
    """a: (n,2), b: (n,2) do -> km."""
    a, b = np.radians(a), np.radians(b)
    dlat, dlon = b[:, 0] - a[:, 0], b[:, 1] - a[:, 1]
    h = np.sin(dlat / 2) ** 2 + np.cos(a[:, 0]) * np.cos(b[:, 0]) * np.sin(dlon / 2) ** 2
    return 2 * EARTH_R * np.arcsin(np.sqrt(np.clip(h, 0, 1)))


def haversine_torch(p, q):
    """p: (n,2), q: (m,2) radian -> (n,m) km."""
    dlat = q[None, :, 0] - p[:, None, 0]
    dlon = q[None, :, 1] - p[:, None, 1]
    h = torch.sin(dlat / 2) ** 2 + torch.cos(p[:, None, 0]) * torch.cos(q[None, :, 0]) * torch.sin(dlon / 2) ** 2
    return 2 * EARTH_R * torch.asin(torch.sqrt(h.clamp(0, 1)))


class GeoPowerLaw:
    def __init__(self, lam=0.1, min_dist=0.01, fit_mode="q90", device=None):
        self.lam = lam                  # lambda trong Eq. 9
        # fit_mode: "all"  = moi bin 1 km tu 1 km tro len
        #           "q90"  = chi phan "tuyen tinh" chua 90% so cap POI (paper, Muc 3: "covers the majority (90%)")
        #           "logbin" = bin chia deu theo log (mat do = so cap / do rong bin), trong [1 km, q90]
        self.fit_mode = fit_mode
        self.min_dist = min_dist        # km; kep khoang cach khi du doan (2 POI trung toa do -> tranh log 0)
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")

    # ---------- Buoc 1: fit a, b ----------
    def pair_distances(self, C, coords):
        out = []
        for u in range(C.shape[0]):
            lids = C.indices[C.indptr[u]:C.indptr[u + 1]]
            if len(lids) < 2:
                continue
            i, j = np.triu_indices(len(lids), k=1)          # moi cap (m != n) dem 1 lan
            out.append(haversine_np(coords[lids[i]], coords[lids[j]]))
        return np.concatenate(out)

    def fit(self, C, coords):
        self.C = C.tocsr()
        self.coords = coords
        d = self.pair_distances(self.C, coords)
        # Histogram theo bin 1 km (bin k = [k, k+1) km); xac suat = so cap trong bin / tong so cap.
        bins = np.floor(d).astype(np.int64)
        counts = np.bincount(bins)
        prob = counts / counts.sum()
        x = np.arange(len(counts), dtype=float)
        keep = (x >= 1) & (prob > 0)                         # log(0) khong xac dinh -> bo bin 0 va bin rong
        self.zero_bin_share = prob[0]                        # ty le cap < 1 km (khong dung de fit)
        q90 = np.quantile(d, 0.9)
        if self.fit_mode == "q90":
            keep &= x <= q90
        elif self.fit_mode == "logbin":
            edges = np.logspace(0, np.log10(q90), 40)
            cnt, _ = np.histogram(d, edges)
            dens = cnt / len(d) / np.diff(edges)             # xac suat tren moi km (cung don vi voi bin 1 km)
            x, prob = np.sqrt(edges[:-1] * edges[1:]), dens
            keep = prob > 0
        X = np.log2(x[keep])
        T = np.log2(prob[keep])
        # Ridge dang dong (Eq. 9): w = (A^T A + lam I)^-1 A^T t
        A = np.stack([np.ones_like(X), X], axis=1)
        w0, w1 = np.linalg.solve(A.T @ A + self.lam * np.eye(2), A.T @ T)
        self.a, self.b = 2.0 ** w0, w1
        self.hist = (np.arange(1, len(counts)), (counts / counts.sum())[1:])   # histogram 1 km de ve Figure 2
        self.fit_points = (x[keep], prob[keep])
        self._coords_rad = torch.tensor(np.radians(coords), dtype=torch.float32, device=self.device)
        return self

    def pr_d(self, d):
        return self.a * np.maximum(d, self.min_dist) ** self.b

    # ---------- Buoc 2: du doan ----------
    def predict_log(self, users):
        """Tra ve log p^g (log tu nhien) cho batch user: (len(users), n_pois)."""
        out = np.zeros((len(users), self.C.shape[1]), dtype=np.float64)
        log_a = np.log(self.a)
        for r, u in enumerate(users):
            lids = self.C.indices[self.C.indptr[u]:self.C.indptr[u + 1]]
            if len(lids) == 0:
                continue
            D = haversine_torch(self._coords_rad, self._coords_rad[torch.as_tensor(lids, device=self.device)])
            logd = torch.log(D.clamp_min(self.min_dist)).double()
            out[r] = (len(lids) * log_a + self.b * logd.sum(dim=1)).cpu().numpy()
        return out
