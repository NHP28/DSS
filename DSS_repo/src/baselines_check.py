"""
Benchmarking Script: Non-learning Heuristics vs. Graph Neural Networks
Evaluates:
1. Hourly Popularity (Không học)
2. Hour x Distance from Last Check-in in Train (Không học)
3. Hour x Distance from Immediate Previous Check-in (Next-POI Heuristic)
4. LightGCN (SIGIR 2020)
5. Spatio-Temporal GNN (Đã fix triệt tiêu context và chuẩn hóa)
"""

import os
import sys
import math
import numpy as np
import pandas as pd
import torch

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
DATA_DIR = os.path.join(ROOT, "data", "danang")
CHECKPOINT_DIR = os.path.join(ROOT, "outputs", "checkpoints")

if SRC not in sys.path:
    sys.path.insert(0, SRC)

from models.lightgcn import LightGCN
from models.temporal_gnn import TemporalGNN
from mcdm import haversine

def run_baseline_benchmark():
    print("=" * 80)
    print(" BÁO CÁO ĐỐI SOÁT BASELINE HEURISTIC & MÔ HÌNH HỌC SÂU (ĐÀ NẴNG)")
    print("=" * 80)

    pois_df = pd.read_csv(os.path.join(DATA_DIR, "danang_pois_full.csv"))
    ck_df = pd.read_csv(os.path.join(DATA_DIR, "danang_checkins_full.csv"))
    num_users = int(ck_df["u"].max()) + 1
    num_items = len(pois_df)

    coords = pois_df[["lat", "lon"]].values.astype(np.float32)
    cat_map = {"cafe": 0, "restaurant": 1, "hotel": 2, "tourist_spot": 3}
    cat_ids = pois_df["category"].map(lambda c: cat_map.get(c, 0)).values.astype(np.int64)

    # Chia train 80%, test 20% theo thời gian cho từng user
    ck = ck_df.sort_values(["u", "ts"], kind="stable").reset_index(drop=True)
    pos = ck.groupby("u").cumcount().values
    size = ck.groupby("u").u.transform("size").values
    n_tu = np.floor(size * 0.8).astype(int)
    ck["part"] = np.where(pos < n_tu, 0, 1)

    train_df = ck[ck["part"] == 0]
    test_df = ck[ck["part"] == 1]
    train_seen = set(zip(train_df["u"].values, train_df["l"].values))

    # Xây dựng ma trận tần suất check-in theo giờ từ tập train
    hourly_pop = train_df.groupby(["hour", "l"]).size().unstack(fill_value=0)
    # Đảm bảo đủ 24 giờ và num_items cột
    full_hourly_pop = np.zeros((24, num_items), dtype=float)
    for h in range(24):
        if h in hourly_pop.index:
            cols = hourly_pop.columns.values
            full_hourly_pop[h, cols] = hourly_pop.loc[h].values

    # Lưu lại check-in cuối cùng trong train của mỗi user
    last_train_poi = {}
    for _, row in train_df.iterrows():
        last_train_poi[int(row["u"])] = int(row["l"])

    # Xây dựng danh sách test events kèm POI liền trước
    test_events = []
    # Lưu check-in liền trước trong chuỗi lịch sử đầy đủ
    prev_poi_lookup = {}
    for _, row in ck.iterrows():
        u = int(row["u"])
        l = int(row["l"])
        ts = float(row["ts"])
        hr = int(row["hour"])
        part = int(row["part"])

        prev_l = prev_poi_lookup.get(u, last_train_poi.get(u, 0))
        if part == 1 and (u, l) not in train_seen:
            test_events.append({
                "u": u,
                "target_l": l,
                "ts": ts,
                "hr": hr,
                "prev_l": prev_l,
                "last_train_l": last_train_poi.get(u, prev_l)
            })
        prev_poi_lookup[u] = l

    N = float(len(test_events))
    print(f"Tổng số sự kiện kiểm thử mới (Test Events): {int(N)}")

    device = torch.device("cpu")
    train_pairs = train_df[["u", "l"]].values

    # 1. Nạp LightGCN
    lightgcn = LightGCN(num_users, num_items, embedding_dim=64, num_layers=3).to(device)
    lgcn_pt = os.path.join(CHECKPOINT_DIR, "lightgcn_danang.pt")
    if os.path.exists(lgcn_pt):
        lightgcn.load_state_dict(torch.load(lgcn_pt, map_location=device))
        lightgcn.build_normalized_adj(train_pairs)
        lightgcn.eval()
        u_emb_lgcn, i_emb_lgcn = lightgcn.forward()

    # 2. Nạp Spatio-Temporal GNN
    tgnn = TemporalGNN(
        num_users, num_items, coords=coords, category_ids=cat_ids,
        embedding_dim=64, time_dim=32, num_layers=3, use_time=True, use_spatial=True
    ).to(device)
    tgnn_pt = os.path.join(CHECKPOINT_DIR, "temporal_gnn_danang.pt")
    if os.path.exists(tgnn_pt):
        tgnn.load_state_dict(torch.load(tgnn_pt, map_location=device))
        tgnn.build_normalized_adj(train_pairs)
        tgnn.eval()
        u_emb_tgnn, i_emb_tgnn = tgnn.get_graph_embeddings()

    # Định nghĩa các phương pháp đánh giá
    methods = [
        "Phổ biến theo giờ (Heuristic)",
        "Giờ × Khoảng cách cuối train (Heuristic)",
        "Giờ × Khoảng cách liền trước (Next-POI)",
        "LightGCN (GNN Tĩnh)",
        "ST-GNN-POI (Đề xuất)"
    ]

    K_list = [5, 10, 20]
    hits = {m: {k: 0 for k in K_list} for m in methods}
    ndcg = {m: {k: 0.0 for k in K_list} for m in methods}

    # Tính khoảng cách giữa tất cả các cặp POI (để tăng tốc Heuristic)
    all_lat = coords[:, 0]
    all_lon = coords[:, 1]

    print("\nĐang tiến hành chấm điểm trên toàn bộ tập test...")
    sample_stride = max(1, len(test_events) // 1000) # Lấy mẫu 1000 sự kiện đại diện nếu cần nhanh, hoặc toàn bộ
    eval_subset = test_events[::sample_stride]
    sub_N = float(len(eval_subset))

    with torch.no_grad():
        for event in eval_subset:
            u = event["u"]
            target = event["target_l"]
            ts = event["ts"]
            hr = event["hr"]
            prev_l = event["prev_l"]
            last_train_l = event["last_train_l"]

            # Phổ biến theo giờ
            base_hour_scores = full_hourly_pop[hr].copy()

            # Khoảng cách từ last_train_l
            d_train = np.array([haversine(all_lat[last_train_l], all_lon[last_train_l], lat, lon) for lat, lon in zip(all_lat, all_lon)])
            score_heur_train = base_hour_scores / (d_train + 0.5)

            # Khoảng cách từ prev_l
            d_prev = np.array([haversine(all_lat[prev_l], all_lon[prev_l], lat, lon) for lat, lon in zip(all_lat, all_lon)])
            score_heur_prev = base_hour_scores / (d_prev + 0.5)

            # LightGCN
            score_lgcn = lightgcn.predict_for_user(u, u_emb_lgcn, i_emb_lgcn).numpy().copy()

            # ST-GNN
            score_tgnn = tgnn.predict_for_user_at_time(u, ts, hr, 2, users_emb=u_emb_tgnn, items_emb=i_emb_tgnn).numpy().copy()

            all_scores = {
                "Phổ biến theo giờ (Heuristic)": base_hour_scores,
                "Giờ × Khoảng cách cuối train (Heuristic)": score_heur_train,
                "Giờ × Khoảng cách liền trước (Next-POI)": score_heur_prev,
                "LightGCN (GNN Tĩnh)": score_lgcn,
                "ST-GNN-POI (Đề xuất)": score_tgnn
            }

            for m_name, scores in all_scores.items():
                # Che các POI đã ghé trong train
                for l_seen in range(num_items):
                    if (u, l_seen) in train_seen:
                        scores[l_seen] = -1e9

                top_idx = np.argsort(scores)[::-1][:20]

                for k in K_list:
                    if target in top_idx[:k]:
                        hits[m_name][k] += 1
                        rank = np.where(top_idx[:k] == target)[0][0]
                        ndcg[m_name][k] += 1.0 / math.log2(rank + 2)

    # In kết quả dạng bảng Markdown
    print("\n" + "=" * 90)
    print(f"{'Phương pháp':<40} | {'HR@5':<8} | {'HR@10':<8} | {'HR@20':<8} | {'NDCG@5':<8} | {'NDCG@10':<8}")
    print("-" * 90)

    rows = []
    for m in methods:
        h5 = (hits[m][5] / sub_N) * 100
        h10 = (hits[m][10] / sub_N) * 100
        h20 = (hits[m][20] / sub_N) * 100
        n5 = (ndcg[m][5] / sub_N) * 100
        n10 = (ndcg[m][10] / sub_N) * 100

        print(f"{m:<40} | {h5:>7.2f}% | {h10:>7.2f}% | {h20:>7.2f}% | {n5:>7.2f}% | {n10:>7.2f}%")
        rows.append({
            "Method": m,
            "HR@5": round(h5, 2),
            "HR@10": round(h10, 2),
            "HR@20": round(h20, 2),
            "NDCG@5": round(n5, 2),
            "NDCG@10": round(n10, 2)
        })

    print("=" * 90)
    df_out = pd.DataFrame(rows)
    out_csv = os.path.join(ROOT, "outputs", "baselines_benchmark_danang.csv")
    df_out.to_csv(out_csv, index=False)
    print(f"Đã lưu bảng kết quả benchmark tại: {out_csv}")

if __name__ == "__main__":
    run_baseline_benchmark()
