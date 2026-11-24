# Frontend Đà Nẵng DSS

Ứng dụng Next.js, React, TypeScript, Tailwind CSS và Leaflet. Thư mục `FE`
có `package.json`, `package-lock.json` và `node_modules` riêng; có thể sao chép
và chạy độc lập với mã Python/API/model.

## Chạy frontend

Yêu cầu Node.js 22+.

```powershell
cd DSS_repo/FE
npm.cmd ci
Copy-Item .env.example .env.local
npm.cmd run dev
```

Mở http://127.0.0.1:3000. Chỉ copy `.env.example` ở lần thiết lập đầu;
sửa `API_URL` trong `.env.local` nếu NestJS chạy ở địa chỉ khác.
Mặc định `API_URL=http://127.0.0.1:4000`.

Frontend gọi `/api/*`; Next.js proxy tới NestJS qua HTTP. NestJS gọi dịch vụ
Python inference; FE không import code Python, checkpoint hoặc dữ liệu model.
Để lấy dữ liệu/gợi ý, chạy các dịch vụ backend theo [hướng dẫn](../docs/RUNNING.md).

Bản đồ nền dùng Esri World Street Map và dự phòng OpenStreetMap. Khi một nguồn
không tải được tile, FE chuyển sang nguồn còn lại; nếu cả hai lỗi, bản đồ hiện
thông báo và nút **Thử tải lại**. Marker và danh sách địa điểm vẫn thao tác được.
Trình duyệt cần truy cập Internet để tải lớp nền. Nguồn Esri đã được kiểm tra
bằng tile thực tại trung tâm Đà Nẵng sau khi nguồn OSM gặp lỗi phân giải DNS.

## Kiểm tra và build

```powershell
npm.cmd run typecheck
npm.cmd run build
npm.cmd start
```

Từ thư mục `DSS_repo` cũng có thể dùng `npm.cmd run dev:fe` hoặc
`npm.cmd run build:fe` sau khi cài dependency trong `FE`.

## Các luồng demo trên giao diện

- Chọn **Cafe sáng gần bạn**, **Một bữa tối thảnh thơi** hoặc **Khám phá theo sở thích** để gửi truy vấn thực tới API.
  Kịch bản cá nhân hóa chỉ bật khi đã tải được danh sách người dùng; nguồn gợi ý hiển thị theo kết quả thực tế trả về.
- **Khám phá theo sở thích** tìm trong tất cả danh mục. Tab **Tất cả** hiển thị xen kẽ gợi ý theo thứ hạng trong từng danh mục;
  chọn tab riêng để xem cà phê, nhà hàng, khách sạn hoặc tham quan. TOPSIS không so điểm giữa các danh mục.
- Bật **Tự điều chỉnh** để thay đổi năm mức ưu tiên. FE chuyển các mức 1–9 thành ma trận AHP đối ứng, nhất quán;
  bấm **Tìm địa điểm** để API tính lại trọng số và xếp hạng TOPSIS.
- Khi sửa bộ lọc, thông báo nhắc áp dụng thay đổi; phần ngữ cảnh kết quả vẫn chỉ người dùng, giờ/ngày và ngân sách của lần tìm thành công gần nhất.
  Phản hồi lưu theo người dùng của kết quả đó, tránh gắn nhầm khi bộ lọc chưa được áp dụng.
- Tìm tên hoặc khu vực có dấu/không dấu; chọn marker để đưa địa điểm tương ứng vào vùng nhìn của danh sách.
  Đường nối trên bản đồ minh họa khoảng cách chim bay, không phải tuyến đường di chuyển.
- Dữ liệu mô phỏng và ý nghĩa tương đối của điểm xếp hạng được ghi rõ trên giao diện.

Kiểm chứng lần cải tiến này: typecheck/build thành công; kiểm tra HTTP với MySQL/API thật cho ba kịch bản
và trọng số tùy chỉnh, gồm giới hạn giá/bán kính và CR hợp lệ. Nhật ký tại `../outputs/qa/fe-improvements.json`.
Chưa thực hiện kiểm tra giao diện bằng trình duyệt trong phiên này vì không có trình duyệt kết nối.

## Demo HTML cũ

File `public/demo_danang.html` được giữ nguyên và phục vụ bởi Next.js tại
http://127.0.0.1:3000/demo_danang.html.
Demo này gọi `/legacy-api/*`; Next.js proxy tới `server.py` theo `LEGACY_API_URL`
(mặc định `http://127.0.0.1:8000`). Để chạy demo cũ riêng, mở terminal tại
`DSS_repo` và chạy `python server.py`, đồng thời chạy FE ở terminal khác.

Để chạy cả hai giao diện cùng lúc, đặt `LEGACY_API_URL=http://127.0.0.1:8001`
trong `FE/.env.local`, chạy `python -m uvicorn server:app --host 127.0.0.1 --port 8001`
từ `DSS_repo`, rồi restart/rebuild FE. Python inference của giao diện chính tiếp tục dùng cổng 8000.
Cấu hình local hiện tại đã dùng cách này.

## Bộ artifacts Colab đã tích hợp

Từ thư mục `DSS_repo`, nhập lại gói bằng:

```powershell
python tools/import_artifacts.py notebooks/dss_full_global_time_641d6a1a_artifacts.zip
```

Lệnh giải nén vào `outputs/imported/dss_full_global_time_641d6a1a`, xác minh 124 file
theo manifest và kiểm tra fingerprint/POI ID với dữ liệu Đà Nẵng trên máy.
Model phục vụ là TAS-GNN seed 42, epoch 16, chia thời gian `global_time`;
LightGCN cùng lượt chạy dùng trong demo HTML. Bộ nạp riêng giữ đúng embedding
không gian của phiên bản Colab này. Model cũ ở `outputs/colab` được giữ lại.

Restart Python sau khi nhập. Giao diện chính hiển thị bộ model trên kết quả;
chọn **Về hệ thống** hoặc mở http://127.0.0.1:3000/training để xem bảng
trung bình/độ lệch chuẩn qua 3 seed, biểu đồ Đà Nẵng/Gowalla và tải CSV/báo cáo.
Gowalla là thí nghiệm độc lập; gợi ý bản đồ sử dụng catalog/model Đà Nẵng.
FE chỉ chứa báo cáo và ảnh trong `public/artifacts`; checkpoint nằm ở Python.

Đã kiểm tra build/typecheck, 21 test Python, 7 test API và HTTP qua FE → NestJS →
Python/MySQL; TAS-GNN và LightGCN cho điểm khớp code gốc trong ZIP trên các truy vấn
đối chiếu. Chưa kiểm tra trực quan bằng trình duyệt do chưa có trình duyệt kết nối.
