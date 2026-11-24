"""Serving the two checkpoints that ship in outputs/checkpoints."""
import sys
import unittest
from pathlib import Path

import numpy as np
import torch
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ml.repo_models import load_repo_models  # noqa: E402

TS = 1_700_000_000.0


class RepoModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(2)
        cls.models = load_repo_models(ROOT)

    def test_loads_both_models(self):
        self.assertEqual(self.models.available, ["tas_gnn", "lightgcn"])
        self.assertEqual(len(self.models.poi_ids), 996)
        self.assertEqual(self.models.hourly_counts.shape, (24, 996))

    def test_scores_match_legacy_path(self):
        m = self.models
        with torch.no_grad():
            expected = m.tas.predict_for_user_at_time(12, TS, 8, 0, users_emb=m.tas_users, items_emb=m.tas_items).numpy()
            expected_light = m.light.predict_for_user(12, m.light_users, m.light_items).numpy()
        self.assertTrue(np.allclose(m.score("tas_gnn", 12, 8, 0, TS), expected, atol=1e-5))
        self.assertTrue(np.allclose(m.score("lightgcn", 12, 8, 0, TS), expected_light, atol=1e-5))

    def test_use_time_false_ignores_hour(self):
        m = self.models
        morning = m.score("tas_gnn", 12, 8, 0, TS, use_time=False)
        evening = m.score("tas_gnn", 12, 20, 5, TS, use_time=False)
        self.assertTrue(np.array_equal(morning, evening))
        self.assertFalse(np.allclose(morning, m.score("tas_gnn", 12, 8, 0, TS)))

    def test_time_changes_ranking(self):
        m = self.models
        self.assertFalse(np.allclose(m.score("tas_gnn", 12, 8, 0, TS), m.score("tas_gnn", 12, 20, 5, TS)))

    def test_foldin(self):
        m = self.models
        scores = m.score("tas_gnn", None, 8, 0, TS, history=[1, 2, 3])
        self.assertEqual(scores.shape, (996,))
        self.assertTrue(np.isfinite(scores).all())
        self.assertLess(spearmanr(scores, m.hourly_counts[8]).statistic, 0.99)
        other = m.score("tas_gnn", None, 8, 0, TS, history=[500, 600, 700])
        self.assertFalse(np.allclose(scores, other))
        self.assertEqual(m.score("lightgcn", None, 8, 0, TS, history=[1, 2, 3]).shape, (996,))

    def test_foldin_needs_three(self):
        with self.assertRaises(ValueError):
            self.models.score("tas_gnn", None, 8, 0, TS, history=[1, 2])

    def test_unknown_history_poi_rejected(self):
        with self.assertRaises(ValueError):
            self.models.score("tas_gnn", None, 8, 0, TS, history=[1, 2, 99999])


class HttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from fastapi.testclient import TestClient
        from ml.serve import app
        cls.context = TestClient(app)
        cls.client = cls.context.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.context.__exit__(None, None, None)

    def post(self, **body):
        response = self.client.post("/score", json=body)
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(len(data["scores"]), 996)
        self.assertTrue(all(0 <= item["score"] <= 1 for item in data["scores"]))
        return data

    def test_health_lists_models(self):
        data = self.client.get("/health").json()
        self.assertTrue(data["ready"])
        self.assertEqual(data["models"], ["tas_gnn", "lightgcn"])
        self.assertEqual(data["origin"], "repo_checkpoint")
        self.assertEqual(data["info"]["embeddingDim"], 64)

    def test_http_score_models(self):
        self.assertEqual(self.post(userId=12, hour=8, dayOfWeek=0)["source"], "tas_gnn")
        self.assertEqual(self.post(userId=12, hour=8, dayOfWeek=0, model="lightgcn")["source"], "lightgcn")
        self.assertEqual(self.post(hour=8, dayOfWeek=0, historyPoiIds=[1, 2, 3])["source"], "tas_gnn_foldin")
        self.assertEqual(self.post(hour=8, dayOfWeek=0, model="lightgcn", historyPoiIds=[1, 2, 3])["source"], "lightgcn_foldin")
        self.assertEqual(self.post(hour=8, dayOfWeek=0)["source"], "hourly_popularity")
        self.assertEqual(self.post(hour=8, dayOfWeek=0, historyPoiIds=[1, 2])["source"], "hourly_popularity")
        self.assertEqual(self.post(userId=12, hour=8, dayOfWeek=0, model="popularity")["source"], "popularity")
        self.assertEqual(self.post(userId=999999, hour=8, dayOfWeek=0)["source"], "hourly_popularity")

    def test_http_rejects_unknown_model(self):
        self.assertEqual(self.client.post("/score", json={"hour": 8, "dayOfWeek": 0, "model": "xgboost"}).status_code, 422)


if __name__ == "__main__":
    unittest.main()
