# DSS_POIRS: Location-Based Decision Support System & Contextualized POI Recommendation

Hệ thống Hỗ trợ Ra quyết định Lựa chọn Địa điểm (L-DSS) tích hợp Mô hình Gợi ý POI theo Ngữ cảnh (CPR - IJCAI 2020) và Phương pháp Ra quyết định Đa tiêu chí (MCDM: AHP + TOPSIS).

---

## 📌 Tổng quan Dự án

Dự án **DSS_POIRS** giải quyết bài toán gợi ý và hỗ trợ người dùng đưa ra quyết định lựa chọn địa điểm (POI: Point of Interest như quán cafe, nhà hàng, khách sạn, điểm du lịch) tối ưu dựa trên:
1. **Mô hình Trí tuệ Nhân tạo CPR (Contextualized POI Recommendation - IJCAI 2020):** Khai thác đồ thị không gian - thời gian - quan hệ bạn bè của người dùng (User/POI Graph Laplacian, Group Lasso) để dự đoán mức độ ưa thích (Preference Score $C_4$) theo thời gian thực.
2. **Phương pháp Ra quyết định Đa tiêu chí (MCDM):**
   - **AHP (Analytic Hierarchy Process):** Xác định trọng số ưu tiên linh hoạt cho các tiêu chí: Khoảng cách ($C_1$), Giá cả ($C_2$), Đánh giá rating ($C_3$), Độ phù hợp sở thích ($C_4$), và Độ phổ biến ($C_5$).
   - **TOPSIS / SAW:** Tính toán độ tương đồng với giải pháp lý tưởng để xếp hạng địa điểm tốt nhất.
3. **Giải thích Quyết định (Explainable AI - XAI):** Cung cấp lý do minh bạch vì sao địa điểm được đề xuất cho người dùng.

---

## 🏗 Kiến trúc Hệ thống

```
DSS_POIRS/
├── BE_API/                  # Backend API (NestJS + TypeScript + Drizzle ORM)
│   ├── src/                 # Modules: Auth, Places, Recommendations (AHP + TOPSIS), etc.
│   ├── drizzle.config.ts    # Cấu hình Drizzle ORM
│   ├── package.json         # Danh sách dependencies
│   └── ...
├── DSS_repo/                # AI Engine & Nghiên cứu CPR Algorithm (Python / PyTorch / FastAPI / Streamlit)
│   ├── data/                # Dataset Gowalla / LBSN & dữ liệu tiền xử lý
│   ├── paper/               # Các bài báo nghiên cứu (IJCAI 2020 CPR, VLDB 2017 Benchmark)
│   ├── src/                 # Thuật toán CPR (cpr.py, graphs.py, data.py, baselines USG, v.v.)
│   ├── outputs/             # Kết quả đánh giá, checkpoint ma trận R*, tuning logs & biểu đồ
│   ├── app.py               # Ứng dụng demo trực quan hóa bằng Streamlit
│   ├── server.py            # FastAPI Inference Server phục vụ cho Backend API
│   ├── README.md            # Tài liệu chi tiết về tái lập bài báo CPR IJCAI 2020
│   └── TOM_TAT.md           # Tóm tắt thuật toán & kết quả nghiên cứu
├── location_based_dss_project_plan(1).md  # Kế hoạch & đặc tả chi tiết đề tài L-DSS
├── test_api.py              # Script kiểm thử tích hợp End-to-End giữa DSS và Backend API
└── .gitignore               # Cấu hình bỏ qua tệp tin rác cho cả Node.js & Python
```

---

## 🚀 Hướng dẫn Cài đặt & Khởi chạy

### 1. Chuẩn bị Môi trường
- **Node.js**: phiên bản 18+ hoặc 20+
- **Python**: phiên bản 3.10+ hoặc 3.11+
- **Cơ sở dữ liệu**: PostgreSQL / Supabase / SQLite (tùy cấu hình trong `.env`)

---

### 2. Khởi chạy AI Inference Engine (`DSS_repo`)

```bash
# Di chuyển vào thư mục DSS_repo
cd DSS_repo

# Cài đặt thư viện Python cần thiết
pip install torch numpy scipy pandas fastapi uvicorn streamlit matplotlib

# Chạy FastAPI Model Inference Server (cung cấp API điểm preference CPR)
python server.py
# Server chạy tại: http://localhost:8000 (Swagger docs: http://localhost:8000/docs)

# (Tùy chọn) Chạy Streamlit Web UI để khám phá mô hình & trực quan hóa kết quả
streamlit run app.py
```

---

### 3. Khởi chạy Backend Decision Support API (`BE_API`)

```bash
# Di chuyển vào thư mục BE_API
cd BE_API

# Cài đặt dependencies
npm install

# Cấu hình biến môi trường
cp .env.example .env
# Chỉnh sửa file .env với thông tin database và port mong muốn (mặc định 4000)

# Khởi chạy server ở chế độ Development
npm run start:dev
# API Server chạy tại: http://localhost:4000
```

---

### 4. Kiểm thử Tích hợp Toàn hệ thống (End-to-End Test)

Tại thư mục gốc của dự án:
```bash
python test_api.py
```

Kết quả trả về sẽ đánh giá ứng viên địa điểm theo vị trí địa lý, gọi mô hình AI CPR để tính điểm ngữ cảnh thời gian thực, chuẩn hóa ma trận quyết định và xếp hạng qua TOPSIS.

---

## 📊 Kết quả Thực nghiệm & Thuật toán

- **Mô hình CPR**: Tái lập thành công thuật toán từ bài báo *Peng Han et al. (IJCAI 2020)*, đạt kết quả Precision@K và Recall@K vượt trội trên tập dữ liệu chuẩn Gowalla (18.737 người dùng, 32.510 địa điểm, 1.278.274 lượt check-in).
- **MCDM Engine**: Hỗ trợ ra quyết định đa tiêu chí thích ứng linh hoạt với ngữ cảnh thời gian thực (giờ trong ngày, vị trí GPS, ngân sách, bán kính di chuyển).

---

## 📄 License & Tác giả

- Dự án phục vụ mục đích nghiên cứu và học tập.
- Tham khảo chi tiết trong thư mục [`DSS_repo/paper`](file:///f:/dss/DSS_repo/paper) và tài liệu đặc tả [`location_based_dss_project_plan(1).md`](file:///f:/dss/location_based_dss_project_plan%281%29.md).
