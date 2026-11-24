# Chạy DSS: Colab + Next.js + NestJS + MySQL

Kiến trúc mới nằm hoàn toàn trong `DSS_repo`. Code Python/demo cũ được giữ để đối chiếu.
Không dùng thư mục `../BE_API` của phiên bản cũ.
Frontend nằm riêng trong `FE`, có dependency/lockfile riêng và không thuộc npm workspace backend.
Python API/model không phục vụ giao diện HTML. Xem thêm [FE/README.md](../FE/README.md).

```text
Colab notebook ── train/validation/refit/test ── artifacts
                                                   │
FE/Next.js :3000 ── /api proxy ── apps/api/NestJS :4000 ── ml/Python :8000
                                    │                    │
                               MySQL :3306          artifact + fit graph
                               hoặc :3307
```

## 0. Chạy nhanh bản hiện tại

Thành phần mới so với mô tả bên dưới: Neo4j (đồ thị tri thức), đăng nhập theo tài khoản, model lấy từ
`outputs/checkpoints` (không cần file zip Colab).

```powershell
cd DSS_repo
npm.cmd ci
npm.cmd --prefix FE ci
python -m pip install -r ml/requirements.txt
Copy-Item apps/api/.env.example apps/api/.env   # rồi đổi AUTH_SECRET thành chuỗi ngẫu nhiên ≥ 32 ký tự
```

**Cách A, đầy đủ (cần Docker Desktop đang chạy):**

```powershell
docker compose up -d --wait        # MySQL :3306 và Neo4j :7474/:7687
npm.cmd run db:init                # nạp 996 địa điểm, 36.210 check-in, tạo 4 tài khoản demo
python tools/build_kg.py           # dựng đồ thị tri thức: 2.512 nút, 54.343 cạnh
```

Nếu Docker báo cổng 3306 đã bị chiếm (máy có sẵn MySQL khác, kể cả trong WSL): tạo file `.env` cạnh
`compose.yaml` với dòng `MYSQL_HOST_PORT=3307`, đổi `DB_PORT=3307` trong `apps/api/.env`, rồi chạy lại lệnh trên.

Ba terminal:

```powershell
python -m uvicorn ml.serve:app --host 127.0.0.1 --port 8000
npm.cmd run dev:api
npm.cmd run dev:fe
```

**Cách B, không cần Docker (dự phòng cho buổi demo):** API đọc thẳng CSV và giữ tài khoản, cài đặt,
phản hồi trong bộ nhớ (mất khi tắt API). Không có Neo4j nên nút "Vì sao gợi ý?" và khung xem đồ thị báo chưa bật.

```powershell
python -m uvicorn ml.serve:app --host 127.0.0.1 --port 8000
npm.cmd run dev:api:memory
npm.cmd run dev:fe
```

Mở http://127.0.0.1:3000.

- **Tài khoản demo:** `demo_cafe`, `demo_amthuc`, `demo_thamquan`, `demo_dadang`; mật khẩu là `DEMO_PASSWORD` trong `apps/api/.env`.
- **Model:** `ml.serve` nạp `outputs/checkpoints/temporal_gnn_danang.pt` và `lightgcn_danang.pt`. Nếu có
  `MODEL_PATH` hoặc `outputs/active_artifact.json` (gói Colab đã nhập) thì gói đó được ưu tiên.
- **Chạy lại bảng so sánh (có biểu đồ):** mở lần lượt `notebooks/01_du_lieu_va_baseline_heuristic.ipynb`, `02_baseline_machine_learning.ipynb`,
  `03_so_sanh_voi_gnn.ipynb` bằng VS Code hoặc Jupyter rồi chọn Run All; hoặc chạy cả ba một lệnh: `python tools/build_notebooks.py`.
  Bản không có biểu đồ: `python src/benchmark_ml.py` (cùng kết quả). **Cập nhật số liệu trang Dữ liệu:** `python tools/export_data_profile.py`.
- **Ảnh và sao thật từ Google Maps (tùy chọn):** cần API key, xem [GOOGLE_PLACES.md](GOOGLE_PLACES.md).
- **Kiểm tra:** `python -m pytest tests -q`, `npm.cmd test`, `npm.cmd --prefix FE run build`.

Neo4j Browser: http://127.0.0.1:7474 (user `neo4j`, mật khẩu `NEO4J_PASSWORD`). Thử:
`MATCH (p:POI {id: 1})<-[:VISITED]-(u:User)-[:VISITED]->(q:POI) RETURN p.name, q.name, count(u) AS n ORDER BY n DESC LIMIT 10`

Các mục 1–6 bên dưới mô tả chi tiết từng phần; riêng mục 3 (nhập gói Colab) là tùy chọn.

## 1. Cài dependency

Yêu cầu Node.js 22+, Python 3.11+, MySQL 8.4 hoặc Docker.
Trên PowerShell dùng `npm.cmd` nếu `npm.ps1` bị ExecutionPolicy chặn.

```powershell
cd DSS_repo
npm.cmd ci
npm.cmd --prefix FE ci
python -m pip install -r ml/requirements.txt
```

## 2. MySQL và dữ liệu

Chọn một trong ba cách:

**Máy hiện tại, có `mysqld.exe` trong PATH:**

```powershell
node tools/local-mysql.mjs start
npm.cmd run db:init
```

Helper dùng dữ liệu riêng ở `.runtime/mysql-data`, bind `127.0.0.1:3307`, không cài Windows service.
Helper tạo `apps/api/.env` nếu chưa tồn tại. Có thể chỉ định binary bằng biến `MYSQLD_PATH`.
Lệnh `node tools/local-mysql.mjs stop` dừng instance này. Không xóa thư mục `.runtime` nếu cần giữ phản hồi đã lưu.

**Docker:**

```powershell
docker compose up -d --wait
Copy-Item apps/api/.env.example apps/api/.env
npm.cmd run db:init
```

**MySQL đang có:** tạo database `danang_dss` với charset `utf8mb4`, cấp quyền cho tài khoản ứng dụng,
copy `.env.example` và sửa `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME` trước khi chạy `db:init`.

Không ghi đè `.env` đang dùng khi đổi giữa Docker (3306) và helper (3307).
Tài khoản/mật khẩu ví dụ dành cho môi trường local. Không commit `.env`.

`db:init` tạo bảng rồi upsert 996 POI, 1.500 user, 36.210 check-in từ `data/danang`.
Seed chạy trong transaction, chạy lại không trùng check-in và giữ nguyên phản hồi.
Schema: `apps/api/src/database/schema.sql`. Không có bước xóa hoặc reset dữ liệu.
Nếu dữ liệu CSV được thay toàn bộ bằng bộ khác, dùng database mới; seed không xóa các ID cũ.

## 3. Huấn luyện trên Google Colab

```powershell
python tools/build_notebook.py
```

Mở [Google Colab](https://colab.research.google.com/), chọn notebook `notebooks/DSS_POI_Colab.ipynb`, chọn T4 GPU và **Run all**.
Notebook tự tải dữ liệu; **không upload CSV/ZIP, không mount Drive, không cần clone repo**.

- **Đà Nẵng:** CSV từ GitHub public `NHP28/DSS`, pin commit `a3f6059c0594788e42c9746debf33d803723fb31` và SHA256 từng file.
- **Gowalla:** file check-in chính thức từ [Stanford SNAP](https://snap.stanford.edu/data/loc-gowalla.html), pin SHA256,
  đọc chunk và lọc lặp ≥15 POI/user, ≥10 user/POI. Dữ liệu thực, không tự tạo category/rating/giá.
- Mặc định `DATASETS = ["danang", "gowalla"]`, `RUN_MODE = "full"`: train hai model riêng cho mỗi bộ.
  Đà Nẵng tối đa 20 epoch, Gowalla 10, seed 42; early stopping dựa trên validation HR@10.
- `GOWALLA_MAX_USERS = None` dùng toàn bộ sau lọc. Đổi thành `2000` để thử subset ngẫu nhiên có seed;
  báo cáo ghi rõ subset, không gọi đó là full benchmark. Bộ Gowalla đầy đủ cần nhiều thời gian/GPU hơn.
- `RUN_MODE = "smoke"` chạy 24 user mỗi bộ, 1 epoch, dim 16, 1 lớp; artifact gắn cờ `smoke_run`.
- `SEEDS = [42, 123, 2026]` nếu cần mean/std; không lựa chọn seed từ test.
- Evaluation full catalog theo batch, không sampled negatives. Hạ `EVAL_BATCH_SIZE` từ 128 xuống 32 khi thiếu VRAM.
- Kết quả đóng gói vào `dss_two_datasets_artifacts.zip`:

```text
danang/tas_gnn.pt
danang/lightgcn.pt
danang/metrics.json
gowalla/tas_gnn.pt
gowalla/lightgcn.pt
gowalla/metrics.json
all_datasets_comparison.csv
comparison.png
manifest.json
```

**Nhập gói full `global_time` đã tải từ Colab:**

```powershell
python tools/import_artifacts.py notebooks/dss_full_global_time_641d6a1a_artifacts.zip
```

Tool xác minh manifest SHA256, kiểm tra dữ liệu/ID và tạo bản serving có khai báo
kiến trúc `spatial_history_v2`. Bộ model này bổ sung embedding không gian từ lịch sử
fit của user; format checkpoint vẫn là 1 nên cần khai báo kiến trúc để tính điểm đúng.
Tool ghi `outputs/active_artifact.json`; `ml.serve` và `server.py` cùng đọc cấu hình này.
Artifact gốc được giữ ở `outputs/imported`, model cũ ở `outputs/colab` vẫn còn nguyên.
Restart Python sau khi nhập. `MODEL_PATH` có độ ưu tiên cao hơn cấu hình active.

Báo cáo/ảnh được xuất sang `FE/public/artifacts`, xem tại `/training` hoặc **Về hệ thống**.
Gowalla là thí nghiệm độc lập; catalog/model Đà Nẵng phục vụ ứng dụng.
Fingerprint được kiểm tra qua các bản chuẩn hóa LF/CRLF trước khi thêm hash checkout
Windows vào alias; tool không bỏ qua kiểm tra nội dung dữ liệu.

Với checkpoint kiến trúc cũ `poi_graph_v1`, có thể copy nội dung `danang/` vào
`outputs/colab/` rồi đặt `MODEL_PATH=outputs/colab/tas_gnn.pt`.

Có thể tải và train bằng cùng mã trên máy cá nhân:

```powershell
python -m ml.datasets all
python -m ml.poi_model --data-dir outputs/datasets/datasets/danang --output-dir outputs/colab --epochs 20
python -m ml.poi_model --data-dir outputs/datasets/datasets/gowalla_full --output-dir outputs/gowalla --epochs 10 --batch-size 4096
```

Download có cache/checksum; không tự thay Gowalla bằng dữ liệu giả khi nguồn tải lỗi.
Notebook hiện đã chạy smoke local qua tất cả cell trên hai nguồn thật; full train Gowalla trên GPU Colab chưa được thực hiện tại môi trường này.
Artifact cũ từ lượt Đà Nẵng 12 epoch/seed 42/CPU vẫn ở `outputs/colab`, được giữ nguyên.

## 4. Chạy ba tiến trình

Terminal 1, từ `DSS_repo`:

```powershell
python -m uvicorn ml.serve:app --host 127.0.0.1 --port 8000
```

Terminal 2:

```powershell
npm.cmd run dev:api
```

Terminal 3, chạy riêng từ `FE`:

```powershell
cd DSS_repo/FE
npm.cmd run dev
```

Mở **http://127.0.0.1:3000**. Frontend gọi `/api` cùng origin, Next.js proxy tới NestJS.
Từ `DSS_repo` có thể dùng `npm.cmd run dev:fe`; `dev:web` vẫn là lệnh tương đương.
API dev biên dịch bằng TypeScript để giữ decorator metadata; sửa code API thì chạy lại `dev:api`
hoặc chạy `npx.cmd tsc -w -p apps/api/tsconfig.json` ở terminal khác. Không dùng `tsx` để chạy NestJS.

Build và chạy production local:

```powershell
npm.cmd run build
npm.cmd run start -w @dss/api
# Terminal khác:
npm.cmd --prefix FE start
```

`API_URL` trong `FE/.env.local` đổi địa chỉ NestJS; thay đổi này cần restart/rebuild Next.js.
`AI_URL` trong `apps/api/.env` đổi inference URL. `MODEL_PATH` của Python đổi artifact.
Inference chỉ lắng nghe loopback; không cần CORS hoặc ngrok. Model chỉ tải lúc khởi động, thay artifact thì restart.
Ứng dụng hiện là bản nghiên cứu local, chưa có đăng nhập/phân quyền cho nhiều người dùng.

Demo HTML cũ nằm tại `FE/public/demo_danang.html`, mở qua
http://127.0.0.1:3000/demo_danang.html. Demo gọi Next.js proxy `/legacy-api` tới
`server.py` theo `LEGACY_API_URL` (mặc định cổng 8000). Để chạy cùng giao diện chính,
đặt `LEGACY_API_URL=http://127.0.0.1:8001` trong `FE/.env.local`, restart/rebuild FE,
và chạy `python -m uvicorn server:app --host 127.0.0.1 --port 8001` ở terminal riêng.
`server.py` dùng TAS-GNN/LightGCN trong bộ active và hiển thị seed/epoch trên demo.
Python không còn phục vụ trang tại `/` hoặc `/demo`.

## 5. Chức năng và API

- Bộ lọc: người dùng hoặc khách mới, tọa độ/GPS, giờ, thứ, danh mục, bán kính, ngân sách, ẩn đã ghé.
- 4 preset trọng số; TOPSIS xếp hạng **riêng từng danh mục** để tránh so giá khách sạn với cà phê.
- Bản đồ Leaflet/OSM, chọn địa điểm, xem giải thích, mở chỉ đường.
- So sánh tối đa 3 địa điểm cùng danh mục; like/đã ghé lưu MySQL khi chọn user có sẵn.
- Phản hồi `visit` được dùng để ẩn địa điểm trong lần tìm tiếp; like/dislike được lưu cho vòng huấn luyện sau,
  chưa cập nhật trọng số mô hình trực tuyến.
- Khi thiếu AI/artifact không khớp fingerprint hoặc ID, dùng hourly popularity và hiển thị rõ nguồn.
  Khách mới dùng baseline từ artifact, không mượn embedding của user khác.
- Điểm model được min-max theo catalog, là điểm xếp hạng tương đối, không phải xác suất.
- Bản đồ cần kết nối tới máy chủ tile Esri hoặc OpenStreetMap. FE tự chuyển nguồn khi tải lỗi,
  hiện thông báo/nút thử lại nếu cả hai nguồn đều lỗi. Các minh họa trên thẻ là đồ họa danh mục, không phải ảnh thực địa.

| Method | Endpoint | Chức năng |
|---|---|---|
| GET | `/api/health` | MySQL + tình trạng AI |
| GET | `/api/stats` | Số POI/user/check-in/feedback |
| GET | `/api/pois?category=cafe&limit=100` | Catalog từ MySQL |
| GET | `/api/users?limit=1500` | Chọn user |
| GET | `/api/presets` | Thứ tự tiêu chí + preset |
| POST | `/api/recommendations` | Bộ lọc + AI + DSS |
| POST | `/api/feedback` | `{userId, poiId, action: like/dislike/visit}` |
| GET | `:8000/health` | Artifact sẵn sàng hay chưa |
| POST | `:8000/score` | Nội bộ: `{userId?, hour, dayOfWeek}` |

Ví dụ PowerShell:

```powershell
$body = @{ userId=12; latitude=16.0678; longitude=108.2208; hour=8; dayOfWeek=0; category='cafe'; radiusKm=10; maxPrice=100000; preset='balanced'; topK=10; excludeVisited=$true } | ConvertTo-Json
Invoke-RestMethod http://127.0.0.1:4000/api/recommendations -Method Post -ContentType application/json -Body $body
```

API còn nhận `matrix: number[5][5]` theo thứ tự distance/rating/price/preference/popularity.
Ma trận cần đối ứng, đường chéo 1, phần tử trong [1/9,9], CR < 0,1; sai trả HTTP 400.
Khi dùng matrix hợp lệ, trọng số matrix thay preset. `topK` áp dụng mỗi danh mục.

## 6. Kiểm tra

```powershell
npm.cmd run typecheck
npm.cmd test
npm.cmd run build
python -m unittest discover -s tests -v
python tools/check_notebook.py
# Khi MySQL, Python, NestJS và Next.js đang chạy:
node tools/check-live.mjs
```

`check_notebook.py` kiểm tra schema và thực thi tất cả cell bằng cấu hình smoke, bỏ cell cài pip và dùng backend đồ thị Agg.
Đã thử tải thật từ GitHub/SNAP và train smoke cả hai bộ; Colab GPU chưa được chạy trực tiếp trên hạ tầng Google.
`check-live.mjs` kiểm tra HTTP và ghi một phản hồi like cho user 12 trong database đang cấu hình.
Chỉ chạy lệnh này trên database thực nghiệm của dự án.

Đã kiểm tra với MySQL 8.4.3, Node 24.15, Next.js 16.4.5, NestJS 11.2.8, Tailwind 4.3.4, Python 3.11.9, PyTorch 2.11 CPU.
Môi trường công cụ hiện không có trình duyệt khả dụng nên chưa kiểm tra trực quan desktop/mobile hoặc thao tác bản đồ bằng trình duyệt.

Xem [review mô hình](MODEL_REVIEW.md) và [kết quả chạy](experiments/seed42_cpu.json).

Tham khảo chính thức khi triển khai: [Next.js rewrites](https://nextjs.org/docs/app/api-reference/config/next-config-js/rewrites),
[Tailwind PostCSS](https://tailwindcss.com/docs/installation/using-postcss),
[NestJS ValidationPipe](https://docs.nestjs.com/techniques/validation),
[PyTorch serialization](https://docs.pytorch.org/docs/stable/notes/serialization).
