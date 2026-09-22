"""Baseline USG (SIGIR 2011, code trong src/baselines/) chay tren CUNG bo du lieu + cach chia voi CPR.

  python src/run_usg.py               # tune + test
  python src/run_usg.py --test-only   # chi test voi eta, alpha, beta da luu
TUNE (train -> tune): chon eta, roi grid alpha, beta (buoc 0.1, alpha + beta <= 1) theo P@10 (nhu VLDB 2017).
TEST (train + tune -> test): bao cao P@K, R@K voi K = 5, 10, 20, 50.
"""
import json
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from baselines.friend_cf import FriendCF                                  # noqa: E402
from baselines.geo_powerlaw import GeoPowerLaw                            # noqa: E402
from baselines.user_cf import UserCF                                      # noqa: E402
from baselines.usg import fuse, grid, max_normalize, max_normalize_log    # noqa: E402
from data import ROOT, build                                              # noqa: E402
from evaluate import KS, fmt                                              # noqa: E402

OUT = os.path.join(ROOT, "outputs")


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def friends_of(ds):
    f = [[] for _ in range(ds.m)]
    for u, v in ds.social:
        f[u].append(v); f[v].append(u)
    return [np.array(sorted(x), dtype=np.int64) for x in f]


def evaluate_configs(ds, u, s, g, configs, batch=512, save_top=None):
    """save_top = ten cau hinh -> luu top-50 cua moi user co ground truth vao outputs/usg_top50.npz."""
    users = np.array(sorted(ds.truth))
    tops = {}
    acc = {c: {k: np.zeros(2) for k in KS} for c in configs}
    kmax = max(KS)
    for i in range(0, len(users), batch):
        b = users[i:i + batch]
        mask = ds.Y[b].toarray() > 0
        su = max_normalize(u.predict(b), mask)
        ss = max_normalize(s.predict(b), mask)
        sg = max_normalize_log(g.predict_log(b), mask)
        for c, (a, be) in configs.items():
            S = fuse(su, ss, sg, a, be, mask)
            idx = np.argpartition(-S, kmax, axis=1)[:, :kmax]
            top = np.take_along_axis(idx, np.argsort(-np.take_along_axis(S, idx, axis=1), axis=1, kind="stable"), 1)
            if c == save_top:
                tops.update(zip(b.tolist(), top))
            for row, uu in zip(top, b):
                gt = ds.truth[int(uu)]
                hit = np.fromiter((p in gt for p in row), bool, kmax)
                for k in KS:
                    h = hit[:k].sum()
                    acc[c][k] += (h / k, h / len(gt))
    if save_top:
        top_all = np.full((ds.m, kmax), -1, dtype=np.int32)
        for uu, row in tops.items():
            top_all[uu] = row
        np.savez_compressed(os.path.join(OUT, "usg_top50.npz"), top=top_all)
    return {c: {k: tuple(v / len(users)) for k, v in d.items()} for c, d in acc.items()}


def fit(ds, eta):
    t = time.time()
    fr = friends_of(ds)
    u = UserCF().fit(ds.Y)
    s = FriendCF(eta).fit(ds.Y, fr)
    g = GeoPowerLaw(fit_mode="q90").fit(ds.Y, ds.coords)
    log(f"  fit U/S/G ({time.time() - t:.0f}s) | power law a={g.a:.4g}, b={g.b:.3f}")
    return u, s, g


def main():
    os.makedirs(OUT, exist_ok=True)
    if "--test-only" in sys.argv:                      # dung lai eta, alpha, beta da chon o lan chay truoc
        prev = json.load(open(os.path.join(OUT, "usg_results.json")))
        run_test(prev["eta"], prev["alpha"], prev["beta"], prev["tune_best"])
        return
    log("USG - TUNE: train -> tune")
    ds = build("tune")
    u, _, g = fit(ds, 0.05)
    fr = friends_of(ds)
    eta_res = {}
    for e in [0.0, 0.05, 0.1, 0.3, 0.5, 1.0]:
        eta_res[e] = evaluate_configs(ds, u, FriendCF(e).fit(ds.Y, fr), g, {"S": (1.0, 0.0)})["S"][10]
    eta = max(eta_res, key=lambda e: eta_res[e][0])
    log(f"  eta tot nhat = {eta} (P@10 cua S: " + ", ".join(f"{e}:{v[0]:.4f}" for e, v in eta_res.items()) + ")")
    s = FriendCF(eta).fit(ds.Y, fr)
    configs = {f"{a:.1f},{b:.1f}": (a, b) for a, b in grid(0.1)}
    res = evaluate_configs(ds, u, s, g, configs)
    best = max(res, key=lambda c: (res[c][10][0], res[c][10][1]))
    a, b = configs[best]
    log(f"  alpha={a}, beta={b} | tune: {fmt(res[best])}")
    del u, s, g, ds
    run_test(eta, a, b, res[best])


def run_test(eta, a, b, tune_best):
    log("USG - TEST: train + tune -> test")
    ds = build("test")
    u, s, g = fit(ds, eta)
    chosen = {"U": (0.0, 0.0), "USG": (a, b)}
    test = evaluate_configs(ds, u, s, g, chosen, save_top="USG")
    for c in chosen:
        log(f"  {c:4s}: {fmt(test[c])}")
    json.dump({"eta": eta, "alpha": a, "beta": b, "power_law": [g.a, g.b],
               "tune_best": tune_best, "test": {c: {k: list(v) for k, v in d.items()} for c, d in test.items()}},
              open(os.path.join(OUT, "usg_results.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
