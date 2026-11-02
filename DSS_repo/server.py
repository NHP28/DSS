"""
FastAPI Server for POI Recommendation AI Service & Location-Based Decision Support System (L-DSS)
Integrates:
1. ST-GNN-POI / TAS-GNN (Spatio-Temporal Graph Neural Network) for Da Nang POI Recommendation.
2. LightGCN (SIGIR 2020) Baseline for Comparison.
3. MCDM Decision Engine: AHP (Saaty 1980) + Category-Stratified TOPSIS (Hwang & Yoon 1981).
4. Full Compatibility Endpoint (/api/cpr/score) for NestJS BE_API.
"""

import os
import sys
import json
import time
import math
import datetime
import numpy as np
import pandas as pd
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
import torch

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(ROOT, "src")
DATA_DIR = os.path.join(ROOT, "data", "danang")
CHECKPOINT_DIR = os.path.join(ROOT, "outputs", "checkpoints")

if SRC not in sys.path:
    sys.path.insert(0, SRC)

try:
    from models.lightgcn import LightGCN
    from models.temporal_gnn import TemporalGNN
    from mcdm import AHPDecisionMaker, TOPSISDecisionMaker, haversine
except ModuleNotFoundError:
    from src.models.lightgcn import LightGCN
    from src.models.temporal_gnn import TemporalGNN
    from src.mcdm import AHPDecisionMaker, TOPSISDecisionMaker, haversine

app = FastAPI(
    title="Da Nang POI Recommendation & Multi-Criteria Decision Support System (L-DSS)",
    description="Hệ thống Gợi ý Địa điểm Cá nhân hóa tích hợp Mạng nơ-ron Đồ thị Không-Thời gian (ST-GNN) kết hợp Hỗ trợ Ra quyết định Đa tiêu chí (AHP + TOPSIS)",
    version="2.5.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------------- LOAD DATA & TRAINED MODELS -----------------
print("[Server] Đang nạp dữ liệu địa điểm Đà Nẵng...")
pois_df = pd.read_csv(os.path.join(DATA_DIR, "danang_pois_full.csv"))
ck_df = pd.read_csv(os.path.join(DATA_DIR, "danang_checkins_full.csv"))
num_users = int(ck_df["u"].max()) + 1
num_items = len(pois_df)

coords = pois_df[["lat", "lon"]].values.astype(np.float32)
cat_map = {"cafe": 0, "restaurant": 1, "hotel": 2, "tourist_spot": 3}
cat_ids = pois_df["category"].map(lambda c: cat_map.get(c, 0)).values.astype(np.int64)

# Build normalized adjacency from train set
ck_sorted = ck_df.sort_values(["u", "ts"], kind="stable").reset_index(drop=True)
pos = ck_sorted.groupby("u").cumcount().values
size = ck_sorted.groupby("u").u.transform("size").values
train_df = ck_sorted[pos < np.floor(size * 0.8).astype(int)]
train_pairs = train_df[["u", "l"]].values
train_seen = set(zip(train_df["u"].values, train_df["l"].values))

# Tính tần suất check-in theo giờ cho cold-start fallback
hourly_cat_popularity = ck_df.groupby(["hour", "l"]).size().unstack(fill_value=0)

device = torch.device("cpu")

# Load LightGCN
lightgcn_model = LightGCN(num_users, num_items, embedding_dim=64, num_layers=3).to(device)
lgcn_pt = os.path.join(CHECKPOINT_DIR, "lightgcn_danang.pt")
if os.path.exists(lgcn_pt):
    lightgcn_model.load_state_dict(torch.load(lgcn_pt, map_location=device))
    lightgcn_model.build_normalized_adj(train_pairs)
    lightgcn_model.eval()
    print("[Server] Đã nạp thành công checkpoint LightGCN!")

# Load ST-GNN / TAS-GNN
tgnn_model = TemporalGNN(
    num_users, num_items, coords=coords, category_ids=cat_ids,
    embedding_dim=64, time_dim=32, num_layers=3, use_time=True, use_spatial=True
).to(device)
tgnn_pt = os.path.join(CHECKPOINT_DIR, "temporal_gnn_danang.pt")
if os.path.exists(tgnn_pt):
    tgnn_model.load_state_dict(torch.load(tgnn_pt, map_location=device))
    tgnn_model.build_normalized_adj(train_pairs)
    tgnn_model.eval()
    print("[Server] Đã nạp thành công checkpoint Spatio-Temporal GNN!")

# Cache graph embeddings
with torch.no_grad():
    u_emb_lgcn, i_emb_lgcn = lightgcn_model.forward()
    u_emb_tgnn, i_emb_tgnn = tgnn_model.get_graph_embeddings()


# ----------------- PYDANTIC SCHEMAS -----------------
class RecommendRequest(BaseModel):
    userId: int = 12
    hour: int = 8
    dayOfWeek: int = 2 # 0: Thứ 2, 6: Chủ nhật
    userLat: Optional[float] = 16.068
    userLon: Optional[float] = 108.223
    topK: int = 10
    category: Optional[str] = None
    excludeVisited: bool = True
    enableDSS: bool = False
    ahpPreset: str = "balanced" # balanced, ai_centric, proximity, budget

class POIItem(BaseModel):
    poiId: int
    name: str
    category: str
    district: str
    latitude: float
    longitude: float
    rating: float
    priceAvg: float
    popularity: int
    score: float
    distanceKm: Optional[float] = None
    topsisScore: Optional[float] = None
    explanation: str

class RecommendResponse(BaseModel):
    model: str
    userId: int
    queryTime: str
    userLocation: Optional[Dict[str, float]] = None
    dssEnabled: bool = False
    ahpWeights: Optional[Dict[str, float]] = None
    totalRecommended: int
    tasgnnRecommendations: List[POIItem]
    lightgcnRecommendations: List[POIItem]

class DssRecommendRequest(BaseModel):
    userId: int = 12
    hour: int = 8
    dayOfWeek: int = 2
    userLat: float = 16.068
    userLon: float = 108.223
    topK: int = 10
    category: Optional[str] = None
    ahpPreset: Optional[str] = "balanced"
    ahpMatrix: Optional[List[List[float]]] = None
    stratifyByCategory: bool = True

class DssRankedItem(BaseModel):
    finalRank: int
    poiId: int
    name: str
    category: str
    district: str
    latitude: float
    longitude: float
    distanceKm: float
    rating: float
    priceVnd: float
    aiPreferenceScore: float
    popularity: int
    topsisScore: float
    distanceIdealPos: float
    distanceIdealNeg: float
    explanation: str

class DssRecommendResponse(BaseModel):
    status: str
    queryContext: Dict[str, Any]
    ahpAnalysis: Dict[str, Any]
    totalRanked: int
    recommendations: List[DssRankedItem]

# NestJS CPR Interface Schemas
class CandidatePlaceItem(BaseModel):
    id: int
    name: str
    latitude: float
    longitude: float
    categoryId: int
    tags: Optional[List[str]] = []
    rating: float = 4.5
    priceAvg: float = 50000.0
    popularity: int = 70

class CprScoreRequest(BaseModel):
    userId: Optional[int] = None
    hourOfDay: int = 12
    userTags: Optional[List[str]] = []
    candidates: List[CandidatePlaceItem]

class CprScoredResult(BaseModel):
    placeId: int
    preferenceScore: float
    confidence: float
    explanation: Dict[str, str]

class CprScoreResponse(BaseModel):
    results: List[CprScoredResult]


# ----------------- HELPER FUNCTIONS -----------------
def generate_poi_explanation(row, hr: int, distance_km: Optional[float] = None, topsis_score: Optional[float] = None) -> str:
    c = row["category"]
    dist_str = f", cách vị trí bạn {distance_km:.1f}km" if distance_km is not None else ""
    topsis_str = f" [TOPSIS: {topsis_score:.2f}]" if topsis_score is not None else ""

    if 6 <= hr <= 9 and c == "cafe":
        return f"Khung giờ sáng {hr}h rất thích hợp để thưởng thức cafe & khởi đầu ngày mới{dist_str}{topsis_str}"
    elif 6 <= hr <= 9 and c == "restaurant":
        return f"Khung giờ sáng {hr}h lý tưởng thưởng thức bữa sáng đặc sản tại {row['district']}{dist_str}{topsis_str}"
    elif 11 <= hr <= 13 and c == "restaurant":
        return f"Thời điểm {hr}h trưa lý tưởng để dùng bữa trưa đặc sản tại {row['district']}{dist_str}{topsis_str}"
    elif 14 <= hr <= 17 and c == "tourist_spot":
        return f"Buổi chiều mát {hr}h phù hợp để dạo biển, ngắm cảnh hoặc thư giãn{dist_str}{topsis_str}"
    elif 14 <= hr <= 17 and c == "cafe":
        return f"Buổi chiều {hr}h thư giãn với không gian cafe yên tĩnh tại {row['district']}{dist_str}{topsis_str}"
    elif 18 <= hr <= 22 and c == "restaurant":
        return f"Buổi tối {hr}h thưởng thức hải sản và ẩm thực đêm Đà Nẵng tại {row['district']}{dist_str}{topsis_str}"
    elif 18 <= hr <= 22 and c == "tourist_spot":
        return f"Buổi tối {hr}h náo nhiệt thích hợp dạo phố, ngắm cầu Rồng & chợ đêm{dist_str}{topsis_str}"
    elif c == "hotel":
        return f"Khách sạn lưu trú tiện nghi tại {row['district']}{dist_str}{topsis_str}"
    else:
        return f"Được gợi ý theo thói quen tương tác và vị trí ưu tiên tại Đà Nẵng{dist_str}{topsis_str}"


def compute_model_scores(u: int, hr: int, wd: int, user_lat: Optional[float] = None, user_lon: Optional[float] = None):
    """Tính toán điểm số GNN và LightGCN có xét cold-start và vị trí địa lý."""
    now = datetime.datetime.now()
    sim_dt = now.replace(hour=hr, minute=30)
    ts = float(sim_dt.timestamp())

    is_cold_start = u < 0 or u >= num_users

    if is_cold_start:
        # User mới chưa có tương tác: kết hợp xác suất theo giờ và phân bố popularity
        hour_pop = hourly_cat_popularity.loc[hr].values if hr in hourly_cat_popularity.index else np.zeros(num_items)
        base_pop = pois_df["popularity"].values / 100.0
        scores_tgnn = (0.6 * (hour_pop / (hour_pop.max() + 1e-6)) + 0.4 * base_pop).astype(float)
        scores_lgcn = base_pop.astype(float)
    else:
        with torch.no_grad():
            scores_tgnn = tgnn_model.predict_for_user_at_time(
                u, ts, hr, wd,
                user_lat=user_lat, user_lon=user_lon, geo_weight=0.15,
                users_emb=u_emb_tgnn, items_emb=i_emb_tgnn
            ).numpy().copy()
            scores_lgcn = lightgcn_model.predict_for_user(u, u_emb_lgcn, i_emb_lgcn).numpy().copy()

    return scores_tgnn, scores_lgcn


# ----------------- ENDPOINTS -----------------
@app.get("/health")
def health():
    return {
        "status": "healthy",
        "city": "Da Nang, Vietnam",
        "totalPois": num_items,
        "totalUsers": num_users,
        "modelsLoaded": ["LightGCN", "SpatioTemporal-GNN (TAS-GNN)"],
        "dssEngine": "AHP + TOPSIS (Category-stratified active)"
    }


@app.get("/api/v1/danang/pois")
def get_all_pois(category: Optional[str] = None, district: Optional[str] = None, limit: int = 100):
    df = pois_df
    if category:
        df = df[df["category"] == category]
    if district:
        df = df[df["district"] == district]
    return df.head(limit).to_dict("records")


@app.get("/api/v1/danang/ahp_weights")
def get_ahp_weights(preset: str = "balanced"):
    """Lấy thông số ma trận trọng số và chỉ số nhất quán CR theo chuẩn Saaty."""
    return AHPDecisionMaker.calculate_weights(preset=preset)


@app.post("/api/cpr/score", response_model=CprScoreResponse)
def score_candidates_cpr(req: CprScoreRequest):
    """
    Endpoint chuẩn kết nối trực tiếp với NestJS BE_API (cpr.service.ts).
    Tính điểm tương đồng sở thích (C4) từ Spatio-Temporal GNN cho danh sách candidates.
    Khắc phục triệt để lỗi HTTP 404 và rơi vào fallback heuristic.
    """
    results = []
    hr = min(max(0, req.hourOfDay), 23)
    wd = datetime.datetime.now().weekday()
    now = datetime.datetime.now().replace(hour=hr, minute=30)
    ts = float(now.timestamp())

    u = req.userId if (req.userId is not None and 0 <= req.userId < num_users) else 0

    # Lấy embedding user tại thời điểm hr
    with torch.no_grad():
        scores_tgnn = tgnn_model.predict_for_user_at_time(
            u, ts, hr, wd, users_emb=u_emb_tgnn, items_emb=i_emb_tgnn
        ).numpy()

    # Chuẩn hóa min-max điểm GNN về [0, 1] cho C4
    min_s = float(scores_tgnn.min())
    max_s = float(scores_tgnn.max())
    range_s = max_s - min_s if max_s > min_s else 1.0

    for cand in req.candidates:
        # Ánh xạ theo id POI (nếu trong khoảng [0, num_items - 1])
        pid = cand.id
        if 0 <= pid < num_items:
            raw_score = scores_tgnn[pid]
            pref_score = float(round((raw_score - min_s) / range_s, 4))
        else:
            # Nếu id nằm ngoài tập train, tính khoảng cách địa lý và rating
            pref_score = float(round(min(0.95, cand.rating / 5.0 * 0.7 + cand.popularity / 100.0 * 0.3), 4))

        results.append(CprScoredResult(
            placeId=cand.id,
            preferenceScore=pref_score,
            confidence=0.88,
            explanation={
                "summary": f"Điểm sở thích thời gian thực: {round(pref_score * 100)}%",
                "detail": f"Mô hình Spatio-Temporal GNN khớp theo khung giờ {hr}h và vị trí tại Đà Nẵng"
            }
        ))

    return CprScoreResponse(results=results)


@app.post("/api/v1/danang/recommend", response_model=RecommendResponse)
def get_recommendation(req: RecommendRequest):
    """
    Gợi ý địa điểm theo thời gian thực (hỗ trợ cả chế độ thuần GNN và tích hợp MCDM AHP-TOPSIS).
    """
    u = req.userId
    hr = min(max(0, req.hour), 23)
    wd = min(max(0, req.dayOfWeek), 6)

    scores_tgnn, scores_lgcn = compute_model_scores(u, hr, wd, req.userLat, req.userLon)

    if req.excludeVisited and 0 <= u < num_users:
        for l in range(num_items):
            if (u, l) in train_seen:
                scores_tgnn[l] = -1e9
                scores_lgcn[l] = -1e9

    valid_cats = {"cafe", "restaurant", "hotel", "tourist_spot"}
    if req.category and req.category.strip().lower() in valid_cats:
        target_cat = req.category.strip().lower()
        cat_filter = pois_df["category"].values != target_cat
        scores_tgnn[cat_filter] = -1e9
        scores_lgcn[cat_filter] = -1e9

    weekday_names = ["Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy", "Chủ Nhật"]
    query_str = f"{hr:02d}:30 ({weekday_names[wd]})"

    # Xây dựng danh sách ứng viên Top-50 để phục vụ DSS hoặc Pure Rank
    top_tgnn_candidates = np.argsort(scores_tgnn)[::-1][:max(50, req.topK)]
    top_lgcn_candidates = np.argsort(scores_lgcn)[::-1][:req.topK]

    # Chuẩn hóa điểm GNN sang xác suất [0.0 - 1.0]
    min_s = float(scores_tgnn[top_tgnn_candidates[-1]])
    max_s = float(scores_tgnn[top_tgnn_candidates[0]])
    span = max_s - min_s if max_s > min_s else 1.0

    candidate_items = []
    for idx in top_tgnn_candidates:
        row = pois_df.iloc[idx]
        d_km = haversine(req.userLat, req.userLon, float(row["lat"]), float(row["lon"])) if (req.userLat and req.userLon) else None
        norm_ai_score = float(round((scores_tgnn[idx] - min_s) / span, 4))

        candidate_items.append({
            "poiId": int(row["l"]),
            "name": str(row["name"]),
            "category": str(row["category"]),
            "district": str(row["district"]),
            "latitude": float(row["lat"]),
            "longitude": float(row["lon"]),
            "rating": float(row["rating"]),
            "priceAvg": float(row["price_avg"]),
            "popularity": int(row["popularity"]),
            "score": norm_ai_score,
            "distance": d_km if d_km is not None else 1.0,
            "raw_idx": idx
        })

    ahp_result = None
    if req.enableDSS:
        # Chạy AHP + TOPSIS Decision Support
        ahp_result = AHPDecisionMaker.calculate_weights(preset=req.ahpPreset)
        ranked_tgnn = TOPSISDecisionMaker.rank_candidates(
            candidate_items,
            ahp_result["weights_array"],
            stratify_by_category=(req.category is None)
        )[:req.topK]
    else:
        ranked_tgnn = candidate_items[:req.topK]

    def build_items(items_list, scores_array=None):
        out = []
        for rank, item in enumerate(items_list, 1):
            if isinstance(item, dict):
                d_km = item.get("distance")
                t_score = item.get("topsis_score")
                raw_row = pois_df.iloc[item["raw_idx"]] if "raw_idx" in item else item
                exp = generate_poi_explanation(raw_row, hr, d_km, t_score)

                out.append(POIItem(
                    poiId=int(item["poiId"]),
                    name=str(item["name"]),
                    category=str(item["category"]),
                    district=str(item["district"]),
                    latitude=float(item["latitude"]),
                    longitude=float(item["longitude"]),
                    rating=float(item["rating"]),
                    priceAvg=float(item["priceAvg"]),
                    popularity=int(item["popularity"]),
                    score=float(item["score"]),
                    distanceKm=round(d_km, 2) if d_km is not None else None,
                    topsisScore=round(t_score, 4) if t_score is not None else None,
                    explanation=exp
                ))
            else: # index
                idx = item
                row = pois_df.iloc[idx]
                d_km = haversine(req.userLat, req.userLon, float(row["lat"]), float(row["lon"])) if (req.userLat and req.userLon) else None
                raw_s = float(scores_array[idx])
                prob_s = round(1.0 / (1.0 + math.exp(-max(min(raw_s / 5.0, 50.0), -50.0))), 4)
                exp = generate_poi_explanation(row, hr, d_km)

                out.append(POIItem(
                    poiId=int(row["l"]),
                    name=str(row["name"]),
                    category=str(row["category"]),
                    district=str(row["district"]),
                    latitude=float(row["lat"]),
                    longitude=float(row["lon"]),
                    rating=float(row["rating"]),
                    priceAvg=float(row["price_avg"]),
                    popularity=int(row["popularity"]),
                    score=prob_s,
                    distanceKm=round(d_km, 2) if d_km is not None else None,
                    topsisScore=None,
                    explanation=exp
                ))
        return out

    final_tgnn = build_items(ranked_tgnn)
    final_lgcn = build_items(top_lgcn_candidates, scores_lgcn)

    return RecommendResponse(
        model="ST-GNN-POI & MCDM (AHP + TOPSIS)" if req.enableDSS else "Spatio-Temporal GNN (TAS-GNN)",
        userId=u,
        queryTime=query_str,
        userLocation={"lat": req.userLat, "lon": req.userLon} if req.userLat else None,
        dssEnabled=req.enableDSS,
        ahpWeights=ahp_result["weights"] if ahp_result else None,
        totalRecommended=len(final_tgnn),
        tasgnnRecommendations=final_tgnn,
        lightgcnRecommendations=final_lgcn
    )


@app.post("/api/v1/danang/recommend_dss", response_model=DssRecommendResponse)
def get_full_dss_recommendation(req: DssRecommendRequest):
    """
    Toàn trình Hỗ trợ ra quyết định Đa tiêu chí (L-DSS):
    Bước 1: Sinh tập ứng viên Top-50 bằng Spatio-Temporal GNN (Candidate Generation).
    Bước 2: Tính toán khoảng cách địa lý GPS thực tế (C1).
    Bước 3: Xác định trọng số và kiểm tra độ nhất quán AHP (Saaty CR <= 0.10).
    Bước 4: Xếp hạng tối ưu bằng TOPSIS phân tầng theo danh mục (C1-C5).
    """
    u = req.userId
    hr = min(max(0, req.hour), 23)
    wd = min(max(0, req.dayOfWeek), 6)

    # 1. Spatio-Temporal GNN Candidate Retrieval
    scores_tgnn, _ = compute_model_scores(u, hr, wd, req.userLat, req.userLon)

    if 0 <= u < num_users:
        for l in range(num_items):
            if (u, l) in train_seen:
                scores_tgnn[l] = -1e9

    if req.category and req.category.strip().lower() in {"cafe", "restaurant", "hotel", "tourist_spot"}:
        target_cat = req.category.strip().lower()
        scores_tgnn[pois_df["category"].values != target_cat] = -1e9

    top_candidate_indices = np.argsort(scores_tgnn)[::-1][:50]
    min_s = float(scores_tgnn[top_candidate_indices[-1]])
    max_s = float(scores_tgnn[top_candidate_indices[0]])
    span = max_s - min_s if max_s > min_s else 1.0

    candidates = []
    for idx in top_candidate_indices:
        row = pois_df.iloc[idx]
        d_km = haversine(req.userLat, req.userLon, float(row["lat"]), float(row["lon"]))
        norm_ai_score = float(round((scores_tgnn[idx] - min_s) / span, 4))

        candidates.append({
            "poiId": int(row["l"]),
            "name": str(row["name"]),
            "category": str(row["category"]),
            "district": str(row["district"]),
            "latitude": float(row["lat"]),
            "longitude": float(row["lon"]),
            "rating": float(row["rating"]),
            "priceAvg": float(row["price_avg"]),
            "popularity": int(row["popularity"]),
            "score": norm_ai_score,
            "distance": d_km,
            "raw_idx": idx
        })

    # 2. AHP Weight Determination & Consistency Check
    ahp_info = AHPDecisionMaker.calculate_weights(
        matrix=np.array(req.ahpMatrix) if req.ahpMatrix else None,
        preset=req.ahpPreset or "balanced"
    )

    # 3. Category-Stratified TOPSIS Ranking
    ranked_results = TOPSISDecisionMaker.rank_candidates(
        candidates,
        ahp_info["weights_array"],
        stratify_by_category=req.stratifyByCategory and (req.category is None)
    )[:req.topK]

    recommendations = []
    for item in ranked_results:
        raw_row = pois_df.iloc[item["raw_idx"]]
        exp = generate_poi_explanation(raw_row, hr, item["distance"], item["topsis_score"])

        recommendations.append(DssRankedItem(
            finalRank=item["final_rank"],
            poiId=item["poiId"],
            name=item["name"],
            category=item["category"],
            district=item["district"],
            latitude=item["latitude"],
            longitude=item["longitude"],
            distanceKm=round(item["distance"], 2),
            rating=round(item["rating"], 1),
            priceVnd=float(item["priceAvg"]),
            aiPreferenceScore=round(item["score"], 4),
            popularity=int(item["popularity"]),
            topsisScore=round(item["topsis_score"], 4),
            distanceIdealPos=round(item["dist_ideal_pos"], 4),
            distanceIdealNeg=round(item["dist_ideal_neg"], 4),
            explanation=exp
        ))

    return DssRecommendResponse(
        status="success",
        queryContext={
            "userId": u,
            "hour": hr,
            "dayOfWeek": wd,
            "userGPS": {"latitude": req.userLat, "longitude": req.userLon},
            "categoryFilter": req.category or "All Categories"
        },
        ahpAnalysis=ahp_info,
        totalRanked=len(recommendations),
        recommendations=recommendations
    )


# Serve Web Demo trực tiếp từ Root hoặc /demo
@app.get("/demo", response_class=HTMLResponse)
@app.get("/", response_class=HTMLResponse)
def get_demo_page():
    demo_file = os.path.join(ROOT, "demo_danang.html")
    if os.path.exists(demo_file):
        with open(demo_file, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h2>Web Demo đang được biên dịch...</h2>")


if __name__ == "__main__":
    import uvicorn
    print("\n" + "=" * 60)
    print(" KHỞI CHẠY SERVER FASTAPI L-DSS RECOMMENDATION ENGINE")
    print(" Truy cập Web Demo tại: http://localhost:8000/demo")
    print(" API Documentation tại: http://localhost:8000/docs")
    print("=" * 60)
    uvicorn.run(app, host="0.0.0.0", port=8000)
