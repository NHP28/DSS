"""Regression checks for the changed Colab spatial-history inference semantics."""
import tempfile
import unittest
from pathlib import Path

import numpy as np
import torch

from ml.colab_model import HistorySpatialPOIGraph
from ml.poi_model import restore_bundle, seed_everything


class ColabServingTests(unittest.TestCase):
    def setUp(self):
        seed_everything(42)
        torch.set_num_threads(2)
        self.coords = np.array([[16., 108.], [16.1, 108.1], [16.2, 108.2]], np.float32)
        self.pairs = torch.tensor([[0, 0], [0, 1], [1, 2]])
        self.model = HistorySpatialPOIGraph(2, self.coords, [0, 1, 2], dim=8, layers=1)
        self.model.build_graph(self.pairs)

    def test_spatial_history_contributes_mean_of_distinct_visited_pois(self):
        model = self.model
        initial = torch.cat([model.user_embedding.weight, model.item_embedding.weight])
        graph_users, graph_items = ((initial + torch.sparse.mm(model.adj, initial)) / 2).split([2, 3])
        spatial = model.spatial_encoder((model.coords - model.coord_center) / model.coord_scale)
        spatial = spatial + model.category_embedding(model.categories)
        users, items = model.embeddings()
        expected_history = torch.stack([spatial[:2].mean(0), spatial[2]])
        self.assertTrue(torch.allclose(users, graph_users + expected_history))
        self.assertTrue(torch.allclose(items, graph_items + spatial))
        model.build_graph(torch.cat([self.pairs, self.pairs[:1]]))
        self.assertTrue(torch.allclose(model.embeddings()[0], users))

    def test_versioned_checkpoint_preserves_scores_and_rejects_unknown_architecture(self):
        bundle = {"format_version": 1, "model_architecture": "spatial_history_v2",
                  "model_config": {"n_users": 2, "dim": 8, "layers": 1, "temporal": True, "spatial": True},
                  "state_dict": self.model.state_dict(), "fit_pairs": self.pairs}
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "model.pt"
            torch.save(bundle, path)
            restored, _ = restore_bundle(path)
            self.assertIsInstance(restored, HistorySpatialPOIGraph)
            self.assertTrue(torch.allclose(self.model.scores(0, 8, 1, 0), restored.scores(0, 8, 1, 0)))
            bundle["model_architecture"] = "unknown"
            torch.save(bundle, path)
            with self.assertRaisesRegex(ValueError, "architecture"):
                restore_bundle(path)

    def test_categoryless_export_restores_dedicated_temporal_item_weights(self):
        model = HistorySpatialPOIGraph(2, self.coords, [0, 0, 0], dim=8, layers=1, category_features=False)
        model.build_graph(self.pairs)
        model.scores(0, 8, 1, 0).sum().backward()
        self.assertGreater(model.time_item.weight.grad.abs().sum().item(), 0)


if __name__ == "__main__":
    unittest.main()
