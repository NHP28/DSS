"""Tim tham so CPR tren tap TUNE (tim kiem theo tung giai doan) roi bao cao tren TEST.

  python src/run_cpr.py            # tune + test (co the dung giua chung, chay lai se bo qua cau hinh da xong)
  python src/run_cpr.py --test     # chi chay TEST voi cau hinh tot nhat da luu

Chon tham so theo P@10 tren tap tune (giong VLDB 2017). lambda3 = 1 (paper Muc 5.3).
"""
import argparse
import csv
import itertools
import json
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from cpr import CPR                                                                        # noqa: E402
from data import ROOT, build                                                               # noqa: E402
from evaluate import KS, evaluate_scores, fmt                                              # noqa: E402
from graphs import normalized_laplacian, poi_graph, spectral_clusters, user_graph          # noqa: E402

OUT = os.path.join(ROOT, "outputs")
TUNE_CSV = os.path.join(OUT, "cpr_tuning.csv")
KEYS = ["k_user", "alpha_user", "k_poi", "alpha_poi", "sigma", "G", "lam1", "lam2", "lam4", "outer"]
BASE = dict(k_user=50, alpha_user=0.5, k_poi=50, alpha_poi=0.5, sigma=1.0, G=50,
            lam1=1.0, lam2=1.0, lam4=1e-4, outer=3)
# Giai doan: moi giai doan thay doi 1-2 nhom tham so, giu phan con lai o gia tri tot nhat hien tai
STAGES = [
    ("Do thi POI (sigma km, k_poi)", {"sigma": [0.5, 1.0, 3.0, 10.0], "k_poi": [20, 50]}),
    ("Do thi POI (alpha_poi)", {"alpha_poi": [0.0, 0.5, 1.0]}),
    ("Do thi user (k_user, alpha_user)", {"k_user": [20, 50], "alpha_user": [0.0, 0.5, 1.0]}),
    ("Trong so Laplacian (lambda1, lambda2)", {"lam1": [0.5, 1.0, 2.0, 5.0], "lam2": [0.3, 1.0, 3.0]}),
    ("Tinh chinh lambda (lambda2 nho, trong khoang [0.05, 10] cua paper)",
     {"lam1": [0.2, 0.5, 1.0], "lam2": [0.05, 0.1, 0.2, 0.3]}),
    ("Group lasso (lambda4)", {"lam4": [0.0, 1e-4, 1e-3, 1e-2]}),
    ("So cum G", {"G": [20, 50, 100]}),
    ("So vong lap ngoai", {"outer": [3, 5, 8]}),
]


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


class Runner:
    """Luu cache do thi / cum de khong xay lai khi chi doi lambda."""

    def __init__(self, ds):
        self.ds, self.cache = ds, {}

    def get(self, key, fn):
        if key not in self.cache:
            self.cache[key] = fn()
        return self.cache[key]

    def graphs(self, c):
        ds = self.ds
        Lu, Au = self.get(("u", c["k_user"], c["alpha_user"]), lambda: normalized_laplacian(
            user_graph(ds.train, ds.m, ds.n, ds.social, ds.coords, k=c["k_user"], alpha=c["alpha_user"])))
        Lp, _ = self.get(("p", c["k_poi"], c["alpha_poi"], c["sigma"]), lambda: normalized_laplacian(
            poi_graph(ds.train, ds.n, ds.coords, k=c["k_poi"], alpha=c["alpha_poi"], sigma=c["sigma"])))
        cl = self.get(("c", c["k_user"], c["alpha_user"], c["G"]), lambda: spectral_clusters(Au, c["G"]))
        return Lu, Lp, cl

    def run(self, c):
        Lu, Lp, cl = self.graphs(c)
        model = CPR(lam1=c["lam1"], lam2=c["lam2"], lam4=c["lam4"], outer_iters=int(c["outer"])).fit(
            self.ds.Y, Lu, Lp, cl)
        res = evaluate_scores(lambda a, b: model.R[a:b], self.ds.Y, self.ds.truth)
        return res, model


def cfg_key(c):
    return tuple(float(c[k]) for k in KEYS)


def load_done():
    done = {}
    if os.path.exists(TUNE_CSV):
        for row in csv.DictReader(open(TUNE_CSV)):
            done[tuple(float(row[k]) for k in KEYS)] = {k: (float(row[f"P@{k}"]), float(row[f"R@{k}"])) for k in KS}
    return done


def tune():
    ds = build("tune")
    log(f"TUNE: {ds.m:,} user, {ds.n:,} POI, Y nnz={ds.Y.nnz:,}, {len(ds.truth):,} user co ground truth")
    runner, done = Runner(ds), load_done()
    new_file = not os.path.exists(TUNE_CSV)
    f = open(TUNE_CSV, "a", newline="")
    w = csv.writer(f)
    if new_file:
        w.writerow(KEYS + [f"{m}@{k}" for k in KS for m in ("P", "R")] + ["seconds"])
    best = dict(BASE)

    def score(c):
        key = cfg_key(c)
        if key not in done:
            t = time.time()
            res, _ = runner.run(c)
            done[key] = res
            w.writerow([c[k] for k in KEYS] + [v for k in KS for v in res[k]] + [round(time.time() - t)])
            f.flush()
            log(f"    {c} -> {fmt(res)} ({time.time() - t:.0f}s)")
        return done[key]

    for name, grid in STAGES:
        log(f"Giai doan: {name}")
        names = list(grid)
        combos = [dict(zip(names, vals)) for vals in itertools.product(*grid.values())]
        cands = [{**best, **cmb} for cmb in combos]
        scores = [score(c) for c in cands]
        i = max(range(len(cands)), key=lambda j: (scores[j][10][0], scores[j][10][1]))
        best = cands[i]
        log(f"  -> tot nhat: {best} | P@10={scores[i][10][0]:.4f} R@10={scores[i][10][1]:.4f}")
    f.close()
    json.dump(best,
              open(os.path.join(OUT, "cpr_best_config.json"), "w"), indent=1)
    return best


def test(best):
    ds = build("test")
    log(f"TEST: train+tune -> test | {len(ds.truth):,} user co ground truth | cau hinh {best}")
    res, model = Runner(ds).run(best)
    log(f"  CPR: {fmt(res)}")
    # Luu top-50 goi y cua moi user (dung cho giao dien) - khong can giu ca ma tran R
    top = np.zeros((ds.m, 50), dtype=np.int32); sc = np.zeros((ds.m, 50), dtype=np.float32)
    for i0 in range(0, ds.m, 1024):
        S = np.array(model.R[i0:i0 + 1024], copy=True)
        S[ds.Y[i0:i0 + 1024].toarray() > 0] = -np.inf
        idx = np.argpartition(-S, 50, axis=1)[:, :50]
        v = np.take_along_axis(S, idx, axis=1)
        o = np.argsort(-v, axis=1)
        top[i0:i0 + 1024] = np.take_along_axis(idx, o, 1); sc[i0:i0 + 1024] = np.take_along_axis(v, o, 1)
    np.savez_compressed(os.path.join(OUT, "cpr_top50.npz"), top=top, score=sc)
    json.dump({"config": best, "test": {k: list(v) for k, v in res.items()}, "log": model.log},
              open(os.path.join(OUT, "cpr_results.json"), "w"), indent=1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--test", action="store_true")
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    if args.test:
        best = json.load(open(os.path.join(OUT, "cpr_best_config.json")))
    else:
        best = tune()
    test(best)


if __name__ == "__main__":
    main()
