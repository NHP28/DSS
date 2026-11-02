"""
FastAPI Server for POI Recommendation AI Service
Integrates:
1. TAS-GNN (Time-Aware Spatio-Temporal Graph Neural Network) for Da Nang POI Recommendation.
2. LightGCN (SIGIR 2020) Baseline for Comparison.
3. Legacy CPR (IJCAI 2020) Contextualized Preference Model.
"""

import os
import sys
import json
import time
import math
import datetime
import numpy as np
import pandas as pd
from typing import List, Optional, Dict
from pydantic import BaseModel
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
except ModuleNotFoundError:
    from src.models.lightgcn import LightGCN
    from src.models.temporal_gnn import TemporalGNN

app = FastAPI(
    title="Time-Aware POI Recommendation AI Service (TAS-GNN)",
    description="Hệ thống Gợi ý Địa điểm Cá nhân hóa tích hợp Mạng nơ-ron Đồ thị Động và Thời gian thực (Đà Nẵng)",
    version="2.0.0"
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

device = torch.device("cpu")

# Load LightGCN
lightgcn_model = LightGCN(num_users, num_items, embedding_dim=64, num_layers=3).to(device)
lgcn_pt = os.path.join(CHECKPOINT_DIR, "lightgcn_danang.pt")
if os.path.exists(lgcn_pt):
    lightgcn_model.load_state_dict(torch.load(lgcn_pt, map_location=device))
    lightgcn_model.build_normalized_adj(train_pairs)
    lightgcn_model.eval()
    print("[Server] Đã nạp thành công checkpoint LightGCN!")

# Load TAS-GNN
tgnn_model = TemporalGNN(
    num_users, num_items, coords=coords, category_ids=cat_ids,
    embedding_dim=64, time_dim=32, num_layers=3, use_time=True, use_spatial=True
).to(device)
tgnn_pt = os.path.join(CHECKPOINT_DIR, "temporal_gnn_danang.pt")
if os.path.exists(tgnn_pt):
    tgnn_model.load_state_dict(torch.load(tgnn_pt, map_location=device))
    tgnn_model.build_normalized_adj(train_pairs)
    tgnn_model.eval()
    print("[Server] Đã nạp thành công checkpoint TAS-GNN!")

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
    explanation: str

class RecommendResponse(BaseModel):
    model: str
    userId: int
    queryTime: str
    totalRecommended: int
    tasgnnRecommendations: List[POIItem]
    lightgcnRecommendations: List[POIItem]

# ----------------- ENDPOINTS -----------------
@app.get("/health")
def health():
    return {
        "status": "healthy",
        "city": "Da Nang, Vietnam",
        "totalPois": num_items,
        "totalUsers": num_users,
        "modelsLoaded": ["LightGCN", "TAS-GNN"]
    }

@app.get("/api/v1/danang/pois")
def get_all_pois(category: Optional[str] = None, district: Optional[str] = None, limit: int = 100):
    df = pois_df
    if category:
        df = df[df["category"] == category]
    if district:
        df = df[df["district"] == district]
    return df.head(limit).to_dict("records")

@app.post("/api/v1/danang/recommend", response_model=RecommendResponse)
def get_recommendation(req: RecommendRequest):
    u = min(max(0, req.userId), num_users - 1)
    hr = min(max(0, req.hour), 23)
    wd = min(max(0, req.dayOfWeek), 6)
    
    # Giả lập timestamp dựa trên hour & day
    now = datetime.datetime.now()
    sim_dt = now.replace(hour=hr, minute=30)
    ts = float(sim_dt.timestamp())

    # 1. Dự đoán với TAS-GNN (Đề xuất)
    with torch.no_grad():
        scores_tgnn = tgnn_model.predict_for_user_at_time(u, ts, hr, wd, u_emb_tgnn, i_emb_tgnn).numpy().copy()
        scores_lgcn = lightgcn_model.predict_for_user(u, u_emb_lgcn, i_emb_lgcn).numpy().copy()

    if req.excludeVisited:
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

    top_tgnn_indices = np.argsort(scores_tgnn)[::-1][:req.topK]
    top_lgcn_indices = np.argsort(scores_lgcn)[::-1][:req.topK]

    weekday_names = ["Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy", "Chủ Nhật"]
    query_str = f"{hr:02d}:30 ({weekday_names[wd]})"

    def build_items(indices, scores):
        items = []
        for rank, idx in enumerate(indices, 1):
            row = pois_df.iloc[idx]
            c = row["category"]
            exp = ""
            if 6 <= hr <= 9 and c == "cafe":
                exp = f"Khung giờ sáng {hr}h rất thích hợp để thưởng thức cafe & khởi đầu ngày mới"
            elif 6 <= hr <= 9 and c == "restaurant":
                exp = f"Khung giờ sáng {hr}h thưởng thức bữa sáng đặc sản Đà Nẵng tại {row['district']}"
            elif 11 <= hr <= 13 and c == "restaurant":
                exp = f"Thời điểm {hr}h trưa lý tưởng để dùng bữa trưa đặc sản tại {row['district']}"
            elif 15 <= hr <= 17:
                exp = f"Buổi chiều mát {hr}h phù hợp để dạo biển, ngắm cảnh hoặc thư giãn"
            elif 18 <= hr <= 22 and c == "restaurant":
                exp = f"Buổi tối {hr}h thưởng thức hải sản và ẩm thực đêm Đà Nẵng tại {row['district']}"
            elif 18 <= hr <= 22:
                exp = f"Buổi tối {hr}h thích hợp dạo phố, ngắm cầu Rồng hoặc ẩm thực đêm"
            else:
                exp = f"Được gợi ý theo thói quen tương tác và vị trí ưa thích tại Đà Nẵng"

            raw_s = float(scores[idx])
            if raw_s <= -1e8:
                prob_s = 0.0
            else:
                scaled_s = max(min(raw_s / 5.0, 50.0), -50.0)
                prob_s = round(1.0 / (1.0 + math.exp(-scaled_s)), 4)

            items.append(POIItem(
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
                explanation=exp
            ))
        return items

    return RecommendResponse(
        model="Time-Aware Spatio-Temporal GNN (TAS-GNN)",
        userId=u,
        queryTime=query_str,
        totalRecommended=req.topK,
        tasgnnRecommendations=build_items(top_tgnn_indices, scores_tgnn),
        lightgcnRecommendations=build_items(top_lgcn_indices, scores_lgcn)
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
    print(" KHỞI CHẠY SERVER FASTAPI TAS-GNN RECOMMENDATION")
    print(" Truy cập Web Demo tại: http://localhost:8000/demo")
    print(" API Documentation tại: http://localhost:8000/docs")
    print("=" * 60)
    uvicorn.run(app, host="0.0.0.0", port=8000)
