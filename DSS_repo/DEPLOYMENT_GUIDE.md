> **Tài liệu của phiên bản cũ.** Số liệu và kiến trúc hiện hành xem [docs/TRA_LOI_GOP_Y.md](docs/TRA_LOI_GOP_Y.md) và [docs/RUNNING.md](docs/RUNNING.md).

# 📘 HƯỚNG DẪN TRIỂN KHAI HỆ THỐNG GỢI Ý ĐỊA ĐIỂM (L-DSS)
## Time-Aware Spatio-Temporal GNN (TAS-GNN) kết hợp AHP + TOPSIS

> **Đề tài:** Nghiên cứu và phát triển mô hình mạng nơ-ron đồ thị tích hợp thông tin thời gian cho hệ thống gợi ý địa điểm cá nhân hóa (TAS-GNN) kết hợp hỗ trợ ra quyết định đa tiêu chí (AHP - TOPSIS).  
> **Khu vực thực nghiệm:** TP. Đà Nẵng, Việt Nam.

---

## 📑 Mục lục

1. [Kiến trúc tổng thể hệ thống](#1-kiến-trúc-tổng-thể-hệ-thống)
2. [Yêu cầu môi trường & Cài đặt](#2-yêu-cầu-môi-trường--cài-đặt)
3. [Cấu trúc thư mục dự án](#3-cấu-trúc-thư-mục-dự-án)
4. [Dữ liệu thực nghiệm (Đà Nẵng Dataset)](#4-dữ-liệu-thực-nghiệm-đà-nẵng-dataset)
5. [Quy trình huấn luyện mô hình (Training Pipeline)](#5-quy-trình-huấn-luyện-mô-hình-training-pipeline)
6. [Quy trình kiểm thử & Thực nghiệm khoa học](#6-quy-trình-kiểm-thử--thực-nghiệm-khoa-học)
7. [Triển khai FastAPI Server & REST APIs](#7-triển-khai-fastapi-server--rest-apis)
8. [Tích hợp với NestJS Backend API](#8-tích-hợp-với-nestjs-backend-api)
9. [Giao diện Web Demo](#9-giao-diện-web-demo)
10. [Xử lý lỗi thường gặp (Troubleshooting)](#10-xử-lý-lỗi-thường-gặp-troubleshooting)

---

## 1. Kiến trúc tổng thể hệ thống

Hệ thống được thiết kế theo mô hình 2 tầng (Two-Stage Pipeline):
1. **Stage 1 - Candidate Retrieval (Spatio-Temporal GNN / TAS-GNN):** Mạng nơ-ron đồ thị tích hợp mã hóa thời gian liên tục (Bochner Fourier Time Embedding), không gian GPS và cơ chế Dynamic Temporal Gating để sinh Top-50 ứng viên phù hợp nhất với ngữ cảnh thời gian và vị trí của người dùng.
2. **Stage 2 - Multi-Criteria Decision Support (AHP + TOPSIS):** Động cơ ra quyết định đa tiêu chí cân đối 5 chiều thông tin:
   - $C_1$: Khoảng cách GPS (Cost - tối thiểu hóa)
   - $C_2$: Đánh giá Rating (Benefit - tối đa hóa)
   - $C_3$: Chi phí trung bình (Cost - tối thiểu hóa)
   - $C_4$: Điểm sở thích AI từ GNN (Benefit - tối đa hóa)
   - $C_5$: Độ phổ biến Popularity (Benefit - tối đa hóa)
   - Kiểm tra tỷ số nhất quán ma trận so sánh cặp $CR \le 0.10$ (Saaty). Phân tầng theo danh mục (Category-stratified) tránh phạt chênh lệch giá giữa khách sạn và quán cafe.

---

## 2. Yêu cầu môi trường & Cài đặt

### 2.1. Yêu cầu hệ thống
- **Hệ điều hành:** Windows 10/11, Ubuntu 20.04+, macOS.
- **Python:** Khuyến nghị Python 3.10 hoặc 3.11.
- **Phần cứng:** Tối thiểu 8GB RAM. Có thể chạy hoàn toàn trên CPU hoặc GPU (NVIDIA CUDA).

### 2.2. Các bước cài đặt chi tiết

```bash
# 1. Truy cập thư mục dự án
cd f:\dss\DSS_repo

# 2. Khởi tạo môi trường ảo Python
python -m venv venv

# Kích hoạt môi trường ảo:
# Trên Windows:
venv\Scripts\activate
# Trên Linux/macOS:
# source venv/bin/activate

# 3. Nâng cấp pip và cài đặt dependencies
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Nếu muốn tận dụng GPU CUDA (tùy chọn):
```bash
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
```

---

## 3. Cấu trúc thư mục dự án

```text
DSS_repo/
├── data/
│   ├── danang/                         # Dữ liệu thực nghiệm Đà Nẵng
│   │   ├── danang_pois_full.csv        # 996 POIs (tọa độ, danh mục, giá, rating...)
│   │   ├── danang_checkins_full.csv    # 36.210 check-in (timestamp, user, poi, hour, day_of_week)
│   │   ├── danang_social_full.csv      # 7.765 quan hệ bạn bè giữa users
│   │   └── metadata.json               # Metadata mô tả dataset
│   └── processed/                      # Dữ liệu Gowalla (phục vụ đối sánh CPR)
│
├── src/
│   ├── models/
│   │   ├── temporal_gnn.py             # ★ Mô hình TAS-GNN (Spatio-Temporal GNN)
│   │   └── lightgcn.py                 # Mô hình baseline LightGCN (SIGIR 2020)
│   ├── mcdm.py                         # ★ Động cơ AHP & Category-stratified TOPSIS
│   ├── train_compare.py                # Script huấn luyện & so sánh TAS-GNN vs LightGCN
│   ├── evaluate_time_aware.py          # Đánh giá chuẩn Next-POI thời gian thực
│   ├── ablation_study.py               # Thí nghiệm bóc tách thành phần (Ablation)
│   ├── baselines_check.py              # Đánh giá các baselines cổ điển (User-CF, USG, Friend-CF)
│   ├── showcase_personas.py            # Kiểm chứng định tính trên 3 nhóm personas
│   ├── plot_scientific_charts.py       # Xuất biểu đồ nghiên cứu khoa học
│   └── baselines/                      # Triển khai các thuật toán baseline
│
├── outputs/
│   ├── checkpoints/                    # Lưu model weights (.pt)
│   │   ├── lightgcn_danang.pt
│   │   └── temporal_gnn_danang.pt
│   ├── figures/                        # Hình ảnh biểu đồ phân tích
│   └── *.csv                           # File kết quả thực nghiệm chi tiết
│
├── server.py                           # ★ FastAPI Server (L-DSS Engine + NestJS API)
├── FE/                                 # Frontend Next.js độc lập
│   └── public/demo_danang.html          # Demo bản đồ HTML cũ
├── app.py                              # Streamlit GUI Demo (tùy chọn)
├── run_app.bat                         # Batch file khởi chạy nhanh
└── requirements.txt                    # Thư viện phụ thuộc
```

---

## 4. Dữ liệu thực nghiệm (Đà Nẵng Dataset)

- **996 POIs thực địa** phân bố tại các quận Hải Châu, Sơn Trà, Ngũ Hành Sơn, Liên Chiểu... gồm 4 nhóm:
  - `cafe`: 304 điểm
  - `hotel`: 295 điểm
  - `restaurant`: 293 điểm
  - `tourist_spot`: 104 điểm
- **36.210 Check-ins** của 1.500 người dùng trong năm 2023.
- **Chiến lược chia dữ liệu (Temporal Split):** 70% Train, 10% Tune, 20% Test phân chia theo trình tự thời gian cho từng user (ngăn chặn rò rỉ dữ liệu tương lai).

---

## 5. Quy trình huấn luyện mô hình (Training Pipeline)

Nếu muốn huấn luyện lại từ đầu hoặc cập nhật checkpoint:

```bash
python src/train_compare.py
```

**Chi tiết quá trình huấn luyện:**
- Huấn luyện song song **LightGCN** và **TAS-GNN** với hàm mất mát Bayesian Personalized Ranking (BPR Loss).
- Tự động sinh batch âm (negative sampling) và học ma trận kề chuẩn hóa đối xứng $\hat{A} = D^{-1/2} A D^{-1/2}$.
- Sau khi kết thúc 15 epochs, checkpoint sẽ tự động được lưu tại:
  - `outputs/checkpoints/lightgcn_danang.pt`
  - `outputs/checkpoints/temporal_gnn_danang.pt`
- Xuất file so sánh định lượng: `outputs/experiment_comparison_danang.csv`.

---

## 6. Quy trình kiểm thử & Thực nghiệm khoa học

Các script tái lập kết quả báo cáo khoa học:

### 6.1. Đánh giá chuẩn Next-POI thời gian thực (Time-Aware Evaluation)
```bash
python src/evaluate_time_aware.py
```
*Đánh giá chính xác sự kiện test $(u, l, t)$ tại đúng khung giờ $t$ xảy ra.*

### 6.2. Thí nghiệm bóc tách thành phần (Ablation Study)
```bash
python src/ablation_study.py
```
*Đánh giá vai trò của Temporal Encoding và Spatial Embedding đối với hiệu năng mô hình.*

### 6.3. Kiểm thử trên các Personas điển hình
```bash
python src/showcase_personas.py
```
*Mô phỏng sự thay đổi gợi ý theo chu kỳ ngày/đêm của cư dân Hải Châu và khách du lịch Sơn Trà.*

### 6.4. Xuất biểu đồ khoa học
```bash
python src/plot_scientific_charts.py
```
*Vẽ biểu đồ so sánh mô hình, t-SNE cụm thời gian và lưu vào `outputs/figures/`.*

---

## 7. Triển khai FastAPI Server & REST APIs

### 7.1. Khởi chạy Server

```bash
python server.py
```

Server sẽ lắng nghe tại `http://localhost:8000`:
- **Swagger Docs:** `http://localhost:8000/docs`
- **ReDoc:** `http://localhost:8000/redoc`
- **Health Check:** `http://localhost:8000/health`

Frontend chạy ở tiến trình riêng, từ terminal khác:

```powershell
cd F:\dss\DSS_repo\FE
npm.cmd ci
npm.cmd run dev
```

Demo HTML cũ: `http://127.0.0.1:3000/demo_danang.html`.
FastAPI chỉ phục vụ API; `/` trả thông tin JSON, không đọc/nhúng HTML.
Giao diện Next.js chính tại `http://127.0.0.1:3000` dùng NestJS và `ml.serve`;
xem [hướng dẫn chạy kiến trúc mới](docs/RUNNING.md).

### 7.2. Các Endpoints cốt lõi

#### 1. Gợi ý cá nhân hóa tích hợp MCDM: `POST /api/v1/danang/recommend_dss`
Gửi yêu cầu kèm ngữ cảnh vị trí, thời gian và thiết lập AHP.
```json
{
  "userId": 12,
  "hour": 8,
  "dayOfWeek": 2,
  "userLat": 16.068,
  "userLon": 108.223,
  "topK": 10,
  "category": "cafe",
  "ahpPreset": "balanced",
  "stratifyByCategory": true
}
```
**Các preset AHP hỗ trợ:**
- `"balanced"`: Cân đối giữa khoảng cách, rating và sở thích AI ($CR \approx 0.01$).
- `"ai_centric"`: Đặt trọng số cao nhất cho mô hình học sâu TAS-GNN ($CR \approx 0.02$).
- `"proximity"`: Ưu tiên địa điểm gần nhất với tọa độ người dùng.
- `"budget"`: Ưu tiên các địa điểm có mức giá hợp lý.

#### 2. Endpoint chuẩn cho NestJS Backend: `POST /api/cpr/score`
Tính điểm sở thích thời gian thực ($C_4$) cho danh sách ứng viên từ cơ sở dữ liệu:
```json
{
  "userId": 12,
  "hourOfDay": 12,
  "candidates": [
    {
      "id": 10,
      "name": "Bếp Cuốn Đà Nẵng",
      "latitude": 16.059,
      "longitude": 108.242,
      "categoryId": 1,
      "rating": 4.6,
      "priceAvg": 80000,
      "popularity": 85
    }
  ]
}
```

---

## 8. Tích hợp với NestJS Backend API

Trong kiến trúc Microservices, FastAPI đóng vai trò là **AI Inference Engine**:
1. NestJS truy vấn các địa điểm trong bán kính tìm kiếm từ MySQL/PostgreSQL/PostGIS.
2. NestJS gọi `POST http://localhost:8000/api/cpr/score` để nhận điểm $C_4$ từ mô hình TAS-GNN.
3. NestJS hoặc FastAPI thực thi AHP-TOPSIS để trả về danh sách xếp hạng cuối cùng cho Mobile App/Web Frontend.

---

## 9. Giao diện Web Demo

Hệ thống tích hợp sẵn 2 giao diện phục vụ bảo vệ/thuyết minh đề tài:

1. **Bản đồ trực quan Đà Nẵng (Leaflet / HTML5):**
   - Chạy FE và `server.py` riêng; truy cập `http://127.0.0.1:3000/demo_danang.html`.
   - Hỗ trợ chọn người dùng, giả lập giờ trong ngày (sáng/trưa/chiều/tối), tùy chỉnh ma trận AHP và hiển thị biểu đồ radar TOPSIS.

2. **Streamlit Analysis Dashboard (Gowalla & CPR):**
   ```bash
   streamlit run app.py
   # hoặc click file run_app.bat trên Windows
   ```

---

## 10. Xử lý lỗi thường gặp (Troubleshooting)

| Vấn đề | Nguyên nhân | Cách khắc phục |
|:---|:---|:---|
| `FileNotFoundError: checkpoints/...pt` | Chưa có file trọng số mô hình | Chạy `python src/train_compare.py` để sinh checkpoints. |
| `Address already in use: 8000` | Cổng 8000 đang bị chiếm | Chạy uvicorn trên cổng khác: `uvicorn server:app --port 8001` |
| `UnicodeEncodeError` trên PowerShell/CMD | Mã hóa console Windows chưa đặt UTF-8 | Đã có patch tự động trong code; hoặc gõ `chcp 65001` trước khi chạy. |
| Người dùng mới (Cold-start) | `userId` chưa từng xuất hiện trong tập train | Server tự động kích hoạt fallback dựa trên phân bố giờ check-in và popularity. |

