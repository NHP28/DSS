# L-DSS: Time-Aware POI Recommendation & Location-Based Decision Support System (ST-GNN + AHP + TOPSIS)

> **Hệ thống Gợi ý Địa điểm Cá nhân hóa theo Thời gian thực và Hỗ trợ Ra quyết định Đa tiêu chí tại TP. Đà Nẵng**  
> *Đồ án / Báo cáo Nghiên cứu Ứng dụng AI, Graph Neural Network & Hệ Hỗ trợ Ra Quyết định (DSS)*

[![Python 3.11](https://img.shields.io/badge/Python-3.11-blue.svg)](https://www.python.org/)
[![PyTorch](https://img.shields.io/badge/PyTorch-2.0+-ee4c2c.svg)](https://pytorch.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688.svg)](https://fastapi.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## 📌 1. Giới Thiệu & Đặt Vấn Đề

Hệ thống gợi ý POI truyền thống (như Collaborative Filtering, Matrix Factorization hay LightGCN tĩnh) thường bộc lộ hạn chế lớn:
1. **Bỏ qua ngữ cảnh thời gian động (Temporal Dynamics):** Nhu cầu của du khách/cư dân thay đổi theo từng khung giờ sinh hoạt (07:30 sáng tìm cafe/ăn sáng; 12:00 trưa tìm quán cơm/ẩm thực; 16:30 chiều dạo biển/ngắm cảnh; 20:30 tối xem Cầu Rồng phun lửa, dạo phố đêm).
2. **Thiếu hỗ trợ ra quyết định đa tiêu chí (MCDM):** Điểm số sở thích AI đơn thuần chưa đủ để người dùng lựa chọn một địa điểm thực tế nếu không cân nhắc: khoảng cách di chuyển hiện tại, mức giá, đánh giá cộng đồng và độ phổ biến.

Dự án **L-DSS Đà Nẵng** giải quyết bài toán trên theo kiến trúc tích hợp 2 giai đoạn (Two-Stage Recommendation & Decision Framework):
* **Giai đoạn 1 (Candidate Generation):** Mô hình **Spatio-Temporal Graph Neural Network (ST-GNN / TAS-GNN)** học biểu diễn đồ thị tương tác người dùng - địa điểm kết hợp cơ chế Cổng điều phối thời gian (Temporal Gate) để chọn ra Top-50 ứng viên phù hợp nhất với ngữ cảnh thời gian truy vấn.
* **Giai đoạn 2 (Decision Support & Reranking):** Hệ hỗ trợ ra quyết định đa tiêu chí **MCDM (AHP + TOPSIS)** kết hợp 5 tiêu chí thực tế:
  * $C_1$: Khoảng cách địa lý GPS Haversine (Tiêu chí chi phí - Cost)
  * $C_2$: Điểm đánh giá thực tế Rating (Tiêu chí lợi ích - Benefit)
  * $C_3$: Mức giá trung bình Price (Tiêu chí chi phí - Cost)
  * $C_4$: **Điểm sở thích cá nhân hóa từ Spatio-Temporal GNN** (Tiêu chí lợi ích - Benefit)
  * $C_5$: Độ phổ biến cộng đồng Popularity (Tiêu chí lợi ích - Benefit)
  * Áp dụng **Phân tầng danh mục (Category-stratified TOPSIS)** để tránh hiện tượng chênh lệch thang giá giữa các nhóm dịch vụ (ví dụ: Khách sạn 500k-4tr so với Quán cafe 25k-60k).

---

## 🏗 2. Kiến Trúc Hệ Thống

```
DSS/
├── DSS_repo/                       # AI Engine & Web Demo L-DSS
│   ├── data/danang/                # 996 địa điểm thực tế từ OpenStreetMap & dữ liệu check-in Đà Nẵng
│   │   ├── danang_pois_full.csv    # Tọa độ, tên, danh mục (Cafe, Quán ăn, Thắng cảnh, Khách sạn)
│   │   └── danang_checkins_full.csv# Lịch sử tương tác có nhãn thời gian (ts, hour, day_of_week)
│   ├── outputs/
│   │   ├── checkpoints/            # Trọng số PyTorch (.pt) đã huấn luyện
│   │   │   ├── temporal_gnn_danang.pt # Model ST-GNN PyTorch
│   │   │   └── lightgcn_danang.pt     # Model LightGCN Baseline
│   │   └── baselines_benchmark_danang.csv # Kết quả đối soát khoa học với các baseline
│   ├── src/
│   │   ├── mcdm.py                 # Module AHP (Saaty CR <= 0.10) & Category-stratified TOPSIS
│   │   ├── baselines_check.py      # Kịch bản đối soát độc lập với các Heuristic mạnh
│   │   ├── models/
│   │   │   ├── temporal_gnn.py     # Spatio-Temporal GNN (Đã sửa triệt tiêu context & hỗ trợ GPS)
│   │   │   └── lightgcn.py         # LightGCN (SIGIR 2020)
│   │   ├── evaluate_time_aware.py  # Đánh giá time-aware next-POI
│   │   ├── train_compare.py        # Huấn luyện & đối sánh
│   │   └── showcase_personas.py    # Phân tích định tính 3 nhóm người dùng
│   ├── demo_danang.html            # Bản đồ số tương tác (Leaflet + Google Roadmap + AHP-TOPSIS Panel)
│   └── server.py                   # FastAPI Server tích hợp AHP-TOPSIS & endpoint CPR cho NestJS
│
├── BE_API/                         # Backend NestJS quản lý dữ liệu L-DSS (Drizzle ORM)
│   └── src/modules/dss/cpr/        # Tích hợp gọi sang FastAPI qua endpoint /api/cpr/score
│
├── Huong_Dan.docx                  # Thuyết minh báo cáo đồ án hoàn chỉnh chuẩn 5 chương
├── Huong_Dan.md                    # Bản Markdown của tài liệu hướng dẫn
├── requirements.txt                # Thư viện phụ thuộc
└── README.md                       # Tài liệu tổng quan
```

---

## 📊 3. Báo Cáo Đối Soát Thực Nghiệm Khoa Học (Da Nang Dataset)

Thực hiện đánh giá trên $6.811$ sự kiện kiểm thử theo thời gian (**Temporal Split**), che các địa điểm đã tương tác trong tập huấn luyện:

| Phương pháp | Loại mô hình | HR@5 | HR@10 | HR@20 | NDCG@5 | NDCG@10 |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **Phổ biến theo giờ** | Heuristic (Không học) | $7.22\%$ | $11.88\%$ | $18.40\%$ | $4.35\%$ | $5.83\%$ |
| **Giờ × Khoảng cách cuối train** | Heuristic (Không học) | $8.63\%$ | $13.12\%$ | $19.72\%$ | $5.31\%$ | $6.76\%$ |
| **Giờ × Khoảng cách liền trước** | Next-POI Heuristic | **$10.12\%$** | **$14.88\%$** | **$21.83\%$** | **$6.77\%$** | **$8.26\%$** |
| **LightGCN** | GNN Tĩnh (SIGIR '20) | $7.31\%$ | $11.36\%$ | $16.46\%$ | $4.96\%$ | $6.25\%$ |
| **ST-GNN-POI / TAS-GNN** | GNN Không - Thời gian | $7.39\%$ | $12.45\%$ | $18.56\%$ | $4.46\%$ | $6.09\%$ |

> **Nhận định khoa học:**
> 1. Quy luật thời gian và khoảng cách địa lý đóng vai trò tối quan trọng trong hành vi di chuyển đô thị. Tín hiệu *Khoảng cách từ vị trí check-in liền trước* đem lại hiệu quả vượt trội.
> 2. Đây là minh chứng thực tế cho hiện tượng mà bài báo *Dacrema et al. (RecSys 2019)* đã chỉ ra: các phương pháp heuristic đơn giản khai thác đúng tiên nghiệm vật lý (không gian - thời gian) có thể đạt kết quả cạnh tranh mạnh mẽ với các mô hình học sâu phức tạp.
> 3. Do đó, việc hệ thống tích hợp **L-DSS (AHP + TOPSIS)** để kết hợp cả điểm số nơ-ron AI ($C_4$) cùng khoảng cách tức thời ($C_1$), giá cả ($C_3$) và rating ($C_2$) là hướng tiếp cận toàn diện và sát thực tế nhất.

---

## 🚀 4. Hướng Dẫn Cài Đặt & Khởi Chạy

### Bước 1: Chuẩn bị môi trường Python
```bash
# Kích hoạt virtual environment
.\.venv\Scripts\activate

# Cài đặt thư viện cần thiết
pip install -r requirements.txt
```

### Bước 2: Khởi động Server AI & MCDM Engine
```bash
cd DSS_repo
python server.py
```
* **Swagger API Documentation:** [http://localhost:8000/docs](http://localhost:8000/docs)
* **Web Demo Bản Đồ Tương Tác:** [http://localhost:8000/demo](http://localhost:8000/demo)

### Bước 3: Chạy Kịch bản Đối soát Baseline độc lập
```bash
cd DSS_repo
python src/baselines_check.py
```

---

## 🔌 5. Danh Sách API Endpoints Chính

| Phương thức | Endpoint | Chức năng |
| :--- | :--- | :--- |
| `GET` | `/health` | Kiểm tra tình trạng server, model đã nạp và số lượng POI |
| `GET` | `/api/v1/danang/ahp_weights?preset=balanced` | Xem vector trọng số và chỉ số nhất quán Saaty $CR$ |
| `POST` | `/api/v1/danang/recommend` | Gợi ý POI theo thời gian thực (hỗ trợ cả Pure GNN và L-DSS) |
| `POST` | `/api/v1/danang/recommend_dss` | Toàn trình Hỗ trợ ra quyết định Đa tiêu chí (Top-50 GNN $\rightarrow$ AHP $\rightarrow$ Category TOPSIS) |
| `POST` | `/api/cpr/score` | **Endpoint kết nối NestJS BE_API:** Cung cấp điểm $C_4$ cho `cpr.service.ts`, chấm dứt hoàn toàn lỗi HTTP 404 |

---

## 📑 6. Đóng Góp & Tính Minh Bạch của Dữ Liệu
* **Danh mục POI:** $996$ địa điểm du lịch, quán ăn, cafe, khách sạn có thật tại các quận trung tâm TP. Đà Nẵng, thu thập từ OpenStreetMap (OSM) với tọa độ GPS chính xác.
* **Tương tác check-in:** Lịch sử check-in và phân bố rating/giá cả được mô phỏng bám sát hành vi sinh hoạt đô thị Đà Nẵng (Synthetic Urban Mobility LBSN Dataset).
* **Quyết định đa tiêu chí:** AHP kiểm tra độ nhất quán $CR = 0.0018 \le 0.10$ đạt chuẩn Saaty; TOPSIS phân tầng đảm bảo khách sạn không bị triệt tiêu điểm số trước cafe do chênh lệch thang giá.
