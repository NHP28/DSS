# Trả lời góp ý của Thầy

Đề tài: **Ứng dụng mạng nơ-ron đồ thị động tích hợp thông tin thời gian trong hệ thống gợi ý địa điểm cá nhân hóa.**

Mỗi mục dưới đây trả lời một góp ý, kèm nơi xem trên website, file mã nguồn và số liệu.
Số liệu lấy từ `outputs/benchmark_ml_danang.csv` (chạy lại từng bước, có biểu đồ, bằng ba notebook `notebooks/01…03`; hoặc `python src/benchmark_ml.py`).

| # | Góp ý | Xem trên web | Mã nguồn chính |
|---|---|---|---|
| 1 | Dataset Đà Nẵng + bộ mẫu, mô tả cấu trúc | `/data` | `data/danang/`, `tools/export_data_profile.py` |
| 2 | TAS-GNN: kiến trúc, thông số, ưu nhược | `/model` | `src/models/temporal_gnn.py`, `src/train_compare.py` |
| 3 | Cơ chế thông tin thời gian | `/model` (mục "Cơ chế thông tin thời gian") | `ContinuousTimeEncoder`, `user_gate` |
| 4 | Knowledge Graph bằng Neo4j | `/data` (mục Neo4j), nút "Vì sao gợi ý?" | `tools/build_kg.py`, `tools/kg_schema.py`, `apps/api/src/kg/` |
| 5 | Môi trường huấn luyện: Colab | `/model` (bảng thông số) | `notebooks/DSS_POI_Colab (1).ipynb` |
| 6 | So sánh với baseline ML | `/evaluation` | `src/benchmark_ml.py`, `src/baselines/` |
| 7 | Bộ chỉ số đánh giá, biểu đồ | `/evaluation` | `src/benchmark_ml.py` (`rank_metrics`) |
| 8 | Website: login, chủ đề du lịch, giao diện | `/`, `/login`, `/register`, `/themes/...`, `/explore`, `/saved` | `FE/src/`, `apps/api/src/auth/`, `apps/api/src/themes.ts` |
| 9 | Trang setting cho model | `/settings` | `FE/src/app/settings/page.tsx`, `apps/api/src/settings/` |

---

## 1. Dataset: khách đến Đà Nẵng

**Bộ chính: Đà Nẵng** (`data/danang/`)

| File | Số dòng | Nội dung |
|---|---:|---|
| `danang_pois_full.csv` | 996 | Địa điểm: mã, tên, danh mục, vĩ độ, kinh độ, quận, đánh giá, số lượt đánh giá, giá trung bình, độ phổ biến |
| `danang_checkins_full.csv` | 36.210 | Check-in: người dùng, địa điểm, timestamp, giờ địa phương, giờ (0–23), thứ (0–6), cuối tuần |
| `danang_social_full.csv` | 7.765 | Quan hệ bạn bè giữa hai người dùng |

- **996 địa điểm thật** thu thập từ OpenStreetMap: 304 cà phê, 293 nhà hàng, 295 khách sạn, 104 điểm tham quan, thuộc 7 quận huyện.
- **1.500 người dùng, 36.210 check-in** trong năm 2023. Mỗi người có 9–50 check-in (trung vị 23).
- **Nguồn gốc cần nói rõ:** tên, tọa độ, danh mục, quận là dữ liệu thật. Người dùng, check-in, bạn bè, đánh giá, giá và độ phổ biến là **dữ liệu mô phỏng** theo nhịp sinh hoạt đô thị, vì Đà Nẵng chưa có bộ check-in công khai.
- Cà phê chiếm 53% check-in, nhà hàng 30%, tham quan 17%. **295 khách sạn không có check-in nào.**
- Tín hiệu thời gian rất rõ: cà phê 7–10h, nhà hàng 7–9h, 11–13h và 18–21h, tham quan 15–21h.

**Bộ mẫu đối chiếu: Gowalla** (Stanford SNAP): 18.737 người dùng, 32.510 địa điểm, 1.278.102 check-in thật, không có danh mục hay giá. Dùng trong notebook Colab để kiểm tra mô hình trên dữ liệu thật.

## 2. Mô hình TAS-GNN

**Vai trò:** TAS-GNN là mô hình chính; LightGCN là mô hình đối chứng (đồ thị tĩnh, không thời gian).

**Kiến trúc** (`src/models/temporal_gnn.py`):

1. Embedding người dùng (1.500 × 64) và địa điểm (996 × 64).
2. Ba lớp lan truyền kiểu LightGCN trên ma trận kề chuẩn hóa đối xứng của đồ thị người dùng–địa điểm; lấy trung bình bốn tầng biểu diễn.
3. Địa điểm được cộng thêm biểu diễn không gian (MLP 2 → 64 → 64 trên tọa độ) và embedding danh mục (4 × 64).
4. Thời điểm truy vấn được mã hóa rồi đưa qua cổng thời gian để điều chỉnh vector người dùng (mục 3).
5. Điểm sở thích = tích vô hướng của vector người dùng và vector địa điểm.

**Thông số huấn luyện** (`src/train_compare.py`):

| Thông số | Giá trị |
|---|---|
| Kích thước embedding / vector thời gian | 64 / 32 |
| Số lớp lan truyền | 3 |
| Hàm mất mát | BPR + L2 (1e-4) |
| Tối ưu | Adam, tốc độ học 0,005 |
| Batch / epoch | 1.024 / 15 |
| Mẫu âm | 1 địa điểm ngẫu nhiên mỗi check-in |
| Chia dữ liệu | 70/10/20 theo thời gian từng người dùng |
| Tổng số tham số | 180.992 (LightGCN: 159.744) |

**Ưu điểm**
- Gộp ba nguồn tín hiệu trong một mô hình: đồ thị tương tác, thời gian, không gian và danh mục.
- Cùng một người, gợi ý đổi theo giờ; LightGCN cho cùng một danh sách cả ngày.
- Nhẹ, chấm điểm toàn bộ catalog trong vài mili-giây trên CPU.
- Tài khoản mới được cá nhân hóa từ vài địa điểm đã chọn mà không cần huấn luyện lại.

**Nhược điểm**
- Không mô hình hóa chuỗi di chuyển (không biết người dùng vừa ở đâu).
- Trên Đà Nẵng vẫn thua Gradient Boosting dùng đặc trưng thủ công và heuristic khoảng cách (mục 6).
- Lúc suy luận, thời gian chỉ tác động qua phía người dùng; số hạng phía địa điểm cộng cùng một vector cho mọi địa điểm nên không đổi thứ hạng.
- Dữ liệu huấn luyện là mô phỏng; trên Gowalla phần thời gian không cải thiện kết quả.
- Khách sạn và người dùng hoàn toàn mới không có tín hiệu huấn luyện.

## 3. Cơ chế thông tin thời gian

Ba bước, đều nằm trong `ContinuousTimeEncoder` và `TemporalGNN`:

1. **Mã hóa thời điểm.** Timestamp liên tục qua 16 tần số Fourier có tham số học được: `Φ(t) = [cos(ω·t/86400 + b), sin(ω·t/86400 + b)]`. Giờ và thứ qua hai bảng embedding (24 × 32 và 7 × 32). Ghép lại rồi qua MLP thành vector thời gian `τ` 32 chiều.
2. **Cổng thời gian phía người dùng.** `g = σ(W_g [e_u ‖ W_u τ])`, `e_u(t) = e_u + g ⊙ W_u τ`. Cổng quyết định từng chiều sở thích nhận bao nhiêu ngữ cảnh thời gian.
3. **Học từ check-in có giờ.** Mỗi mẫu huấn luyện mang giờ và thứ thật. Khi huấn luyện, ngữ cảnh phía địa điểm được điều biến theo danh mục: `e_i(t) = e_i + W_i τ ⊙ σ(c_i)`.

**Kiểm chứng trực tiếp trên web** (trang `/model`, đăng nhập tài khoản `demo_cafe`): lúc 8 giờ, 10 địa điểm được chấm cao nhất đều là cà phê; lúc 20 giờ, cả 10 đều là điểm tham quan. Tắt "Dùng ngữ cảnh thời gian" thì danh sách không đổi khi đổi giờ.

## 4. Knowledge Graph trên Neo4j

Dựng bằng `python tools/build_kg.py` (chạy lại không tạo trùng). **2.512 nút, 54.343 cạnh.**

| Nút | Số lượng | | Quan hệ | Số lượng |
|---|---:|---|---|---:|
| `User` | 1.500 | | `(User)-[:VISITED]->(POI)` | 32.661 |
| `POI` | 996 | | `(User)-[:FRIEND_OF]->(User)` | 7.765 |
| `Category` | 4 | | `(POI)-[:IN_CATEGORY]->(Category)` | 996 |
| `District` | 7 | | `(POI)-[:LOCATED_IN]->(District)` | 996 |
| `TimeSlot` | 5 | | `(POI)-[:NEAR]->(POI)` | 4.980 |
| | | | `(POI)-[:BUSY_AT]->(TimeSlot)` | 1.977 |
| | | | `(User)-[:ACTIVE_AT]->(TimeSlot)` | 4.968 |

**Dùng để làm gì trong hệ thống**
- Đồ thị hai phía người dùng–địa điểm mà TAS-GNN lan truyền chính là phần `VISITED` của đồ thị này.
- Nút "Vì sao gợi ý?" trên mỗi địa điểm truy vấn Neo4j: gần nơi bạn đã chọn, bao nhiêu người ghé nơi bạn chọn cũng ghé nơi này, khung giờ đông.
- Trang `/data` vẽ vùng lân cận của một địa điểm và hiện câu Cypher tương ứng.

**Giới hạn:** notebook Colab đọc trực tiếp CSV (Colab không nối được Neo4j trên máy cá nhân); hai nguồn cùng một dữ liệu gốc. MySQL vẫn giữ tài khoản, cài đặt và phản hồi. Neo4j tắt thì website vẫn gợi ý được, chỉ ẩn phần giải thích.

## 5. Môi trường huấn luyện

Google Colab, GPU T4, PyTorch. Notebook `notebooks/DSS_POI_Colab (1).ipynb` tự tải dữ liệu Đà Nẵng và Gowalla, huấn luyện, đánh giá 3 seed và xuất biểu đồ. Baseline machine learning ở mục 6 nhẹ nên chạy trên CPU máy cá nhân (dưới 1 phút).

## 6. So sánh với baseline machine learning

Dữ liệu Đà Nẵng, 6.811 sự kiện kiểm tra, xếp hạng trên toàn bộ 996 địa điểm.

| Phương pháp | Nhóm | HR@5 | HR@10 | HR@20 | NDCG@10 | MRR@10 |
|---|---|---:|---:|---:|---:|---:|
| Giờ × khoảng cách liền trước ¹ | Không học | 9,90% | 14,64% | 21,79% | 8,05% | 6,05% |
| Gradient Boosting (đặc trưng) | ML truyền thống | 7,71% | 13,93% | 20,44% | 6,90% | 4,80% |
| **TAS-GNN (model chính)** | GNN | **7,39%** | **12,45%** | **18,56%** | **6,09%** | **4,18%** |
| LightGCN (đối chứng) | GNN | 6,81% | 11,13% | 16,15% | 5,76% | 4,15% |
| Phổ biến theo giờ | Không học | 6,33% | 10,53% | 16,37% | 5,13% | 3,50% |
| User-KNN | ML truyền thống | 6,33% | 10,35% | 15,49% | 5,38% | 3,89% |
| Item-KNN | ML truyền thống | 5,77% | 9,10% | 13,82% | 5,00% | 3,76% |
| BPR-MF | ML truyền thống | 4,07% | 6,24% | 9,93% | 3,32% | 2,44% |
| Phổ biến chung | Không học | 2,17% | 6,12% | 11,19% | 2,29% | 1,17% |

¹ Được biết vị trí check-in ngay trước sự kiện kiểm tra; các phương pháp khác không có thông tin này.

**Nhận xét**
- TAS-GNN hơn LightGCN 1,32 điểm phần trăm HR@10 (12,45% so với 11,13%) và hơn cả ba phương pháp lọc cộng tác truyền thống (User-KNN, Item-KNN, BPR-MF).
- TAS-GNN **chưa phải tốt nhất**. Gradient Boosting với đặc trưng thủ công đạt 13,93%, heuristic khoảng cách đạt 14,64%. Trên dữ liệu này, tín hiệu "gần và đúng giờ" mạnh hơn tín hiệu cộng tác.
- Đây là lý do hệ thống không dùng riêng điểm GNN mà đưa nó vào TOPSIS cùng khoảng cách, giá, đánh giá và độ phổ biến.
- Lượt chạy Colab 3 seed (kiến trúc viết lại, chia theo mốc thời gian toàn cục) cho cùng xu hướng trên Đà Nẵng: TAS-GNN 16,66% so với LightGCN 11,41%. Trên Gowalla thì TAS-GNN (5,32%) thấp hơn LightGCN (5,50%). Hai bảng dùng kiến trúc và cách chia khác nhau nên không so trực tiếp.

## 7. Bộ chỉ số và biểu đồ

- **HR@K (Hit Rate):** tỉ lệ sự kiện mà địa điểm đúng nằm trong K gợi ý đầu.
- **NDCG@K:** như HR nhưng thưởng nhiều hơn khi địa điểm đúng đứng cao: trung bình của `1 / log₂(hạng + 1)`.
- **MRR@K:** trung bình của `1 / hạng`.

**Giao thức:** 80% check-in đầu của mỗi người để huấn luyện, 20% cuối để kiểm tra; chỉ chấm lần ghé địa điểm mới; xếp hạng toàn catalog, không lấy mẫu âm; siêu tham số của baseline chọn trên phần cuối tập huấn luyện.

**Biểu đồ trên `/evaluation`:** cột so sánh 9 phương pháp theo từng chỉ số, bảng số đầy đủ, kết quả Colab 3 seed có độ lệch chuẩn, ablation (bỏ thời gian, không gian, danh mục), đường học. Trang `/data` có biểu đồ check-in theo giờ, theo thứ, theo quận.

## 8. Website

| Yêu cầu | Đã làm |
|---|---|
| Login theo user | Đăng ký, đăng nhập, đăng xuất. Mật khẩu băm scrypt, phiên là cookie `HttpOnly` ký HMAC. Bốn tài khoản demo có sẵn lịch sử. |
| Gợi ý theo từng người | Tài khoản demo dùng embedding đã huấn luyện. Tài khoản mới được cá nhân hóa sau khi thích hoặc đánh dấu đã ghé 3 địa điểm. |
| Liệt kê theo chủ đề du lịch | 8 chủ đề: Ăn uống, Cà phê, Tham quan & giải trí, Lưu trú, Bữa sáng Đà Nẵng, Đà Nẵng về đêm, Ven biển, Tiết kiệm. |
| Gợi ý ăn / giải trí / tham quan | Mỗi chủ đề có danh sách xếp hạng kèm bản đồ, đổi được thời điểm. |
| Giao diện | Thiết kế lại toàn bộ, chạy được trên điện thoại, có trạng thái đang tải, rỗng và lỗi. |

"Giải trí" gộp với "Tham quan" vì OpenStreetMap chỉ cấp một nhãn chung. 53 điểm ngắm cảnh có tên ghi chú kiểu "End of the Road?" được ẩn khỏi trang chủ đề (vẫn còn trong dữ liệu và mô hình).

## 9. Trang cài đặt mô hình (`/settings`)

Lưu theo từng tài khoản, có khung xem trước Top 5 cập nhật ngay khi đổi:

- **Mô hình chấm điểm:** TAS-GNN, LightGCN, phổ biến theo giờ, phổ biến chung.
- **Dùng ngữ cảnh thời gian:** bật/tắt.
- **Số ứng viên của mô hình đưa vào TOPSIS:** tất cả, 20, 50 hoặc 100 mỗi danh mục.
- **Top-K, bán kính, ngân sách, ẩn nơi đã ghé.**
- **Trọng số AHP:** bốn bộ có sẵn hoặc tự chỉnh năm tiêu chí.
- **Trạng thái hệ thống:** dịch vụ mô hình, MySQL, Neo4j, kích thước embedding, số lớp, số tham số.

Kích thước embedding, số lớp và tốc độ học chỉ hiển thị: đổi chúng cần huấn luyện lại trên Colab.

---

## Những điều chưa làm được

- Chưa có dữ liệu check-in thật của Đà Nẵng; mọi kết luận về hiệu quả chỉ đúng trên dữ liệu mô phỏng.
- Bước AHP–TOPSIS chưa có thước đo offline.
- Cách cá nhân hóa cho tài khoản mới (trung bình embedding của các địa điểm đã chọn) là xấp xỉ, chưa được đánh giá.
- Chất lượng gợi ý khách sạn chưa kiểm chứng được vì không có tương tác.
