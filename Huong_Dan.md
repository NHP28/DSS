# TÀI LIỆU HƯỚNG DẪN THỰC HIỆN ĐỀ TÀI TỪ ĐẦU TỚI CUỐI
## HỆ THỐNG HỖ TRỢ RA QUYẾT ĐỊNH GỢI Ý ĐỊA ĐIỂM DỰA TRÊN VỊ TRÍ VÀ MẠNG NƠ-RON ĐỒ THỊ ĐỘNG THEO THỜI GIAN
**Tên tiếng Anh:** *Location-Based Decision Support System with Time-Aware Spatio-Temporal Graph Neural Networks (L-DSS & TAS-GNN)*  
**Khu vực thử nghiệm:** Thành phố Đà Nẵng, Việt Nam  
**Mã dự án:** `DSS_POIRS`

---

## MỤC LỤC
1. [Tổng Quan Đề Tài & Bài Toán Giải Quyết](#1-tổng-quan-đề-tài--bài-toán-giải-quyết)
2. [Kiến Trúc Tổng Thể Hệ Thống (End-to-End Architecture)](#2-kiến-trúc-tổng-thể-hệ-thống)
3. [Giai Đoạn 1: Thu Thập & Xử Lý Dữ Liệu Thực Địa Đà Nẵng](#3-giai-đoạn-1-thu-thập--xử-lý-dữ-liệu-thực-địa-đà-nẵng)
4. [Giai Đoạn 2: Xây Dựng & Huấn Luyện Mô Hình AI (TAS-GNN vs Baseline)](#4-giai-đoạn-2-xây-dựng--huấn-luyện-mô-hình-ai)
5. [Giai Đoạn 3: Tích Hợp Đa Tiêu Chí Hỗ Trợ Ra Quyết Định (MCDM: AHP + TOPSIS)](#5-giai-đoạn-3-tích-hợp-đa-tiêu-chí-mcdm-ahp--topsis)
6. [Giai Đoạn 4: Triển Khai Backend AI Service & Giao Diện Web Trực Quan](#6-giai-đoạn-4-triển-khai-backend-ai-service--giao-diện-web)
7. [Quy Trình Chạy Toàn Bộ Hệ Thống (Step-by-Step Runbook)](#7-quy-trình-chạy-toàn-bộ-hệ-thống)
8. [Cấu Trúc Đề Cương Báo Cáo Khóa Luận / Đồ Án Tốt Nghiệp](#8-cấu-trúc-đề-cương-báo-cáo-khóa-luận)

---

## 1. TỔNG QUAN ĐỀ TÀI & BÀI TOÁN GIẢI QUYẾT

### 1.1. Đặt Vấn Đề
Khi đến một thành phố du lịch như Đà Nẵng, người dùng đối mặt với **nghịch lý của sự lựa chọn (Choice Overload)**: có hàng nghìn quán cafe, nhà hàng, khách sạn và điểm tham quan. Việc lựa chọn một địa điểm tối ưu phụ thuộc vào nhiều yếu tố:
1. **Ngữ cảnh thời gian thực:** Sáng sớm cần tìm cafe/ăn sáng; trưa cần quán cơm/mì Quảng; chiều muốn ra biển Mỹ Khê/Sơn Trà; tối muốn ngắm Cầu Rồng phun lửa, dạo phố đi bộ hay ăn hải sản.
2. **Khoảng cách địa lý:** Ưu tiên địa điểm gần vị trí hiện tại (GPS).
3. **Chất lượng & Chi phí:** Đánh giá sao (Rating), mức giá cả phù hợp túi tiền.
4. **Sở thích cá nhân hóa:** Người thích sống ảo, check-in khác với người thích yên tĩnh làm việc hoặc tín đồ sành ăn.

### 1.2. Giải Pháp Của Đề Tài
Đề tài kết hợp sức mạnh của 2 lĩnh vực:
* **Deep Learning (Graph Neural Networks - TAS-GNN):** Dự đoán mức độ phù hợp cá nhân hóa của người dùng đối với từng địa điểm dựa trên đồ thị tương tác và vector thời gian liên tục Fourier.
* **Hệ Hỗ Trợ Ra Quyết Định (Decision Support System - MCDM):** Kết hợp thuật toán **AHP** (xác định trọng số ưu tiên của người dùng) và **TOPSIS** (xếp hạng đa tiêu chí: Khoảng cách, Đánh giá, Giá cả, Độ phù hợp AI, Độ phổ biến).

---

## 2. KIẾN TRÚC TỔNG THỂ HỆ THỐNG

```
[ TẦNG 1: DỮ LIỆU (DATA LAYER) ]
OpenStreetMap API + Dữ liệu Đà Nẵng ──> [Tiền xử lý & Khử trùng] ──> danang_pois_full.csv (996 POIs)
                                                                ──> danang_checkins_full.csv (36.210 check-ins)
                                                                ──> danang_social_graph.csv (7.765 quan hệ bạn bè)

[ TẦNG 2: MÔ HÌNH HÓA AI & RA QUYẾT ĐỊNH (CORE ENGINE) ]
┌──────────────────────────────────────────────┐    ┌──────────────────────────────────────────────┐
│  MÔ HÌNH AI GỢI Ý CÁ NHÂN HÓA (TAS-GNN)      │    │  HỆ THỐNG RA QUYẾT ĐỊNH ĐA TIÊU CHÍ (DSS)    │
│  - Graph Convolution Backbone (LightGCN)     │    │  - Tiêu chí: Khoảng cách, Rating, Giá,       │
│  - Continuous Fourier Time Embedding         │    │              Độ phổ biến, Phù hợp AI (C4)    │
│  - Dynamic Temporal Gating Mechanism         │    │  - AHP: Tính trọng số nhất quán (CR < 0.1)   │
│  - BPR Ranking Loss Optimization             │    │  - TOPSIS: Chuẩn hóa vector & Tính khoảng     │
│  ==> Output: Điểm dự đoán sở thích C4 (AI)   │    │            cách nghiệm lý tưởng PIS / NIS    │
└──────────────────────┬───────────────────────┘    └──────────────────────┬───────────────────────┘
                       │                                                   │
                       └───────────────────────┬───────────────────────────┘
                                               ▼
[ TẦNG 3: DỊCH VỤ DỊCH CHUYỂN & GIAO DIỆN (API & PRESENTATION) ]
FastAPI Server (server.py) / NestJS Backend (BE_API)
       │ (RESTful JSON APIs)
       ▼
Giao diện Bản đồ Web tương tác (demo_danang.html) & Bảng điều khiển Quản trị (app.py)
```

---

## 3. GIAI ĐOẠN 1: THU THẬP & XỬ LÝ DỮ LIỆU THỰC ĐỊA ĐÀ NẴNG

### 3.1. Nguồn Dữ Liệu
* **POI Thực địa:** Sử dụng Overpass API cào dữ liệu từ OpenStreetMap (OSM) trong giới hạn tọa độ TP. Đà Nẵng:
  - Vĩ độ (`latitude`): $15.95^\circ \text{N} \to 16.15^\circ \text{N}$
  - Kinh độ (`longitude`): $108.10^\circ \text{E} \to 108.30^\circ \text{E}$
* **Các file script thu thập:**
  - `crawl_osm_danang.py`, `crawl_full_danang_osm.py`: Cào POIs thô với các tag `amenity=cafe`, `amenity=restaurant`, `tourism=hotel`, `tourism=attraction`.
  - `merge_master_poi.py`: Làm sạch tên địa điểm, bổ sung quận/huyện (Hải Châu, Sơn Trà, Ngũ Hành Sơn, Thanh Khê, Liên Chiểu, Cẩm Lệ), loại bỏ tọa độ trùng hoặc nằm ngoài Đà Nẵng.
  - `build_danang_dataset.py`: Chuẩn hóa 996 POIs thành bộ dữ liệu chính thức [danang_pois_full.csv](file:///f:/dss/DSS_repo/data/danang/danang_pois_full.csv).

### 3.2. Cấu Trúc Bộ Dữ Liệu Chuẩn Hóa
1. **Dữ liệu địa điểm (`danang_pois_full.csv` - 996 địa điểm):**
   - `l`: POI ID ($0 \to 995$).
   - `name`: Tên địa điểm (ví dụ: *43 Factory Coffee Roaster*, *Hải Sản Bé Mặn*).
   - `category`: 4 nhóm chính gồm `cafe` (304), `restaurant` (293), `hotel` (295), `tourist_spot` (104).
   - `lat`, `lon`: Tọa độ GPS thực địa.
   - `rating`: Đánh giá trung bình ($1.0 \to 5.0$).
   - `price_avg`: Mức giá trung bình (VNĐ).
   - `popularity`: Chỉ số độ phổ biến ($0 \to 100$).

2. **Dữ liệu di chuyển & check-in (`danang_checkins_full.csv` - 36.210 sự kiện):**
   - Được mô phỏng theo chu kỳ sinh học ngày đêm (Circadian Pattern: sáng cafe, trưa nhà hàng, chiều dạo mát, tối giải trí) kết hợp mô hình trọng lực khoảng cách (Gravity Model).
   - Mỗi bản ghi gồm: `u` (User ID), `l` (POI ID), `ts` (Unix Timestamp), `hour` ($0 \to 23$), `day` ($0 \to 6$).

---

## 4. GIAI ĐOẠN 2: XÂY DỰNG & HUẤN LUYỆN MÔ HÌNH AI (TAS-GNN)

### 4.1. Kiến Trúc Mô Hình TAS-GNN (`src/models/temporal_gnn.py`)
Mô hình kết hợp 3 thành phần cải tiến vượt trội so với LightGCN truyền thống:
1. **Đồ thị tương tác User-POI (Graph Convolution):**
   - Học biểu diễn người dùng và địa điểm qua 3 lớp tích chập đồ thị LightGCN không cần trọng số trọng tâm:
     $$E^{(k+1)} = \tilde{A} E^{(k)}, \quad \tilde{A} = D^{-\frac{1}{2}} A D^{-\frac{1}{2}}$$
2. **Nhúng thời gian liên tục Fourier (Continuous Fourier Time Encoding):**
   - Biến đổi mốc thời gian $t$ thành vector nhúng bảo toàn chu kỳ và khoảng cách thời gian:
     $$\Phi(t) = [\cos(\omega_1 t + b_1), \sin(\omega_1 t + b_1), \dots, \cos(\omega_d t + b_d), \sin(\omega_d t + b_d)]$$
   - Cộng thêm vector điều hòa của giờ trong ngày $h$ và thứ trong tuần $w$.
3. **Cơ chế Cổng Ngữ Cảnh Thời Gian (Temporal Gating):**
   - Cập nhật linh hoạt vector người dùng tại thời điểm truy vấn:
     $$g_u(t) = \sigma(W_g [e_u \parallel W_t \Phi(t)])$$
     $$e_u(t) = e_u + g_u(t) \odot (W_t \Phi(t))$$
4. **Hàm mất mát tối ưu:** Huấn luyện bằng Bayesian Personalized Ranking (BPR Loss).

### 4.2. Huấn Luyện & Kết Quả Thực Nghiệm (`src/train_compare.py`)
Mô hình được huấn luyện trên giao thức phân chia thời gian thực tế (**Temporal Split**: 70% Train, 10% Tune, 20% Test) để kiểm thử khả năng dự đoán tương lai:
* **Kết quả đối sánh thực nghiệm trên Đà Nẵng:**
  - **HitRate@10:** TAS-GNN đạt **12.45%** (vượt trội so với LightGCN: 11.13%, tăng **+11.87%**).
  - **NDCG@10:** TAS-GNN đạt **6.09%** (vượt trội so với LightGCN: 5.76%, tăng **+5.63%**).
* Checkpoint mô hình được lưu tại:
  - `DSS_repo/outputs/checkpoints/temporal_gnn_danang.pt`
  - `DSS_repo/outputs/checkpoints/lightgcn_danang.pt`

---

## 5. GIAI ĐOẠN 3: TÍCH HỢP ĐA TIÊU CHÍ (MCDM: AHP + TOPSIS)

Để biến một mô hình AI thành một **Hệ Thống Hỗ Trợ Ra Quyết Định (DSS)** hoàn chỉnh, hệ thống sử dụng thuật toán Ra quyết định đa tiêu chí (MCDM) để xếp hạng các địa điểm theo 5 tiêu chí:

### 5.1. Bảng 5 Tiêu Chí Đánh Giá Địa Điểm
| Ký hiệu | Tiêu chí | Loại | Ý nghĩa & Cách tính |
| :---: | :--- | :---: | :--- |
| **C1** | Khoảng cách (Distance) | **Cost** (càng nhỏ càng tốt) | Tính khoảng cách Haversine từ GPS người dùng đến địa điểm (km). |
| **C2** | Đánh giá (Rating) | **Benefit** (càng cao càng tốt) | Điểm số đánh giá trung bình từ 1.0 đến 5.0 sao. |
| **C3** | Mức giá (Price) | **Cost** (càng rẻ càng tốt) | Giá trung bình món ăn/dịch vụ (VNĐ). |
| **C4** | Độ phù hợp AI (Preference) | **Benefit** (càng cao càng tốt) | **Điểm dự đoán từ mô hình TAS-GNN theo giờ thực ($0.0 \to 1.0$).** |
| **C5** | Độ phổ biến (Popularity) | **Benefit** (càng cao càng tốt) | Điểm check-in và tương tác cộng đồng ($0 \to 100$). |

### 5.2. Thuật Toán AHP (Analytic Hierarchy Process)
* Cho phép người dùng hoặc chuyên gia so sánh cặp giữa các tiêu chí (Ma trận $A_{5 \times 5}$).
* Tính vector trọng số $W = [w_1, w_2, w_3, w_4, w_5]$ thỏa mãn $\sum w_i = 1$.
* Kiểm định tính nhất quán (Consistency Ratio):
  $$CR = \frac{CI}{RI} = \frac{\lambda_{max} - n}{(n - 1) \times RI} < 0.1$$
  Nếu $CR < 0.1$, ma trận so sánh hợp lệ và trọng số được chấp nhận.

### 5.3. Thuật Toán TOPSIS (Technique for Order of Preference by Similarity to Ideal Solution)
1. **Chuẩn hóa ma trận quyết định:**
   $$r_{ij} = \frac{x_{ij}}{\sqrt{\sum_{k=1}^m x_{kj}^2}}$$
2. **Nhân trọng số từ AHP:** $v_{ij} = w_j \cdot r_{ij}$
3. **Xác định nghiệm lý tưởng:**
   - Nghiệm lý tưởng tốt nhất ($A^+$ - PIS): Chọn giá trị max cho Benefit, min cho Cost.
   - Nghiệm lý tưởng tồi nhất ($A^-$ - NIS): Chọn giá trị min cho Benefit, max cho Cost.
4. **Tính khoảng cách Euclid** $S_i^+$ và $S_i^-$ của từng địa điểm đến $A^+$ và $A^-$.
5. **Tính chỉ số tương tự và xếp hạng:**
   $$C_i^* = \frac{S_i^-}{S_i^+ + S_i^-} \quad (0 \le C_i^* \le 1)$$
   Địa điểm có $C_i^*$ cao nhất là địa điểm được hệ thống đề xuất ưu tiên số 1!

---

## 6. GIAI ĐOẠN 4: TRIỂN KHAI BACKEND AI SERVICE & GIAO DIỆN WEB

### 6.1. Backend AI Service (`DSS_repo/server.py`)
* Xây dựng bằng **FastAPI**:
  - Tải trước trọng số PyTorch từ checkpoint khi server khởi động (Warm-up caching).
  - Cache sẵn biểu diễn vector đồ thị $e_u, e_i$ để đáp ứng truy vấn trong thời gian dưới **50ms**.
* **Endpoint API chính:**
  - `POST /api/v1/danang/recommend`: Nhận `userId`, `hour`, `topK`, `category` (restaurant, cafe, tourist_spot), chạy mô hình TAS-GNN và trả về danh sách địa điểm đề xuất kèm lời giải thích ngữ cảnh theo giờ.
  - `GET /api/v1/danang/pois`: Lấy danh sách địa điểm theo bộ lọc quận/huyện và danh mục.
  - `GET /demo`: Phục vụ trực tiếp giao diện Web demo.

### 6.2. Giao Diện Bản Đồ Tương Tác (`DSS_repo/demo_danang.html`)
* **Thiết kế giao diện:** Tối ưu hóa UI/UX với chủ đề Dark Mode hiện đại, bản đồ vệ tinh/roadmap số Google Maps ổn định 100% tại Việt Nam.
* **Các tính năng tương tác người dùng:**
  - **Persona Selector:** 3 đối tượng người dùng giả lập (Cư dân địa phương, Khách du lịch ẩm thực sành ăn, Khách phượt tham quan check-in).
  - **Time Slider & Presets:** Thanh trượt thời gian 24 giờ và các nút nhanh (Sáng 7h30, Trưa 12h, Chiều 16h30, Tối 20h30).
  - **Chế độ Đối so sánh trực tiếp:** Bấm chuyển tab giữa **TAS-GNN (Đề xuất)** và **LightGCN (Baseline)** để thấy rõ sự khác biệt của đề xuất theo thời gian thực.
  - **Bộ lọc danh mục & Top K:** Lọc riêng Ẩm thực (Quán ăn / Nhà hàng), Cafe, Thắng cảnh và chọn số lượng Top 5, 10, 15.

---

## 7. QUY TRÌNH CHẠY TOÀN BỘ HỆ THỐNG (STEP-BY-STEP RUNBOOK)

### Bước 1: Cài đặt Môi Trường
Mở Terminal tại thư mục `f:\dss`:
```bash
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

### Bước 2: Huấn Luyện Mô Hình AI
Huấn luyện TAS-GNN và LightGCN trên tập dữ liệu Đà Nẵng:
```bash
cd f:\dss\DSS_repo
python src/train_compare.py
```
*(Kết quả huấn luyện và checkpoint `.pt` sẽ được lưu tự động trong `outputs/checkpoints/`)*.

### Bước 3: Khởi Động AI Backend Service
Khởi chạy server FastAPI phục vụ API và Web:
```bash
cd f:\dss\DSS_repo
python -m uvicorn server:app --host 127.0.0.1 --port 8000 --reload
```

### Bước 4: Trải Nghiệm & Thử Nghiệm Trên Trình Duyệt
1. **Giao diện Web Demo trực quan:** Truy cập [http://localhost:8000/demo](http://localhost:8000/demo)
2. **Tài liệu API Swagger tương tác:** Truy cập [http://localhost:8000/docs](http://localhost:8000/docs)
3. **Ứng dụng Phân tích Đánh giá Khoa học (Streamlit Dashboard):**
   ```bash
   python -m streamlit run app.py
   ```

---

## 8. CẤU TRÚC ĐỀ CƯƠNG BÁO CÁO KHÓA LUẬN / ĐỒ ÁN TỐT NGHIỆP

Nếu bạn dùng đề tài này làm Báo cáo Đồ án / Khóa luận tốt nghiệp Đại học, cấu trúc chuẩn mực nhất gồm 5 chương như sau:

* **CHƯƠNG 1: TỔNG QUAN VỀ BÀI TOÁN GỢI Ý ĐỊA ĐIỂM (POI RECOMMENDATION)**
  - Đặt vấn đề, mục tiêu và phạm vi nghiên cứu tại TP. Đà Nẵng.
  - Giới thiệu các thách thức: Tính thưa thớt của dữ liệu (Data Sparsity) và sự phụ thuộc vào ngữ cảnh thời gian (Temporal Dynamics).
* **CHƯƠNG 2: CƠ SỞ LÝ THUYẾT VÀ PHƯƠNG PHÁP NGHIÊN CỨU**
  - Mạng nơ-ron đồ thị (GNN) và mô hình LightGCN.
  - Lý thuyết biểu diễn thời gian liên tục Fourier và cơ chế Cổng thời gian (Temporal Gating).
  - Phương pháp Ra quyết định đa tiêu chí (MCDM): Lý thuyết AHP và TOPSIS.
* **CHƯƠNG 3: THIẾT KẾ MÔ HÌNH TAS-GNN VÀ HỆ THỐNG L-DSS**
  - Kiến trúc chi tiết của mô hình TAS-GNN.
  - Quy trình tích hợp điểm số AI vào ma trận đa tiêu chí TOPSIS.
  - Thiết kế luồng dữ liệu và kiến trúc Backend - Frontend.
* **CHƯƠNG 4: THỰC NGHIỆM VÀ ĐÁNH GIÁ KẾT QUẢ**
  - Mô tả bộ dữ liệu 996 POIs thực tế tại Đà Nẵng.
  - Thiết lập thực nghiệm, độ đo đánh giá (HitRate@K, NDCG@K).
  - Phân tích biểu đồ đối sánh giữa TAS-GNN và các mô hình cơ sở.
  - Nghiên cứu bóc tách thành phần (Ablation Study).
* **CHƯƠNG 5: CÀI ĐẶT HỆ THỐNG VÀ THỰC NGHIỆM DEMO**
  - Cài đặt dịch vụ FastAPI và hệ thống Web GIS tương tác trên bản đồ Đà Nẵng.
  - Minh họa các kịch bản thực tế của từng đối tượng người dùng (Người bản địa, Khách du lịch ẩm thực, Khách tham quan).
  - Kết luận, hạn chế và hướng phát triển tiếp theo.
