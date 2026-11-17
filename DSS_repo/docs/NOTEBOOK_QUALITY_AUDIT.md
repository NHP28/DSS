# Đánh giá dữ liệu và nâng cấp notebook POI

Ngày đánh giá: 11/11/2026, múi giờ Asia/Saigon.

Notebook: [DSS_POI_Colab.ipynb](../notebooks/DSS_POI_Colab.ipynb).
Bố cục hiện tại được gộp còn **20 cell: 13 code và 7 Markdown**, giữ các bước phân tích/huấn luyện và mô tả mục đích trong comment.
Số liệu đầy đủ: [dataset_quality_audit.json](experiments/dataset_quality_audit.json).
Audit đọc toàn bộ hai CSV đã xử lý và 6.442.892 dòng Gowalla raw; không huấn luyện lại toàn bộ dataset trong lần audit này.
Mã tái lập audit: [audit_dataset_quality.py](../tools/audit_dataset_quality.py).

## 1. Kết luận về dữ liệu

Hai bộ dữ liệu vượt qua kiểm tra cấu trúc trên snapshot đang có: không có ô thiếu ở các CSV đã xử lý,
không có POI ID trùng, check-in tham chiếu ID không tồn tại, sự kiện `(u,l,ts)` trùng hoặc tọa độ ngoài miền hợp lệ.
Điều này xác nhận chất lượng kỹ thuật của file, chưa xác nhận tính đại diện hay độ chính xác hành vi.

| Chỉ tiêu đo trên toàn bộ dữ liệu đã xử lý | Đà Nẵng | Gowalla |
|---|---:|---:|
| User | 1.500 | 18.737 |
| POI trong catalog | 996 | 32.510 |
| Check-in | 36.210 | 1.278.102 |
| Cặp user–POI duy nhất | 32.661 | 821.931 |
| Độ thưa theo cặp user–POI | 97,81% | 99,87% |
| Tỷ lệ event vượt quá lượt đầu của cặp user–POI | 9,80% | 35,69% |
| POI không có tương tác | **295** | 0 |
| Trung vị event/user | 23 | 40 |
| Thiếu ô / trùng event / ID không tồn tại sau xử lý | 0 / 0 / 0 | 0 / 0 / 0 |
| Giờ/thứ không khớp quy tắc timestamp được khai báo | 0 | 0 |

### Đà Nẵng: phù hợp demo và kiểm tra giả thuyết trên mô phỏng

- Đã đối chiếu thêm script gốc ở cấp workspace, ngoài `DSS_repo`: [crawl_full_danang_osm.py](../../crawl_full_danang_osm.py)
  và [build_danang_dataset.py](../../build_danang_dataset.py). Danh sách 996 tên POI khớp JSON seed hiện có;
  tọa độ, rating, giá, popularity và số review trong CSV cũng khớp các trường nguồn tương ứng.
- Tương tác, rating, giá và độ phổ biến được khai báo là mô phỏng. Kết quả không đủ chứng minh hiệu quả trên người dùng thực.
- **Toàn bộ 295 khách sạn không có check-in**, bằng 29,62% catalog. Không có bằng chứng đánh giá cho gợi ý khách sạn.
  Script chọn hotel làm vị trí xuất phát của khách du lịch nhưng không ghi hotel vào các event; lịch ghé chỉ gồm cafe/restaurant/tourist_spot.
- Check-in chỉ bao phủ cafe (19.275 event), restaurant (10.766) và tourist_spot (6.169).
- Rating chỉ trong 4,1–4,9 và popularity 65–99. Những trường mô phỏng này không dùng làm nhãn chất lượng thực cho DSS.
- District có 13 nhãn raw; chuẩn hóa chuỗi còn 8 nhãn, trong đó có `danang` ở cấp thành phố.
  Cần đối soát địa danh trước khi dùng cho phân tích theo quận/huyện. Notebook chỉ báo cáo, không sửa ngầm CSV.
- CSV không có OSM element ID để đối soát từng POI; cần bổ sung nguồn trích xuất và lịch sử cập nhật nếu dùng cho triển khai thật.
- Crawler hiện lấy node với giới hạn 250 kết quả mỗi tag, khử trùng theo tên và gán quận bằng heuristic khi thiếu nhãn.
  Rating/số review/popularity/giá được sinh ngẫu nhiên. Seed 42 được đặt ở bước sinh check-in, không bao phủ lần cào và gán thuộc tính POI.
- Timestamp trong generator được tạo từ `datetime` chưa gắn timezone; chạy lại trên máy khác timezone có thể đổi Unix time.
  Cần đóng gói snapshot đầu vào, script và cấu hình timezone để tái lập từ đầu, không chỉ tái sử dụng CSV đã pin.
- `curated_highlights` được khai báo bên trong `merge_datasets`, trong khi builder kiểm tra thuộc tính cấp module.
  Nhánh bổ sung curated trong builder hiện không chạy; không dùng comment về danh sách curated làm bằng chứng dữ liệu đã được ghép.
- Ba file tải pin SHA256 hợp lệ. CSV trong checkout khớp cache khi bỏ khác biệt LF/CRLF.
- Fingerprint trong `seed42_cpu.json` cũ **không khớp các fingerprint hiện tại**, kể cả newline aliases.
  Chưa xác định do phiên bản dữ liệu hay cách tính hash; notebook mới không chèn lại các điểm số cũ này.

### Gowalla: phù hợp benchmark lịch sử với phạm vi rõ ràng

- Raw đọc được 6.442.892 dòng, 107.092 user có check-in và 1.280.969 POI ID.
  Con số user này là user trong file check-in, khác tổng node của mạng bạn bè.
- Xác minh raw SHA256 khớp bản pin. Có 29 dòng tọa độ lỗi; metadata tiền xử lý ghi thêm 601 sự kiện trùng đã loại.
- Sau core còn **19,84% event, 17,50% user và 2,54% POI ID** so với raw check-in.
  Đây là benchmark thiên về các user/POI đủ hoạt động, chưa đại diện cho cold-start và long tail của nguồn gốc.
- Dữ liệu lịch sử 2009–2010, không đại diện trực tiếp cho địa điểm/hành vi tại Đà Nẵng hiện nay.
- Không có category/rating/giá. Không suy diễn nhãn cafe cho category thiếu.
- Giờ địa phương dùng kinh độ, chưa xử lý đúng ranh giới timezone/DST.
- Có 1.150 bước liên tiếp vượt ngưỡng chẩn đoán 1.000 km/h và 1 km; 16 bước cùng timestamp nhưng cách nhau trên 1 km.
  Chỉ số dùng tọa độ catalog tĩnh, có thể chịu sai lệch từ dữ liệu vị trí; **không tự động coi toàn bộ là lỗi hoặc xóa**.
- Có 281 POI dùng lại tọa độ và 14 raw POI ID có đường chéo bounding box tọa độ lớn hơn 1 km.
  Cần đối soát trước nghiên cứu chi tiết về di chuyển; vị trí trùng không tự động đồng nghĩa POI trùng.

Nguồn chính thức: [Stanford SNAP — Gowalla](https://snap.stanford.edu/data/loc-gowalla.html).
Trang nguồn công bố 6.442.890 check-in; audit lưu số dòng thực đọc được, không điều chỉnh để ép khớp con số công bố.

## 2. Giao thức mới và phạm vi đánh giá

Notebook mặc định `global_time`, cắt theo timestamp toàn bộ dữ liệu với tỷ lệ mục tiêu 70/10/20.
Chỉ fit graph trên dữ liệu trước thời điểm đánh giá; assert các mốc thời gian không chồng lấn.
Core, catalog và điều kiện đủ lịch sử vẫn lấy từ nguồn đầy đủ: thiết lập còn transductive, chưa hoàn toàn inductive.

| Chỉ tiêu đo trên toàn bộ dữ liệu, global time | Đà Nẵng | Gowalla |
|---|---:|---:|
| Train event | 25.347 | 894.671 |
| Validation event của warm user | 2.025 | 109.658 |
| Test event của warm user | 3.883 | 207.611 |
| Cold-user test event được đếm và loại khỏi bảng warm-user | 3.359 | 48.010 |
| Novel test event | 3.055 | 135.604 |
| Lượt ghé lại trong warm-user test | 21,32% | 34,68% |

Hai bảng kết quả tách biệt: novel visits mask lịch sử fit; all visits giữ lịch sử trong candidate set.
Không cập nhật graph/lịch sử bằng các event test trước đó. Không gọi event HR là Recall theo tập POI duy nhất.
User không xuất hiện trong fit được đánh dấu, không dùng embedding chưa được fit để phục vụ inference.

Audit JSON cũng giữ số liệu **giao thức per-user cũ** để đối chiếu: nó loại 13,24% test event Đà Nẵng
và 38,96% Gowalla khỏi novel metric. Các tỷ lệ này không được dùng thay cho tỷ lệ global time mới.
Động cơ thay giao thức tham khảo [Ji et al., data leakage](https://arxiv.org/abs/2010.11060).

## 3. Rà soát toàn bộ tiêu chí sau nâng cấp

| Tiêu chí | Đã thực hiện | Giới hạn còn lại |
|---|---|---|
| Bài toán, giả thuyết, phạm vi | Nêu câu hỏi về time/spatial và định nghĩa hai scope | Chưa kiểm chứng hành vi thật ở Đà Nẵng |
| Nguồn gốc dữ liệu | URL, commit, checksum, metadata riêng từng bộ; tìm thấy script gốc ở cấp workspace | Thiếu OSM element ID; cần đóng gói script/snapshot/timezone vào repo để tái lập độc lập |
| Kiểm tra cấu trúc | Schema, ID, missing, duplicate, GPS, timestamp | Check hợp lệ không bảo đảm dữ liệu phản ánh thực tế |
| Chất lượng ngữ nghĩa | Cảnh báo GPS, nhãn địa danh, category không có tương tác | Cần nguồn thực hoặc đối soát để khắc phục tận gốc |
| Độ đại diện | Đo coverage, sparsity, core retention và user activity | Thiếu toàn bộ tương tác hotel; core loại long tail |
| EDA | Activity, popularity, category, bản đồ, thứ × giờ | Hình mẫu smoke không đại diện full |
| Ma trận | User–POI mẫu và model × ranking metric | Ma trận mẫu được ghi rõ kích thước/phạm vi |
| Chia tập | Global timeline, timestamp ties, cold-user counts | Catalog/core transductive vẫn được khai báo |
| Baseline | Popularity, hourly, geo-hourly, BPR-MF, LightGCN | Geo dùng vị trí proxy và thang 5 km cố định |
| Kiến trúc và công thức | Giải thích graph, time/spatial/category, BPR, rank metric | Mô hình của dự án, không khẳng định đóng góp mới đã công bố |
| Hyperparameter | Cùng grid learning rate, epoch max và patience | DIM/LAYERS cố định; không phải tìm kiếm toàn bộ không gian |
| Ablation | Bỏ time, spatial, category khi có nhãn | No-space/no-category phải đọc cùng matrix cấu hình vì có nhánh dùng chung |
| Metrics | HR/NDCG/MRR, macro-user HR và coverage mẫu | Chưa có thước đo hài lòng thực/A-B test |
| Độ ổn định | 3 seed mặc định, mean/std dùng toàn bộ seed | Smoke mới chạy 2 seed, 1 epoch |
| Độ bất định | Paired user bootstrap, CI 95% cho macro-user HR chênh lệch | Thăm dò nhiều so sánh, chưa hiệu chỉnh; không gọi CI event HR |
| Phân tích lỗi | Theo giờ, category, lịch sử, độ phổ biến và ví dụ đúng/sai | Slice ít mẫu không đủ suy rộng |
| Tài nguyên | Train/eval time, parameter count, checkpoint size, CUDA memory khi có | Chưa đo full GPU trong phiên làm việc này |
| Inference | Warm cached batch scoring p50/p95 | Chưa phải latency end-to-end qua HTTP |
| Tái lập | Seed, config, phiên bản runtime, nguồn pin, module parity | Phần cứng/driver và thuật toán GPU có thể khác số học |
| Artifact | Mọi model/seed, graph, mapping, trained users, ZIP checksum | Cần chạy full để có artifact benchmark đủ chất lượng |
| Diễn giải và kết luận | Báo cáo sinh từ số liệu thực, nhãn smoke/subset trên hình | Không đảm bảo TAS-GNN thắng baseline |

Confusion matrix không được thêm máy móc: mục tiêu chính là xếp hạng POI.
Notebook dùng ranking metrics và heatmap phù hợp, không dùng accuracy phân loại để thay thế.

## 4. Kiểm chứng đã chạy

- Schema notebook, cú pháp các cell thường và AST các module nhúng khớp nguồn.
- Kiểm tra hồi quy cho tải dữ liệu, metric, graph, artifact, global time, bootstrap, coverage,
  generator inference không làm tắt gradient và fallback cho user chưa được fit.
- Mọi code cell chạy smoke trên CPU với 24 user/dataset, 1 epoch, 2 seed và 2 learning rate.
- Có 66 lượt fit tính cả tuning/refit, 22 checkpoint khôi phục đúng, 10 hình và ZIP đã kiểm tra checksum.
- Bản executed smoke có bảng/hình thực tế tại `outputs/qa/notebook_v3/DSS_POI_Colab.smoke.executed.ipynb`.
- Global time invariants và profile chất lượng cũng được chạy trên toàn bộ 36.210/1.278.102 event.
- Chưa chạy benchmark full GPU 3 seed. Không sử dụng điểm smoke để kết luận model tốt hoặc kém trong triển khai thật.

Tái tạo source notebook: `python tools/build_notebook.py`.
Kiểm tra smoke: `python tools/check_notebook.py`.
Kiểm tra hồi quy: `python -m unittest discover -s tests -p 'test_*.py' -v`.
