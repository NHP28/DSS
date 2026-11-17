# Review mô hình và notebook Colab

Repo ban đầu chưa có `.ipynb`; phần huấn luyện nằm trong script Python.
Notebook mới `notebooks/DSS_POI_Colab.ipynb` dùng mã trong `ml/poi_model.py`, nhúng trực tiếp để chạy độc lập.
Code cũ và báo cáo cũ được giữ nguyên; checkpoint cũ không bị ghi đè.

## Cập nhật notebook: tự tải và thêm benchmark Gowalla

- Mặc định chạy cả Đà Nẵng và Gowalla, tự tải từ GitHub/SNAP với SHA256; không có `files.upload()` hoặc bước mount Drive.
- `ml/datasets.py` chuẩn hóa Gowalla gốc theo chunk, loại event/GPS lỗi, trùng `(user, POI, timestamp)`, lọc core lặp
  ≥15 POI/user và ≥10 user/POI. Thống kê sau xử lý được ghi lại; số event có thể khác pipeline CPR cũ vì loại bản ghi trùng/lỗi.
- Gowalla không có category: model bỏ category embedding và dùng time × learned item interaction. Không gán tất cả thành cafe.
  Giờ/thứ xấp xỉ theo kinh độ, chưa có timezone/DST thực tế. Không sử dụng social edges trong hai kiến trúc hiện tại.
- Scoring/evaluation theo batch và tìm top-K trên toàn catalog để giảm chi phí khi có hàng chục nghìn POI.
  Có kiểm tra scoring batch khớp scoring cặp, cả khi có và thiếu category.
- Split giữ ít nhất một nhóm timestamp mỗi phần, kể cả user có nhiều sự kiện cùng thời điểm.
- Kết quả/checkpoint hai bộ nằm ở thư mục riêng; chỉ artifact Đà Nẵng dùng cho ứng dụng Đà Nẵng.
- Toàn bộ raw Gowalla đã tải và lọc thử; tất cả cell notebook đã chạy smoke trên hai nguồn dữ liệu thật.
  Chưa có full GPU training Gowalla, nên chưa báo cáo accuracy đầy đủ cho bộ này.

## Các vấn đề tìm thấy

| Mức độ | Vị trí cũ | Phát hiện và ảnh hưởng | Cách xử lý trong luồng mới |
|---|---|---|---|
| Cao | `src/train_compare.py::generate_batches` | Chọn mẫu âm ngẫu nhiên toàn catalog có thể chọn chính positive hoặc POI đã ghé, khiến tín hiệu BPR mâu thuẫn. | Loại toàn bộ positive của user trong **tập fit**, có kiểm tra user đã ghé hết catalog. Không nhìn nhãn held-out. |
| Cao | `src/models/temporal_gnn.py::compute_bpr_loss`, `predict_for_user_at_time` | Train dùng item context nhân sigmoid category; predict cộng cùng item context cho mọi POI, làm sai hàm chấm điểm lúc phục vụ. | Dùng chung `score_pairs` cho loss và predict mọi POI. Có regression test so điểm từng cặp và toàn catalog. |
| Cao | `src/train_compare.py::train_and_compare` | Tạo tune set nhưng không dùng để chọn số epoch/checkpoint. Không có early stopping hoặc seed cố định. | Chọn epoch bằng validation HR@10; refit train+validation từ đầu đúng số epoch; test sau cùng. |
| Cao | `server.py` và `src/evaluate_time_aware.py` | Checkpoint huấn luyện trên graph 70% nhưng phục vụ/đánh giá dựng graph 80%; graph không nằm trong artifact. | Lưu `fit_pairs` và dựng lại chính xác graph đã fit. Metadata ghi split protocol, ID mapping, cấu hình, fingerprint. |
| Cao | `src/models/temporal_gnn.py` | `category_ids` là tensor CPU; indexing bằng CUDA index trước `.to(device)` có thể lỗi khi train trên Colab GPU. | Tọa độ/category/chuẩn hóa là registered buffers, di chuyển cùng model. |
| Cao | `src/train_compare.py::temporal_split`, `evaluate_model` | Gộp mọi nhãn test của user nhưng dùng ngữ cảnh của sự kiện test cuối cùng để chấm tất cả. Giao thức không phản ánh next-POI theo từng thời điểm. | Đánh giá từng event ở đúng giờ/thứ của nó, chỉ lấy context biết tại truy vấn. Tách rõ HR sự kiện với Recall tập POI. |
| Vừa | `src/models/temporal_gnn.py::ContinuousTimeEncoder` | Fourier trên Unix time float32 dễ mất độ chính xác phút/giây và pha lệ thuộc thời điểm tuyệt đối. | Sin/cos chu kỳ ngày/tuần, giờ địa phương từ dữ liệu; timestamp float64 chỉ bổ sung phần trong giờ. |
| Vừa | `SpatialEncoder` và cách gọi | Chuẩn hóa spatial có cờ nhưng không bật mặc định khi train. Tọa độ thô có scale lớn so với embedding. | Center/scale catalog được lưu trong state. |
| Vừa | `src/train_compare.py::evaluate_model` | Truyền embedding theo vị trí đối số vào `predict_for_user_at_time` thực chất rơi vào `user_lat/user_lon`; graph embedding phải tính lại. | Interface dùng một hàm scoring; cache graph embedding khi inference/eval. |
| Vừa | `server.py` | Có thể xây model ngẫu nhiên nếu thiếu checkpoint; fingerprint và ánh xạ ID không được kiểm tra. | Thiếu artifact trả 503 ở AI; NestJS dùng fallback có nhãn rõ. Unknown user không bị clamp sang user khác. |
| Vừa | Script dữ liệu/mô hình cũ | Giả định ID POI/user liên tiếp và thứ tự CSV trùng embedding. | Mapping raw ID ↔ internal index lưu cùng artifact; kiểm tra ID lạ và category. |
| Vừa | Phân chia train/test | Timestamp bằng nhau có thể nằm ở hai tập. | Gom timestamp bằng nhau về cùng partition. |
| Báo cáo | Báo cáo cũ và dữ liệu | Check-in được mô phỏng theo thời gian/địa lý; rating, giá và phổ biến dùng cho demo. Điểm model min-max không phải xác suất. | Ghi provenance/giới hạn trong notebook, API và giao diện; không dùng kết quả này làm bằng chứng cho hành vi thật. |

Các sửa đổi trên áp dụng cho pipeline mới `ml/`; script nghiên cứu cũ được giữ để tái lập và so sánh.

## Giao thức mới

1. Kiểm tra schema, finite values, ID, category; bỏ đúng các event trùng hoàn toàn `(u,l,ts)`, giữ repeated visits.
2. User có ít nhất 5 event; chia theo thời gian từng user 70/10/20, không tách timestamp bằng nhau.
3. Tuning dùng graph/negative từ train. Chọn epoch theo validation HR@10, patience 4.
4. Refit train+validation với số epoch đã chọn, dùng cùng seed và hyperparameter đã định.
5. Test trên event mới so với tập fit; mask tất cả POI đã ghé trong fit. Không dùng vị trí POI đích làm input.
6. So sánh popularity, hourly popularity, LightGCN và TAS-GNN. Metric event-level HR/NDCG/MRR@5/10/20,
   macro-user HR@10, số event bị loại và mẫu số thực tế.

Đồ thị là static LightGCN backbone cộng truy vấn ngữ cảnh thời gian; đây **không phải** thuật toán cập nhật graph online
theo từng sự kiện như các mô hình temporal graph memory. Tên TAS-GNN mô tả kiến trúc trong dự án, không khẳng định một đóng góp mới đã được công bố.

## Kết quả kiểm tra toàn bộ dữ liệu

Chạy ngày 06/11/2026, CPU, seed 42, dim 64, 3 lớp, tối đa 12 epoch, batch 1.024, learning rate 0,001.
1.500 user, 996 POI; 6.811 test event mới được đánh giá, 1.039 test event thuộc lịch sử fit bị loại.
LightGCN chọn epoch 4 qua validation; TAS-GNN chọn epoch 12. Không tối ưu cấu hình theo test.

| Phương pháp | HR@10 | NDCG@10 | HR@20 |
|---|---:|---:|---:|
| Popularity | 6,12% | 2,29% | 11,19% |
| Hourly popularity | 10,53% | 5,13% | 16,37% |
| LightGCN mới | 8,66% | 4,38% | 12,22% |
| TAS-GNN mới | 12,63% | 6,31% | 19,40% |

Đây là một lượt chạy trên dữ liệu mô phỏng, không phải ước lượng cải thiện có ý nghĩa thống kê.
Giao thức và implementation đã thay đổi nên không lấy chênh lệch với bảng cũ làm bằng chứng nhân quả cho từng cải tiến.
Chi tiết raw metrics và lịch sử validation ở `docs/experiments/seed42_cpu.json`.

## Hướng nghiên cứu tiếp theo

- Chạy ≥3 seed, báo cáo mean/std và bootstrap theo user; không chọn model từ test.
- So sánh thêm hourly × khoảng cách từ **vị trí quan sát trước truy vấn**, tuned trên validation; baseline này đã có hiệu quả tốt trong báo cáo cũ.
  Pipeline mới chưa tái chạy baseline địa lý này nên chưa thể khẳng định TAS-GNN tốt nhất mọi phương án.
- Ablation time/spatial/category theo cùng giao thức và budget tuning; pipeline hiện chưa tự động hóa bảng ablation.
- Global temporal split để giảm việc graph của user khác chứa tương tác xảy ra sau timestamp test của user đang đánh giá.
- Đánh giá riêng cold-start, short-history, returning visits và novel visits. Giao thức hiện chỉ đánh giá novel events của user đã có lịch sử.
- Thử dữ liệu check-in thật có nguồn gốc rõ, consent phù hợp, metadata giờ địa phương tin cậy.
- Test latency, độ đa dạng/coverage và tác động của AHP/TOPSIS riêng với accuracy của model; không đồng nhất score TOPSIS với NDCG model.

## Kiểm chứng đã chạy

- 11 Python regression tests: 5 bài cho model/graph/artifact/metric và 6 bài cho downloader, core, Gowalla preprocessing,
  timestamp, missing-category, batch scoring, newline fingerprint và split có nhiều timestamp trùng.
- 7 bài kiểm tra Node: HTTP DTO, xếp hạng/filter/history, AI failure/mismatch, LF/CRLF compatibility, feedback, AHP, TOPSIS.
- Toàn bộ cell notebook chạy smoke local, có export artifact; schema notebook hợp lệ.
- TypeScript, build Next.js/NestJS thành công.
- Luồng thật MySQL 8.4.3 → NestJS → Python → Next.js qua HTTP: seed, known user, cold start, AHP, filter, feedback đọc lại từ DB, proxy.
- Chưa có browser QA do công cụ không có trình duyệt khả dụng; chưa chạy trực tiếp Colab GPU.

Thiết kế notebook tham khảo cách lưu/khôi phục state từ [PyTorch serialization](https://docs.pytorch.org/docs/stable/notes/serialization).
