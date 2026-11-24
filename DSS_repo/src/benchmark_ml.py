"""One protocol, every method: heuristics, classical ML, LightGCN and TAS-GNN on Đà Nẵng.

Protocol: each user's check-ins sorted by time, first 80% train, last 20% test. Only test
events at a POI the user did not visit in train are scored; candidates are the whole
catalog minus the user's train POIs. Every test event is evaluated (no sub-sampling) with
its real hour and weekday.

    python src/benchmark_ml.py          (hoặc từng bước, có biểu đồ: notebooks/01..03)
"""
from __future__ import annotations

import json
import math
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import scipy.sparse as sp
import torch

os.environ.setdefault("LOKY_MAX_CPU_COUNT", "4")
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

KS = (5, 10, 20)
CATEGORY_IDS = {"cafe": 0, "restaurant": 1, "hotel": 2, "tourist_spot": 3}
MODELS = [
    ("popularity", "Phổ biến chung", "heuristic"),
    ("hourly_popularity", "Phổ biến theo giờ", "heuristic"),
    ("hour_prev_distance", "Giờ × khoảng cách liền trước", "heuristic"),
    ("user_knn", "User-KNN", "ml"),
    ("item_knn", "Item-KNN", "ml"),
    ("bpr_mf", "BPR-MF", "ml"),
    ("feature_gbm", "Gradient Boosting (đặc trưng)", "ml"),
    ("lightgcn", "LightGCN", "gnn"),
    ("tas_gnn", "TAS-GNN", "gnn"),
]


def rank_metrics(ranks, ks=KS) -> dict:
    """ranks: 1-based rank of the true POI per event (np.inf when it is not ranked)."""
    ranks = np.asarray(ranks, dtype=float)
    metrics = {}
    for k in ks:
        hit = ranks <= k
        metrics[f"HR@{k}"] = float(hit.mean())
        metrics[f"NDCG@{k}"] = float(np.where(hit, 1 / np.log2(np.where(hit, ranks, 1) + 1), 0).mean())
        metrics[f"MRR@{k}"] = float(np.where(hit, 1 / np.where(hit, ranks, 1), 0).mean())
    return metrics


def target_ranks(scores, targets, seen):
    """Rank of each row's target among unseen items; ties go to the lower item index."""
    scores = np.where(seen, -np.inf, np.asarray(scores, dtype=float))
    rows = np.arange(len(targets))
    own = scores[rows, targets][:, None]
    index = np.arange(scores.shape[1])[None, :]
    return 1 + (scores > own).sum(1) + ((scores == own) & (index < targets[:, None])).sum(1)


def load_split():
    data = ROOT / "data" / "danang"
    pois = pd.read_csv(data / "danang_pois_full.csv")
    pois["category_id"] = pois.category.map(CATEGORY_IDS).fillna(0).astype(int)
    events = pd.read_csv(data / "danang_checkins_full.csv").sort_values(["u", "ts"], kind="stable").reset_index(drop=True)
    position = events.groupby("u").cumcount().to_numpy()
    size = events.groupby("u").u.transform("size").to_numpy()
    events["position"], events["size"] = position, size
    events["prev_l"] = events.groupby("u").l.shift(1)
    train = events[position < np.floor(size * 0.8).astype(int)].copy()
    test = events[position >= np.floor(size * 0.8).astype(int)].copy()
    return pois, events, train, test


def prepare():
    """Everything the methods share: the split, the scored test events and train-only statistics."""
    pois, events, train, test = load_split()
    n_users, n_items = int(events.u.max()) + 1, len(pois)
    pairs = train[["u", "l"]].to_numpy(int)
    seen = np.zeros((n_users, n_items), dtype=bool)
    seen[pairs[:, 0], pairs[:, 1]] = True
    novel = test[~seen[test.u.to_numpy(int), test.l.to_numpy(int)]].copy()
    novel["prev_l"] = novel.prev_l.fillna(0).astype(int)
    counts = sp.coo_matrix((np.ones(len(pairs), np.float32), (pairs[:, 0], pairs[:, 1])), shape=(n_users, n_items)).tocsr()
    hourly = np.zeros((24, n_items))
    np.add.at(hourly, (train.hour.to_numpy(int), train.l.to_numpy(int)), 1)
    return SimpleNamespace(pois=pois, events=events, train=train, test=test, novel=novel, n_users=n_users, n_items=n_items,
                           pairs=pairs, seen=seen, counts=counts, hourly=hourly, popularity=hourly.sum(0),
                           coords=pois[["lat", "lon"]].to_numpy(float))


def evaluate(bench, score, batch=256):
    """Rank of the true POI for every scored test event. score(chunk) -> (len(chunk), n_items)."""
    ranks = []
    for start in range(0, len(bench.novel), batch):
        chunk = bench.novel.iloc[start:start + batch]
        ranks.append(target_ranks(score(chunk), chunk.l.to_numpy(int), bench.seen[chunk.u.to_numpy(int)]))
    return np.concatenate(ranks)


def heuristic_scorers(bench):
    from baselines.feature_gbm import km

    def distance(chunk):
        c = bench.coords
        return np.vstack([km(c[p, 0], c[p, 1], c[:, 0], c[:, 1]) for p in chunk.prev_l.to_numpy(int)])

    return {"popularity": lambda chunk: np.tile(bench.popularity, (len(chunk), 1)),
            "hourly_popularity": lambda chunk: bench.hourly[chunk.hour.to_numpy(int)],
            "hour_prev_distance": lambda chunk: bench.hourly[chunk.hour.to_numpy(int)] / (distance(chunk) + 0.5)}


def tune_bpr(bench, grid=((30, 0.005), (100, 0.005), (30, 0.02), (100, 0.02)), log=print):
    """Pick epochs/lr on the last eighth of train, then refit on all of train.

    Returns (model, (epochs, lr), trials) where trials is a list of {epochs, lr, HR@10}.
    """
    from baselines.bpr_mf import BPRMF

    train = bench.train
    cut = np.floor(train["size"] * 0.7).astype(int)
    early, late = train[train.position < cut], train[train.position >= cut]
    early_pairs = early[["u", "l"]].to_numpy(int)
    early_seen = np.zeros((bench.n_users, bench.n_items), dtype=bool)
    early_seen[early_pairs[:, 0], early_pairs[:, 1]] = True
    late = late[~early_seen[late.u.to_numpy(int), late.l.to_numpy(int)]]
    users, targets = late.u.to_numpy(int), late.l.to_numpy(int)
    trials = []
    for epochs, lr in grid:
        model = BPRMF(epochs=epochs, lr=lr).fit(early_pairs, bench.n_users, bench.n_items)
        hr = rank_metrics(target_ranks(model.predict(users), targets, early_seen[users]))["HR@10"]
        log(f"    epochs={epochs} lr={lr}: validation HR@10 {hr:.4f}")
        trials.append({"epochs": epochs, "lr": lr, "HR@10": hr})
    best = max(trials, key=lambda t: t["HR@10"])
    config = (best["epochs"], best["lr"])
    return BPRMF(epochs=config[0], lr=config[1]).fit(bench.pairs, bench.n_users, bench.n_items), config, trials


def tune_gbm(bench, depths=(4, 8), log=print):
    """Labels come from the last 30% of train; user features only from the 70% before it.

    Returns a namespace: model, depth, rows, trials, X, y and scorer(chunk), which ranks with features of all of train.
    """
    from baselines.feature_gbm import History, fit_gbm, training_set

    train, items = bench.train, np.arange(bench.n_items)
    cut = np.floor(train["size"] * 0.8 * 0.7).astype(int)
    early, late = train[train.position < cut], train[train.position >= cut]
    history = History(early, bench.pois, bench.n_users)
    late = late[~history.seen[late.u.to_numpy(int), late.l.to_numpy(int)]]
    validation_cut = np.floor(late["size"] * 0.8 * 0.9).astype(int)
    fit_part, validation = late[late.position < validation_cut], late[late.position >= validation_cut]
    X, y = training_set(history, fit_part)
    sample = validation.iloc[:: max(1, len(validation) // 800)]
    users = sample.u.to_numpy(int)
    trials = []
    for depth in depths:
        model = fit_gbm(X, y, depth)
        scores = np.vstack([model.predict_proba(history.rows(u, items, h, w))[:, 1]
                            for u, h, w in sample[["u", "hour", "day_of_week"]].to_numpy(int)])
        hr = rank_metrics(target_ranks(scores, sample.l.to_numpy(int), history.seen[users]))["HR@10"]
        log(f"    max_depth={depth}: validation HR@10 {hr:.4f}")
        trials.append({"max_depth": depth, "HR@10": hr})
    depth = max(trials, key=lambda t: t["HR@10"])["max_depth"]
    X, y = training_set(history, late)
    model = fit_gbm(X, y, depth)
    full = History(train, bench.pois, bench.n_users)

    def scorer(chunk):
        rows = np.vstack([full.rows(u, items, h, w) for u, h, w in chunk[["u", "hour", "day_of_week"]].to_numpy(int)])
        return model.predict_proba(rows)[:, 1].reshape(len(chunk), bench.n_items)

    return SimpleNamespace(model=model, depth=depth, rows=len(y), trials=trials, scorer=scorer, X=X, y=y, history=full)


def gnn_scorers(repo):
    """Score with the checkpoints in outputs/checkpoints (no retraining)."""
    def tas(chunk, use_time=True):
        u = chunk.u.to_numpy(int)
        with torch.no_grad():
            vector = repo.tas_users[u]
            if not use_time:
                return (vector @ repo.tas_items.T).numpy()
            net = repo.tas
            encoded = net.time_encoder(torch.as_tensor(chunk.ts.to_numpy(np.float32)), torch.as_tensor(chunk.hour.to_numpy(int)),
                                       torch.as_tensor(chunk.day_of_week.to_numpy(int)))
            context = net.time_proj_user(encoded)
            vector = vector + net.user_gate(torch.cat([vector, context], -1)) * context
            # time_proj_item adds the same vector to every POI, so it shifts all scores equally.
            return (vector @ repo.tas_items.T + (vector * net.time_proj_item(encoded)).sum(-1, keepdim=True)).numpy()

    def light(chunk):
        with torch.no_grad():
            return (repo.light_users[chunk.u.to_numpy(int)] @ repo.light_items.T).numpy()

    return {"lightgcn": light, "tas_gnn": tas}


RANKS = ROOT / "outputs" / "benchmark_ranks"


def save_ranks(key, ranks, seconds=0.0, note=None):
    """Keep one method's per-event ranks so the notebooks can be run one after another."""
    RANKS.mkdir(parents=True, exist_ok=True)
    np.save(RANKS / f"{key}.npy", np.asarray(ranks))
    meta_path = RANKS / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.is_file() else {}
    meta[key] = {"seconds": round(float(seconds), 2), "note": note}
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


def load_ranks():
    """(ranks, seconds, notes) of every method saved so far, in the order of MODELS."""
    meta_path = RANKS / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.is_file() else {}
    ranks = {key: np.load(RANKS / f"{key}.npy") for key, _, _ in MODELS if (RANKS / f"{key}.npy").is_file()}
    return ranks, {k: meta.get(k, {}).get("seconds", 0.0) for k in ranks}, {k: meta.get(k, {}).get("note") for k in ranks}


def results_table(ranks):
    """Metrics in percent, one row per method."""
    labels = {key: label for key, label, _ in MODELS}
    groups = {key: group for key, _, group in MODELS}
    return pd.DataFrame([{"model": key, "label": labels[key], "group": groups[key],
                          **{name: round(value * 100, 2) for name, value in rank_metrics(ranks[key]).items()}}
                         for key, _, _ in MODELS if key in ranks])


def write_report(bench, ranks, seconds, notes):
    """Write the CSV and the JSON the /evaluation page reads. Needs all nine methods."""
    missing = [key for key, _, _ in MODELS if key not in ranks]
    if missing:
        raise ValueError(f"Chưa có kết quả của: {', '.join(missing)}")
    results = []
    for key, label, group in MODELS:
        metrics = rank_metrics(ranks[key])
        results.append({"key": key, "label": label, "group": group, "main": key == "tas_gnn",
                        "usesPrevLocation": key == "hour_prev_distance", "trainSeconds": seconds.get(key, 0.0),
                        "metrics": {name: round(value, 6) for name, value in metrics.items()}})
    table = results_table(ranks)
    table["train_seconds"] = [seconds.get(key, 0.0) for key in table.model]
    (ROOT / "outputs").mkdir(exist_ok=True)
    table.to_csv(ROOT / "outputs" / "benchmark_ml_danang.csv", index=False, encoding="utf-8-sig")
    report = {
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "dataset": {"users": int(bench.events.u.nunique()), "pois": bench.n_items, "events": len(bench.events),
                    "trainEvents": len(bench.train), "testEvents": len(bench.test), "novelTestEvents": len(bench.novel)},
        "protocol": "Chia 80/20 theo thời gian cho từng người dùng; chỉ tính sự kiện test tại địa điểm chưa ghé trong train; "
                    "xếp hạng trên toàn bộ catalog trừ các địa điểm đã ghé; đánh giá toàn bộ sự kiện với giờ và thứ thật.",
        "notes": {"feature_gbm": notes.get("feature_gbm"), "bpr_mf": notes.get("bpr_mf"), "user_knn": "cosine trên ma trận số lượt ghé",
                  "item_knn": "cosine, 50 láng giềng", "gnn": "checkpoint huấn luyện trên 70% đầu, đồ thị lan truyền dựng từ 80% đầu; không huấn luyện lại",
                  "hour_prev_distance": "được biết vị trí check-in ngay trước sự kiện test; các phương pháp khác thì không"},
        "models": results,
    }
    target = ROOT / "FE" / "public" / "artifacts" / "benchmark-ml.json"
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def bpr_note(config):
    return f"dim 64, {config[0]} epoch, Adam lr {config[1]} (chọn trên validation)"


def gbm_note(gbm):
    return f"HistGradientBoosting, max_depth={gbm.depth}, {gbm.rows:,} dòng huấn luyện, mẫu âm 4:1"


def run():
    """All nine methods in one go; the notebooks in notebooks/ do the same step by step with charts."""
    from baselines.item_knn import ItemKNN
    from baselines.user_cf import UserCF
    from ml.repo_models import load_repo_models

    torch.set_num_threads(min(4, torch.get_num_threads()))
    bench = prepare()
    print(f"Train {len(bench.train):,} | test {len(bench.test):,} | test tại POI mới {len(bench.novel):,}", flush=True)
    seconds, notes = {key: 0.0 for key, _, _ in MODELS}, {}

    def timed(key, build):
        start = time.perf_counter()
        result = build()
        seconds[key] = round(time.perf_counter() - start, 2)
        print(f"  {key}: {seconds[key]} s", flush=True)
        return result

    print("Huấn luyện baseline…", flush=True)
    user_knn = timed("user_knn", lambda: UserCF().fit(bench.counts))
    item_knn = timed("item_knn", lambda: ItemKNN(k=50).fit(bench.counts))
    bpr, bpr_config, _ = timed("bpr_mf", lambda: tune_bpr(bench, log=lambda m: print(m, flush=True)))
    gbm = timed("feature_gbm", lambda: tune_gbm(bench, log=lambda m: print(m, flush=True)))
    notes.update(bpr_mf=bpr_note(bpr_config), feature_gbm=gbm_note(gbm))

    scorers = {**heuristic_scorers(bench), "user_knn": lambda c: user_knn.predict(c.u.to_numpy(int)),
               "item_knn": lambda c: item_knn.predict(c.u.to_numpy(int)), "bpr_mf": lambda c: bpr.predict(c.u.to_numpy(int)),
               "feature_gbm": gbm.scorer, **gnn_scorers(load_repo_models(ROOT))}
    print("Chấm điểm toàn bộ sự kiện test…", flush=True)
    ranks = {key: evaluate(bench, scorers[key]) for key, _, _ in MODELS}
    for key in ranks:
        save_ranks(key, ranks[key], seconds[key], notes.get(key))
    report = write_report(bench, ranks, seconds, notes)

    print("\n" + f"{'Phương pháp':<32} {'HR@5':>7} {'HR@10':>7} {'HR@20':>7} {'NDCG@10':>8} {'MRR@10':>7}")
    for row in report["models"]:
        m = row["metrics"]
        print(f"{row['label']:<32} {m['HR@5']:>7.2%} {m['HR@10']:>7.2%} {m['HR@20']:>7.2%} {m['NDCG@10']:>8.2%} {m['MRR@10']:>7.2%}")
    print("\nĐã ghi FE/public/artifacts/benchmark-ml.json và outputs/benchmark_ml_danang.csv")
    return report


if __name__ == "__main__":
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8")
    run()
