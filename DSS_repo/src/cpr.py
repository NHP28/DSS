"""Mo hinh CPR - toi uu ham muc tieu Eq. 6 bang Algorithm 1 (toi uu xen ke).

  L(R) = 1/2 [ l1 tr(R^T Lu R) + l2 tr(R Lp R^T) + l3 ||R - Y||_F^2 + l4 J(R) ],
  J(R) = sum_g sum_j sqrt(n_g) ||R_(g),j||_2                                             (Eq. 5)

  User step: T1 = argmin_R 1/2[ l1 tr(R^T Lu R) + l3||R - T2||^2 ] + l4/2 J(R)      -> APG (Eq. 13-17)
  POI  step: T2 = nghiem cua R (l2 Lp + l3 I) = l3 T1                                -> Conjugate Gradient (Eq. 19)
  R* = T1 sau vong lap cuoi.

Bo nho: R la ma tran day 18,737 x 32,510 (~2.4 GB float32) -> luu tren dia (np.memmap).
  - User step TACH RIENG duoc theo tung COT (moi POI j doc lap: Laplacian user + group lasso tren cot j)
  - POI  step TACH RIENG duoc theo tung HANG (moi user i doc lap)
  => xu ly tung khoi cot / khoi hang tren GPU.
"""
import math
import os
import time

import numpy as np
import torch


def to_torch_sparse(M, device):
    M = M.tocsr().astype(np.float32)
    return torch.sparse_csr_tensor(torch.from_numpy(M.indptr.astype(np.int64)),
                                   torch.from_numpy(M.indices.astype(np.int64)),
                                   torch.from_numpy(M.data), size=M.shape, device=device)


class CPR:
    def __init__(self, lam1=1.0, lam2=1.0, lam3=1.0, lam4=1e-4, outer_iters=5, apg_iters=30, cg_iters=30,
                 tol=1e-4, col_chunk=2048, row_chunk=1024, in_memory=True, device=None, workdir="."):
        self.lam1, self.lam2, self.lam3, self.lam4 = lam1, lam2, lam3, lam4
        self.outer_iters, self.apg_iters, self.cg_iters, self.tol = outer_iters, apg_iters, cg_iters, tol
        self.col_chunk, self.row_chunk = col_chunk, row_chunk
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.workdir = workdir
        self.in_memory = in_memory          # True: giu R trong RAM (~2.4 GB); False: np.memmap tren dia
        self.log = []

    # ------------------------------------------------------------------ user step
    def _user_step(self, T):
        m, n = T.shape
        dev, l1, l3 = self.device, self.lam1, self.lam3
        tau = 2.0 * l1 + l3                                  # hang so Lipschitz: lambda_max(Lu) <= 2
        thr = (self.lam4 * self.omega / tau)[:, None]        # nguong Eq. 17: l4 * w_g / tau
        diff2 = base2 = 0.0
        for j0 in range(0, n, self.col_chunk):
            j1 = min(j0 + self.col_chunk, n)
            Tc = torch.from_numpy(np.ascontiguousarray(T[:, j0:j1])).to(dev)
            R, Yk, t = Tc.clone(), Tc.clone(), 1.0
            for _ in range(self.apg_iters):
                grad = l1 * (self.Lu @ Yk) + l3 * (Yk - Tc)                         # Eq. 15
                Z = Yk - grad / tau
                # prox group lasso (Eq. 17): co ||Z_(g),j|| ve 0 neu <= nguong, nguoc lai co ti le
                gn2 = torch.zeros(self.G, j1 - j0, device=dev).index_add_(0, self.cl, Z * Z)
                scale = torch.clamp(1.0 - thr / torch.sqrt(gn2).clamp_min(1e-12), min=0.0)
                Rn = Z * scale[self.cl]
                tn = (1 + math.sqrt(1 + 4 * t * t)) / 2                               # FISTA momentum
                Yk = Rn + ((t - 1) / tn) * (Rn - R)
                rel = (torch.linalg.norm(Rn - R) / torch.linalg.norm(R).clamp_min(1e-12)).item()
                R, t = Rn, tn
                if rel < self.tol:
                    break
            diff2 += float(torch.sum((R - Tc) ** 2)); base2 += float(torch.sum(Tc ** 2))
            T[:, j0:j1] = R.cpu().numpy()
        return math.sqrt(diff2 / max(base2, 1e-12))

    # ------------------------------------------------------------------ POI step
    def _poi_step(self, T):
        m, n = T.shape
        dev, l2, l3 = self.device, self.lam2, self.lam3
        for i0 in range(0, m, self.row_chunk):
            i1 = min(i0 + self.row_chunk, m)
            B = torch.from_numpy(np.ascontiguousarray(T[i0:i1].T)).to(dev) * l3       # (n, r)

            def A(X):                                                                    # (l2 Lp + l3 I) X
                return l2 * (self.Lp @ X) + l3 * X

            X = B / l3                                                                   # khoi dau = T1
            r = B - A(X); p = r.clone(); rs = (r * r).sum(0)
            b2 = (B * B).sum(0).clamp_min(1e-12)
            for _ in range(self.cg_iters):                                               # CG theo tung cot
                Ap = A(p)
                a = rs / (p * Ap).sum(0).clamp_min(1e-20)
                X += a * p; r -= a * Ap
                rs_new = (r * r).sum(0)
                if torch.sqrt(rs_new / b2).max().item() < self.tol:
                    break
                p = r + (rs_new / rs.clamp_min(1e-20)) * p; rs = rs_new
            T[i0:i1] = X.T.cpu().numpy()

    # ------------------------------------------------------------------ fit
    def fit(self, Y, Lu, Lp, clusters, name="R"):
        m, n = Y.shape
        self.Lu, self.Lp = to_torch_sparse(Lu, self.device), to_torch_sparse(Lp, self.device)
        self.G = int(clusters.max()) + 1
        self.cl = torch.from_numpy(clusters.astype(np.int64)).to(self.device)
        sizes = np.bincount(clusters, minlength=self.G)
        self.omega = torch.tensor(np.sqrt(sizes), dtype=torch.float32, device=self.device)   # w_g = sqrt(n_g)

        if self.in_memory:
            T = np.empty((m, n), dtype=np.float32)
        else:
            T = np.lib.format.open_memmap(os.path.join(self.workdir, f"{name}.npy"), mode="w+",
                                          dtype=np.float32, shape=(m, n))
        for i0 in range(0, m, 2048):                                                    # T[2] <- Y (dong 8)
            T[i0:i0 + 2048] = Y[i0:i0 + 2048].toarray()
        for it in range(self.outer_iters):
            t0 = time.time()
            change = self._user_step(T)                                                  # T[1] (dong 10)
            t1 = time.time()
            if it < self.outer_iters - 1:
                self._poi_step(T)                                                        # T[2] (dong 11)
            self.log.append((it, change, t1 - t0, time.time() - t1))
            print(f"    vong {it + 1}/{self.outer_iters}: user step {t1 - t0:.0f}s (thay doi {change:.4f}), "
                  f"POI step {time.time() - t1:.0f}s", flush=True)
        if not self.in_memory:
            T.flush()
        self.R = T                                                                       # R* = T[1] (dong 13)
        return self
