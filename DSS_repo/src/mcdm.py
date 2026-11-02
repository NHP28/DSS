"""
MCDM Module: AHP (Analytic Hierarchy Process) & TOPSIS (Technique for Order Preference by Similarity to Ideal Solution)
Designed specifically for Location-Based Decision Support System (L-DSS) in POI Recommendation.

Key Features:
1. Exact Saaty AHP consistency check (RI = 1.12 for n = 5, CR <= 0.10).
2. Multi-criteria vector normalization with configurable Benefit/Cost criteria:
   - C1: Distance (Cost - minimize distance)
   - C2: Rating (Benefit - maximize quality)
   - C3: Price (Cost - minimize average expense)
   - C4: AI Preference Score (Benefit - maximize Spatio-Temporal GNN affinity)
   - C5: Popularity (Benefit - maximize general reputation)
3. Category-stratified TOPSIS: Evaluates candidates within each POI category
   to avoid unfair price penalization between disparate POI categories (e.g., Hotels vs. Cafes).
"""

import math
import numpy as np
from typing import List, Dict, Any, Optional, Tuple

EARTH_RADIUS_KM = 6371.0

# Saaty's Random Consistency Index (RI) table
RANDOM_INDEX_TABLE = {
    1: 0.00,
    2: 0.00,
    3: 0.58,
    4: 0.90,
    5: 1.12,
    6: 1.24,
    7: 1.32,
    8: 1.41,
    9: 1.45,
    10: 1.49
}

def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculates great-circle distance between two GPS coordinates in kilometers."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi / 2.0) ** 2 + \
        math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(max(0.0, 1.0 - a)))
    return EARTH_RADIUS_KM * c


class AHPDecisionMaker:
    """
    Analytic Hierarchy Process (Saaty, 1980) for Criteria Weight Determination.
    Criteria: [Distance (C1), Rating (C2), Price (C3), AI Preference (C4), Popularity (C5)]
    """
    CRITERIA_KEYS = ["distance", "rating", "price", "preference", "popularity"]
    CRITERIA_LABELS = [
        "C1: Khoảng cách (Distance)",
        "C2: Đánh giá (Rating)",
        "C3: Chi phí (Price)",
        "C4: Sở thích AI (GNN Preference)",
        "C5: Độ phổ biến (Popularity)"
    ]

    # Pre-calculated consistent pairwise comparison matrices (CR < 0.10)
    PRESETS = {
        # Balanced: Even distribution prioritizing AI and location
        "balanced": np.array([
            [1.0, 1.0, 1.5, 0.67, 1.5],   # C1: Distance
            [1.0, 1.0, 1.5, 0.67, 1.5],   # C2: Rating
            [0.67, 0.67, 1.0, 0.5, 1.0],  # C3: Price
            [1.5, 1.5, 2.0, 1.0, 2.0],    # C4: AI Preference
            [0.67, 0.67, 1.0, 0.5, 1.0]   # C5: Popularity
        ], dtype=float),

        # AI-Centric: Heavy emphasis on personalized temporal GNN predictions
        "ai_centric": np.array([
            [1.0, 1.0, 2.0, 0.33, 1.5],
            [1.0, 1.0, 2.0, 0.33, 1.5],
            [0.5, 0.5, 1.0, 0.25, 0.67],
            [3.0, 3.0, 4.0, 1.0, 3.0],
            [0.67, 0.67, 1.5, 0.33, 1.0]
        ], dtype=float),

        # Proximity: User wants nearest spots (walking or quick transit)
        "proximity": np.array([
            [1.0, 3.0, 3.0, 2.0, 4.0],
            [0.33, 1.0, 1.0, 0.5, 1.5],
            [0.33, 1.0, 1.0, 0.5, 1.5],
            [0.5, 2.0, 2.0, 1.0, 2.0],
            [0.25, 0.67, 0.67, 0.5, 1.0]
        ], dtype=float),

        # Budget: User seeks affordable meals and places
        "budget": np.array([
            [1.0, 1.0, 0.33, 0.67, 1.5],
            [1.0, 1.0, 0.33, 0.67, 1.5],
            [3.0, 3.0, 1.0, 2.0, 4.0],
            [1.5, 1.5, 0.5, 1.0, 2.0],
            [0.67, 0.67, 0.25, 0.5, 1.0]
        ], dtype=float)
    }

    @classmethod
    def calculate_weights(cls, matrix: Optional[np.ndarray] = None, preset: str = "balanced") -> Dict[str, Any]:
        """
        Calculates priority vector (weights) and checks Consistency Ratio (CR).
        """
        if matrix is None:
            matrix = cls.PRESETS.get(preset, cls.PRESETS["balanced"]).copy()

        matrix = np.array(matrix, dtype=float)
        n = matrix.shape[0]
        if n != 5 or matrix.shape[1] != 5:
            raise ValueError(f"Ma trận AHP phải có kích thước 5x5, nhận: {matrix.shape}")

        # 1. Sum of each column
        col_sums = matrix.sum(axis=0)
        # Avoid division by zero
        col_sums[col_sums == 0] = 1e-9

        # 2. Normalized matrix
        norm_matrix = matrix / col_sums

        # 3. Principal priority vector (Row average)
        weights = norm_matrix.mean(axis=1)

        # 4. Lambda Max calculation
        # Ax = lambda * x -> compute lambda_max = sum(col_sums * weights)
        lambda_max = float(np.sum(col_sums * weights))

        # 5. Consistency Index & Consistency Ratio
        ci = (lambda_max - n) / (n - 1) if n > 1 else 0.0
        ri = RANDOM_INDEX_TABLE.get(n, 1.12)
        cr = float(ci / ri) if ri > 0 else 0.0

        is_consistent = cr <= 0.10

        weights_dict = {cls.CRITERIA_KEYS[i]: float(round(weights[i], 4)) for i in range(n)}

        return {
            "weights": weights_dict,
            "weights_array": weights.tolist(),
            "lambda_max": round(lambda_max, 4),
            "consistency_index": round(ci, 4),
            "consistency_ratio": round(cr, 4),
            "is_consistent": is_consistent,
            "criteria_labels": cls.CRITERIA_LABELS
        }


class TOPSISDecisionMaker:
    """
    Technique for Order of Preference by Similarity to Ideal Solution (TOPSIS)
    Ranks POI candidates considering both positive ideal (A+) and negative ideal (A-) solutions.
    """
    # [C1: Distance (cost), C2: Rating (benefit), C3: Price (cost), C4: Preference (benefit), C5: Popularity (benefit)]
    IS_BENEFIT = [False, True, False, True, True]

    @classmethod
    def rank_candidates(
        cls,
        candidates: List[Dict[str, Any]],
        weights: List[float],
        stratify_by_category: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Ranks candidate POIs using TOPSIS.
        candidates: List of dicts with keys:
            ['poiId', 'name', 'category', 'district', 'latitude', 'longitude',
             'distance', 'rating', 'priceAvg', 'score', 'popularity', ...]
        weights: list of 5 floats summing to 1.0
        """
        if not candidates:
            return []

        weights = np.array(weights, dtype=float)
        if len(weights) != 5:
            raise ValueError(f"Vector trọng số TOPSIS phải có đúng 5 phần tử, nhận: {len(weights)}")

        # Normalize weights so they sum to 1.0
        w_sum = weights.sum()
        if w_sum > 0:
            weights = weights / w_sum

        if stratify_by_category:
            # Group by category, rank separately, then interleave/merge by TOPSIS closeness
            grouped: Dict[str, List[Dict[str, Any]]] = {}
            for item in candidates:
                cat = item.get("category", "other")
                grouped.setdefault(cat, []).append(item)

            all_ranked = []
            for cat, cat_items in grouped.items():
                cat_ranked = cls._evaluate_group(cat_items, weights)
                all_ranked.extend(cat_ranked)

            # Sort globally by TOPSIS closeness score descending
            all_ranked.sort(key=lambda x: x["topsis_score"], reverse=True)
            for idx, item in enumerate(all_ranked, 1):
                item["final_rank"] = idx
            return all_ranked
        else:
            return cls._evaluate_group(candidates, weights)

    @classmethod
    def _evaluate_group(cls, items: List[Dict[str, Any]], weights: np.ndarray) -> List[Dict[str, Any]]:
        m = len(items)
        if m == 0:
            return []
        if m == 1:
            item_copy = dict(items[0])
            item_copy["topsis_score"] = 1.0
            item_copy["final_rank"] = 1
            item_copy["dist_ideal_pos"] = 0.0
            item_copy["dist_ideal_neg"] = 1.0
            return [item_copy]

        # Decision Matrix X: shape (m, 5)
        # Columns: [distance, rating, price, preference_score, popularity]
        X = np.zeros((m, 5), dtype=float)
        for i, item in enumerate(items):
            X[i, 0] = max(0.01, float(item.get("distance", 1.0)))    # Distance in km (avoid 0)
            X[i, 1] = float(item.get("rating", 4.0))                 # Rating (1.0 - 5.0)
            X[i, 2] = max(1.0, float(item.get("priceAvg", 50000.0))) # Price (VNĐ)
            X[i, 3] = float(item.get("score", 0.5))                  # AI GNN preference (0.0 - 1.0)
            X[i, 4] = float(item.get("popularity", 50))              # Popularity (0 - 100)

        # 1. Vector Normalization
        # r_ij = x_ij / sqrt(sum_k x_kj^2)
        norm_denom = np.sqrt(np.sum(X ** 2, axis=0))
        norm_denom[norm_denom == 0] = 1e-9
        R = X / norm_denom

        # 2. Weighted Normalized Matrix V
        V = R * weights

        # 3. Determine Ideal Positive (A+) and Ideal Negative (A-)
        A_pos = np.zeros(5, dtype=float)
        A_neg = np.zeros(5, dtype=float)

        for j in range(5):
            if cls.IS_BENEFIT[j]:
                A_pos[j] = np.max(V[:, j])
                A_neg[j] = np.min(V[:, j])
            else: # Cost
                A_pos[j] = np.min(V[:, j])
                A_neg[j] = np.max(V[:, j])

        # 4. Euclidean distances to A+ and A-
        # S+ = sqrt(sum_j (v_ij - A+_j)^2)
        # S- = sqrt(sum_j (v_ij - A-_j)^2)
        S_pos = np.sqrt(np.sum((V - A_pos) ** 2, axis=1))
        S_neg = np.sqrt(np.sum((V - A_neg) ** 2, axis=1))

        # 5. Closeness Coefficient C_i = S- / (S+ + S-)
        denom = S_pos + S_neg
        denom[denom == 0] = 1e-9
        C = S_neg / denom

        results = []
        for i, item in enumerate(items):
            item_out = dict(item)
            item_out["topsis_score"] = float(round(C[i], 4))
            item_out["dist_ideal_pos"] = float(round(S_pos[i], 4))
            item_out["dist_ideal_neg"] = float(round(S_neg[i], 4))
            item_out["criteria_breakdown"] = {
                "distance_km": float(round(X[i, 0], 2)),
                "rating": float(round(X[i, 1], 2)),
                "price_vnd": float(X[i, 2]),
                "ai_preference": float(round(X[i, 3], 4)),
                "popularity": int(X[i, 4])
            }
            results.append(item_out)

        # Sort descending by C_i
        results.sort(key=lambda x: x["topsis_score"], reverse=True)
        for rank, res in enumerate(results, 1):
            res["final_rank"] = rank

        return results
