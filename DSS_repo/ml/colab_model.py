"""Inference for the spatial-history architecture exported by the full Colab run.

Older format-1 checkpoints use POIGraph directly. The new export adds the mean
spatial representation of a user's fit history to their graph embedding.
"""
import torch
from torch import nn

from ml.poi_model import POIGraph


class HistorySpatialPOIGraph(POIGraph):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.register_buffer("user_item_adj", None, persistent=False)
        if self.temporal and not self.category_features:
            self.time_item = nn.Embedding(self.n_items, self.item_embedding.embedding_dim)

    def build_graph(self, pairs):
        super().build_graph(pairs)
        pairs = torch.as_tensor(pairs, dtype=torch.long, device=self.coords.device).unique(dim=0)
        users, items = pairs[:, 0], pairs[:, 1]
        degree = torch.bincount(users, minlength=self.n_users).float().clamp_min(1)
        self.user_item_adj = torch.sparse_coo_tensor(
            torch.stack([users, items]), degree[users].reciprocal(),
            (self.n_users, self.n_items), check_invariants=True,
        ).coalesce()

    def embeddings(self):
        if self.adj is None:
            raise RuntimeError("Build the fit graph before inference")
        if self.layers == 0:
            users, items = self.user_embedding.weight, self.item_embedding.weight
        else:
            current = torch.cat([self.user_embedding.weight, self.item_embedding.weight])
            result = current
            for _ in range(self.layers):
                current = torch.sparse.mm(self.adj, current)
                result = result + current
            users, items = (result / (self.layers + 1)).split([self.n_users, self.n_items])
        if self.spatial:
            spatial = self.spatial_encoder((self.coords - self.coord_center) / self.coord_scale)
            if self.category_features:
                spatial = spatial + self.category_embedding(self.categories)
            users = users + torch.sparse.mm(self.user_item_adj, spatial)
            items = items + spatial
        return users, items

    def item_modulation(self, items):
        if self.category_features:
            return torch.sigmoid(self.time_category(self.categories[items]))
        return torch.sigmoid(self.time_item(items))
