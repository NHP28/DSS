"""Doc du lieu da xu ly va chia train / tune / test THEO THOI GIAN (giao thuc VLDB 2017, dung trong CPR).

Moi user: sap xep check-in theo thoi gian -> 70% som nhat = train, 10% tiep theo = tune, 20% muon nhat = test.
Y (ma tran danh gia, Muc 3.1 cua paper) la NHI PHAN: Y_ij = 1 neu (u_i, v_j) co trong tap train.
Ground truth cua tune/test = cac POI user ghe trong giai doan do MA CHUA TUNG ghe trong train
(bai toan goi y POI MOI; POI da ghe bi loai khoi danh sach goi y nen khong the "doan dung").
"""
import os
from dataclasses import dataclass

import numpy as np
import pandas as pd
import scipy.sparse as sp

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROC = os.path.join(ROOT, "data", "processed")


@dataclass
class Split:
    m: int
    n: int
    coords: np.ndarray        # (n, 2) lat, lon
    social: np.ndarray        # (E, 2) canh ban be u < v
    train: pd.DataFrame       # check-in (u, l, ts) dung de xay do thi va Y
    Y: sp.csr_matrix          # (m, n) nhi phan
    truth: dict               # truth[u] = set POI moi trong giai doan danh gia


def load():
    ck = pd.read_csv(os.path.join(PROC, "checkins.csv"))
    pois = pd.read_csv(os.path.join(PROC, "pois.csv")).sort_values("l")
    social = pd.read_csv(os.path.join(PROC, "social.csv")).values
    return ck, pois[["lat", "lon"]].values, social


def temporal_split(ck, ratios=(0.7, 0.1, 0.2)):
    """Gan nhan 0 = train, 1 = tune, 2 = test cho moi check-in theo thu tu thoi gian cua tung user."""
    ck = ck.sort_values(["u", "ts"], kind="stable").reset_index(drop=True)   # stable: nhieu check-in trung thoi diem
    pos = ck.groupby("u").cumcount().values
    size = ck.groupby("u").u.transform("size").values
    n_tr = np.floor(size * ratios[0]).astype(int)                 # ranh gioi: floor(0.7 N), floor(0.8 N)
    n_tu = np.floor(size * (ratios[0] + ratios[1])).astype(int)
    ck["part"] = np.where(pos < n_tr, 0, np.where(pos < n_tu, 1, 2))
    return ck


def _truth(train, evalp):
    seen = set(zip(train.u.values, train.l.values))
    truth = {}
    for u, l in zip(evalp.u.values, evalp.l.values):
        if (u, l) not in seen:
            truth.setdefault(int(u), set()).add(int(l))
    return truth


def build(mode):
    """mode = 'tune'  : train -> danh gia tren tune (chon tham so)
       mode = 'test'  : train + tune -> danh gia tren test (bao cao ket qua)"""
    ck, coords, social = load()
    ck = temporal_split(ck)
    m, n = int(ck.u.max()) + 1, len(coords)
    if mode == "tune":
        train, evalp = ck[ck.part == 0], ck[ck.part == 1]
    else:
        train, evalp = ck[ck.part <= 1], ck[ck.part == 2]
    pairs = train[["u", "l"]].drop_duplicates()
    Y = sp.csr_matrix((np.ones(len(pairs), dtype=np.float32), (pairs.u.values, pairs.l.values)), shape=(m, n))
    return Split(m, n, coords, social, train[["u", "l", "ts"]].reset_index(drop=True), Y, _truth(train, evalp))
