import os
import sys
import math
import numpy as np
import pandas as pd
import torch
import torch.optim as optim

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.append(CURRENT_DIR)

from models.lightgcn import LightGCN
from models.temporal_gnn import TemporalGNN

DATA_DIR = os.path.join(os.path.dirname(CURRENT_DIR), "data", "danang")
OUTPUT_DIR = os.path.join(os.path.dirname(CURRENT_DIR), "outputs")
os.makedirs(OUTPUT_DIR, exist_ok=True)

def run_ablation(epochs=10, batch_size=1024, lr=0.005):
    print("=" * 70)
    print(" NGHIÊN CỨU BÓC TÁCH THÀNH PHẦN (ABLATION STUDY)")
    print("=" * 70)

    pois_df = pd.read_csv(os.path.join(DATA_DIR, "danang_pois_full.csv"))
    ck_df = pd.read_csv(os.path.join(DATA_DIR, "danang_checkins_full.csv"))
    num_users = int(ck_df["u"].max()) + 1
    num_items = len(pois_df)

    coords = pois_df[["lat", "lon"]].values.astype(np.float32)
    cat_map = {"cafe": 0, "restaurant": 1, "hotel": 2, "tourist_spot": 3}
    cat_ids = pois_df["category"].map(lambda c: cat_map.get(c, 0)).values.astype(np.int64)

    # Train / Test split
    ck = ck_df.sort_values(["u", "ts"], kind="stable").reset_index(drop=True)
    pos = ck.groupby("u").cumcount().values
    size = ck.groupby("u").u.transform("size").values
    n_tu = np.floor(size * 0.8).astype(int)
    ck["part"] = np.where(pos < n_tu, 0, 1)

    train_df = ck[ck["part"] == 0]
    test_df = ck[ck["part"] == 1]
    train_seen = set(zip(train_df["u"].values, train_df["l"].values))
    train_pairs = train_df[["u", "l"]].values

    test_events = []
    for _, row in test_df.iterrows():
        u, l = int(row["u"]), int(row["l"])
        if (u, l) not in train_seen:
            test_events.append((u, l, float(row["ts"]), int(row["hour"]), int(row["day_of_week"])))

    device = torch.device("cpu")
    configurations = [
        ("1. Full TGNN (Proposed)", True, True),
        ("2. TGNN w/o Time", False, True),
        ("3. TGNN w/o Spatial", True, False),
        ("4. LightGCN (Graph Only)", False, False)
    ]

    results_table = []

    for name, use_time, use_spatial in configurations:
        print(f"\n---> Đang huấn luyện: {name} (Time={use_time}, Spatial={use_spatial})...")
        if name == "4. LightGCN (Graph Only)":
            model = LightGCN(num_users, num_items, embedding_dim=64, num_layers=3).to(device)
            model.build_normalized_adj(train_pairs)
            opt = optim.Adam(model.parameters(), lr=lr)
            for ep in range(epochs):
                for u_b, pos_b, neg_b, _, _, _ in get_batches(train_df, num_items, batch_size):
                    opt.zero_grad()
                    loss = model.compute_bpr_loss(
                        torch.tensor(u_b, dtype=torch.long),
                        torch.tensor(pos_b, dtype=torch.long),
                        torch.tensor(neg_b, dtype=torch.long)
                    )
                    loss.backward()
                    opt.step()
            u_emb, i_emb = model.forward()
        else:
            model = TemporalGNN(
                num_users, num_items, coords=coords, category_ids=cat_ids,
                embedding_dim=64, time_dim=32, num_layers=3,
                use_time=use_time, use_spatial=use_spatial
            ).to(device)
            model.build_normalized_adj(train_pairs)
            opt = optim.Adam(model.parameters(), lr=lr)
            for ep in range(epochs):
                for u_b, pos_b, neg_b, ts_b, hr_b, wd_b in get_batches(train_df, num_items, batch_size):
                    opt.zero_grad()
                    loss = model.compute_bpr_loss(
                        torch.tensor(u_b, dtype=torch.long),
                        torch.tensor(pos_b, dtype=torch.long),
                        torch.tensor(neg_b, dtype=torch.long),
                        torch.tensor(ts_b, dtype=torch.float32),
                        torch.tensor(hr_b, dtype=torch.long),
                        torch.tensor(wd_b, dtype=torch.long)
                    )
                    loss.backward()
                    opt.step()
            u_emb, i_emb = model.get_graph_embeddings()

        # Đánh giá nhanh trên test events
        model.eval()
        hr10_count = 0
        ndcg10_sum = 0.0
        with torch.no_grad():
            for u, target_l, ts, hr, wd in test_events:
                if use_time:
                    scores = model.predict_for_user_at_time(u, ts, hr, wd, u_emb, i_emb).numpy()
                elif hasattr(model, "predict_for_user"):
                    scores = model.predict_for_user(u, u_emb, i_emb).numpy()
                else:
                    scores = torch.matmul(i_emb, u_emb[u]).numpy()

                for l_seen in range(num_items):
                    if (u, l_seen) in train_seen:
                        scores[l_seen] = -1e9
                top10 = np.argsort(scores)[::-1][:10]
                if target_l in top10:
                    hr10_count += 1
                    rank = np.where(top10 == target_l)[0][0]
                    ndcg10_sum += 1.0 / math.log2(rank + 2)

        n_ev = float(len(test_events))
        hr10 = (hr10_count / n_ev) * 100
        ndcg10 = (ndcg10_sum / n_ev) * 100
        print(f"     => HitRate@10: {hr10:.2f}% | NDCG@10: {ndcg10:.2f}%")
        results_table.append({
            "Variant": name,
            "Use_Time": use_time,
            "Use_Spatial": use_spatial,
            "HitRate@10": round(hr10, 2),
            "NDCG@10": round(ndcg10, 2)
        })

    print("\n" + "=" * 70)
    print(" BẢNG KẾT QUẢ ABLATION STUDY (BÓC TÁCH THÀNH PHẦN)")
    print("=" * 70)
    print(f"{'Mô hình / Biến thể':<28} | {'HitRate@10':<15} | {'NDCG@10':<15}")
    print("-" * 65)
    for row in results_table:
        print(f"{row['Variant']:<28} | {row['HitRate@10']:>13.2f}% | {row['NDCG@10']:>13.2f}%")

    out_csv = os.path.join(OUTPUT_DIR, "ablation_study_danang.csv")
    pd.DataFrame(results_table).to_csv(out_csv, index=False)
    print(f"\nĐã xuất kết quả ra: {out_csv}")

def get_batches(df, num_items, batch_size=1024):
    u_vals = df["u"].values
    l_vals = df["l"].values
    ts_vals = df["ts"].values
    hr_vals = df["hour"].values
    wd_vals = df["day_of_week"].values

    n = len(u_vals)
    indices = np.random.permutation(n)
    for i in range(0, n, batch_size):
        idx = indices[i:min(i + batch_size, n)]
        yield u_vals[idx], l_vals[idx], np.random.randint(0, num_items, size=len(idx)), ts_vals[idx], hr_vals[idx], wd_vals[idx]

if __name__ == "__main__":
    run_ablation(epochs=8, batch_size=1024, lr=0.005)
