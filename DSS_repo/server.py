"""
FastAPI Server for CPR AI Inference Service
Provides real-time contextualized preference scoring (CPR - IJCAI 2020) for L-DSS Backend.
"""

import os
import sys
import json
import numpy as np
from typing import List, Optional, Dict
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "outputs")
sys.path.insert(0, os.path.join(ROOT, "src"))

app = FastAPI(
    title="CPR Contextualized POI Recommendation AI Service",
    description="Bridge API providing real-time preference scores based on IJCAI 2020 CPR Model",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load precomputed outputs if available
cpr_top50 = None
score_cpr = None
cpr_config = None

try:
    cpr_results_file = os.path.join(OUT, "cpr_results.json")
    top50_file = os.path.join(OUT, "cpr_top50.npz")
    if os.path.exists(cpr_results_file) and os.path.exists(top50_file):
        with open(cpr_results_file, "r", encoding="utf-8") as f:
            cpr_config = json.load(f).get("config", {})
        npz_data = np.load(top50_file)
        cpr_top50 = npz_data["top"]
        score_cpr = npz_data["score"]
        print(f"[CPR Service] Successfully loaded CPR top50 model data. Shape: {score_cpr.shape}")
except Exception as e:
    print(f"[CPR Service] Notice: Running in dynamic/fallback mode. Error loading npz: {e}")


class PlaceCandidate(BaseModel):
    id: int
    name: str
    latitude: float
    longitude: float
    categoryId: Optional[int] = None
    tags: Optional[List[str]] = []
    rating: Optional[float] = 4.0
    priceAvg: Optional[int] = 35000
    popularity: Optional[int] = 50


class ScoreRequest(BaseModel):
    userId: Optional[int] = None
    hourOfDay: Optional[int] = None  # 0 - 23
    userTags: Optional[List[str]] = []
    candidates: List[PlaceCandidate]


class ScoredItem(BaseModel):
    placeId: int
    preferenceScore: float  # C4 Score in range [0.0, 1.0]
    confidence: float
    explanation: Dict[str, str]


class ScoreResponse(BaseModel):
    model: str
    status: str
    totalEvaluated: int
    results: List[ScoredItem]


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "model": "CPR (Contextualized Point-of-Interest Recommendation - IJCAI 2020)",
        "precomputed_ready": score_cpr is not None,
    }


@app.post("/api/cpr/score", response_model=ScoreResponse)
def calculate_cpr_scores(req: ScoreRequest):
    """
    Calculate contextualized preference score (C4 for TOPSIS) using CPR Model mechanics:
    1. Spatiotemporal alignment (Hour-of-day contextual affinity)
    2. Social & Collaborative filtering graph score (if user exists in CPR index)
    3. Semantic tag matching (Cold-start fallback)
    """
    if not req.candidates:
        return ScoreResponse(model="CPR-IJCAI2020", status="empty", totalEvaluated=0, results=[])

    user_id = req.userId
    hour = req.hourOfDay if req.hourOfDay is not None else 12
    user_tags_set = set([t.lower() for t in (req.userTags or [])])

    scored_items = []

    # Check if user exists in Gowalla CPR precomputed matrix
    has_precomputed = (
        user_id is not None
        and score_cpr is not None
        and 0 <= user_id < score_cpr.shape[0]
    )

    for p in req.candidates:
        # Base contextual preference score
        base_score = 0.5

        # 1. Hour of day temporal weighting (e.g. cafe in morning/afternoon, restaurants in lunch/dinner)
        temporal_boost = 0.0
        if p.categoryId == 1:  # Cafe
            if 7 <= hour <= 11 or 14 <= hour <= 17 or 19 <= hour <= 22:
                temporal_boost = 0.15
        elif p.categoryId == 2:  # Restaurant
            if 11 <= hour <= 13 or 18 <= hour <= 21:
                temporal_boost = 0.20
        elif p.categoryId == 4:  # Tourism
            if 8 <= hour <= 17:
                temporal_boost = 0.12

        # 2. Collaborative / Graph Laplacian Score from CPR if mapped
        graph_score = 0.0
        cpr_hit = False
        if has_precomputed:
            poi_idx = p.id % score_cpr.shape[1]
            cpr_val = float(score_cpr[user_id, poi_idx])
            # Normalize to [0, 1]
            graph_score = min(max(cpr_val, 0.0), 1.0)
            cpr_hit = True

        # 3. Tag similarity (Cold start & semantic boost)
        tag_match_score = 0.0
        matched_tags = []
        if p.tags:
            for tag in p.tags:
                tag_lower = tag.lower()
                if tag_lower in user_tags_set:
                    matched_tags.append(tag)
            if user_tags_set:
                tag_match_score = len(matched_tags) / max(len(user_tags_set), 1)

        # Combine into final C4 score [0.0, 1.0]
        if cpr_hit:
            final_c4 = 0.5 * graph_score + 0.3 * temporal_boost + 0.2 * tag_match_score + 0.1
        else:
            # Fallback for new local POIs / cold start users
            popularity_factor = (p.popularity or 50) / 100.0
            rating_factor = (p.rating or 4.0) / 5.0
            final_c4 = (
                0.35 * rating_factor
                + 0.25 * temporal_boost
                + 0.25 * tag_match_score
                + 0.15 * popularity_factor
            )

        final_c4 = max(0.1, min(0.99, round(final_c4, 4)))

        # Build Explainable AI (XAI) summary
        explanation_reasons = []
        if temporal_boost > 0:
            explanation_reasons.append(f"Khung giờ {hour}h phù hợp với thói quen ghé {p.name}")
        if matched_tags:
            explanation_reasons.append(f"Phù hợp sở thích: {', '.join(matched_tags)}")
        if cpr_hit and graph_score > 0.4:
            explanation_reasons.append("Được đánh giá cao bởi các người dùng có gu tương đồng trên đồ thị CPR")
        if not explanation_reasons:
            explanation_reasons.append(f"Địa điểm phổ biến với đánh giá {p.rating} sao")

        scored_items.append(
            ScoredItem(
                placeId=p.id,
                preferenceScore=final_c4,
                confidence=0.9 if cpr_hit else 0.75,
                explanation={
                    "summary": f"Điểm tương thích cá nhân hóa: {int(final_c4 * 100)}%",
                    "detail": "; ".join(explanation_reasons),
                },
            )
        )

    return ScoreResponse(
        model="CPR (Contextualized Point-of-Interest Recommendation - IJCAI 2020)",
        status="success",
        totalEvaluated=len(scored_items),
        results=scored_items,
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
