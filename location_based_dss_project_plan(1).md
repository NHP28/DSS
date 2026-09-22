# Location-Based Decision Support System

## 1. Tên đề tài

### Tiếng Việt
**Xây dựng hệ thống hỗ trợ ra quyết định lựa chọn địa điểm dựa trên vị trí và phương pháp ra quyết định đa tiêu chí**

### Tiếng Anh
**Location-Based Decision Support System for Multi-Criteria Place Selection**

Tên viết tắt: **L-DSS (Location-Based Decision Support System)**

---

## 2. Bài toán

Người dùng có nhiều phương án địa điểm khác nhau. Mỗi địa điểm có ưu nhược điểm về khoảng cách, giá, đánh giá, mức độ phù hợp và độ phổ biến.

Hệ thống phân tích nhiều tiêu chí để hỗ trợ người dùng lựa chọn phương án phù hợp.

### Quy trình tổng quát

```text
Vị trí người dùng
       ↓
Các địa điểm phù hợp
       ↓
Khoảng cách / Rating / Giá / Sở thích / Độ phổ biến
       ↓
Phân tích đa tiêu chí
       ↓
Xếp hạng địa điểm
       ↓
Đề xuất các phương án
       ↓
Người dùng đưa ra quyết định
```

---

## 3. Mục tiêu

1. Thu thập và quản lý dữ liệu địa điểm.
2. Xác định các địa điểm phù hợp với vị trí người dùng.
3. Cho phép người dùng xác định mức độ quan trọng của từng tiêu chí.
4. Sử dụng phương pháp MCDM để tính điểm và xếp hạng.
5. Xây dựng web trực quan để hỗ trợ người dùng ra quyết định.

---

## 4. Phạm vi đề tài

### Loại địa điểm

Có thể bắt đầu với:

- Cafe
- Nhà hàng
- Khách sạn
- Điểm du lịch

Để giảm phạm vi, phiên bản đầu tiên có thể chỉ tập trung vào **Cafe/Restaurant**.

### Khu vực

Có thể giới hạn dữ liệu trong **Đà Nẵng** để dễ xây dựng database và demo.

---

## 5. Kịch bản sử dụng

Ví dụ người dùng muốn tìm quán cafe:

```text
Bước 1: Cho phép lấy vị trí
        ↓
Bước 2: Chọn loại địa điểm: Cafe
        ↓
Bước 3: Chọn bán kính: 5 km
        ↓
Bước 4: Điều chỉnh trọng số tiêu chí
        ↓
Bước 5: Tìm kiếm
        ↓
Bước 6: DSS tính toán
        ↓
Bước 7: Hiển thị TOP địa điểm
```

---

## 6. Các tiêu chí quyết định

| Ký hiệu | Tiêu chí | Loại | Nguồn dữ liệu & Cơ sở tính toán |
|---|---|---|---|
| C1 | Khoảng cách (Distance) | Cost | Tính bằng công thức Haversine từ tọa độ GPS người dùng |
| C2 | Đánh giá (Rating) | Benefit | Điểm số trung bình từ Google Maps / Hệ thống (1.0 - 5.0) |
| C3 | Giá (Price) | Cost | Mức giá trung bình trên menu (VNĐ) |
| C4 | Mức độ phù hợp (Preference) | Benefit | **Tính từ Mô hình AI CPR (IJCAI 2020)**: Kết hợp thói quen 24h, bạn bè, đồ thị láng giềng $k$-NN & Group Lasso |
| C5 | Độ phổ biến (Popularity) | Benefit | Số lượt check-in và tương tác thực tế (0 - 100) |

### Benefit

Giá trị càng lớn càng tốt.

Ví dụ:

```text
Rating:
5 > 4 > 3
```

### Cost

Giá trị càng nhỏ càng tốt.

Ví dụ:

```text
Distance:
1 km > 3 km > 5 km
```

---

## 7. Phương pháp DSS

Sử dụng mô hình **AHP + TOPSIS**.

```text
User
 │
 ▼
AHP
 │
 ├── Xác định trọng số tiêu chí
 │
 ▼
TOPSIS
 │
 ├── Chuẩn hóa dữ liệu
 ├── Tính ma trận có trọng số
 ├── Xác định nghiệm lý tưởng
 ├── Tính khoảng cách
 └── Tính hệ số gần lý tưởng
 │
 ▼
Ranking
 │
 ▼
Recommended Places
```

### Vì sao dùng AHP + TOPSIS?

- AHP dùng để xác định mức độ quan trọng của các tiêu chí.
- TOPSIS dùng để xếp hạng các địa điểm dựa trên mức độ gần với phương án lý tưởng.
- Phù hợp với bài toán DSS/MCDM.
- Có thể giải thích rõ cách hệ thống đưa ra kết quả.

---

## 8. AHP

Ví dụ trọng số:

```text
Distance       0.30
Rating         0.25
Price          0.20
Preference     0.15
Popularity     0.10
```

Tổng trọng số:

```text
1.00
```

AHP có thể được dùng để xác định các trọng số này dựa trên mức độ ưu tiên giữa các tiêu chí.

---

## 9. TOPSIS

Ví dụ dữ liệu:

| Địa điểm | Distance | Rating | Price | Preference | Popularity |
|---|---:|---:|---:|---:|---:|
| Cafe A | 1 km | 4.8 | 40k | 0.90 | 80 |
| Cafe B | 2 km | 4.9 | 30k | 0.80 | 95 |
| Cafe C | 4 km | 4.7 | 25k | 0.70 | 90 |
| Cafe D | 3 km | 4.5 | 50k | 0.95 | 70 |

TOPSIS thực hiện:

```text
1. Decision Matrix
        ↓
2. Normalize
        ↓
3. Weighted Matrix
        ↓
4. Positive Ideal
        ↓
5. Negative Ideal
        ↓
6. Distance
        ↓
7. Closeness Coefficient
        ↓
8. Ranking
```

Ví dụ kết quả:

```text
1. Cafe B     0.82
2. Cafe A     0.78
3. Cafe D     0.65
4. Cafe C     0.61
```

---

## 10. Kiến trúc hệ thống phân tầng (2-Layer Hybrid Architecture)
 
 ```text
                     USER / CLIENT (Next.js)
                              │
                              ▼
                     NestJS API Gateway
                              │
         ┌────────────────────┼────────────────────┐
         ▼                    ▼                    ▼
     PostgreSQL          Spatial Filter       Map Service
     (Drizzle ORM)       (Bounding Box)      (OpenStreetMap)
                              │
                              ▼
                  [Danh sách ứng viên trong bán kính]
                              │
                              ▼
              ┌───────────────────────────────┐
              │ TẦNG 1: AI PREFERENCE ENGINE  │
              │  (Mô hình CPR - IJCAI 2020)   │
              │  - Đồ thị User k-NN & POI     │
              │  - Graph Laplacian + Lasso    │
              │  - Điểm sở thích ngữ cảnh R*  │
              └───────────────┬───────────────┘
                              │
                              ▼  (Gán R* vào Tiêu chí C4)
              ┌───────────────────────────────┐
              │  TẦNG 2: DECISION ENGINE      │
              │   - Trọng số tiêu chí AHP     │
              │   - Xếp hạng đa mục tiêu TOPSIS│
              │   - Sinh giải thích XAI       │
              └───────────────┬───────────────┘
                              │
                              ▼
                   TOP-K RECOMMENDED PLACES
                (Kèm lý do & bản đồ trực quan)
 ```

---

## 11. Database

### users

```text
id
name
latitude
longitude
```

### places

```text
id
name
category
latitude
longitude
rating
price
popularity
```

### categories

```text
id
name
```

### user_preferences

```text
id
user_id
distance_weight
rating_weight
price_weight
preference_weight
popularity_weight
```

### recommendations

```text
id
user_id
place_id
score
rank
created_at
```

---

## 12. Backend

Sử dụng NestJS.

```text
src/

users/
places/
categories/
preferences/
recommendation/
dss/
```

Phần DSS:

```text
dss/
├── ahp
└── topsis
```

Luồng xử lý:

```text
DSSService
    ↓
AHPService
    ↓
TOPSISService
    ↓
RankingService
```

---

## 13. Frontend

Sử dụng Next.js.

### Trang Home

- Lấy vị trí.
- Chọn loại địa điểm.
- Chọn bán kính.
- Chọn/điều chỉnh tiêu chí.

### Trang Recommendation

- Bản đồ.
- Danh sách địa điểm.
- Score.
- Ranking.
- Khoảng cách.
- Rating.

### Trang Decision Analysis

Hiển thị trọng số:

```text
Distance       ████████████ 30%
Rating         ██████████   25%
Price          ████████     20%
Preference     ██████       15%
Popularity     ████         10%
```

Và kết quả:

```text
#1 Cafe B
Score: 0.82

#2 Cafe A
Score: 0.78

#3 Cafe D
Score: 0.65
```

---

## 14. Chức năng quan trọng: điều chỉnh trọng số

Cho phép người dùng thay đổi mức độ ưu tiên.

Ví dụ:

```text
Distance = 50%
Rating   = 20%
Price    = 15%
Preference = 10%
Popularity = 5%
```

Sau đó bấm **Recalculate**.

Hệ thống chạy lại TOPSIS và cập nhật ranking.

Ví dụ:

```text
Ưu tiên khoảng cách
        ↓
Cafe A có thể lên #1

Ưu tiên rating
        ↓
Cafe B có thể lên #1

Ưu tiên giá
        ↓
Cafe C có thể lên #1
```

Đây là phần demo DSS rất quan trọng vì nó thể hiện kết quả thay đổi theo sở thích và ưu tiên của người ra quyết định.

---

## 15. Giao diện Web

### Trang tìm kiếm

```text
┌───────────────────────────────────────────┐
│              LOCATION DSS                 │
├───────────────────────────────────────────┤
│                                           │
│  Vị trí hiện tại                         │
│  [ Đà Nẵng                         ]      │
│                                           │
│  Loại địa điểm                           │
│  [ Cafe ▼ ]                               │
│                                           │
│  Bán kính                                 │
│  [ 5 km ]                                 │
│                                           │
│              [ FIND PLACES ]              │
│                                           │
└───────────────────────────────────────────┘
```

### Trang kết quả

```text
┌───────────────────┬───────────────────────┐
│                   │ DSS Recommendation     │
│       MAP         │                       │
│                   │ #1 Cafe B             │
│    📍             │ Score 0.82             │
│   📍 📍            │                       │
│      📍            │ #2 Cafe A             │
│                   │ Score 0.78             │
└───────────────────┴───────────────────────┘
```

---

## 16. Thực nghiệm

### Experiment 1: So sánh khoảng cách và DSS

So sánh:

```text
Nearest Location
        VS
DSS TOPSIS
```

Mục đích:

> Chứng minh địa điểm gần nhất không nhất thiết là phương án phù hợp nhất khi xét nhiều tiêu chí.

### Experiment 2: Thay đổi trọng số

Case 1:

```text
Distance = 50%
```

Case 2:

```text
Rating = 50%
```

Case 3:

```text
Price = 50%
```

So sánh sự thay đổi ranking.

---

## 17. Đánh giá hệ thống

### Tính đúng

- Kiểm tra công thức AHP.
- Kiểm tra TOPSIS.
- So sánh với kết quả tính thủ công hoặc dữ liệu mẫu.

### Tính hiệu quả

- API response time.
- Thời gian tính ranking.
- Số lượng địa điểm xử lý.

### Tính hữu ích

Cho người dùng đánh giá:

```text
Relevant
Partially Relevant
Not Relevant
```

---

## 18. Slide presentation

Đề xuất 18 slide:

```text
01. Title
02. Problem
03. Motivation
04. DSS Overview
05. Recommendation System
06. Location-Based Recommendation
07. Problem Definition
08. Data
09. System Architecture
10. DSS Process
11. Decision Criteria
12. AHP
13. TOPSIS
14. Web Architecture
15. Web Demo
16. Experiment
17. Evaluation
18. Conclusion
```

---

## 19. Công nghệ

```text
Frontend
- Next.js
- Tailwind CSS
- Leaflet

Backend
- NestJS

Database
- PostgreSQL

DSS
- AHP
- TOPSIS

Map
- OpenStreetMap
- Leaflet
```

Không cần Machine Learning ở phiên bản đầu.

Nếu muốn nâng cấp sau này có thể bổ sung Machine Learning.

---

## 20. Roadmap

### Phase 1 — Nghiên cứu

```text
DSS
AHP
TOPSIS
Location-based system
```

### Phase 2 — Data

```text
Places
Users
Ratings
Coordinates
Categories
```

### Phase 3 — DSS Engine

```text
AHP
 ↓
Weights
 ↓
TOPSIS
 ↓
Ranking
```

### Phase 4 — Backend

```text
NestJS
PostgreSQL
REST API
```

### Phase 5 — Frontend

```text
Next.js
Map
Search
Filter
Weight adjustment
Ranking
```

### Phase 6 — Evaluation

```text
Test data
 ↓
Run experiments
 ↓
Screenshots
 ↓
Charts
 ↓
Conclusion
```

---

## 21. Kiến trúc tổng thể

```text
              LOCATION DSS
                   │
        ┌──────────┴──────────┐
        │                     │
    LOCATION              USER NEED
        │                     │
        └──────────┬──────────┘
                   ↓
             PLACE FILTER
                   ↓
          DECISION MATRIX
                   ↓
                 AHP
                   ↓
              WEIGHTS
                   ↓
                TOPSIS
                   ↓
                RANKING
                   ↓
        ┌──────────┴──────────┐
        ↓                     ↓
      MAP                 TOP PLACES
                              ↓
                     USER DECISION
```

---

## 22. Kết luận

Hệ thống cần thể hiện rõ 4 thành phần:

```text
Data
  +
Decision Model
  +
User Preferences
  +
Analysis
  ↓
Decision Support
```

Điểm cốt lõi của đề tài không phải chỉ là “tìm địa điểm gần”, mà là:

> **Phân tích nhiều tiêu chí, xếp hạng các phương án và cung cấp thông tin để hỗ trợ người dùng đưa ra quyết định.**
