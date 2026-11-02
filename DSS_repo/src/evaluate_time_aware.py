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

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.append(CURRENT_DIR)

from models.lightgcn import LightGCN
from models.temporal_gnn import TemporalGNN

DATA_DIR = os.path.join(os.path.dirname(CURRENT_DIR), "data", "danang")
CHECKPOINT_DIR = os.path.join(os.path.dirname(CURRENT_DIR), "outputs", "checkpoints")

def evaluate_next_poi():
    print("=" * 70)
    print(" ĐÁNH GIÁ CHUẨN TIME-AWARE NEXT-POI RECOMMENDATION")
    print(" (Mỗi tương tác test (u, l, t) được kiểm tra tại đúng thời điểm t xảy ra)")
    print("=" * 70)

    pois_df = pd.read_csv(os.path.join(DATA_DIR, "danang_pois_full.csv"))
    ck_df = pd.read_csv(os.path.join(DATA_DIR, "danang_checkins_full.csv"))
    num_users = int(ck_df["u"].max()) + 1
    num_items = len(pois_df)

    coords = pois_df[["lat", "lon"]].values.astype(np.float32)
    cat_map = {"cafe": 0, "restaurant": 1, "hotel": 2, "tourist_spot": 3}
    cat_ids = pois_df["category"].map(lambda c: cat_map.get(c, 0)).values.astype(np.int64)

    # Chia train 70%, tune 10%, test 20%
    ck = ck_df.sort_values(["u", "ts"], kind="stable").reset_index(drop=True)
    pos = ck.groupby("u").cumcount().values
    size = ck.groupby("u").u.transform("size").values
    n_tu = np.floor(size * 0.8).astype(int)
    ck["part"] = np.where(pos < n_tu, 0, 1)

    train_df = ck[ck["part"] == 0]
    test_df = ck[ck["part"] == 1]
    train_seen = set(zip(train_df["u"].values, train_df["l"].values))

    # Chỉ đánh giá trên các lượt ghé thăm địa điểm mới (chưa từng đi trong train)
    test_events = []
    for _, row in test_df.iterrows():
        u, l = int(row["u"]), int(row["l"])
        if (u, l) not in train_seen:
            test_events.append((u, l, float(row["ts"]), int(row["hour"]), int(row["day_of_week"])))

    print(f"Tổng số sự kiện kiểm thử mới (Test Events): {len(test_events)}")

    device = torch.device("cpu")

    train_pairs = train_df[["u", "l"]].values

    # 1. Nạp LightGCN
    lightgcn = LightGCN(num_users, num_items, embedding_dim=64, num_layers=3).to(device)
    lightgcn.load_state_dict(torch.load(os.path.join(CHECKPOINT_DIR, "lightgcn_danang.pt")))
    lightgcn.build_normalized_adj(train_pairs)
    lightgcn.eval()
    u_emb_lgcn, i_emb_lgcn = lightgcn.forward()

    # 2. Nạp Temporal GNN
    tgnn = TemporalGNN(
        num_users, num_items, coords=coords, category_ids=cat_ids,
        embedding_dim=64, time_dim=32, num_layers=3, use_time=True, use_spatial=True
    ).to(device)
    tgnn.load_state_dict(torch.load(os.path.join(CHECKPOINT_DIR, "temporal_gnn_danang.pt")))
    tgnn.build_normalized_adj(train_pairs)
    tgnn.eval()
    u_emb_tgnn, i_emb_tgnn = tgnn.get_graph_embeddings()

    K_list = [5, 10, 20]
    lgcn_hits = {k: 0 for k in K_list}
    lgcn_ndcg = {k: 0.0 for k in K_list}
    tgnn_hits = {k: 0 for k in K_list}
    tgnn_ndcg = {k: 0.0 for k in K_list}

    # Đánh giá trên từng event
    with torch.no_grad():
        for idx, (u, target_l, ts, hr, wd) in enumerate(test_events):
            # A. LightGCN Scores
            scores_lgcn = lightgcn.predict_for_user(u, u_emb_lgcn, i_emb_lgcn).numpy()
            for l_seen in range(num_items):
                if (u, l_seen) in train_seen:
                    scores_lgcn[l_seen] = -1e9
            top_lgcn = np.argsort(scores_lgcn)[::-1][:20]

            for k in K_list:
                if target_l in top_lgcn[:k]:
                    lgcn_hits[k] += 1
                    rank = np.where(top_lgcn[:k] == target_l)[0][0]
                    lgcn_ndcg[k] += 1.0 / math.log2(rank + 2)

            # B. Temporal GNN Scores tại đúng thời điểm (ts, hr, wd)
            scores_tgnn = tgnn.predict_for_user_at_time(u, ts, hr, wd, u_emb_tgnn, i_emb_tgnn).numpy()
            for l_seen in range(num_items):
                if (u, l_seen) in train_seen:
                    scores_tgnn[l_seen] = -1e9
            top_tgnn = np.argsort(scores_tgnn)[::-1][:20]

            for k in K_list:
                if target_l in top_tgnn[:k]:
                    tgnn_hits[k] += 1
                    rank = np.where(top_tgnn[:k] == target_l)[0][0]
                    tgnn_ndcg[k] += 1.0 / math.log2(rank + 2)

    N = float(len(test_events))
    print("\n" + "=" * 70)
    print(" KẾT QUẢ ĐÁNH GIÁ CHUẨN TIME-AWARE NEXT-POI RECOMMENDATION")
    print("=" * 70)
    print(f"{'Metric':<16} | {'LightGCN (Baseline)':<20} | {'Temporal GNN (Proposed)':<22} | {'Cải thiện (Δ%)':<12}")
    print("-" * 75)

    comparison_results = []
    for k in K_list:
        # Recall@K / HitRate@K
        m_name = f"HitRate@{k}"
        b_val = (lgcn_hits[k] / N) * 100
        p_val = (tgnn_hits[k] / N) * 100
        diff = ((p_val - b_val) / b_val * 100) if b_val > 0 else 0.0
        sign = "+" if diff >= 0 else ""
        print(f"{m_name:<16} | {b_val:>18.2f}% | {p_val:>20.2f}% | {sign}{diff:>10.2f}%")
        comparison_results.append({"Metric": m_name, "LightGCN": b_val, "Temporal_GNN": p_val, "Diff": f"{sign}{diff:.2f}%"})

        # NDCG@K
        m_ndcg = f"NDCG@{k}"
        b_ndcg = (lgcn_ndcg[k] / N) * 100
        p_ndcg = (tgnn_ndcg[k] / N) * 100
        diff_n = ((p_ndcg - b_ndcg) / b_ndcg * 100) if b_ndcg > 0 else 0.0
        sign_n = "+" if diff_n >= 0 else ""
        print(f"{m_ndcg:<16} | {b_ndcg:>18.2f}% | {p_ndcg:>20.2f}% | {sign_n}{diff_n:>10.2f}%")
        comparison_results.append({"Metric": m_ndcg, "LightGCN": b_ndcg, "Temporal_GNN": p_ndcg, "Diff": f"{sign_n}{diff_n:.2f}%"})

    # Precision@10
    b_p10 = (lgcn_hits[10] / (N * 10)) * 100
    p_p10 = (tgnn_hits[10] / (N * 10)) * 100
    diff_p = ((p_p10 - b_p10) / b_p10 * 100) if b_p10 > 0 else 0.0
    sign_p = "+" if diff_p >= 0 else ""
    print(f"{'Precision@10':<16} | {b_p10:>18.2f}% | {p_p10:>20.2f}% | {sign_p}{diff_p:>10.2f}%")
    comparison_results.append({"Metric": "Precision@10", "LightGCN": b_p10, "Temporal_GNN": p_p10, "Diff": f"{sign_p}{diff_p:.2f}%"})

    print("=" * 70)
    out_file = os.path.join(os.path.dirname(CURRENT_DIR), "outputs", "time_aware_evaluation_danang.csv")
    pd.DataFrame(comparison_results).to_csv(out_file, index=False)
    print(f"Đã lưu kết quả tại: {out_file}")

if __name__ == "__main__":
    evaluate_next_poi()
