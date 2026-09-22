"""USG - khung hop nhat (Muc 4, Eq. 13 va 17).

  S^u_ij = p^u_ij / max_{j not in L_i} p^u_ij      (tuong tu cho S^s, S^g)      (Eq. 17)
  S_ij   = (1 - alpha - beta) S^u_ij + alpha S^s_ij + beta S^g_ij             (Eq. 13)

Dac biet:  U: alpha=beta=0   S: alpha=1   G: beta=1   US: beta=0   UG: alpha=0
"""
import numpy as np


def max_normalize(p, visited_mask):
    """Eq. 17: chia cho max tren cac POI CHUA ghe; POI da ghe gan 0 (se bi loai o buoc fuse)."""
    p = np.where(visited_mask, -np.inf, p)
    z = p.max(axis=1, keepdims=True)
    s = np.divide(p, z, out=np.zeros_like(p), where=z > 0)
    return np.where(visited_mask, 0.0, s)


def max_normalize_log(logp, visited_mask):
    """Eq. 17 cho p^g tinh bang log: p / max p = exp(log p - max log p). Tuong duong chinh xac, khong underflow."""
    logp = np.where(visited_mask, -np.inf, logp)
    z = logp.max(axis=1, keepdims=True)
    s = np.exp(logp - z)
    return np.where(visited_mask, 0.0, s)


def minmax_normalize_log(logp, visited_mask):
    """BIEN THE (lech khoi paper): min-max tren log p^g cua cac POI chua ghe -> [0, 1].
    Dung de so sanh vi S^g theo Eq. 17 rat "nhon" (gan one-hot) khi user ghe nhieu POI."""
    lp = np.where(visited_mask, np.nan, logp)
    lo, hi = np.nanmin(lp, axis=1, keepdims=True), np.nanmax(lp, axis=1, keepdims=True)
    s = (lp - lo) / np.where(hi > lo, hi - lo, 1.0)
    return np.where(visited_mask, 0.0, s)


def fuse(su, ss, sg, alpha, beta, visited_mask):
    s = (1 - alpha - beta) * su + alpha * ss + beta * sg
    return np.where(visited_mask, -np.inf, s)          # khong goi y lai POI da ghe


def grid(step=0.1):
    vals = np.round(np.arange(0, 1 + 1e-9, step), 2)
    return [(a, b) for a in vals for b in vals if a + b <= 1 + 1e-9]
