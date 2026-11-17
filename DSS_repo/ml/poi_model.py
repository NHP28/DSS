"""Reproducible POI experiments. Shared by the standalone Colab notebook and serving."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import random
import platform
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from torch import nn
from torch.nn import functional as F

CATEGORIES = {"cafe": 0, "restaurant": 1, "hotel": 2, "tourist_spot": 3}
FORMAT_VERSION = 1


def dataset_metadata(directory):
    directory = Path(directory)
    metadata = {"dataset_id":"danang", "has_categories":True, "timezone":"Asia/Ho_Chi_Minh",
                "data_provenance":"OSM POIs; synthetic check-ins/ratings/prices/popularity"}
    for name in ("metadata.json", "experiment_metadata.json"):
        if (directory / name).is_file():
            metadata.update(json.loads((directory / name).read_text(encoding="utf-8")))
    metadata.setdefault("poi_file", "danang_pois_full.csv")
    metadata.setdefault("event_file", "danang_checkins_full.csv")
    return metadata


def dataset_fingerprints(directory):
    metadata = dataset_metadata(directory)
    raw, lf, crlf = hashlib.sha256(), hashlib.sha256(), hashlib.sha256()
    for name in (metadata["poi_file"], metadata["event_file"]):
        content = (Path(directory) / name).read_bytes()
        normalized = content.replace(b"\r\n", b"\n")
        raw.update(content)
        lf.update(normalized)
        crlf.update(normalized.replace(b"\n", b"\r\n"))
    return raw.hexdigest(), sorted({lf.hexdigest(), crlf.hexdigest()})


def seed_everything(seed: int):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True


def load_data(directory, max_users=None):
    directory = Path(directory)
    metadata = dataset_metadata(directory)
    pois = pd.read_csv(directory / metadata["poi_file"]).sort_values("l").reset_index(drop=True)
    events = pd.read_csv(directory / metadata["event_file"])
    required = {"u", "l", "ts", "hour", "day_of_week"}
    if not required.issubset(events.columns) or not {"l", "lat", "lon", "category"}.issubset(pois.columns):
        raise ValueError("CSV thiếu cột bắt buộc")
    if events[list(required)].isna().any().any() or pois[["l", "lat", "lon", "category"]].isna().any().any():
        raise ValueError("Dữ liệu có giá trị thiếu")
    if not np.isfinite(events[["ts", "hour", "day_of_week"]].to_numpy(dtype=float)).all():
        raise ValueError("Thời gian không hữu hạn")
    if not events.hour.between(0, 23).all() or not events.day_of_week.between(0, 6).all():
        raise ValueError("Giờ/thứ nằm ngoài miền hợp lệ")
    if not np.isfinite(pois[["lat", "lon"]].to_numpy()).all() or not pois.lat.between(-90, 90).all() or not pois.lon.between(-180, 180).all():
        raise ValueError("Tọa độ không hợp lệ")
    allowed_categories = set(CATEGORIES) if metadata["has_categories"] else {"unknown"}
    if pois.l.duplicated().any() or not set(pois.category).issubset(allowed_categories):
        raise ValueError("POI ID trùng hoặc category không hỗ trợ")
    for column in (events.u, events.l, pois.l, events.hour, events.day_of_week):
        values = column.to_numpy(dtype=float)
        if not np.isfinite(values).all() or not (values >= 0).all() or not (values == np.floor(values)).all():
            raise ValueError("ID, giờ, thứ phải là số nguyên không âm")
    if not set(events.l).issubset(set(pois.l)):
        raise ValueError("Check-in tham chiếu POI không tồn tại")
    # Keep repeated visits; remove only identical event records.
    events = events.drop_duplicates(["u", "l", "ts"]).copy()
    counts = events.groupby("u").size()
    distinct_times = events.groupby("u").ts.nunique()
    eligible = counts[(counts >= 5) & (distinct_times >= 3)].index
    events = events[events.u.isin(eligible)].copy()
    user_ids = sorted(int(u) for u in events.u.unique())
    if max_users is not None:
        user_ids = user_ids[:max_users]
        events = events[events.u.isin(user_ids)].copy()
    if not user_ids:
        raise ValueError("Không đủ người dùng có ít nhất 5 sự kiện")
    if max_users is not None and metadata["dataset_id"] == "gowalla":
        pois = pois[pois.l.isin(events.l)].reset_index(drop=True)
    poi_ids = [int(v) for v in pois.l]
    events["user"] = events.u.map({u: i for i, u in enumerate(user_ids)})
    events["item"] = events.l.map({v: i for i, v in enumerate(poi_ids)})
    events = events.sort_values(["user", "ts"], kind="stable").reset_index(drop=True)
    fingerprint, _ = dataset_fingerprints(directory)
    return pois, events, user_ids, poi_ids, fingerprint


def temporal_split(events):
    """Per-user 70/10/20; identical timestamps always stay in the same partition."""
    parts = np.empty(len(events), dtype=np.int64)
    for _, rows in events.groupby("user", sort=False):
        ts = rows.ts.to_numpy()
        starts = np.flatnonzero(np.r_[True, ts[1:] != ts[:-1]])
        if len(starts) < 3:
            raise ValueError("Mỗi user cần ít nhất 3 timestamp khác nhau")
        # Preserve at least one timestamp group per split, including heavily tied users.
        ai = int(np.clip(np.searchsorted(starts, int(len(ts) * .7), side="right") - 1, 1, len(starts) - 2))
        bi = int(np.clip(np.searchsorted(starts, int(len(ts) * .8), side="right") - 1, ai + 1, len(starts) - 1))
        a, b = starts[ai], starts[bi]
        parts[rows.index] = np.where(np.arange(len(ts)) < a, 0, np.where(np.arange(len(ts)) < b, 1, 2))
    frames = tuple(events[parts == i].copy() for i in range(3))
    if any(frame.empty for frame in frames):
        raise ValueError("Không đủ timestamp khác nhau để chia train/validation/test")
    return frames


def seen_items(frame):
    return {int(u): set(map(int, group.item)) for u, group in frame.groupby("user")}


def negative_samples(users, seen, n_items, rng):
    """Exclude ALL fit positives, including the current positive item."""
    negatives = rng.integers(n_items, size=len(users))
    for index, user in enumerate(users):
        visited = seen[int(user)]
        if len(visited) >= n_items:
            raise ValueError("User đã ghé toàn bộ POI; không thể lấy mẫu âm")
        while int(negatives[index]) in visited:
            negatives[index] = rng.integers(n_items)
    return negatives


class POIGraph(nn.Module):
    def __init__(self, n_users, coords, categories, dim=64, layers=3, temporal=True, spatial=True, category_features=True):
        super().__init__()
        self.n_users, self.n_items = n_users, len(coords)
        self.temporal, self.spatial, self.layers = temporal, spatial, layers
        self.category_features = category_features
        self.user_embedding = nn.Embedding(n_users, dim)
        self.item_embedding = nn.Embedding(self.n_items, dim)
        nn.init.xavier_uniform_(self.user_embedding.weight)
        nn.init.xavier_uniform_(self.item_embedding.weight)
        coords = torch.as_tensor(coords.copy() if isinstance(coords, np.ndarray) else coords, dtype=torch.float32).clone()
        self.register_buffer("coords", coords)
        self.register_buffer("coord_center", coords.mean(0))
        self.register_buffer("coord_scale", coords.std(0, unbiased=False).clamp_min(1e-3))
        self.register_buffer("categories", torch.as_tensor(categories.copy() if isinstance(categories, np.ndarray) else categories, dtype=torch.long).clone())
        self.register_buffer("adj", None, persistent=False)
        if spatial:
            self.spatial_encoder = nn.Sequential(nn.Linear(2, dim), nn.ReLU(), nn.Linear(dim, dim))
            if category_features:
                self.category_embedding = nn.Embedding(len(CATEGORIES), dim)
        if temporal:
            # Small periodic inputs; never feed float32 Unix timestamps to Fourier features.
            self.time_encoder = nn.Sequential(nn.Linear(4, dim), nn.Tanh(), nn.Linear(dim, dim))
            self.user_gate = nn.Linear(dim * 2, dim)
            self.item_context = nn.Linear(dim, dim)
            if category_features:
                self.time_category = nn.Embedding(len(CATEGORIES), dim)

    def build_graph(self, pairs):
        pairs = torch.as_tensor(pairs.copy() if isinstance(pairs, np.ndarray) else pairs, dtype=torch.long, device=self.coords.device).unique(dim=0)
        u, i = pairs[:, 0], pairs[:, 1] + self.n_users
        row, col = torch.cat([u, i]), torch.cat([i, u])
        n = self.n_users + self.n_items
        degree = torch.bincount(row, minlength=n).float().clamp_min(1)
        values = degree[row].rsqrt() * degree[col].rsqrt()
        self.adj = torch.sparse_coo_tensor(torch.stack([row, col]), values, (n, n), check_invariants=True).coalesce()

    def embeddings(self):
        if self.adj is None:
            raise RuntimeError("Phải build_graph bằng đúng fit_pairs trước khi predict")
        current = torch.cat([self.user_embedding.weight, self.item_embedding.weight])
        result = current
        for _ in range(self.layers):
            current = torch.sparse.mm(self.adj, current)
            result = result + current
        users, items = (result / (self.layers + 1)).split([self.n_users, self.n_items])
        if self.spatial:
            items = items + self.spatial_encoder((self.coords - self.coord_center) / self.coord_scale)
            if self.category_features:
                items = items + self.category_embedding(self.categories)
        return users, items

    def context(self, hours, weekdays, timestamps):
        # hour/day_of_week in CSV are local Asia/Ho_Chi_Minh; timestamp supplies minutes/seconds.
        fraction = torch.remainder(timestamps.double(), 3600) / 3600
        day = (hours.double() + fraction) / 24
        week = (weekdays.double() + day) / 7
        features = torch.stack([torch.sin(2 * math.pi * day), torch.cos(2 * math.pi * day),
                                torch.sin(2 * math.pi * week), torch.cos(2 * math.pi * week)], -1).float()
        return self.time_encoder(features)

    def item_modulation(self, items):
        if self.category_features:
            return torch.sigmoid(self.time_category(self.categories[items]))
        # Gowalla has no category labels: learn an item-specific interaction instead.
        return torch.sigmoid(self.item_embedding(items))

    def score_pairs(self, users, items, hours, weekdays, timestamps, embeddings=None):
        ue, ie = embeddings if embeddings is not None else self.embeddings()
        user, item = ue[users], ie[items]
        if self.temporal:
            context = self.context(hours, weekdays, timestamps)
            user = user + torch.sigmoid(self.user_gate(torch.cat([user, context], -1))) * context
            item = item + self.item_context(context) * self.item_modulation(items)
        return (user * item).sum(-1)

    def scores(self, user, hour, weekday, timestamp, embeddings=None):
        device = self.coords.device
        return self.scores_batch(torch.tensor([user],device=device), torch.tensor([hour],device=device),
                                 torch.tensor([weekday],device=device), torch.tensor([timestamp],dtype=torch.float64,device=device), embeddings)[0]

    def scores_batch(self, users, hours, weekdays, timestamps, embeddings=None):
        ue, ie = embeddings if embeddings is not None else self.embeddings()
        user = ue[users]
        if not self.temporal:
            return user @ ie.T
        context = self.context(hours, weekdays, timestamps)
        user = user + torch.sigmoid(self.user_gate(torch.cat([user, context], -1))) * context
        modulation = self.item_modulation(torch.arange(self.n_items, device=user.device))
        return user @ ie.T + (user * self.item_context(context)) @ modulation.T

    def loss(self, users, pos, neg, hours, weekdays, timestamps):
        emb = self.embeddings()
        delta = self.score_pairs(users, pos, hours, weekdays, timestamps, emb) - self.score_pairs(users, neg, hours, weekdays, timestamps, emb)
        reg = sum(x.square().sum() for x in [self.user_embedding(users), self.item_embedding(pos), self.item_embedding(neg)]) / len(users)
        return F.softplus(-delta).mean() + 1e-4 * reg


def hourly_counts(frame, n_items):
    counts = np.ones((24, n_items), dtype=np.float32)  # Laplace smoothing
    np.add.at(counts, (frame.hour.to_numpy(int), frame.item.to_numpy(int)), 1)
    return counts


def evaluate(predict, held_out, seen, ks=(5, 10, 20)):
    """Event-level novel-POI HR/NDCG; fixed fit history, no target location input."""
    sums = {f"{m}@{k}": 0.0 for k in ks for m in ("HR", "NDCG", "MRR")}
    per_user = {}
    count, skipped = 0, 0
    for row in held_out.itertuples():
        if row.item in seen.get(row.user, set()):
            skipped += 1
            continue
        scores = np.array(predict(row), dtype=float, copy=True)
        scores[list(seen.get(row.user, set()))] = -np.inf
        finite = np.flatnonzero(np.isfinite(scores))
        k = min(max(ks), len(finite))
        if k:
            threshold = np.partition(scores[finite], -k)[-k]
            candidates = finite[scores[finite] >= threshold]
            order = candidates[np.lexsort((candidates, -scores[candidates]))[:k]]
        else:
            order = np.array([], dtype=int)
        indices = np.flatnonzero(order == row.item)
        rank = int(indices[0]) + 1 if len(indices) else math.inf
        per_user.setdefault(int(row.user), []).append(float(rank <= 10))
        for k in ks:
            if rank <= k:
                sums[f"HR@{k}"] += 1
                sums[f"NDCG@{k}"] += 1 / math.log2(rank + 1)
                sums[f"MRR@{k}"] += 1 / rank
        count += 1
    if not count:
        raise ValueError("Không có sự kiện POI mới để đánh giá")
    return {**{key: val / count for key, val in sums.items()}, "events": count, "excluded_seen_events": skipped,
            "users": len(per_user), "macro_user_HR@10": float(np.mean([np.mean(v) for v in per_user.values()]))}


def model_metrics(model, held_out, seen, batch_size=128):
    model.eval()
    with torch.inference_mode():
        emb = model.embeddings()
        novel = held_out[np.fromiter((r.item not in seen.get(r.user, set()) for r in held_out.itertuples()), dtype=bool)]
        device = model.coords.device
        def predictions():
            for start in range(0, len(novel), batch_size):
                rows = novel.iloc[start:start + batch_size]
                values = [torch.as_tensor(rows[c].to_numpy(copy=True), dtype=torch.long, device=device) for c in ("user","hour","day_of_week")]
                timestamps = torch.as_tensor(rows.ts.to_numpy(np.float64, copy=True), device=device)
                scores = model.scores_batch(*values, timestamps, emb).cpu().numpy()
                yield from scores
        iterator = predictions()
        metrics = evaluate(lambda row: next(iterator), novel, seen)
        metrics["excluded_seen_events"] = len(held_out) - len(novel)
        return metrics


def fit_model(config, coords, categories, frame, epochs, seed, device, validation=None, patience=4, batch_size=1024, eval_batch_size=128, lr=.001):
    seed_everything(seed)
    model = POIGraph(coords=coords, categories=categories, **config).to(device)
    model.build_graph(frame[["user", "item"]].to_numpy())
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    seen, rng = seen_items(frame), np.random.default_rng(seed)
    best, best_epoch, best_state, stale, history = -1.0, 0, None, 0, []
    for epoch in range(1, epochs + 1):
        model.train()
        loss_sum, examples = 0.0, 0
        for start in range(0, len(frame), batch_size):
            # permutation is generated once per epoch below via shuffled
            if start == 0:
                shuffled = frame.iloc[rng.permutation(len(frame))]
            rows = shuffled.iloc[start:start + batch_size]
            users = rows.user.to_numpy(int)
            neg = negative_samples(users, seen, len(coords), rng)
            arrays = [users, rows.item.to_numpy(int), neg, rows.hour.to_numpy(int), rows.day_of_week.to_numpy(int)]
            tensors = [torch.as_tensor(v.copy(), dtype=torch.long, device=device) for v in arrays]
            timestamps = torch.as_tensor(rows.ts.to_numpy(np.float64, copy=True), device=device)
            optimizer.zero_grad(set_to_none=True)
            loss = model.loss(*tensors, timestamps)
            if not torch.isfinite(loss):
                raise ValueError("Loss không hữu hạn")
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 5.0)
            optimizer.step()
            loss_sum += loss.item() * len(rows)
            examples += len(rows)
        record = {"epoch": epoch, "loss": loss_sum / examples}
        if validation is not None:
            metric = model_metrics(model, validation, seen, eval_batch_size)["HR@10"]
            record["validation_HR@10"] = metric
            if metric > best:
                best, best_epoch, stale = metric, epoch, 0
                best_state = copy.deepcopy(model.state_dict())
            else:
                stale += 1
        history.append(record)
        print(json.dumps(record), flush=True)
        if validation is not None and stale >= patience:
            break
    if best_state is not None:
        model.load_state_dict(best_state)
    return model, best_epoch or epochs, history


def run_experiment(data_dir, output_dir, epochs=20, seed=42, max_users=None, dim=64, layers=3, batch_size=1024, eval_batch_size=128):
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    pois, events, user_ids, poi_ids, fingerprint = load_data(data_dir, max_users)
    metadata = dataset_metadata(data_dir)
    _, fingerprint_aliases = dataset_fingerprints(data_dir)
    train, validation, test = temporal_split(events)
    fit = pd.concat([train, validation]).sort_values(["user", "ts"])
    coords = pois[["lat", "lon"]].to_numpy(np.float32)
    categories = pois.category.map(CATEGORIES).fillna(0).to_numpy(np.int64)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    # Avoid excessive CPU thread overhead for the small graph.
    if device == "cpu":
        torch.set_num_threads(min(4, torch.get_num_threads()))
    report = {"seed": seed, "device": device, "dataset_sha256": fingerprint,
              "versions": {"python": platform.python_version(), "torch": str(torch.__version__), "numpy": np.__version__, "pandas": pd.__version__},
              "dataset_id":metadata["dataset_id"], "dataset_metadata":metadata,
              "data_provenance":metadata["data_provenance"],
              "protocol": "per-user chronological 70/10/20; tune epochs on validation; refit train+validation; novel-event test once",
              "smoke_run": max_users is not None, "is_subset":bool(metadata.get("is_subset") or max_users is not None),
              "users": len(user_ids), "pois": len(poi_ids),
              "splits": {"train": len(train), "validation": len(validation), "test": len(test)}, "results": {}, "history": {}}
    seen = seen_items(fit)
    counts = hourly_counts(fit, len(pois))
    report["results"]["hourly_popularity"] = evaluate(lambda r: counts[r.hour], test, seen)
    global_counts = counts.sum(0)
    report["results"]["popularity"] = evaluate(lambda r: global_counts, test, seen)
    for name, temporal, spatial in [("lightgcn", False, False), ("tas_gnn", True, True)]:
        config = dict(n_users=len(user_ids), dim=dim, layers=layers, temporal=temporal, spatial=spatial,
                      category_features=bool(metadata["has_categories"]))
        print(f"Tuning {name} on validation", flush=True)
        _, best_epochs, history = fit_model(config, coords, categories, train, epochs, seed, device,
                                           validation=validation, batch_size=batch_size, eval_batch_size=eval_batch_size)
        print(f"Refit {name}: {best_epochs} epochs", flush=True)
        model, _, _ = fit_model(config, coords, categories, fit, best_epochs, seed, device, batch_size=batch_size)
        report["results"][name] = model_metrics(model, test, seen, eval_batch_size)
        report["history"][name] = {"selected_epoch": best_epochs, "validation": history}
        bundle = {"format_version": FORMAT_VERSION, "model_name": name, "model_config": config,
                  "state_dict": {k: v.cpu() for k, v in model.state_dict().items()},
                  "fit_pairs": torch.as_tensor(fit[["user", "item"]].to_numpy(), dtype=torch.long),
                  "hourly_counts": torch.from_numpy(counts), "user_ids": user_ids, "poi_ids": poi_ids,
                  "dataset_sha256": fingerprint, "dataset_sha256_aliases":fingerprint_aliases,
                  "dataset_id":metadata["dataset_id"], "dataset_metadata":metadata,
                  "timezone":metadata["timezone"], "categories": CATEGORIES if metadata["has_categories"] else {},
                  "seed": seed, "selected_epoch": best_epochs, "smoke_run": max_users is not None}
        torch.save(bundle, output / f"{name}.pt")
    (output / "metrics.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    pd.DataFrame(report["results"]).T.to_csv(output / "comparison.csv")
    print(json.dumps(report["results"], indent=2), flush=True)
    return report


def restore_bundle(path, device="cpu"):
    bundle = torch.load(path, map_location="cpu", weights_only=True)
    if bundle["format_version"] != FORMAT_VERSION:
        raise ValueError("Artifact format không hỗ trợ")
    state = bundle["state_dict"]
    architecture = bundle.get("model_architecture", "poi_graph_v1")
    model_class = POIGraph
    if architecture == "spatial_history_v2":
        from ml.colab_model import HistorySpatialPOIGraph
        model_class = HistorySpatialPOIGraph
    elif architecture != "poi_graph_v1":
        raise ValueError(f"Artifact architecture không hỗ trợ: {architecture}")
    model = model_class(coords=state["coords"], categories=state["categories"], **bundle["model_config"])
    model.load_state_dict(state)
    model.to(device)
    model.build_graph(bundle["fit_pairs"])
    model.eval()
    return model, bundle


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default="data/danang")
    parser.add_argument("--output-dir", default="outputs/colab")
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-users", type=int)
    parser.add_argument("--dim", type=int, default=64)
    parser.add_argument("--layers", type=int, default=3)
    parser.add_argument("--batch-size", type=int, default=1024)
    parser.add_argument("--eval-batch-size", type=int, default=128)
    args = parser.parse_args()
    if args.epochs < 1 or args.batch_size < 1:
        parser.error("epochs và batch-size phải dương")
    run_experiment(**vars(args))
