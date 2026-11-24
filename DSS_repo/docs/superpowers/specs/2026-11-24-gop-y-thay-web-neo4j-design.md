# Thiết kế: hoàn thiện đồ án theo góp ý của Thầy

Ngày: 24/11/2026 · Phạm vi: `DSS_repo/` (web, API, ML serving, Neo4j, tài liệu)

Đề tài: *Ứng dụng mạng nơ-ron đồ thị động tích hợp thông tin thời gian trong hệ thống gợi ý địa điểm cá nhân hóa.*

## 1. Mục đích

Thầy đã góp ý 9 điểm. Repo đã đáp ứng phần nghiên cứu (dữ liệu, mô hình, Colab, baseline, chỉ số)
nhưng còn thiếu phần trình diễn và tài liệu. Bản thiết kế này bổ sung các phần thiếu để buổi bảo vệ
có một website hoàn chỉnh, mỗi góp ý đều có chỗ chỉ ra được trên web hoặc trong tài liệu.

| # | Góp ý | Hiện trạng | Việc cần làm |
|---|---|---|---|
| 1 | Dataset Đà Nẵng + bộ mẫu, mô tả cấu trúc, ~900 POI từ OSM | Có 996 POI, 1.500 user, 36.210 check-in; bộ mẫu Gowalla | Trang **Dữ liệu** + mục tài liệu mô tả cấu trúc |
| 2 | TAS-GNN: kiến trúc, thông số, ưu nhược | Có code; tài liệu lệch với code | Trang **Mô hình** + sửa tài liệu cho khớp code |
| 3 | Cơ chế thông tin thời gian | Có trong code | Mục riêng trên trang Mô hình, có minh họa tương tác |
| 4 | Knowledge Graph bằng Neo4j | Chưa có | Dịch vụ Neo4j, script dựng đồ thị, trang xem đồ thị |
| 5 | Huấn luyện trên Colab | Có notebook | Giữ nguyên, dẫn link từ web và tài liệu |
| 6 | So sánh baseline ML | Có 9 mô hình × 3 seed | Biểu đồ tương tác trên trang **Đánh giá** |
| 7 | Bộ chỉ số, biểu đồ | Có CSV + ảnh tĩnh | Như trên; giải thích HR@K, NDCG@K, MRR@K |
| 8 | Web: login theo user, liệt kê theo chủ đề, giao diện đẹp | Chỉ có trang khám phá | Đăng nhập, trang chủ theo chủ đề, làm lại giao diện |
| 9 | Trang setting cho model | Chưa có | Trang **Cài đặt mô hình** |

## 2. Mục tiêu, ngoài phạm vi, điều phải tránh

**Mục tiêu**
- Người xem đăng ký/đăng nhập, nhận gợi ý ăn uống, cà phê, giải trí – tham quan, lưu trú theo giờ và vị trí.
- Gợi ý thay đổi theo tài khoản: tài khoản demo có lịch sử, tài khoản mới được cá nhân hóa dần theo lượt thích/ghé.
- Trang cài đặt cho phép đổi mô hình và tham số, thấy kết quả đổi theo.
- Đồ thị tri thức nằm trong Neo4j, xem được trên web và dùng để giải thích gợi ý.
- Model chính là **TAS-GNN**; **LightGCN** là model đối chứng. Cả hai dùng checkpoint có sẵn trong repo.
- Có bảng so sánh với nhóm baseline machine learning truyền thống trên dữ liệu Đà Nẵng, cùng giao thức, cùng chỉ số.
- Số liệu trên web, README và báo cáo thống nhất một nguồn: bảng đánh giá mới ở mục 5.10, đo trên đúng model đang phục vụ web.
  Lượt Colab `dss_full_global_time_641d6a1a` (3 seed, kiến trúc khác) hiển thị riêng, ghi rõ nguồn.

**Ngoài phạm vi**
- Huấn luyện lại TAS-GNN/LightGCN, đổi kiến trúc mô hình, đổi bộ dữ liệu. (Baseline ML mới thì được huấn luyện, mục 5.10.)
- Triển khai lên Internet, đăng nhập qua Google/Facebook, quên mật khẩu qua email.
- Viết lại `Huong_Dan.docx`; chỉ cập nhật bản Markdown.
- Demo cũ (`server.py`, `app.py`, `demo_danang.html`) giữ nguyên, không phát triển thêm.

**Điều phải tránh**
- Trình bày số liệu đẹp hơn thực tế. Check-in, rating, giá là dữ liệu mô phỏng; trên Gowalla TAS-GNN
  (HR@10 5,32%) thấp hơn LightGCN (5,50%). Cả hai điều này phải hiện rõ.
- Web chết khi thiếu Neo4j hoặc thiếu file model. Mỗi dịch vụ phụ phải có trạng thái dự phòng nhìn thấy được.
- Sửa file CSV dữ liệu: artifact kiểm tra SHA256 của dữ liệu, sửa là model bị từ chối.

## 3. Ràng buộc

- Giữ kiến trúc hiện có: Next.js 16 (`FE/`), NestJS + Fastify (`apps/api`), FastAPI (`ml/serve.py`), MySQL 8.4.
- Máy hiện tại: Node 22, Python 3.12; Docker Desktop đã cài nhưng đang tắt; không có `mysqld`; `.venv` trống.
  MySQL và Neo4j chạy qua `docker compose`.
- Model phục vụ web là hai checkpoint có sẵn: `outputs/checkpoints/temporal_gnn_danang.pt` (TAS-GNN, lớp
  `TemporalGNN` trong `src/models/temporal_gnn.py`) và `outputs/checkpoints/lightgcn_danang.pt`. Đây là state_dict thuần,
  không kèm metadata; hiện chỉ `server.py` (API cũ) nạp được, `ml/serve.py` thì không.
- File zip của lượt Colab không có trên máy và **không bắt buộc**. Nếu sau này có, `tools/import_artifacts.py`
  vẫn hoạt động và được ưu tiên như hiện tại.
- Đo lại ngày 24/11/2026 bằng `src/baselines_check.py` (6.811 sự kiện test, chia 80/20 theo thời gian từng user):
  TAS-GNN HR@10 13,03%, LightGCN 11,36%, phổ biến theo giờ 11,88%, heuristic "giờ × khoảng cách liền trước" 14,88%.
  README đang ghi 12,45%; file CSV cũ ghi 5,63% (đã được script ghi đè bằng số mới).
- Catalog chỉ có 4 danh mục: `cafe` 304, `hotel` 295, `restaurant` 293, `tourist_spot` 104.
  Không có nhãn "giải trí" riêng. Nhiều `tourist_spot` là điểm ngắm cảnh OSM tên tiếng Anh tự phát
  ("End of the Road?", "This is a dead end!…").
- 295 khách sạn không có tương tác huấn luyện; gợi ý nhóm này dựa vào tiêu chí TOPSIS, không phải GNN.

## 4. Các hướng đã cân nhắc

**Vai trò của Neo4j**

| Hướng | Được | Mất |
|---|---|---|
| A. Neo4j song song MySQL *(đã chọn)* | MySQL giữ tài khoản, phản hồi, lọc nhanh như hiện tại; Neo4j giữ đồ thị tri thức. Phần đang chạy không bị đụng. Neo4j tắt thì web vẫn gợi ý được. | Hai kho dữ liệu, cần script đồng bộ. |
| B. Neo4j thay MySQL | Một kho duy nhất, "thuần đồ thị". | Viết lại toàn bộ API và test; rủi ro cao sát ngày bảo vệ. |
| C. Chỉ xuất đồ thị ra Neo4j để chụp hình | Nhanh nhất. | Neo4j không tham gia hệ thống, khó trả lời khi Thầy hỏi "dùng để làm gì". |

Người dùng chọn A.

**Cá nhân hóa cho tài khoản mới** *(lựa chọn của người viết thiết kế)*

| Hướng | Được | Mất |
|---|---|---|
| 1. Tài khoản mới luôn là cold-start | Không cần code | Login vô nghĩa: mọi tài khoản mới nhận cùng kết quả |
| 2. Gán tài khoản mới vào một user có sẵn trong dữ liệu | Đơn giản | Sai bản chất: lịch sử không phải của họ |
| 3. Fold-in: dựng vector người dùng từ các POI họ đã thích/ghé *(chọn)* | Cá nhân hóa thật, không cần huấn luyện lại, đúng tinh thần GNN quy nạp | Là xấp xỉ, chất lượng chưa được đo offline; phải ghi rõ |

## 5. Thiết kế

### 5.1 Tổng thể

```text
Trình duyệt ── FE Next.js :3000 ── /api ── NestJS :4000 ──┬── MySQL :3306   tài khoản, cài đặt, phản hồi, catalog
                                                         ├── Neo4j :7687   đồ thị tri thức (chỉ đọc khi chạy web)
                                                         └── ml/serve :8000 chấm điểm TAS-GNN / LightGCN
tools/build_kg.py ── đọc CSV data/danang ──> Neo4j     (chạy một lần, chạy lại không trùng)
```

### 5.2 Đồ thị tri thức Neo4j

`compose.yaml` thêm dịch vụ `neo4j:5-community` (cổng 7474, 7687 chỉ bind 127.0.0.1, mật khẩu qua biến môi trường).

Script `tools/build_kg.py` (Python, thư viện `neo4j`) đọc CSV, tạo ràng buộc duy nhất rồi `MERGE` theo lô:

| Nút | Thuộc tính | Số lượng |
|---|---|---|
| `User` | id | 1.500 |
| `POI` | id, name, lat, lon, rating, price_avg, popularity | 996 |
| `Category` | key, label | 4 |
| `District` | name (đã chuẩn hóa) | 7 |
| `TimeSlot` | key: sáng 5–10h, trưa 11–13h, chiều 14–17h, tối 18–22h, khuya 23–4h | 5 |

| Quan hệ | Thuộc tính | Nguồn |
|---|---|---|
| `(User)-[:VISITED]->(POI)` | count, first_ts, last_ts, giờ phổ biến nhất | check-in gộp theo cặp |
| `(User)-[:FRIEND_OF]-(User)` | – | `danang_social_full.csv` |
| `(POI)-[:IN_CATEGORY]->(Category)` | – | catalog |
| `(POI)-[:LOCATED_IN]->(District)` | – | catalog |
| `(POI)-[:NEAR]->(POI)` | km | 5 POI gần nhất theo Haversine |
| `(POI)-[:BUSY_AT]->(TimeSlot)` | count, share | check-in gộp theo khung giờ |
| `(User)-[:ACTIVE_AT]->(TimeSlot)` | count | check-in gộp theo khung giờ |

Tên quận được chuẩn hóa khi nạp ("Quận Sơn Trà", "Hai Chau"… gộp về 7 quận); CSV giữ nguyên.

Nói rõ trong tài liệu: đồ thị hai phía User–POI mà TAS-GNN lan truyền chính là đồ thị con `VISITED` của
đồ thị tri thức này. Notebook Colab vẫn đọc CSV (Colab không nối được Neo4j trên máy cá nhân), hai nguồn cùng
một dữ liệu gốc. Đây là giới hạn, không che giấu.

API (NestJS, `neo4j-driver`), tất cả chỉ đọc:
- `GET /api/kg/stats`: số nút, số cạnh theo loại.
- `GET /api/kg/poi/:id`: lân cận của một POI (danh mục, quận, khung giờ đông, POI gần, số người ghé) để vẽ đồ thị.
- `GET /api/kg/poi/:id/similar`: POI được cùng nhóm người ghé (đếm đường đi `POI<-VISITED-User-VISITED->POI`).
- `GET /api/kg/explain?poiId=`: với tài khoản đăng nhập, trả lý do dạng đồ thị: "gần nơi bạn đã thích",
  "N người ghé nơi bạn thích cũng ghé nơi này", "đông vào khung giờ bạn chọn".

Neo4j không kết nối được: các endpoint trả 503 kèm thông báo; trang Khám phá vẫn chạy, phần lý do đồ thị ẩn đi.

### 5.3 Tài khoản và đăng nhập

Bảng mới trong MySQL (thêm vào `schema.sql`, dùng `CREATE TABLE IF NOT EXISTS`):

- `accounts(id, username UNIQUE, display_name, password_hash, dataset_user_id NULL, created_at)`
- `account_settings(account_id PK, settings JSON, updated_at)`
- `account_interests(account_id, theme)`
- Bảng `feedback` thêm cột `account_id NULL`; `user_id` cho phép NULL.

Mật khẩu băm bằng `scrypt` của `node:crypto` (muối riêng từng tài khoản). Phiên đăng nhập là token ký HMAC
đặt trong cookie `httpOnly`, `SameSite=Lax`, hạn 7 ngày; khóa ký lấy từ `AUTH_SECRET` trong `.env`.
Không thêm thư viện xác thực.

Endpoint: `POST /api/auth/register`, `POST /api/auth/login`, `POST /api/auth/logout`, `GET /api/auth/me`.
Giới hạn 10 lần đăng nhập sai mỗi 15 phút theo username (bộ đếm trong bộ nhớ).

Hai loại tài khoản:
- **Tài khoản demo**: `db:init` tạo sẵn 4 tài khoản gắn với 4 user có lịch sử trong dữ liệu
  (chọn user có nhiều check-in, gu khác nhau: cà phê sáng, ẩm thực tối, tham quan cuối tuần, đa dạng).
  Mật khẩu demo đọc từ `apps/api/.env` (`DEMO_PASSWORD`), ghi trong `.env.example`. Trang đăng nhập có nút
  "Dùng tài khoản demo" để buổi trình bày không phải gõ.
- **Tài khoản tự đăng ký**: sau khi đăng ký, chọn chủ đề yêu thích (ít nhất 1). Cá nhân hóa theo mục 5.4.

Trang Khám phá, Chủ đề xem được khi chưa đăng nhập (chế độ khách, gợi ý theo độ phổ biến theo giờ).
Yêu thích, lịch sử, cài đặt mô hình yêu cầu đăng nhập. Ô "chọn người dùng #id" trong bộ lọc cũ bị bỏ:
người dùng chính là tài khoản đang đăng nhập.

### 5.4 Chấm điểm cho từng loại tài khoản

`ml/serve.py` thêm một bộ nạp cho checkpoint trong repo: dựng `TemporalGNN` / `LightGCN` từ `src/models`
với đúng cấu hình `server.py` đang dùng (dim 64, time_dim 32, 3 lớp, đồ thị từ tập train 80%), bọc lại sau cùng
giao diện chấm điểm với bundle Colab. Thứ tự ưu tiên: `MODEL_PATH` → `outputs/active_artifact.json` → checkpoint trong repo.
Với checkpoint trong repo, SHA256 dữ liệu được tính trực tiếp từ CSV lúc khởi động (file model không chứa).
Bước đầu tiên của người triển khai: xác nhận checkpoint được huấn luyện trên đúng phần train 80% mà
`baselines_check.py` dùng (đối chiếu `src/train_compare.py`); nếu tập test từng lọt vào huấn luyện thì phải ghi rõ.

`POST /score` của `ml/serve.py` nhận thêm:
`model` (`tas_gnn` | `lightgcn` | `hourly_popularity` | `popularity`), `useTime` (bool), `historyPoiIds` (mảng).

- Tài khoản demo: dùng embedding của user tương ứng như hiện tại.
- Tài khoản tự đăng ký có ít nhất 3 POI đã thích/ghé: vector người dùng = trung bình embedding sau lan truyền
  của các POI đó, rồi qua cổng thời gian
  như user thường. Kết quả trả `source: "tas_gnn_foldin"`; web ghi "Cá nhân hóa từ N địa điểm bạn đã chọn (xấp xỉ, chưa đánh giá offline)".
- Dưới 3 POI: độ phổ biến theo giờ, lọc theo chủ đề đã chọn khi đăng ký; web ghi "Hãy thích thêm vài địa điểm để nhận gợi ý riêng".
- `useTime = false`: bỏ số hạng ngữ cảnh thời gian khi tính điểm (chỉ `user · item`). Dùng để người xem thấy
  thời gian thay đổi thứ hạng thế nào. Ghi rõ đây là tắt lúc suy luận, khác biến thể `tas_no_time` được huấn luyện riêng trong bảng ablation.
- Serving nạp cả TAS-GNN và LightGCN. `/health` trả danh sách mô hình sẵn sàng và nguồn của chúng.

NestJS giữ nguyên bước kiểm tra SHA256 dữ liệu và dự phòng theo giờ khi dịch vụ AI lỗi.

### 5.5 Trang Cài đặt mô hình (`/settings`)

Lưu theo tài khoản trong `account_settings`. Bố cục hai cột: trái là cài đặt, phải là bản xem trước
Top 5 cập nhật khi đổi cài đặt (dùng vị trí và giờ mặc định), để thấy tác động ngay.

| Nhóm | Cài đặt | Mặc định |
|---|---|---|
| Mô hình | Mô hình chấm điểm: TAS-GNN, LightGCN, Phổ biến theo giờ, Phổ biến chung (mô hình chưa nạp bị khóa, kèm lý do) | TAS-GNN |
| Mô hình | Dùng ngữ cảnh thời gian (bật/tắt) | Bật |
| Mô hình | Số ứng viên GNN đưa vào TOPSIS: 20 / 50 / 100 / tất cả | Tất cả (hành vi hiện tại) |
| Kết quả | Số gợi ý mỗi danh mục (Top-K): 5–20 | 10 |
| Kết quả | Ẩn nơi đã ghé | Bật |
| Kết quả | Bán kính mặc định (km), ngân sách mặc định | 10 km, không giới hạn |
| Ưu tiên | Bộ trọng số: Cân bằng, Gần tôi, Tiết kiệm, Hợp sở thích, Tự chỉnh (5 thanh trượt, hiện % và CR) | Cân bằng |

Khối **Trạng thái mô hình** (chỉ đọc): run ID, seed, số epoch được chọn, số user/POI đã huấn luyện,
kích thước embedding, số lớp, dịch vụ AI / MySQL / Neo4j đang bật hay tắt. Nút "Khôi phục mặc định".

"Số ứng viên GNN đưa vào TOPSIS" cắt **theo từng danh mục, sau khi lọc** (bán kính, ngân sách, đã ghé):
giữ N địa điểm có điểm GNN cao nhất của mỗi danh mục rồi mới chạy TOPSIS. Cắt toàn cục sẽ loại gần hết khách sạn
(không có tương tác huấn luyện) và làm rỗng các chủ đề. *(Lựa chọn của người viết thiết kế.)*

Siêu tham số huấn luyện (dim, layers, lr, batch) chỉ hiển thị, không sửa được trên web: đổi chúng cần
huấn luyện lại trên Colab. Trang ghi rõ điều này và dẫn link notebook.

### 5.6 Chủ đề du lịch

Chủ đề định nghĩa trong một file cấu hình ở API (`themes.ts`), mỗi chủ đề là một bộ lọc trên catalog
cộng giờ gợi ý và bộ trọng số, nên thêm chủ đề không cần sửa code trang.

| Chủ đề | Bộ lọc | Giờ mặc định | Ưu tiên |
|---|---|---|---|
| Ăn uống | restaurant | giờ hiện tại | Cân bằng |
| Cà phê | cafe | giờ hiện tại | Gần tôi |
| Tham quan & giải trí | tourist_spot | 16h | Hợp sở thích |
| Lưu trú | hotel | 14h | Tiết kiệm |
| Bữa sáng Đà Nẵng | cafe + restaurant, giá ≤ 60.000đ | 7h | Gần tôi |
| Đà Nẵng về đêm | restaurant + cafe + tourist_spot | 20h | Hợp sở thích |
| Ven biển Sơn Trà – Ngũ Hành Sơn | mọi danh mục, hai quận này | giờ hiện tại | Cân bằng |
| Tiết kiệm | mọi danh mục, giá thấp trong danh mục | giờ hiện tại | Tiết kiệm |

"Giải trí" gộp chung với "Tham quan" vì dữ liệu không có nhãn giải trí riêng; trang ghi chú điều này.

Điểm ngắm cảnh tên tự phát: thêm bảng `poi_display(poi_id, hidden, display_name)` do `db:init` điền theo
quy tắc tên (chứa "?", "!", dài bất thường, hoặc thuộc danh sách tay). POI ẩn không hiện ở trang chủ đề và
trang chủ; vẫn còn trong catalog, trong mô hình và trong trang Khám phá khi bật "hiện tất cả". Không sửa CSV.

Endpoint: `GET /api/themes`, `POST /api/themes/:slug/recommendations` (dùng lại luồng `recommend`).

### 5.7 Các trang web

| Đường dẫn | Nội dung | Cần đăng nhập |
|---|---|---|
| `/` | Trang chủ: lời chào theo buổi, lưới chủ đề, "Gợi ý cho bạn lúc này" (Top theo tài khoản), số liệu dữ liệu | Không |
| `/login`, `/register` | Đăng nhập, đăng ký + chọn chủ đề yêu thích, nút tài khoản demo | – |
| `/explore` | Trang khám phá hiện có (bộ lọc, danh sách, bản đồ, so sánh), bỏ ô chọn user | Không |
| `/themes/[slug]` | Danh sách + bản đồ theo chủ đề, đổi giờ nhanh (sáng/trưa/chiều/tối) | Không |
| `/saved` | Yêu thích và nơi đã ghé của tài khoản | Có |
| `/settings` | Cài đặt mô hình (5.5) | Có |
| `/model` | Kiến trúc TAS-GNN, thông số, ưu nhược, cơ chế thời gian | Không |
| `/evaluation` | Baseline, chỉ số, biểu đồ, ablation, giới hạn (thay `/training`) | Không |
| `/data` | Cấu trúc dataset Đà Nẵng + Gowalla, nguồn OSM, đồ thị tri thức Neo4j xem trực tiếp | Không |

Phác thảo trang chủ:

```text
┌───────────────────────────────────────────────────────────────────────┐
│ danang explore   Khám phá  Chủ đề  Đã lưu   Mô hình ▾      (An ▾)      │
├───────────────────────────────────────────────────────────────────────┤
│ Chào buổi tối, An.                         ┌──────────────────────┐   │
│ 19:00 thứ Sáu ở Hải Châu — tối nay đi đâu? │  bản đồ nhỏ + 5 ghim │   │
│ [ Tìm quanh tôi ]  [ Đổi giờ ▾ ]           └──────────────────────┘   │
├───────────────────────────────────────────────────────────────────────┤
│ Chủ đề                                                                │
│ [Ăn uống 293] [Cà phê 304] [Tham quan & giải trí] [Lưu trú 295]        │
│ [Bữa sáng Đà Nẵng] [Đà Nẵng về đêm] [Ven biển] [Tiết kiệm]             │
├───────────────────────────────────────────────────────────────────────┤
│ Gợi ý cho bạn lúc này · TAS-GNN + TOPSIS · vì sao?                    │
│ ①  Quán …   4,6★ · 1,2 km · 85.000đ   ♡                              │
│ ②  …                                                                  │
└───────────────────────────────────────────────────────────────────────┘
```

**Trang `/model`** (góp ý 2, 3) nội dung lấy đúng từ `src/models/temporal_gnn.py` (model đang phục vụ).
Người triển khai đọc file này và viết theo code; các dòng dưới là khung, chỗ nào code khác thì theo code:
- Sơ đồ kiến trúc: embedding user/POI → 3 lớp lan truyền kiểu LightGCN trên đồ thị chuẩn hóa đối xứng →
  cộng bộ mã hóa không gian (MLP trên tọa độ chuẩn hóa) và embedding danh mục → cổng thời gian → tích vô hướng.
- Cơ chế thời gian: bộ mã hóa Fourier có tham số học được trên timestamp (`time_encoder.weights`, `bias`, 16 tần số)
  cộng embedding giờ (24×32) và embedding thứ (7×32) → MLP → vector thời gian 32 chiều; chiếu sang phía user
  (`time_proj_user`) và phía POI (`time_proj_item`); cổng `user_gate` trộn vector user với ngữ cảnh thời gian.
  Có thanh trượt giờ để thấy thứ hạng danh mục đổi theo (gọi API thật).
- Bảng thông số: dim 64, time_dim 32, 3 lớp, BPR loss; các giá trị còn lại (lr, batch, epoch, L2) lấy từ
  `src/train_compare.py`. Kèm số tham số của từng khối đếm từ checkpoint.
- Ưu điểm, nhược điểm, giới hạn (viết thẳng: phụ thuộc dữ liệu mô phỏng, không mô hình hóa chuỗi di chuyển,
  thua trên Gowalla, khách sạn không có tương tác).
- Mô tả "Fourier time encoding" trong tài liệu cũ khớp với model này, giữ lại. `ml/poi_model.py` (bản Colab)
  dùng đặc trưng sin/cos cố định; trang ghi một dòng phân biệt hai bản.

**Trang `/evaluation`** (góp ý 6, 7): biểu đồ vẽ từ dữ liệu JSON, không dùng ảnh tĩnh làm chính:
- Bảng chính: kết quả mục 5.10 trên Đà Nẵng, cột nhóm HR@10 / NDCG@10 / MRR@10, tô nhóm theo loại
  (không học, ML truyền thống, GNN), TAS-GNN được đánh dấu là model chính.
- Tab "Lượt Colab 3 seed": 9 mô hình từ `training-summary.json`, có thanh sai số, chuyển Đà Nẵng ↔ Gowalla,
  ghi rõ đây là kiến trúc bản Colab.
- Ablation: TAS-GNN đầy đủ so với bỏ thời gian, bỏ không gian, bỏ danh mục (từ lượt Colab).
- Đường học (loss, HR@10 validation theo epoch) nếu dữ liệu có trong summary; nếu không, giữ ảnh PNG có sẵn.
- Giải thích từng chỉ số bằng một câu và công thức; giao thức chia theo thời gian toàn cục.
- Bảng số đầy đủ + tải CSV.

**Trang `/data`** (góp ý 1, 4): sơ đồ cột của 3 file CSV, thống kê theo danh mục và quận, phân bố check-in theo giờ,
nguồn gốc từng trường (OSM thật / mô phỏng), bảng so sánh với Gowalla; phần đồ thị tri thức: lược đồ nút–cạnh,
số lượng lấy từ `/api/kg/stats`, khung xem đồ thị tương tác quanh một POI chọn được, và câu Cypher tương ứng.

### 5.8 Giao diện

Giữ tinh thần hiện tại (nền giấy sáng, xanh lá đậm, điểm nhấn cam đất, tiêu đề serif) nhưng làm lại cho đạt chuẩn:
- Cỡ chữ nội dung tối thiểu 14px, chú thích tối thiểu 12px (hiện nhiều chỗ 8–10px); tương phản đạt WCAG AA.
- Thanh điều hướng trên cùng thay sidebar, có menu tài khoản; di động có thanh dưới.
- Thẻ địa điểm: hiện chưa có ảnh thật (OSM không cấp ảnh). Dùng ô minh họa theo danh mục kèm bản đồ thu nhỏ
  vị trí thay cho hình khối trừu tượng hiện tại. Không dùng ảnh lấy từ nguồn không rõ bản quyền.
- CSS tách khỏi một dòng nén trong `globals.css` thành các token và lớp dùng lại; dùng Tailwind 4 đã có sẵn.
- Trạng thái đang tải, rỗng, lỗi cho mọi trang; tôn trọng `prefers-reduced-motion`.

### 5.10 So sánh với baseline machine learning

Script mới `src/benchmark_ml.py`, chạy trên máy cá nhân (CPU), dùng đúng cách chia và cách tính của
`src/baselines_check.py` (80/20 theo thời gian từng user, chỉ tính POI mới, xếp hạng trên toàn bộ catalog),
bổ sung MRR@K. Kết quả ghi `outputs/benchmark_ml_danang.csv` và `FE/public/artifacts/benchmark-ml.json`.

| Nhóm | Phương pháp | Ghi chú |
|---|---|---|
| Không học | Phổ biến chung; phổ biến theo giờ; giờ × khoảng cách liền trước | đã có |
| ML truyền thống | User-KNN (cosine) | dùng lại `src/baselines/user_cf.py` |
| ML truyền thống | Item-KNN (cosine) | mới |
| ML truyền thống | BPR-MF (phân rã ma trận, dim 64) | mới, huấn luyện tại chỗ |
| ML truyền thống | Gradient Boosting xếp hạng theo đặc trưng: giờ, thứ, khoảng cách tới tâm lịch sử của user, danh mục, độ phổ biến, độ phổ biến theo giờ, tỉ lệ danh mục trong lịch sử user | mới; `HistGradientBoostingClassifier` của scikit-learn, mẫu âm 1:4; siêu tham số chọn trên 10% cuối của tập train |
| GNN | LightGCN (đối chứng), TAS-GNN (model chính) | checkpoint trong repo |

Phương pháp nào dùng vị trí check-in liền trước thì ghi rõ trong bảng, vì TAS-GNN không được cấp thông tin đó.
Kết quả ra sao trình bày đúng như vậy. Nếu một baseline thắng TAS-GNN, trang Đánh giá nêu rõ và phân tích lý do.

### 5.9 Tài liệu

- `docs/TRA_LOI_GOP_Y.md`: trả lời lần lượt 9 góp ý, mỗi mục chỉ tới trang web, file code và số liệu tương ứng.
- `README.md` gốc: thay bảng số cũ bằng bảng mục 5.10, thêm Neo4j và đăng nhập
  vào sơ đồ, sửa đường dẫn `F:\dss` thành đường dẫn tương đối.
- `docs/RUNNING.md`: thêm bước Neo4j, `build_kg.py`, biến `.env` mới.
- `RESEARCH_REPORT_TAS_GNN.md`, `../Huong_Dan.md`: sửa mô tả cơ chế thời gian cho khớp code.
- `README.md` và `Huong_Dan.md` nằm ở gốc git (trên `DSS_repo/` một cấp); cả hai thuộc phạm vi sửa.
- `BAO_CAO_TRINH_BAY_DU_AN.md`, `DEPLOYMENT_GUIDE.md`: không viết lại. Thêm một khung ở đầu file ghi
  "tài liệu của phiên bản cũ, số liệu hiện hành xem `docs/TRA_LOI_GOP_Y.md`". *(Lựa chọn của người viết thiết kế.)*

## 6. Kiểm thử

- API (node:test, theo mẫu `apps/api/test`): đăng ký/đăng nhập/sai mật khẩu/cookie giả; lưu và đọc cài đặt;
  bộ lọc chủ đề; `recommend` với từng mô hình và khi AI/Neo4j tắt.
- ML (pytest): bộ nạp checkpoint trong repo cho điểm trùng với `server.py` trên cùng đầu vào; hàm chỉ số của
  `benchmark_ml.py` được test trên ví dụ tính tay; fold-in trả đủ điểm cho mọi POI và khác độ phổ biến; `useTime=false` không phụ thuộc giờ;
  `model=lightgcn` khi có/không có file.
- KG: `build_kg.py` có hàm thuần chuyển CSV → danh sách nút/cạnh, test không cần Neo4j; chạy lại không tăng số nút.
- Web: `tsc --noEmit`, `next build`, rồi đi hết luồng trên trình duyệt: đăng ký → chọn chủ đề → thích 3 nơi →
  gợi ý đổi → đổi mô hình ở cài đặt → gợi ý đổi → xem đồ thị.

## 7. Phần để người triển khai tự quyết

- Thư viện vẽ biểu đồ và vẽ đồ thị (gợi ý: Recharts, `react-force-graph-2d` hoặc Cytoscape).
- Cách chia component và file trong `FE/src`.
- Quy tắc cụ thể để đánh dấu POI ẩn và 4 user được chọn làm tài khoản demo.
- Chi tiết hình ảnh của thẻ địa điểm, miễn đạt mục 5.8.

## 8. Thứ tự làm

Chưa biết ngày bảo vệ, nên xếp theo thứ tự: thứ trả lời trực tiếp góp ý của Thầy làm trước, thứ làm đẹp làm sau.

1. `ml/serve` nạp checkpoint trong repo; `benchmark_ml.py` và bảng kết quả.
2. Hạ tầng: compose (MySQL + Neo4j), schema mới, `db:init`, `build_kg.py`.
3. API: đăng nhập, cài đặt, chủ đề, KG, mở rộng `recommend`; `ml/serve` thêm model/useTime/fold-in.
4. Web: khung giao diện + đăng nhập → trang chủ + chủ đề → mô hình/đánh giá/dữ liệu → cài đặt → khám phá.
5. Tài liệu (`TRA_LOI_GOP_Y.md` trước), chạy thử toàn bộ.

## 9. Việc cần người dùng cung cấp

- Bật Docker Desktop khi chạy thử.
