import math
import sys
import unittest
from pathlib import Path

import numpy as np
import scipy.sparse as sp

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from baselines.bpr_mf import BPRMF  # noqa: E402
from baselines.item_knn import ItemKNN  # noqa: E402
from benchmark_ml import rank_metrics, target_ranks  # noqa: E402


class MetricTests(unittest.TestCase):
    def test_rank_metrics_by_hand(self):
        metrics = rank_metrics(np.array([1, 3, np.inf, 11]))
        self.assertAlmostEqual(metrics["HR@10"], 0.5)
        self.assertAlmostEqual(metrics["MRR@10"], (1 + 1 / 3) / 4)
        self.assertAlmostEqual(metrics["NDCG@10"], (1 + 1 / math.log2(4)) / 4)
        self.assertAlmostEqual(metrics["HR@20"], 0.75)
        self.assertAlmostEqual(metrics["HR@5"], 0.5)

    def test_target_ranks_mask_seen_and_break_ties_by_index(self):
        scores = np.array([[5., 9., 7., 7.], [1., 1., 1., 1.]])
        seen = np.array([[False, True, False, False], [False, False, False, False]])
        # Row 0: item 1 is masked, so item 2 leads and item 3 (tied, higher index) is second.
        self.assertEqual(list(target_ranks(scores, np.array([3, 2]), seen)), [2, 3])
        self.assertEqual(list(target_ranks(scores, np.array([0, 0]), seen)), [3, 1])


class BaselineTests(unittest.TestCase):
    def test_item_knn_tiny(self):
        # Items 0 and 1 are co-visited by users 0 and 1; item 2 only by user 2.
        C = sp.csr_matrix(np.array([[1, 1, 0], [1, 1, 0], [0, 0, 1]], dtype=np.float32))
        probe = sp.csr_matrix(np.array([[1, 0, 0]], dtype=np.float32))
        model = ItemKNN(k=2).fit(C)
        model.B = probe
        scores = model.predict([0])[0]
        self.assertGreater(scores[1], scores[2])

    def test_bpr_mf_learns(self):
        rng = np.random.default_rng(0)
        pairs = np.array([(u, i) for u in range(20) for i in rng.choice(range(10) if u < 10 else range(10, 20), 6, replace=False)])
        model = BPRMF(dim=8, epochs=30, lr=0.05, batch_size=32, seed=0).fit(pairs, 20, 20)
        scores = model.predict(np.arange(20))
        own = np.mean([scores[u, :10].mean() if u < 10 else scores[u, 10:].mean() for u in range(20)])
        other = np.mean([scores[u, 10:].mean() if u < 10 else scores[u, :10].mean() for u in range(20)])
        self.assertGreater(own, other)


if __name__ == "__main__":
    unittest.main()
