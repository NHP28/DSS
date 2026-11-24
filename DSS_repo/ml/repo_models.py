"""Serve the TAS-GNN and LightGCN checkpoints that ship in outputs/checkpoints.

The checkpoints are plain state_dicts trained by src/train_compare.py on the first 70% of each
user's check-ins. The propagation graph is rebuilt as server.py does, from the first 80%; the
last 20% (the test events of src/benchmark_ml.py) never enters the graph.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import torch

from ml.poi_model import CATEGORIES, dataset_fingerprints

MIN_FOLDIN_HISTORY = 3
CONFIG = {"embeddingDim": 64, "timeDim": 32, "layers": 3, "trainShare": 0.8}


class RepoModels:
    origin = "repo_checkpoint"

    def __init__(self, root: Path):
        src = str(root / "src")
        if src not in sys.path:
            sys.path.insert(0, src)
        from models.lightgcn import LightGCN
        from models.temporal_gnn import TemporalGNN

        data = root / "data" / "danang"
        pois = pd.read_csv(data / "danang_pois_full.csv")
        events = pd.read_csv(data / "danang_checkins_full.csv")
        n_users, n_items = int(events.u.max()) + 1, len(pois)
        if list(pois.l) != list(range(n_items)):
            raise ValueError("Checkpoint cần POI ID liên tục 0..N-1 theo đúng thứ tự file")
        coords = pois[["lat", "lon"]].to_numpy(np.float32)
        categories = pois.category.map(CATEGORIES).fillna(0).to_numpy(np.int64)

        ordered = events.sort_values(["u", "ts"], kind="stable").reset_index(drop=True)
        position = ordered.groupby("u").cumcount().to_numpy()
        size = ordered.groupby("u").u.transform("size").to_numpy()
        train = ordered[position < np.floor(size * CONFIG["trainShare"]).astype(int)]
        pairs = train[["u", "l"]].to_numpy()

        self.poi_ids = [int(v) for v in pois.l]
        self.user_ids = sorted(int(u) for u in train.u.unique())
        self._users = set(self.user_ids)
        self.train_events = len(train)
        counts = np.ones((24, n_items), dtype=np.float32)  # Laplace smoothing
        np.add.at(counts, (train.hour.to_numpy(int), train.l.to_numpy(int)), 1)
        self.hourly_counts = counts
        self.popularity = counts.sum(0)
        self.dataset_sha256, self.dataset_sha256_aliases = dataset_fingerprints(data)

        folder = root / "outputs" / "checkpoints"
        self.available, self.info = [], {**CONFIG, "blocks": {}}
        self.tas = self.light = None
        tas_path, light_path = folder / "temporal_gnn_danang.pt", folder / "lightgcn_danang.pt"
        if tas_path.is_file():
            self.tas = TemporalGNN(n_users, n_items, coords=coords, category_ids=categories, embedding_dim=64,
                                   time_dim=32, num_layers=3, use_time=True, use_spatial=True)
            self.tas.load_state_dict(torch.load(tas_path, map_location="cpu", weights_only=True))
            self.tas.build_normalized_adj(pairs)
            self.tas.eval()
            with torch.no_grad():
                self.tas_users, self.tas_items = self.tas.get_graph_embeddings()
            self.available.append("tas_gnn")
            self.info["blocks"] = _parameter_blocks(self.tas)
            self.info["parameters"] = int(sum(p.numel() for p in self.tas.parameters()))
        if light_path.is_file():
            self.light = LightGCN(n_users, n_items, embedding_dim=64, num_layers=3)
            self.light.load_state_dict(torch.load(light_path, map_location="cpu", weights_only=True))
            self.light.build_normalized_adj(pairs)
            self.light.eval()
            with torch.no_grad():
                self.light_users, self.light_items = self.light.forward()
            self.available.append("lightgcn")
            self.info["lightgcnParameters"] = int(sum(p.numel() for p in self.light.parameters()))
        self.info.update(users=len(self.user_ids), pois=n_items, trainEvents=self.train_events)

    def knows(self, user) -> bool:
        return user is not None and int(user) in self._users

    def _user_vector(self, users, items, user, history):
        if history is not None:
            if len(set(history)) < MIN_FOLDIN_HISTORY:
                raise ValueError(f"Fold-in cần ít nhất {MIN_FOLDIN_HISTORY} địa điểm khác nhau")
            index = sorted(set(int(v) for v in history))
            if index[0] < 0 or index[-1] >= len(self.poi_ids):
                raise ValueError("Lịch sử chứa POI không có trong catalog")
            # A new account has no trained embedding: represent it by the places it chose.
            return items[index].mean(0)
        if not self.knows(user):
            raise ValueError("User không có trong tập huấn luyện")
        return users[int(user)]

    def score(self, model, user, hour, weekday, timestamp, use_time=True, history=None) -> np.ndarray:
        if model not in self.available:
            raise ValueError(f"Model {model} chưa được nạp")
        with torch.no_grad():
            if model == "lightgcn":
                vector = self._user_vector(self.light_users, self.light_items, user, history)
                return (self.light_items @ vector).numpy().copy()
            net, items = self.tas, self.tas_items
            vector = self._user_vector(self.tas_users, items, user, history)
            if use_time:
                # Same arithmetic as TemporalGNN.predict_for_user_at_time, for an arbitrary user vector.
                encoded = net.time_encoder(torch.tensor([timestamp], dtype=torch.float32),
                                           torch.tensor([hour]), torch.tensor([weekday]))
                context = net.time_proj_user(encoded).squeeze(0)
                vector = vector + net.user_gate(torch.cat([vector, context], -1)) * context
                items = items + net.time_proj_item(encoded)
            return (items @ vector).numpy().copy()


def _parameter_blocks(model) -> dict:
    groups = {"userEmbedding": ("user_embedding",), "poiEmbedding": ("item_embedding",),
              "timeEncoder": ("time_encoder", "time_proj_user", "time_proj_item"),
              "temporalGate": ("user_gate",), "spatialEncoder": ("spatial_encoder",),
              "categoryEmbedding": ("category_embedding",)}
    return {key: int(sum(p.numel() for name, p in model.named_parameters() if name.startswith(prefixes)))
            for key, prefixes in groups.items()}


def load_repo_models(root: Path) -> RepoModels | None:
    models = RepoModels(Path(root))
    return models if models.available else None
