import os
import sys
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.manifold import TSNE
import torch

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(os.path.dirname(CURRENT_DIR), "outputs")
FIGURES_DIR = os.path.join(OUTPUT_DIR, "figures")
CHECKPOINT_DIR = os.path.join(OUTPUT_DIR, "checkpoints")
os.makedirs(FIGURES_DIR, exist_ok=True)

from models.temporal_gnn import TemporalGNN

def plot_all_charts():
    print("=" * 70)
    print(" KHỞI TẠO BIỂU ĐỒ KHOA HỌC XUẤT SẮC (PUBLICATION-GRADE FIGURES)")
    print("=" * 70)

    # -------------------------------------------------------------
    # BIỂU ĐỒ 1: BẢNG SO SÁNH CÁC CHỈ SỐ HỌC THUẬT (GROUPED BAR CHART)
    # -------------------------------------------------------------
    print("-> Đang vẽ Biểu đồ 1: So sánh hiệu năng LightGCN vs TAS-GNN...")
    csv_eval = os.path.join(OUTPUT_DIR, "time_aware_evaluation_danang.csv")
    if os.path.exists(csv_eval):
        df_eval = pd.read_csv(csv_eval)
        # Lọc các chỉ số chính
        metrics = ["HitRate@5", "HitRate@10", "HitRate@20", "NDCG@5", "NDCG@10", "NDCG@20"]
        df_plot = df_eval[df_eval["Metric"].isin(metrics)].set_index("Metric").reindex(metrics)

        x = np.arange(len(metrics))
        width = 0.35

        plt.figure(figsize=(10, 5), dpi=300)
        plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")
        
        bars1 = plt.bar(x - width/2, df_plot["LightGCN"], width, label="LightGCN (SIGIR 2020 Baseline)", color="#4A90E2", edgecolor="black", linewidth=0.8)
        bars2 = plt.bar(x + width/2, df_plot["Temporal_GNN"], width, label="TAS-GNN (Proposed Model)", color="#E94E77", edgecolor="black", linewidth=0.8)

        plt.ylabel("Phần trăm (%)", fontsize=12, fontweight="bold")
        plt.title("So Sánh Hiệu Năng Gợi Ý POI: LightGCN vs. TAS-GNN (Đà Nẵng Dataset)", fontsize=13, fontweight="bold", pad=12)
        plt.xticks(x, metrics, fontsize=11, fontweight="bold")
        plt.legend(frameon=True, fontsize=10, loc="upper left")
        plt.ylim(0, max(df_plot["Temporal_GNN"]) * 1.25)

        # Ghi giá trị trên đầu cột
        for bar in bars1:
            yval = bar.get_height()
            plt.text(bar.get_x() + bar.get_width()/2.0, yval + 0.3, f"{yval:.1f}%", ha='center', va='bottom', fontsize=8)
        for bar in bars2:
            yval = bar.get_height()
            plt.text(bar.get_x() + bar.get_width()/2.0, yval + 0.3, f"{yval:.1f}%", ha='center', va='bottom', fontsize=8, fontweight="bold", color="#B71C1C")

        chart1_path = os.path.join(FIGURES_DIR, "performance_comparison_bar.png")
        plt.tight_layout()
        plt.savefig(chart1_path)
        plt.close()
        print(f"   Đã lưu: {chart1_path}")

    # -------------------------------------------------------------
    # BIỂU ĐỒ 2: ABLATION STUDY (BÓC TÁCH THÀNH PHẦN)
    # -------------------------------------------------------------
    print("-> Đang vẽ Biểu đồ 2: Ablation Study...")
    csv_abl = os.path.join(OUTPUT_DIR, "ablation_study_danang.csv")
    if os.path.exists(csv_abl):
        df_abl = pd.read_csv(csv_abl)
        plt.figure(figsize=(9, 4.5), dpi=300)
        
        labels = [
            "Full TAS-GNN\n(Proposed)",
            "w/o Time\n(No Time Embed)",
            "w/o Spatial\n(No GPS Coord)",
            "LightGCN\n(Static Graph)"
        ]
        colors = ["#2ECC71", "#E74C3C", "#F39C12", "#3498DB"]
        bars = plt.bar(labels, df_abl["HitRate@10"], color=colors, width=0.5, edgecolor="black", linewidth=0.8)

        plt.ylabel("HitRate@10 (%)", fontsize=12, fontweight="bold")
        plt.title("Nghiên Cứu Bóc Tách Thành Phần (Ablation Study) Trên Tập Đà Nẵng", fontsize=13, fontweight="bold", pad=12)
        plt.ylim(0, max(df_abl["HitRate@10"]) * 1.3)
        plt.grid(axis='y', linestyle='--', alpha=0.7)

        for bar in bars:
            yval = bar.get_height()
            plt.text(bar.get_x() + bar.get_width()/2.0, yval + 0.3, f"{yval:.2f}%", ha='center', va='bottom', fontsize=10, fontweight="bold")

        chart2_path = os.path.join(FIGURES_DIR, "ablation_study_chart.png")
        plt.tight_layout()
        plt.savefig(chart2_path)
        plt.close()
        print(f"   Đã lưu: {chart2_path}")

    # -------------------------------------------------------------
    # BIỂU ĐỒ 3: t-SNE PHÂN CỤM KHÔNG GIAN THỜI GIAN (24 GIỜ TRONG NGÀY)
    # -------------------------------------------------------------
    print("-> Đang vẽ Biểu đồ 3: t-SNE 2D Temporal Clustering (24 Giờ)...")
    # Tải model để lấy vector nhúng thời gian
    tgnn_pt = os.path.join(CHECKPOINT_DIR, "temporal_gnn_danang.pt")
    if os.path.exists(tgnn_pt):
        # Tạo vector 24 giờ
        hours = torch.arange(24, dtype=torch.long)
        ts_sim = torch.full((24,), 1689400000.0, dtype=torch.float32)
        wd_sim = torch.zeros(24, dtype=torch.long) # Thứ 2

        # Tải mô hình
        tgnn = TemporalGNN(1500, 996, embedding_dim=64, time_dim=32)
        tgnn.load_state_dict(torch.load(tgnn_pt))
        tgnn.eval()

        with torch.no_grad():
            time_vectors = tgnn.time_encoder(ts_sim, hours, wd_sim).numpy() # (24, 32)

        # Giảm chiều bằng t-SNE (max_iter tương thích scikit-learn mới)
        tsne = TSNE(n_components=2, perplexity=5, random_state=42, max_iter=1000)
        embedded_2d = tsne.fit_transform(time_vectors)

        plt.figure(figsize=(8, 6), dpi=300)
        
        # Gán nhãn nhóm giờ
        # Sáng (06-09): Vàng cam
        # Trưa (11-13): Đỏ cam
        # Chiều (14-17): Xanh lá
        # Tối (18-23): Xanh dương đậm
        # Đêm (00-05): Tím
        group_colors = []
        for h in range(24):
            if 6 <= h <= 9:
                group_colors.append("#F39C12") # Sáng
            elif 11 <= h <= 13:
                group_colors.append("#E74C3C") # Trưa
            elif 14 <= h <= 17:
                group_colors.append("#27AE60") # Chiều
            elif 18 <= h <= 23:
                group_colors.append("#2980B9") # Tối
            else:
                group_colors.append("#8E44AD") # Đêm

        plt.scatter(embedded_2d[:, 0], embedded_2d[:, 1], c=group_colors, s=180, edgecolors="black", linewidth=1.2, alpha=0.9)

        for h in range(24):
            plt.annotate(
                f"{h:02d}:00",
                (embedded_2d[h, 0] + 0.8, embedded_2d[h, 1] + 0.8),
                fontsize=9,
                fontweight="bold"
            )

        # Legend thủ công
        legend_elements = [
            plt.Line2D([0], [0], marker='o', color='w', label='Sáng (06h - 09h: Cafe/Sáng)', markerfacecolor='#F39C12', markersize=10),
            plt.Line2D([0], [0], marker='o', color='w', label='Trưa (11h - 13h: Ăn trưa)', markerfacecolor='#E74C3C', markersize=10),
            plt.Line2D([0], [0], marker='o', color='w', label='Chiều (14h - 17h: Biển/Thắng cảnh)', markerfacecolor='#27AE60', markersize=10),
            plt.Line2D([0], [0], marker='o', color='w', label='Tối (18h - 23h: Chợ đêm/Sông Hàn/Bar)', markerfacecolor='#2980B9', markersize=10),
            plt.Line2D([0], [0], marker='o', color='w', label='Đêm (00h - 05h: Nghỉ ngơi)', markerfacecolor='#8E44AD', markersize=10),
        ]
        plt.legend(handles=legend_elements, loc="upper right", frameon=True, fontsize=9)
        plt.title("Biểu Diễn t-SNE Không Gian Vector Nhúng Thời Gian (24 Khung Giờ)", fontsize=12, fontweight="bold", pad=12)
        plt.xlabel("Chiều t-SNE 1", fontsize=10)
        plt.ylabel("Chiều t-SNE 2", fontsize=10)
        plt.grid(True, linestyle=":", alpha=0.6)

        chart3_path = os.path.join(FIGURES_DIR, "tsne_temporal_clusters.png")
        plt.tight_layout()
        plt.savefig(chart3_path)
        plt.close()
        print(f"   Đã lưu: {chart3_path}")

    print("\n" + "=" * 70)
    print("✅ HOÀN TẤT VẼ VÀ XUẤT TOÀN BỘ 3 BIỂU ĐỒ KHOA HỌC RA THƯ MỤC:")
    print(f"   {FIGURES_DIR}")
    print("=" * 70)

if __name__ == "__main__":
    plot_all_charts()
