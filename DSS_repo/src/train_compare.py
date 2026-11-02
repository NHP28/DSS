import os
import sys
import time
import math
import random
import numpy as np
import pandas as pd
import torch
import torch.optim as optim

# Fix Windows console UTF-8
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Thêm đường dẫn src
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.append(CURRENT_DIR)

from models.lightgcn import LightGCN
from models.temporal_gnn import TemporalGNN

DATA_DIR = os.path.join(os.path.dirname(CURRENT_DIR), "data", "danang")
CHECKPOINT_DIR = os.path.join(os.path.dirname(CURRENT_DIR), "outputs", "checkpoints")
os.makedirs(CHECKPOINT_DIR, exist_ok=True)

def load_danang_data():
    pois_df = pd.read_csv(os.path.join(DATA_DIR, "danang_pois_full.csv"))
    ck_df = pd.read_csv(os.path.join(DATA_DIR, "danang_checkins_full.csv"))
    
    num_users = int(ck_df["u"].max()) + 1
    num_items = len(pois_df)

    coords = pois_df[["lat", "lon"]].values.astype(np.float32)
    # Map category string -> integer (0, 1, 2, 3)
    cat_map = {"cafe": 0, "restaurant": 1, "hotel": 2, "tourist_spot": 3}
    cat_ids = pois_df["category"].map(lambda c: cat_map.get(c, 0)).values.astype(np.int64)

    return ck_df, pois_df, num_users, num_items, coords, cat_ids

def temporal_split(ck_df, train_ratio=0.7, tune_ratio=0.1):
    ck = ck_df.sort_values(["u", "ts"], kind="stable").reset_index(drop=True)
    pos = ck.groupby("u").cumcount().values
    size = ck.groupby("u").u.transform("size").values
    n_tr = np.floor(size * train_ratio).astype(int)
    n_tu = np.floor(size * (train_ratio + tune_ratio)).astype(int)

    ck["part"] = np.where(pos < n_tr, 0, np.where(pos < n_tu, 1, 2))
    train = ck[ck["part"] == 0]
    tune = ck[ck["part"] == 1]
    test = ck[ck["part"] == 2]

    # Ground truth for test (new POIs in test that user hasn't visited in train)
    train_seen = set(zip(train["u"].values, train["l"].values))
    test_truth = {}
    test_contexts = {} # user -> last test timestamp context (ts, hour, weekday)

    for _, row in test.iterrows():
        u, l = int(row["u"]), int(row["l"])
        if (u, l) not in train_seen:
            test_truth.setdefault(u, set()).add(l)
            test_contexts[u] = (float(row["ts"]), int(row["hour"]), int(row["day_of_week"]))

    return train, tune, test, train_seen, test_truth, test_contexts

def compute_metrics(predicted_ranks, truth, K_list=[5, 10, 20]):
    """
    predicted_ranks: list of top items
    truth: set of ground truth items
    """
    results = {}
    if not truth:
        return {f"Recall@{k}": 0.0 for k in K_list} | {f"NDCG@{k}": 0.0 for k in K_list} | {f"Precision@{k}": 0.0 for k in K_list}

    for k in K_list:
        top_k = predicted_ranks[:k]
        hits = len(set(top_k) & truth)
        
        # Recall@K
        results[f"Recall@{k}"] = hits / float(len(truth))
        # Precision@K
        results[f"Precision@{k}"] = hits / float(k)
        
        # NDCG@K
        dcg = 0.0
        for rank, item in enumerate(top_k):
            if item in truth:
                dcg += 1.0 / math.log2(rank + 2)
        idcg = sum(1.0 / math.log2(r + 2) for r in range(min(len(truth), k)))
        results[f"NDCG@{k}"] = (dcg / idcg) if idcg > 0 else 0.0

    return results

def evaluate_model(model, train_seen, test_truth, test_contexts, num_items, is_temporal=False, device="cpu"):
    model.eval()
    all_metrics = []
    
    with torch.no_grad():
        if is_temporal:
            users_emb, items_emb = model.get_graph_embeddings()
        else:
            users_emb, items_emb = model.forward()

        # Đánh giá trên từng user có ground truth
        for u, truth_items in test_truth.items():
            if not truth_items:
                continue

            if is_temporal and u in test_contexts:
                ts, hr, wd = test_contexts[u]
                scores = model.predict_for_user_at_time(u, ts, hr, wd, users_emb, items_emb).cpu().numpy()
            else:
                scores = model.predict_for_user(u, users_emb, items_emb).cpu().numpy()

            # Mask các POI đã ghé thăm trong train
            for l in range(num_items):
                if (u, l) in train_seen:
                    scores[l] = -1e9

            # Lấy top-20 địa điểm có điểm số cao nhất
            top_ranked = np.argsort(scores)[::-1][:20]
            metrics = compute_metrics(top_ranked, truth_items, K_list=[5, 10, 20])
            all_metrics.append(metrics)

    # Trung bình cộng các độ đo trên toàn bộ test users
    avg_metrics = {}
    for key in all_metrics[0].keys():
        avg_metrics[key] = np.mean([m[key] for m in all_metrics])
    return avg_metrics

def generate_batches(train_df, num_items, batch_size=1024):
    u_vals = train_df["u"].values
    l_vals = train_df["l"].values
    ts_vals = train_df["ts"].values
    hr_vals = train_df["hour"].values
    wd_vals = train_df["day_of_week"].values

    n_samples = len(u_vals)
    indices = np.random.permutation(n_samples)

    for i in range(0, n_samples, batch_size):
        batch_idx = indices[i:min(i + batch_size, n_samples)]
        u_b = u_vals[batch_idx]
        pos_b = l_vals[batch_idx]
        neg_b = np.random.randint(0, num_items, size=len(batch_idx))
        ts_b = ts_vals[batch_idx]
        hr_b = hr_vals[batch_idx]
        wd_b = wd_vals[batch_idx]
        yield u_b, pos_b, neg_b, ts_b, hr_b, wd_b

def train_and_compare(epochs=15, batch_size=1024, lr=0.005):
    print("=" * 70)
    print(" THỰC NGHIỆM SO SÁNH: LIGHTGCN (BASELINE) VS TEMPORAL GNN (PROPOSED)")
    print(" DỮ LIỆU: TP. ĐÀ NẴNG (996 POIs, 36.210 Check-ins)")
    print("=" * 70)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Thiết bị tính toán: {device}")

    # 1. Nạp và phân chia dữ liệu
    ck_df, pois_df, num_users, num_items, coords, cat_ids = load_danang_data()
    train_df, tune_df, test_df, train_seen, test_truth, test_contexts = temporal_split(ck_df)
    train_pairs = train_df[["u", "l"]].values

    print(f"Tổng số Users: {num_users} | Tổng số POIs: {num_items}")
    print(f"Số lượng tương tác Train: {len(train_df)} | Test Users đánh giá: {len(test_truth)}")

    # 2. Huấn luyện Mô hình 1: LightGCN (Baseline)
    print("\n" + "-" * 70)
    print("[1/2] HUẤN LUYỆN MÔ HÌNH BASELINE: LightGCN (SIGIR 2020)")
    print("-" * 70)
    
    lightgcn = LightGCN(num_users, num_items, embedding_dim=64, num_layers=3).to(device)
    lightgcn.build_normalized_adj(train_pairs)
    opt_lgcn = optim.Adam(lightgcn.parameters(), lr=lr)

    start_time = time.time()
    for ep in range(1, epochs + 1):
        lightgcn.train()
        total_loss = 0.0
        batches = 0
        for u_b, pos_b, neg_b, _, _, _ in generate_batches(train_df, num_items, batch_size):
            opt_lgcn.zero_grad()
            loss = lightgcn.compute_bpr_loss(
                torch.tensor(u_b, dtype=torch.long, device=device),
                torch.tensor(pos_b, dtype=torch.long, device=device),
                torch.tensor(neg_b, dtype=torch.long, device=device)
            )
            loss.backward()
            opt_lgcn.step()
            total_loss += loss.item()
            batches += 1
        
        if ep % 5 == 0 or ep == epochs:
            print(f" Epoch {ep:02d}/{epochs:02d} | BPR Loss: {total_loss / batches:.4f}")
    
    lgcn_time = time.time() - start_time
    print(f" -> Hoàn tất huấn luyện LightGCN ({lgcn_time:.1f}s)")
    lgcn_metrics = evaluate_model(lightgcn, train_seen, test_truth, test_contexts, num_items, is_temporal=False, device=device)

    # 3. Huấn luyện Mô hình 2: Temporal GNN (Proposed)
    print("\n" + "-" * 70)
    print("[2/2] HUẤN LUYỆN MÔ HÌNH ĐỀ XUẤT: Temporal GNN (TGNN_POIRec)")
    print("      (Tích hợp Continuous Time Encoding + Spatial Coordinates Đà Nẵng)")
    print("-" * 70)

    tgnn = TemporalGNN(
        num_users,
        num_items,
        coords=coords,
        category_ids=cat_ids,
        embedding_dim=64,
        time_dim=32,
        num_layers=3,
        use_time=True,
        use_spatial=True
    ).to(device)
    tgnn.build_normalized_adj(train_pairs)
    opt_tgnn = optim.Adam(tgnn.parameters(), lr=lr)

    start_time = time.time()
    for ep in range(1, epochs + 1):
        tgnn.train()
        total_loss = 0.0
        batches = 0
        for u_b, pos_b, neg_b, ts_b, hr_b, wd_b in generate_batches(train_df, num_items, batch_size):
            opt_tgnn.zero_grad()
            loss = tgnn.compute_bpr_loss(
                torch.tensor(u_b, dtype=torch.long, device=device),
                torch.tensor(pos_b, dtype=torch.long, device=device),
                torch.tensor(neg_b, dtype=torch.long, device=device),
                torch.tensor(ts_b, dtype=torch.float32, device=device),
                torch.tensor(hr_b, dtype=torch.long, device=device),
                torch.tensor(wd_b, dtype=torch.long, device=device)
            )
            loss.backward()
            opt_tgnn.step()
            total_loss += loss.item()
            batches += 1
            
        if ep % 5 == 0 or ep == epochs:
            print(f" Epoch {ep:02d}/{epochs:02d} | BPR Loss: {total_loss / batches:.4f}")

    tgnn_time = time.time() - start_time
    print(f" -> Hoàn tất huấn luyện Temporal GNN ({tgnn_time:.1f}s)")
    tgnn_metrics = evaluate_model(tgnn, train_seen, test_truth, test_contexts, num_items, is_temporal=True, device=device)

    # 4. Lưu Checkpoint
    torch.save(lightgcn.state_dict(), os.path.join(CHECKPOINT_DIR, "lightgcn_danang.pt"))
    torch.save(tgnn.state_dict(), os.path.join(CHECKPOINT_DIR, "temporal_gnn_danang.pt"))
    print(f"\nĐã lưu checkpoint cả 2 mô hình tại: {CHECKPOINT_DIR}")

    # 5. Bảng Tổng kết Đánh giá So sánh Học thuật
    print("\n" + "=" * 70)
    print(" BẢNG KẾT QUẢ SO SÁNH ĐỐI SÁNH TRÊN TẬP DỮ LIỆU ĐÀ NẴNG (TEST SET)")
    print("=" * 70)
    header = f"{'Metric':<16} | {'LightGCN (Baseline)':<20} | {'Temporal GNN (Proposed)':<22} | {'Cải thiện (Δ%)':<12}"
    print(header)
    print("-" * len(header))

    metrics_order = [
        "Recall@5", "Recall@10", "Recall@20",
        "NDCG@5", "NDCG@10", "NDCG@20",
        "Precision@10"
    ]

    report_data = []
    for m in metrics_order:
        base_val = lgcn_metrics.get(m, 0.0)
        prop_val = tgnn_metrics.get(m, 0.0)
        diff_pct = ((prop_val - base_val) / base_val * 100.0) if base_val > 0 else 0.0
        sign = "+" if diff_pct >= 0 else ""
        print(f"{m:<16} | {base_val * 100:>18.2f}% | {prop_val * 100:>20.2f}% | {sign}{diff_pct:>10.2f}%")
        report_data.append({
            "Metric": m,
            "LightGCN_Baseline": round(base_val * 100, 2),
            "Temporal_GNN_Proposed": round(prop_val * 100, 2),
            "Improvement_Pct": f"{sign}{diff_pct:.2f}%"
        })

    # Lưu kết quả bảng ra CSV
    res_df = pd.DataFrame(report_data)
    res_df.to_csv(os.path.join(os.path.dirname(CURRENT_DIR), "outputs", "experiment_comparison_danang.csv"), index=False)
    print("=" * 70)
    print(" Báo cáo thực nghiệm đã được xuất tự động ra:")
    print(" outputs/experiment_comparison_danang.csv")
    print("=" * 70)

if __name__ == "__main__":
    train_and_compare(epochs=15, batch_size=1024, lr=0.005)
