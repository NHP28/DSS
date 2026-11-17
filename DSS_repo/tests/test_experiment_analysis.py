import json
import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd
import torch

from ml.experiment_analysis import (evaluate_detailed, model_predictions, paired_user_bootstrap,
                                     quality_profile, rank_of_target, study_split)
from ml.poi_model import POIGraph


class ExperimentAnalysisTests(unittest.TestCase):
    def test_service_falls_back_for_user_id_present_but_never_fitted(self):
        from ml.serve import ScoreRequest, app, lifespan, score, state
        config = dict(n_users=2, dim=4, layers=0, temporal=False, spatial=False, category_features=False)
        model = POIGraph(coords=[[16, 108], [16.1, 108.1]], categories=[0, 1], **config)
        bundle = {"format_version": 1, "model_config": config, "state_dict": model.state_dict(),
                  "fit_pairs": torch.tensor([[0, 0]]), "user_ids": [10, 20], "poi_ids": [100, 101],
                  "trained_user_ids": [10], "hourly_counts": torch.ones(24, 2),
                  "model_name": "test_model", "dataset_sha256": "test"}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "model.pt"
            torch.save(bundle, path)
            async def verify():
                async with lifespan(app):
                    self.assertEqual(state["users"], {10: 0})
                    self.assertEqual(score(ScoreRequest(userId=20))["source"], "hourly_popularity")
                    self.assertEqual(score(ScoreRequest(userId=10))["source"], "test_model")
            with patch.dict("os.environ", {"MODEL_PATH": str(path)}):
                asyncio.run(verify())

    def test_partial_prediction_generator_does_not_disable_future_training(self):
        model = POIGraph(1, [[16, 108], [16.1, 108.1]], [0, 1], dim=4, layers=0,
                         temporal=False, spatial=False, category_features=False)
        model.build_graph([[0, 0]])
        frame = pd.DataFrame({"user": [0, 0], "hour": [8, 9], "day_of_week": [0, 0], "ts": [1., 2.]})
        iterator = model_predictions(model, frame, 2)
        next(iterator)
        self.assertTrue(torch.is_grad_enabled())
        self.assertFalse(torch.is_inference_mode_enabled())
        loss = model.loss(torch.tensor([0]), torch.tensor([0]), torch.tensor([1]),
                          torch.tensor([8]), torch.tensor([0]), torch.tensor([1.]))
        loss.backward()
        self.assertIsNotNone(model.user_embedding.weight.grad)

    def test_global_windows_exclude_cold_users_and_have_no_future_fit_edges(self):
        events = pd.DataFrame({"user": [0] * 20 + [1, 1], "ts": list(range(1, 21)) + [19, 20]})
        train, validation, test, fit, metadata = study_split(events)
        self.assertLess(train.ts.max(), validation.ts.min())
        self.assertLess(fit.ts.max(), test.ts.min())
        self.assertEqual(metadata["test_cold_user_events_excluded"], 2)
        self.assertEqual(set(test.user), {0})
        # Tied timestamps across users remain in a single time window.
        raw = events.copy()
        raw.loc[raw.index[-1], "ts"] = train.ts.max()
        train2, _, _, _, _ = study_split(raw)
        self.assertEqual(len(train2[train2.ts == train2.ts.max()]), 2)

    def test_exact_rank_handles_ties_and_nonfinite_scores(self):
        self.assertEqual(rank_of_target(np.array([5., 5., 4., 6.]), 1), 3)
        self.assertEqual(rank_of_target(np.array([np.nan, 5., 4., np.inf]), 1), 1)
        self.assertTrue(np.isinf(rank_of_target(np.array([np.nan, 5.]), 0)))

    def test_all_and_novel_metrics_keep_separate_candidate_sets(self):
        held = pd.DataFrame({"user": [0, 0], "item": [0, 1], "ts": [1, 2],
                             "hour": [8, 8], "day_of_week": [0, 0]})
        novel, all_events, records = evaluate_detailed(lambda row: [100, 5, 4], held, {0: {0}}, 3)
        self.assertEqual(novel["events"], 1)
        self.assertEqual(novel["excluded_seen_events"], 1)
        self.assertEqual(all_events["events"], 2)
        self.assertEqual(records.iloc[1].rank_all, 2)
        self.assertEqual(records.iloc[1].rank_novel, 1)
        self.assertAlmostEqual(novel["sample_catalog_coverage_at_10"], 2 / 3)

    def test_paired_bootstrap_preserves_user_pairing_and_known_difference(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            for model, rank in (("tas_gnn", 1), ("baseline", 100)):
                pd.DataFrame({"user": [0, 1, 2], "novel": [True] * 3,
                              "rank_novel": [rank] * 3}).to_csv(path / f"{model}_events.csv", index=False)
            report = {"seed": 42, "results": {"tas_gnn": {}, "baseline": {}}}
            result = paired_user_bootstrap([(path, report)], samples=100)
            self.assertEqual(result.iloc[0].macro_user_HR10_difference, 1.)
            self.assertEqual(result.iloc[0].ci95_low, 1.)
            self.assertEqual(result.iloc[0].ci95_high, 1.)

    def test_quality_profile_exposes_categories_without_interactions(self):
        pois = pd.DataFrame({"l": [0, 1], "category": ["cafe", "hotel"],
                             "lat": [16., 16.1], "lon": [108., 108.1]})
        ts = int(pd.Timestamp("2023-01-02T01:00:00Z").timestamp())
        events = pd.DataFrame({"u": [0, 0], "l": [0, 0], "user": [0, 0], "item": [0, 0],
                               "ts": [ts, ts + 60], "hour": [8, 8], "day_of_week": [0, 0]})
        result = quality_profile(pois, events, {"dataset_id": "danang", "has_categories": True,
            "timezone": "Asia/Ho_Chi_Minh", "data_provenance": "synthetic"})
        self.assertEqual(result["category_coverage"]["hotel"]["events"], 0)
        self.assertEqual(result["unreferenced_pois"], 1)
        self.assertEqual(result["hour_mismatches"], 0)
        self.assertTrue(any("hotel" in warning for warning in result["warnings"]))
        json.dumps(result, allow_nan=False)


if __name__ == "__main__":
    unittest.main()
