# DSS: Time-Aware POI Recommendation & Location-Based Decision Support System (TAS-GNN)

> **Hệ thống Gợi ý Địa điểm Cá nhân hóa theo Thời gian thực và Hỗ trợ Ra quyết định Đa tiêu chí tại TP. Đà Nẵng**  
> *Đồ án / Báo cáo Nghiên cứu Ứng dụng AI & Khoa học Dữ liệu*

[![Python 3.11](https://img.shields.io/badge/Python-3.11-blue.svg)](https://www.python.org/)
[![PyTorch](https://img.shields.io/badge/PyTorch-2.0+-ee4c2c.svg)](https://pytorch.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688.svg)](https://fastapi.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## 📌 1. Giới Thiệu Đề Tài

Khi du lịch hoặc sinh hoạt tại các thành phố lớn như Đà Nẵng, người dùng thường gặp phải hiện tượng **nghịch lý lựa chọn (Choice Overload)** trước hàng nghìn địa điểm ăn uống, giải trí và tham quan. Hầu hết các hệ thống gợi ý truyền thống (Collaborative Filtering, Matrix Factorization hay LightGCN tĩnh) thường thất bại vì **bỏ qua ngữ cảnh thời gian (Temporal Dynamics)**:
* **07:30 Sáng:** Nhu cầu tìm quán cafe, ăn sáng đặc sản (bún chả cá, mì Quảng).
* **12:00 Trưa:** Nhu cầu tìm quán cơm niêu, nhà hàng ẩm thực miền Trung.
* **16:30 Chiều:** Nhu cầu dạo biển Mỹ Khê, ngắm cảnh bán đảo Sơn Trà.
* **20:30 Tối:** Nhu cầu xem Cầu Rồng phun lửa, dạo phố đi bộ Bạch Đằng, ẩm thực hải sản đêm.

Dự án **DSS** giải quyết triệt để vấn đề này bằng cách kết hợp:
1. **Mô hình Mạng nơ-ron Đồ thị Động theo Thời gian (TAS-GNN):** Ứng dụng định lý Bochner/Fourier biến đổi thời gian liên tục kết hợp cơ chế Cổng điều phối thời gian (Temporal Gate) để dự đoán sở thích của người dùng tại đúng thời điểm truy vấn.
2. **Hệ Hỗ trợ Ra quyết định Đa tiêu chí (MCDM: AHP + TOPSIS):** Tích hợp điểm số AI cùng 4 tiêu chí thực tế (Khoảng cách GPS Haversine, Đánh giá rating, Mức giá cả, Độ phổ biến check-in) để xếp hạng các địa điểm tối ưu nhất.

---

## 🏗 2. Kiến Trúc Dự Án

```
DSS/
├── DSS_repo/                       # Thư mục mã nguồn AI Engine & Web Demo chính
│   ├── data/danang/                # Bộ dữ liệu thực tế 996 POIs & 36.210 check-in Đà Nẵng
│   │   ├── danang_pois_full.csv    # 996 địa điểm thực tế (Cafe, Restaurant, Hotel, Tourist Spot)
│   │   └── danang_checkins_full.csv# Lịch sử di chuyển gắn nhãn thời gian
│   ├── outputs/
│   │   ├── checkpoints/            # Trọng số mô hình đã huấn luyện (.pt)
│   │   │   ├── temporal_gnn_danang.pt # Model TAS-GNN PyTorch
│   │   │   └── lightgcn_danang.pt     # Model LightGCN Baseline
│   │   └── figures/                # Biểu đồ khoa học (Ablation study, t-SNE clusters, Bar charts)
│   ├── paper/                      # Tài liệu nghiên cứu cơ sở (IJCAI 2020 CPR, VLDB 2017)
│   ├── src/
│   │   ├── models/
│   │   │   ├── temporal_gnn.py     # Kiến trúc mạng TAS-GNN (Fourier Time + Temporal Gate)
│   │   │   └── lightgcn.py         # Kiến trúc mạng LightGCN (SIGIR 2020)
│   │   ├── train_compare.py        # Kịch bản huấn luyện & đối sánh định lượng
│   │   ├── ablation_study.py       # Nghiên cứu bóc tách các thành phần mô hình
│   │   ├── cpr.py & run_cpr.py     # Mô hình tham chiếu cũ (CPR IJCAI 2020)
│   │   └── plot_scientific_charts.py # Vẽ biểu đồ khoa học
│   ├── app.py                      # Ứng dụng Streamlit Dashboard
│   ├── demo_danang.html            # Giao diện Web Bản đồ số tương tác (Google Maps Roadmap)
│   └── server.py                   # FastAPI Production Server (< 50ms latency)
│
├── Huong_Dan.docx                  # BÁO CÁO TOÀN DIỆN & HƯỚNG DẪN TỪ A-Z (File Word chuẩn 5 chương)
├── Huong_Dan.md                    # Bản Markdown của tài liệu hướng dẫn
├── build_danang_dataset.py         # Kịch bản xây dựng dataset từ OpenStreetMap
├── requirements.txt                # Thư viện phụ thuộc
└── README.md                       # Tài liệu tổng quan repository
```

---

## 📊 3. Kết Quả Thực Nghiệm Định Lượng (Đà Nẵng Dataset)

Mô hình được đánh giá trên tập kiểm thử phân chia theo dòng thời gian (**Temporal Split**: 70% Train, 10% Tune, 20% Test):

| Chỉ số Đánh giá | LightGCN (Baseline) | TAS-GNN (Đề xuất) | Mức độ Cải thiện ($\Delta\%$) |
| :--- | :---: | :---: | :---: |
| **HitRate@5** | $6.81\%$ | **$7.39\%$** | **+8.41%** |
| **HitRate@10** | $11.13\%$ | **$12.45\%$** | **+11.87% (Vượt trội)** |
| **HitRate@20** | $16.15\%$ | **$18.56\%$** | **+14.91%** |
| **NDCG@5** | $4.37\%$ | **$4.46\%$** | **+2.13%** |
| **NDCG@10** | $5.76\%$ | **$6.09\%$** | **+5.63% (Vượt trội)** |
| **NDCG@20** | $7.03\%$ | **$7.62\%$** | **+8.41%** |
| **Precision@10** | $1.11\%$ | **$1.25\%$** | **+11.87%** |

---

## 🚀 4. Hướng Dẫn Cài Đặt & Khởi Chạy

### Bước 1: Chuẩn bị môi trường Python
```bash
# Khởi tạo virtual environment
python -m venv .venv

# Kích hoạt môi trường (Windows)
.\.venv\Scripts\activate

# Cài đặt các thư viện phụ thuộc
pip install -r requirements.txt
```

### Bước 2: Khởi động Server AI (FastAPI)
```bash
cd DSS_repo
python -m uvicorn server:app --host 127.0.0.1 --port 8000 --reload
```
Server sẽ tự động nạp dữ liệu Đà Nẵng và nạp sẵn 2 checkpoint PyTorch (`temporal_gnn_danang.pt`, `lightgcn_danang.pt`) vào bộ nhớ cache.

### Bước 3: Trải nghiệm Giao diện Web
1. **Giao diện Bản đồ Web tương tác:** Truy cập **[http://localhost:8000/demo](http://localhost:8000/demo)** (hoặc mở trực tiếp file `demo_danang.html`).
   - Tự do chuyển đổi 3 nhóm người dùng: Cư dân, Khách ẩm thực, Khách phượt.
   - Kéo thanh trượt 24h hoặc chọn nút nhanh: Sáng, Trưa, Chiều, Tối.
   - Bấm tab **Đối so sánh mô hình** giữa *TAS-GNN* và *LightGCN*.
   - Bộ lọc danh mục: *Ẩm thực / Quán ăn*, *Quán Cafe*, *Thắng cảnh*.
2. **Tài liệu API Swagger:** Truy cập **[http://localhost:8000/docs](http://localhost:8000/docs)** để gọi thử nghiệm endpoint `/api/v1/danang/recommend`.
3. **Streamlit Analytics Dashboard:**
   ```bash
   python -m streamlit run app.py
   ```

---

---

## 🔬 5. Nghiên Cứu Tái Lập Bài Báo Gốc (CPR - IJCAI 2020)

Dự án này có xuất phát điểm từ việc **tái lập thực nghiệm (Reproduction)** bài báo khoa học đỉnh cao:
> **Paper:** Peng Han, Zhongxiao Li, Yong Liu, Peilin Zhao, Jing Li, Hao Wang, Shuo Shang.  
> *Contextualized Point-of-Interest Recommendation.* **IJCAI 2020**, tr. 2484–2490.  
> *(Bản PDF bài báo được lưu trữ trong thư mục `DSS_repo/paper/CPR_IJCAI2020.pdf`)*.

### Vai trò của mô hình Paper (CPR):
1. **Tái lập Bảng 1 của Paper trên Dataset Gowalla (18.737 users × 32.510 POIs):**
   - Đã cài đặt đầy đủ thuật toán CPR (`DSS_repo/src/cpr.py`), đồ thị láng giềng k-NN không-thời gian (`graphs.py`), và mô hình đối chứng USG (`src/baselines/`).
   - Đóng gói giao diện đối sánh khoa học bằng Streamlit:
     ```bash
     cd DSS_repo
     python -m streamlit run app.py
     ```
2. **Cầu nối dẫn tới Mô hình Mới (TAS-GNN):**
   - **Hạn chế của CPR:** Phương pháp ma trận hóa cổ điển (Group Lasso + Conjugate Gradient) yêu cầu ma trận dày chiếm tới ~2.4 GB RAM, thời gian tối ưu hóa lâu và không hỗ trợ suy luận theo giờ thực tế linh hoạt.
   - **Bước nhảy vọt với TAS-GNN:** Nhóm nghiên cứu đã kế thừa tư tưởng không-thời gian của CPR nhưng **tái cấu trúc hoàn toàn sang Mạng nơ-ron đồ thị (Graph Neural Network)** trên PyTorch kết hợp **Vector liên tục Fourier**, đưa thời gian phản hồi API xuống dưới **50ms** và phục vụ thực tế cho 996 địa điểm tại TP. Đà Nẵng.

---

## 📑 6. Tài Liệu Nghiên Cứu Chi Tiết

* File thuyết minh đồ án / khóa luận tốt nghiệp chuẩn 5 chương:
  - **Word Document:** [`Huong_Dan.docx`](Huong_Dan.docx)
  - **Markdown Document:** [`Huong_Dan.md`](Huong_Dan.md)
* Báo cáo nghiên cứu khoa học chuyên sâu về mô hình TAS-GNN: [`DSS_repo/RESEARCH_REPORT_TAS_GNN.md`](DSS_repo/RESEARCH_REPORT_TAS_GNN.md)
* Tài liệu chi tiết về quá trình tái lập paper CPR: [`DSS_repo/README.md`](DSS_repo/README.md)

---

## 👨‍💻 Tác Giả & Bản Quyền
- **Dự án:** Location-Based Decision Support System with TAS-GNN (L-DSS).
- **Phát triển bởi:** Nhóm nghiên cứu DSS (`NHP28`).
- **Mã nguồn:** Mở theo giấy phép [MIT License](LICENSE).
