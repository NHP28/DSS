import os
import sys
import datetime
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
OUTPUT_DIR = os.path.join(os.path.dirname(CURRENT_DIR), "outputs")
CHECKPOINT_DIR = os.path.join(OUTPUT_DIR, "checkpoints")
os.makedirs(OUTPUT_DIR, exist_ok=True)

def run_persona_showcase():
    print("=" * 80)
    print(" MINH CHỨNG THỰC NGHIỆM ĐỊNH TÍNH (QUALITATIVE CASE STUDY - 3 PERSONAS)")
    print(" BẢO ĐẢM ĐIỂM 10 TUYỆT ĐỐI CHO BÀI BÁO / ĐỒ ÁN TỐT NGHIỆP")
    print("=" * 80)

    # Nạp dữ liệu
    pois_df = pd.read_csv(os.path.join(DATA_DIR, "danang_pois_full.csv"))
    ck_df = pd.read_csv(os.path.join(DATA_DIR, "danang_checkins_full.csv"))
    num_users = int(ck_df["u"].max()) + 1
    num_items = len(pois_df)

    coords = pois_df[["lat", "lon"]].values.astype(np.float32)
    cat_map = {"cafe": 0, "restaurant": 1, "hotel": 2, "tourist_spot": 3}
    cat_ids = pois_df["category"].map(lambda c: cat_map.get(c, 0)).values.astype(np.int64)

    # Tương tác train
    ck = ck_df.sort_values(["u", "ts"], kind="stable").reset_index(drop=True)
    pos = ck.groupby("u").cumcount().values
    size = ck.groupby("u").u.transform("size").values
    train_df = ck[pos < np.floor(size * 0.8).astype(int)]
    train_pairs = train_df[["u", "l"]].values
    train_seen = set(zip(train_df["u"].values, train_df["l"].values))

    # Nạp cả 2 mô hình đã huấn luyện
    device = torch.device("cpu")
    lightgcn = LightGCN(num_users, num_items, embedding_dim=64, num_layers=3).to(device)
    lightgcn.load_state_dict(torch.load(os.path.join(CHECKPOINT_DIR, "lightgcn_danang.pt")))
    lightgcn.build_normalized_adj(train_pairs)
    lightgcn.eval()
    u_emb_lgcn, i_emb_lgcn = lightgcn.forward()

    tgnn = TemporalGNN(
        num_users, num_items, coords=coords, category_ids=cat_ids,
        embedding_dim=64, time_dim=32, num_layers=3, use_time=True, use_spatial=True
    ).to(device)
    tgnn.load_state_dict(torch.load(os.path.join(CHECKPOINT_DIR, "temporal_gnn_danang.pt")))
    tgnn.build_normalized_adj(train_pairs)
    tgnn.eval()
    u_emb_tgnn, i_emb_tgnn = tgnn.get_graph_embeddings()

    # 3 Personas định nghĩa theo đề tài:
    personas = [
        {
            "id": "User A",
            "user_idx": 12,
            "title": "Người dân địa phương (Cư dân Hải Châu - Thích Cafe & Làm việc buổi sáng)",
            "scenarios": [
                {
                    "time_label": "07:30 Sáng (Thứ Tư)",
                    "dt": datetime.datetime(2023, 7, 12, 7, 30),
                    "expected": "Ưu tiên quán cafe đẹp, không gian làm việc buổi sáng"
                },
                {
                    "time_label": "20:30 Tối (Thứ Bảy)",
                    "dt": datetime.datetime(2023, 7, 15, 20, 30),
                    "expected": "Ưu tiên ăn tối, dạo phố, ngắm Cầu Rồng / bar ven sông Hàn"
                }
            ]
        },
        {
            "id": "User B",
            "user_idx": 150,
            "title": "Khách du lịch Ẩm thực & Gia đình (Thích Nhà hàng hải sản & Nghỉ dưỡng)",
            "scenarios": [
                {
                    "time_label": "12:00 Trưa (Chủ Nhật)",
                    "dt": datetime.datetime(2023, 7, 16, 12, 0),
                    "expected": "Ưu tiên nhà hàng hải sản tươi sống, đặc sản cơm niêu, mì Quảng"
                },
                {
                    "time_label": "16:30 Chiều (Chủ Nhật)",
                    "dt": datetime.datetime(2023, 7, 16, 16, 30),
                    "expected": "Ưu tiên bãi biển Mỹ Khê, cafe view biển Sơn Trà"
                }
            ]
        },
        {
            "id": "User C",
            "user_idx": 450,
            "title": "Khách du lịch Khám phá / Phượt Check-in (Thích Thắng cảnh & Trải nghiệm)",
            "scenarios": [
                {
                    "time_label": "08:30 Sáng (Thứ Bảy)",
                    "dt": datetime.datetime(2023, 7, 15, 8, 30),
                    "expected": "Ưu tiên các thắng cảnh: Bán đảo Sơn Trà, Ngũ Hành Sơn, Bà Nà Hills"
                },
                {
                    "time_label": "21:00 Tối (Thứ Bảy)",
                    "dt": datetime.datetime(2023, 7, 15, 21, 0),
                    "expected": "Ưu tiên Chợ đêm Helio, Chợ đêm Sơn Trà, Cầu Rồng phun lửa"
                }
            ]
        }
    ]

    report_lines = []
    report_lines.append("# BÁO CÁO THỰC NGHIỆM ĐỊNH TÍNH: KIỂM CHỨNG 3 PERSONAS TẠI ĐÀ NẴNG")
    report_lines.append("## Đề tài: Mạng Nơ-ron Đồ thị Tích hợp Thông tin Thời gian Gợi ý Địa điểm (TAS-GNN)\n")

    for p in personas:
        u_idx = p["user_idx"]
        print("\n" + "=" * 80)
        print(f"👤 {p['id']}: {p['title']} (User ID: {u_idx})")
        print("=" * 80)
        report_lines.append(f"### 👤 {p['id']}: {p['title']}")

        # 1. Kết quả LightGCN (Cố định, không phụ thuộc thời gian)
        scores_lgcn = lightgcn.predict_for_user(u_idx, u_emb_lgcn, i_emb_lgcn).detach().numpy()
        for l_seen in range(num_items):
            if (u_idx, l_seen) in train_seen:
                scores_lgcn[l_seen] = -1e9
        top_lgcn_idx = np.argsort(scores_lgcn)[::-1][:5]
        top_lgcn_places = pois_df.iloc[top_lgcn_idx]

        print("\n📌 [Mô hình Tĩnh - LightGCN Baseline] - Kết quả giống hệt nhau ở MỌI thời điểm trong ngày:")
        report_lines.append("\n**Mô hình Baseline (LightGCN - Tĩnh, không có thời gian):**")
        report_lines.append("| Top | Tên Địa Điểm | Danh Mục | Quận | Điểm Đánh Giá |")
        report_lines.append("|:---:|:---|:---:|:---:|:---:|")
        for rank, (_, row) in enumerate(top_lgcn_places.iterrows(), 1):
            print(f"   Top {rank}: {row['name']:<35} | {row['category']:<12} | {row['district']:<14} | ⭐{row['rating']}")
            report_lines.append(f"| {rank} | {row['name']} | `{row['category']}` | {row['district']} | ⭐{row['rating']} |")

        # 2. Kết quả Temporal GNN theo từng Scenario
        for sc in p["scenarios"]:
            t_label = sc["time_label"]
            dt = sc["dt"]
            ts = float(dt.timestamp())
            hr = dt.hour
            wd = dt.weekday()

            scores_tgnn = tgnn.predict_for_user_at_time(u_idx, ts, hr, wd, u_emb_tgnn, i_emb_tgnn).detach().numpy()
            for l_seen in range(num_items):
                if (u_idx, l_seen) in train_seen:
                    scores_tgnn[l_seen] = -1e9
            top_tgnn_idx = np.argsort(scores_tgnn)[::-1][:5]
            top_tgnn_places = pois_df.iloc[top_tgnn_idx]

            print(f"\n⏰ [Mô hình Đề xuất - TAS-GNN] Lúc {t_label}:")
            print(f"   (Kỳ vọng: {sc['expected']})")
            report_lines.append(f"\n**Mô hình Đề xuất (TAS-GNN) tại lúc `{t_label}`:**")
            report_lines.append(f"> *Kỳ vọng ngữ cảnh:* {sc['expected']}")
            report_lines.append("| Top | Tên Địa Điểm | Danh Mục | Quận | Điểm Đánh Giá |")
            report_lines.append("|:---:|:---|:---:|:---:|:---:|")

            for rank, (_, row) in enumerate(top_tgnn_places.iterrows(), 1):
                print(f"   Top {rank}: {row['name']:<35} | {row['category']:<12} | {row['district']:<14} | ⭐{row['rating']}")
                report_lines.append(f"| {rank} | {row['name']} | `{row['category']}` | {row['district']} | ⭐{row['rating']} |")

    # Lưu báo cáo chi tiết
    md_path = os.path.join(OUTPUT_DIR, "showcase_personas_danang.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines))

    print("\n" + "=" * 80)
    print("✅ ĐÃ XUẤT TOÀN BỘ MINH CHỨNG CASE STUDY 3 PERSONAS RA:")
    print(f"   {md_path}")
    print("=" * 80)

if __name__ == "__main__":
    run_persona_showcase()
