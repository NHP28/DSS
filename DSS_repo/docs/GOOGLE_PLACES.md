# Ảnh và điểm đánh giá thật từ Google Maps

Tính năng tùy chọn. Khi bật, thẻ địa điểm hiện **ảnh** và **số sao + số lượt đánh giá thật** lấy từ Google Places API.
Không bật thì website chạy đúng như trước (không ảnh, số sao mô phỏng).

## Bật tính năng (làm một lần)

1. Vào <https://console.cloud.google.com/>, tạo một project và **gắn tài khoản thanh toán** (Google bắt buộc, kể cả khi chỉ dùng phần miễn phí).
2. Mở *APIs & Services → Library*, tìm và bật **Places API (New)**.
3. Mở *APIs & Services → Credentials → Create credentials → API key*. Ở mục *API restrictions* chọn chỉ **Places API (New)**.
4. Dán key vào `apps/api/.env`:

   ```
   GOOGLE_PLACES_API_KEY=dán-key-vào-đây
   ```

5. Ghép 996 địa điểm với Google (thử 20 địa điểm trước, rồi chạy hết):

   ```powershell
   python tools/match_google_places.py --limit 20
   python tools/match_google_places.py
   ```

   Kết quả là `data/danang/google_place_ids.csv`. Lệnh chạy lại được: dòng đã có sẽ bỏ qua.
6. Khởi động lại API (`npm.cmd run dev:api`). Kiểm tra: <http://localhost:4000/api/system> phải có `"places":true`.

Không đưa API key lên git: `apps/api/.env` đã nằm trong `.gitignore`.

## Cách hoạt động

| Bước | Ở đâu | Gọi Google |
|---|---|---|
| Ghép địa điểm OSM ↔ Google theo tên và tọa độ, chỉ lưu `place_id` | `tools/match_google_places.py` | Text Search, 1 lần / địa điểm, chạy một lần |
| Lấy sao, số lượt đánh giá, ảnh đầu tiên khi thẻ cuộn vào màn hình | `apps/api/src/google/google.service.ts`, `GET /api/pois/:id/google` | Place Details + Place Photo, 2 lần / địa điểm |
| Hiển thị | `FE/src/components/place-card.tsx` | không |

- Một địa điểm chỉ được ghép khi Google trả về nơi **cách dưới 250 m và tên giống rõ**, hoặc **dưới 60 m và tên giống vừa**. Thà không có ảnh còn hơn ảnh của quán khác. Địa điểm không ghép được giữ giao diện cũ.
- API key chỉ nằm ở máy chủ; trình duyệt chỉ nhận địa chỉ ảnh.
- Tên tác giả ảnh được ghi dưới ảnh, theo yêu cầu ghi nguồn của Google.

## Chi phí và giới hạn

Sao và ảnh thuộc nhóm giá **Enterprise** của Places API; mỗi nhóm có một lượng gọi miễn phí mỗi tháng rồi mới tính tiền.
Bảng giá thay đổi theo thời gian, hãy xem con số hiện hành tại <https://developers.google.com/maps/billing-and-pricing/pricing> trước khi demo.

Để không bị tính tiền ngoài ý muốn, API tự giới hạn:

| Biến trong `apps/api/.env` | Mặc định | Ý nghĩa |
|---|---|---|
| `GOOGLE_PLACES_DAILY_LIMIT` | 300 | Số địa điểm tối đa được hỏi Google mỗi ngày (mỗi địa điểm = 1 Place Details + 1 Place Photo). Hết mức thì các thẻ còn lại hiện như cũ. |
| `GOOGLE_PLACES_CACHE_MINUTES` | 360 | Giữ kết quả trong bộ nhớ bấy nhiêu phút; xem lại cùng địa điểm không gọi Google nữa. Tắt API là mất. |

Nên đặt thêm **hạn mức (quota) và cảnh báo ngân sách** ngay trong Google Cloud Console; đó mới là chốt chặn chắc chắn.

## Điều cần nói rõ khi bảo vệ

- Điều khoản Google **không cho lưu** ảnh và điểm đánh giá vào cơ sở dữ liệu; chỉ `place_id` được lưu lâu dài. Vì vậy dữ liệu này được lấy trực tiếp khi hiển thị.
- **Sao của Google chỉ để người dùng tham khảo.** Mô hình TAS-GNN, bước xếp hạng AHP-TOPSIS và toàn bộ bảng so sánh vẫn dùng điểm đánh giá mô phỏng trong bộ dữ liệu. Thứ hạng gợi ý không đổi khi bật tính năng này.
- Cần mạng Internet lúc demo. Mất mạng hoặc hết hạn mức thì website vẫn chạy, chỉ không có ảnh.
