# Hoàn thiện đồ án theo góp ý của Thầy — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bổ sung baseline ML, Neo4j, đăng nhập, chủ đề du lịch, trang cài đặt mô hình và các trang Mô hình/Đánh giá/Dữ liệu để website trả lời đủ 9 góp ý.

**Architecture:** Giữ Next.js (`FE`) → NestJS (`apps/api`) → FastAPI (`ml/serve.py`). MySQL giữ tài khoản/cài đặt/phản hồi/catalog; Neo4j giữ đồ thị tri thức chỉ đọc. `ml/serve` nạp hai checkpoint có sẵn trong `outputs/checkpoints`.

**Tech Stack:** Next.js 16, React 19, Tailwind 4, Recharts, NestJS 11 + Fastify, mysql2, neo4j-driver, FastAPI, PyTorch, scikit-learn, Python `neo4j`, Docker Compose.

**Spec:** `docs/superpowers/specs/2026-11-24-gop-y-thay-web-neo4j-design.md`

## Global Constraints

- Không sửa file trong `data/`. Không huấn luyện lại TAS-GNN/LightGCN.
- Model chính TAS-GNN, đối chứng LightGCN; checkpoint: `outputs/checkpoints/temporal_gnn_danang.pt`, `lightgcn_danang.pt`; cấu hình dim 64, time_dim 32, 3 lớp; đồ thị dựng từ 80% check-in đầu của mỗi user (như `server.py`).
- Chia đánh giá: 80/20 theo thời gian từng user, chỉ tính POI mới, xếp hạng toàn catalog.
- Mọi dịch vụ phụ (AI, Neo4j) tắt thì web vẫn chạy và hiện trạng thái dự phòng.
- Mọi chỗ hiển thị số liệu ghi rõ check-in/rating/giá là mô phỏng.
- Chữ nội dung ≥ 14px, chú thích ≥ 12px, tương phản AA, có trạng thái tải/rỗng/lỗi, tôn trọng `prefers-reduced-motion`.
- Không thêm thư viện xác thực; mật khẩu `scrypt`, cookie `httpOnly` ký HMAC, khóa `AUTH_SECRET`.
- Cổng chỉ bind 127.0.0.1. Không commit `.env`.
- Chỉ commit khi người dùng yêu cầu (quy tắc phiên làm việc); các bước "Commit" dưới đây là điểm dừng kiểm tra, không tự chạy `git commit`.

## Review Focus

1. Dịch vụ AI tắt hoặc trả mô hình không có → `recommend` vẫn trả kết quả dự phòng kèm `warning` (test ở Task 6).
2. Tài khoản tự đăng ký có < 3 POI → không gọi fold-in, không lỗi (test ở Task 1 và Task 6).
3. Cookie phiên bị sửa/hết hạn → 401, không lộ dữ liệu tài khoản khác (test ở Task 5).
4. Neo4j tắt → `/api/kg/*` trả 503 có thông báo, `/api/recommendations` không bị ảnh hưởng (test ở Task 7).
5. Bộ lọc chủ đề cho ra 0 ứng viên (bán kính nhỏ, ngân sách thấp) → trả nhóm rỗng, trang hiện trạng thái rỗng (test ở Task 6).

---

### Task 1: `ml/serve` nạp checkpoint trong repo, thêm model/useTime/fold-in

**Files:**
- Create: `ml/repo_models.py`
- Modify: `ml/serve.py`
- Test: `tests/test_repo_serving.py`

**Interfaces:**
- Produces: `ml.repo_models.load_repo_models(root: Path) -> RepoModels | None`;
  `RepoModels.available: list[str]` (tập con của `["tas_gnn","lightgcn"]`);
  `RepoModels.score(model: str, user: int | None, hour: int, weekday: int, timestamp: float, use_time: bool = True, history: list[int] | None = None) -> np.ndarray` (độ dài 996, theo thứ tự `poi_ids`);
  `RepoModels.hourly_counts: np.ndarray (24, n_items)`, `.popularity: np.ndarray`, `.poi_ids`, `.user_ids`, `.dataset_sha256`, `.dataset_sha256_aliases`, `.info: dict` (dim, layers, time_dim, số tham số từng khối).
- HTTP `POST /score` body: `{userId?, hour, dayOfWeek, model?: "tas_gnn"|"lightgcn"|"hourly_popularity"|"popularity", useTime?: bool, historyPoiIds?: int[]}`; response giữ nguyên dạng cũ, `source` ∈ `tas_gnn | tas_gnn_foldin | lightgcn | lightgcn_foldin | hourly_popularity | popularity`, thêm `models: string[]`.
- HTTP `GET /health`: thêm `models`, `origin: "repo_checkpoint" | "colab_artifact"`, `info`.

- [ ] **Step 1: Test** `tests/test_repo_serving.py`
  - `test_loads_both_models`: `load_repo_models(ROOT).available == ["tas_gnn","lightgcn"]`.
  - `test_scores_match_legacy_path`: điểm `score("tas_gnn", 12, 8, 0, ts)` bằng `TemporalGNN.predict_for_user_at_time` gọi trực tiếp với cùng embedding (`np.allclose`, atol 1e-5); tương tự LightGCN với `predict_for_user`.
  - `test_use_time_false_ignores_hour`: `score("tas_gnn",12,8,0,ts,use_time=False)` bằng `score(...,20,5,ts,use_time=False)`; và khác bản `use_time=True`.
  - `test_foldin`: `score("tas_gnn", None, 8, 0, ts, history=[1,2,3])` có shape `(996,)`, hữu hạn, tương quan Spearman với `hourly_counts[8]` < 0.99.
  - `test_foldin_needs_three`: `history=[1,2]` → `ValueError`.
  - `test_http_score_models` (FastAPI `TestClient`): `model="lightgcn"` → `source=="lightgcn"`; `userId` không có + `historyPoiIds` 3 phần tử → `tas_gnn_foldin`; không user, không history → `hourly_popularity`; mọi điểm trong [0,1], đủ 996 POI.
- [ ] **Step 2:** `python -m pytest tests/test_repo_serving.py -q` → FAIL (module chưa có).
- [ ] **Step 3: Implement `ml/repo_models.py`.** Đọc CSV như `server.py:65-80`; dựng `TemporalGNN(num_users, num_items, coords=coords, category_ids=cat_ids, embedding_dim=64, time_dim=32, num_layers=3, use_time=True, use_spatial=True)` và `LightGCN(num_users, num_items, embedding_dim=64, num_layers=3)`; `torch.load(..., weights_only=True)`; `build_normalized_adj(train_pairs)`; cache embedding. Đọc `predict_for_user_at_time` (`src/models/temporal_gnn.py:251-298`) để: (a) `use_time=False` → chỉ tích vô hướng embedding đồ thị + không gian, bỏ mọi số hạng thời gian; (b) fold-in → thay vector user bằng trung bình embedding item (sau lan truyền) của `history`, phần còn lại giữ nguyên. Nếu phương thức không nhận vector user tùy ý, tách phần thân thành hàm nội bộ trong `repo_models.py` (không sửa `src/models`). SHA256 dùng `ml.poi_model.dataset_fingerprints`.
- [ ] **Step 4: Sửa `ml/serve.py`.** `lifespan`: nếu có `MODEL_PATH`/`active_artifact` → đường cũ; ngược lại `load_repo_models`. `ScoreRequest` thêm 3 trường. Chuẩn hóa min–max như cũ.
- [ ] **Step 5:** `python -m pytest tests -q` → PASS toàn bộ (kể cả test cũ).

### Task 2: Benchmark baseline ML trên Đà Nẵng

**Files:**
- Create: `src/benchmark_ml.py`, `src/baselines/item_knn.py`, `src/baselines/bpr_mf.py`, `src/baselines/feature_gbm.py`
- Test: `tests/test_benchmark_ml.py`
- Output: `outputs/benchmark_ml_danang.csv`, `FE/public/artifacts/benchmark-ml.json`

**Interfaces:**
- Produces: `benchmark_ml.rank_metrics(ranks: np.ndarray, ks=(5,10,20)) -> dict[str,float]` (khóa `HR@k`, `NDCG@k`, `MRR@k`; `ranks` là hạng 1-based, `np.inf` nếu ngoài top);
  `benchmark-ml.json`: `{generatedAt, dataset:{users,pois,events,trainEvents,testEvents,novelTestEvents}, protocol, models:[{key,label,group:"heuristic"|"ml"|"gnn",main:boolean,usesPrevLocation:boolean,metrics:{"HR@5":..,"HR@10":..,"HR@20":..,"NDCG@5":..,"NDCG@10":..,"NDCG@20":..,"MRR@10":..},trainSeconds}]}`.
- Model keys: `popularity, hourly_popularity, hour_prev_distance, user_knn, item_knn, bpr_mf, feature_gbm, lightgcn, tas_gnn`.

- [ ] **Step 1: Test.** `test_rank_metrics_by_hand`: `ranks=[1,3,inf,11]` → `HR@10==0.5`, `MRR@10==(1+1/3)/4`, `NDCG@10==(1+1/log2(4))/4`, `HR@20==0.75`. `test_item_knn_tiny`: ma trận 3 user × 3 item tay, item đồng xuất hiện được xếp trên item không liên quan. `test_bpr_mf_learns`: dữ liệu khối 2 cụm, sau 30 epoch điểm item cùng cụm > khác cụm.
- [ ] **Step 2:** chạy test → FAIL.
- [ ] **Step 3: Implement.** Chia và mặt nạ `train_seen` chép đúng `src/baselines_check.py:52-75`. User-KNN dùng `baselines.user_cf.UserCF`. Item-KNN: cosine item–item trên ma trận nhị phân train, điểm = tổng tương đồng với item user đã ghé. BPR-MF: PyTorch, dim 64, Adam lr 0.005, 30 epoch, batch 1024, L2 1e-4, seed 42. Feature-GBM: `HistGradientBoostingClassifier(max_iter=200, learning_rate=0.1)`, đặc trưng như spec 5.10, âm:dương 4:1, seed 42; chọn `max_depth` ∈ {4,8} trên 10% cuối train. GNN: dùng `ml.repo_models`. Đo thời gian huấn luyện từng mô hình.
- [ ] **Step 4:** `python src/benchmark_ml.py` → in bảng 9 dòng; LightGCN HR@10 ≈ 11,36%, TAS-GNN ≈ 13,03% (khớp `baselines_check.py`, sai lệch ≤ 0,05 điểm). Hai file output được ghi.
- [ ] **Step 5:** `python -m pytest tests/test_benchmark_ml.py -q` → PASS.

### Task 3: Hạ tầng Docker và schema

**Files:**
- Modify: `compose.yaml`, `apps/api/.env.example`, `apps/api/src/database/schema.sql`, `apps/api/src/database/init.ts`, `.gitignore`
- Create: `apps/api/src/database/display.ts`
- Test: `apps/api/test/display.test.cjs`

**Interfaces:**
- Produces: bảng `accounts`, `account_settings`, `account_interests`, `poi_display` (spec 5.3, 5.6); `feedback.account_id INT NULL`, `feedback.user_id` cho NULL.
- `display.ts`: `isJunkPoiName(name: string, category: string): boolean`; `normalizeDistrict(raw: string): string` (7 quận: Hải Châu, Sơn Trà, Ngũ Hành Sơn, Liên Chiểu, Thanh Khê, Hòa Vang, Cẩm Lệ).
- `.env`: `AUTH_SECRET`, `DEMO_PASSWORD`, `NEO4J_URI=bolt://127.0.0.1:7687`, `NEO4J_USER=neo4j`, `NEO4J_PASSWORD`.
- Tài khoản demo: username `demo_cafe`, `demo_amthuc`, `demo_thamquan`, `demo_dadang`, mỗi cái có `dataset_user_id`.

- [ ] **Step 1: Test** `display.test.cjs`: `isJunkPoiName('End of the Road?','tourist_spot')===true`; `'This is a dead end! Jungle trekking from here!'` → true; `'Great Valley View'` → true (tên mô tả tiếng Anh chứa `view`/`viewpoint`/`path`); `'Chùa Nam Sơn'`, `'Non Nuoc Beach'`, `'Đèo Hải Vân'` → false; mọi tên với category `cafe` → false. `normalizeDistrict('Quận Sơn Trà')==='Sơn Trà'`, `('Hai Chau')==='Hải Châu'`, `('Ngu Hanh Son')==='Ngũ Hành Sơn'`, `('Danang')==='Hải Châu'`.
- [ ] **Step 2:** FAIL.
- [ ] **Step 3: Implement** `display.ts`; schema mới (thêm cột bằng thủ tục kiểm tra `information_schema` để chạy lại được); `init.ts` điền `poi_display`, chọn 4 user demo (nhiều check-in nhất mà danh mục trội lần lượt là cafe / restaurant / tourist_spot / phân bố đều nhất), tạo tài khoản demo bằng `hashPassword` của Task 5 (đặt hàm băm trong `apps/api/src/auth/password.ts` ngay ở task này).
- [ ] **Step 4:** `compose.yaml` thêm `neo4j:5-community` (`127.0.0.1:7474:7474`, `127.0.0.1:7687:7687`, `NEO4J_AUTH=neo4j/${NEO4J_PASSWORD:-neo4j_local_password}`, volume, healthcheck `cypher-shell`).
- [ ] **Step 5:** `docker compose up -d --wait && npm run db:init` → "Imported 996 POIs…", `SELECT COUNT(*) FROM accounts` = 4. Chạy lại lần hai không lỗi, vẫn 4.

### Task 4: Dựng đồ thị tri thức

**Files:**
- Create: `tools/build_kg.py`, `tools/kg_schema.py`
- Modify: `ml/requirements.txt` (thêm `neo4j>=5.20,<6`, `scikit-learn>=1.4`)
- Test: `tests/test_kg_schema.py`

**Interfaces:**
- Produces: `kg_schema.build_rows(pois: DataFrame, checkins: DataFrame, social: DataFrame) -> dict[str, list[dict]]` với khóa `users, pois, categories, districts, timeslots, visited, friend_of, in_category, located_in, near, busy_at, active_at`; `kg_schema.time_slot(hour:int)->str` ∈ `morning(5–10) | noon(11–13) | afternoon(14–17) | evening(18–22) | night(23–4)`.
- Nhãn và quan hệ Neo4j đúng spec 5.2.

- [ ] **Step 1: Test.** `time_slot(5)=="morning"`, `(10)=="morning"`, `(11)=="noon"`, `(22)=="evening"`, `(23)=="night"`, `(4)=="night"`. Trên dữ liệu thật: `len(users)==1500`, `len(pois)==996`, `len(districts)==7`, `len(near)==996*5`, mỗi cặp `(u,l)` trong `visited` duy nhất và tổng `count` == 36210, `friend_of` không có cặp trùng đảo chiều.
- [ ] **Step 2:** FAIL. **Step 3:** implement (NEAR bằng `sklearn.neighbors.BallTree` haversine; chuẩn hóa quận cùng bảng ánh xạ với `display.ts`).
- [ ] **Step 4:** `build_kg.py`: tạo constraint duy nhất cho 5 nhãn, `UNWIND $rows MERGE` theo lô 1000, in số nút/cạnh. `python tools/build_kg.py` → in 2.512 nút; chạy lại số không đổi.
- [ ] **Step 5:** pytest PASS.

### Task 5: API đăng nhập và cài đặt

**Files:**
- Create: `apps/api/src/auth/password.ts`, `auth/session.ts`, `auth/auth.service.ts`, `auth/auth.controller.ts`, `auth/auth.guard.ts`, `settings/settings.ts`, `settings/settings.controller.ts`
- Modify: `apps/api/src/app.module.ts`, `dto.ts`
- Test: `apps/api/test/auth.test.cjs`

**Interfaces:**
- `hashPassword(pw): Promise<string>` (`scrypt$N$salt$hash`), `verifyPassword(pw, stored): Promise<boolean>`.
- `signSession({accountId, exp}, secret): string`, `readSession(token, secret): {accountId:number}|null`; cookie `dss_session`.
- `currentAccount(req): Promise<Account|null>`; `Account = {id, username, displayName, datasetUserId:number|null, interests:string[]}`.
- Routes: `POST /api/auth/register {username(3–30, [a-z0-9_]), displayName(1–60), password(≥8), interests: string[] (≥1)}` → 201 + cookie; `POST /api/auth/login`; `POST /api/auth/logout`; `GET /api/auth/me` → `{account}` hoặc 401.
- `ModelSettings = {model:'tas_gnn'|'lightgcn'|'hourly_popularity'|'popularity', useTime:boolean, candidatePool:20|50|100|0, topK:number(5–20), excludeVisited:boolean, radiusKm:number, maxPrice:number|null, preset:'balanced'|'proximity'|'budget'|'ai_centric'|'custom', weightLevels:number[5]}`; `DEFAULT_SETTINGS = {model:'tas_gnn',useTime:true,candidatePool:0,topK:10,excludeVisited:true,radiusKm:10,maxPrice:null,preset:'balanced',weightLevels:[5,4,3,6,2]}`.
- Routes: `GET /api/settings`, `PUT /api/settings` (validate, trả settings đã lưu), `DELETE /api/settings` (về mặc định); đều cần đăng nhập.

- [ ] **Step 1: Test** (fakeDb như `api.test.cjs`): đăng ký → 201, có `Set-Cookie` chứa `HttpOnly` và `SameSite=Lax`; đăng ký trùng username → 409; mật khẩu 7 ký tự → 400; đăng nhập sai → 401; `me` với cookie hợp lệ → username đúng; cookie bị đổi 1 ký tự → 401; token `exp` quá khứ → 401; sai 10 lần liên tiếp → lần 11 trả 429; `PUT /settings` với `topK:99` → 400; `PUT` hợp lệ rồi `GET` → trả đúng; `GET /settings` không cookie → 401.
- [ ] **Step 2:** FAIL. **Step 3:** implement (so sánh `timingSafeEqual`; đọc cookie từ header thủ công; bộ đếm sai mật khẩu `Map` theo username, cửa sổ 15 phút). **Step 4:** `npm test` PASS.

### Task 6: API gợi ý theo tài khoản, chủ đề, lưu trữ

**Files:**
- Create: `apps/api/src/themes.ts`, `apps/api/src/recommend.service.ts`
- Modify: `apps/api/src/app.service.ts`, `app.controller.ts`, `dto.ts`
- Test: `apps/api/test/api.test.cjs` (cập nhật), `apps/api/test/themes.test.cjs`

**Interfaces:**
- `THEMES: Theme[]`, `Theme = {slug, title, tagline, categories: string[], districts?: string[], maxPrice?: number, cheapestShare?: number, hour: number|'now', preset: string}`; slug: `an-uong, ca-phe, tham-quan-giai-tri, luu-tru, bua-sang, ve-dem, ven-bien, tiet-kiem` (giá trị theo bảng spec 5.6).
- `RecommendDto`: bỏ `userId`; thêm `model?`, `useTime?`, `candidatePool?`, `categories?: string[]`, `districts?: string[]`, `showHidden?: boolean`. Thiếu trường nào thì lấy từ `account_settings` của tài khoản, không đăng nhập thì `DEFAULT_SETTINGS`.
- Response thêm: `personalization: 'trained_user'|'foldin'|'cold_start'`, `historyCount: number`, `model`, `useTime`; mỗi `Place` thêm `saved: boolean`, `visited: boolean`.
- Routes: `GET /api/themes` → `[{...theme, count}]`; `POST /api/themes/:slug/recommendations` (body: latitude, longitude, hour?, dayOfWeek?); `GET /api/saved` → `{liked: Place[], visited: Place[]}`; `POST /api/feedback {poiId, action:'like'|'unlike'|'visit'}` (cần đăng nhập, dùng `account_id`); `GET /api/system` → `{ai:{ready,models,origin,info}, database:true, graph:boolean}`.

- [ ] **Step 1: Test.** Khách → `personalization:'cold_start'`, `source:'hourly_popularity'`. Tài khoản demo (datasetUserId 12) → body gửi AI có `userId:12`. Tài khoản thường có 3 like → body gửi AI có `historyPoiIds` dài 3 và không có `userId`; có 2 like → không có `historyPoiIds`. `model:'lightgcn'` được chuyển tiếp. AI tắt → 200 kèm `warning`. `candidatePool:1` → mỗi nhóm đúng 1 item. Chủ đề `bua-sang` → chỉ cafe/restaurant, mọi `price_avg ≤ 60000`. `radiusKm:0.1` ở vị trí xa → `groups` rỗng, `totalCandidates:0`, status 200. POI `hidden` không xuất hiện trừ khi `showHidden:true`. Slug lạ → 404. `unlike` xóa like.
- [ ] **Step 2:** FAIL. **Step 3:** implement; tách luồng gợi ý sang `recommend.service.ts`, `app.service.ts` giữ catalog/stats. Cắt `candidatePool` theo từng danh mục sau lọc, trước TOPSIS. **Step 4:** `npm test` PASS.

### Task 7: API đồ thị tri thức

**Files:**
- Create: `apps/api/src/kg/kg.service.ts`, `kg/kg.controller.ts`
- Modify: `apps/api/package.json` (`neo4j-driver`), `app.module.ts`
- Test: `apps/api/test/kg.test.cjs`

**Interfaces:**
- `GET /api/kg/stats` → `{nodes:{User,POI,Category,District,TimeSlot}, relationships:{VISITED,FRIEND_OF,IN_CATEGORY,LOCATED_IN,NEAR,BUSY_AT,ACTIVE_AT}}`.
- `GET /api/kg/poi/:id` → `{nodes:[{id,label,type,weight?}], links:[{source,target,type,value?}], cypher:string}` (POI, danh mục, quận, khung giờ đông, 5 POI gần, tối đa 8 POI cùng người ghé).
- `GET /api/kg/poi/:id/similar?limit=8` → `[{id,name,category,sharedVisitors}]`.
- `GET /api/kg/explain?poiId=` (đăng nhập tùy chọn) → `{reasons:[{kind:'near_liked'|'co_visited'|'busy_slot'|'district', text}]}`.

- [ ] **Step 1: Test** với driver giả tiêm qua provider: `stats` ghép đúng số; driver ném lỗi kết nối → 503 với message chứa "Neo4j"; `poi/abc` → 400. **Step 2:** FAIL. **Step 3:** implement (session chỉ đọc, tham số hóa mọi truy vấn, timeout 3 giây). **Step 4:** PASS. **Step 5:** với Neo4j thật: `curl http://127.0.0.1:4000/api/kg/stats` → `nodes.POI==996`.

### Task 8: Khung giao diện và đăng nhập

**Files:**
- Create: `FE/src/app/(site)/layout.tsx`, `FE/src/components/site-header.tsx`, `site-footer.tsx`, `auth-context.tsx`, `ui.tsx`, `FE/src/app/(site)/login/page.tsx`, `register/page.tsx`, `FE/src/styles/tokens.css`, `FE/src/lib/api.ts`
- Modify: `FE/src/app/layout.tsx`, `globals.css`, `FE/package.json` (`recharts`, `react-force-graph-2d`)

**Interfaces:**
- `useAuth(): {account: Account|null, loading: boolean, login(u,p), register(form), logout(), refresh()}`.
- `ui.tsx`: `Button`, `Card`, `Badge`, `EmptyState`, `ErrorState`, `Skeleton`, `SectionHeading`, `Notice`.
- `lib/api.ts`: `api<T>(path, body?, method?)` (chuyển từ `types.ts`, thêm `credentials:'same-origin'`, lỗi 401 ném `AuthError`).
- Điều hướng: Trang chủ `/`, Khám phá `/explore`, Chủ đề `/themes/[slug]`, Đã lưu `/saved`, Mô hình `/model`, Đánh giá `/evaluation`, Dữ liệu `/data`, Cài đặt `/settings`.

- [ ] **Step 1:** Gọi skill `frontend-design` trước khi viết giao diện; token màu/chữ theo spec 5.8.
- [ ] **Step 2:** Implement khung, đăng nhập (có nút "Dùng tài khoản demo" liệt kê 4 tài khoản), đăng ký (chọn ≥1 chủ đề).
- [ ] **Step 3:** `npm --prefix FE run typecheck` → 0 lỗi. Trên trình duyệt: đăng ký → header hiện tên; tải lại trang vẫn đăng nhập; đăng xuất → về khách; sai mật khẩu hiện thông báo.

### Task 9: Trang chủ, chủ đề, khám phá, đã lưu

**Files:**
- Create: `FE/src/app/(site)/page.tsx`, `themes/[slug]/page.tsx`, `explore/page.tsx`, `saved/page.tsx`, `FE/src/components/place-card.tsx`, `theme-grid.tsx`, `time-picker.tsx`, `why-panel.tsx`
- Modify: `FE/src/components/explorer.tsx` (bỏ sidebar, bỏ ô chọn user, dùng `place-card`, đọc mặc định từ settings), `poi-map.tsx`, `lib/types.ts`, `lib/explorer-query.ts`
- Delete: `FE/src/app/page.tsx`, `FE/src/app/training/page.tsx` (thay bằng redirect `/training` → `/evaluation` trong `next.config.ts`)

- [ ] **Step 1:** Implement theo phác thảo spec 5.7. Thẻ địa điểm hiện nhãn cá nhân hóa (`trained_user`/`foldin`/`cold_start`) ở đầu danh sách, nút thích/đã ghé, "vì sao?" mở `why-panel` (gọi `/api/kg/explain`, ẩn khi 503).
- [ ] **Step 2:** typecheck 0 lỗi. Trình duyệt: mỗi chủ đề cho danh sách đúng danh mục; đổi giờ sáng↔tối đổi thứ hạng; thích 3 nơi bằng tài khoản mới → nhãn chuyển sang "Cá nhân hóa từ 3 địa điểm"; trang Đã lưu hiện đủ; bán kính 0,1 km hiện trạng thái rỗng; khung 375px không tràn ngang.

### Task 10: Trang Mô hình, Đánh giá, Dữ liệu, Cài đặt

**Files:**
- Create: `FE/src/app/(site)/model/page.tsx`, `evaluation/page.tsx`, `data/page.tsx`, `settings/page.tsx`, `FE/src/components/charts/metric-bars.tsx`, `charts/hour-profile.tsx`, `kg-viewer.tsx`, `architecture-diagram.tsx`, `time-mechanism-demo.tsx`, `tools/export_data_profile.py`
- Output: `FE/public/artifacts/data-profile.json` (thống kê danh mục, quận đã chuẩn hóa, check-in theo giờ/thứ, lược đồ cột 3 CSV, so sánh Gowalla)
- Delete: `FE/src/components/training-artifacts.tsx` (nội dung chuyển vào `/evaluation`)

- [ ] **Step 1:** `python tools/export_data_profile.py` ghi JSON; tổng check-in theo giờ == 36210.
- [ ] **Step 2:** Implement 4 trang theo spec 5.5, 5.7. `/model`: đọc `src/models/temporal_gnn.py` và `src/train_compare.py` để ghi đúng thông số; số tham số lấy từ `GET /api/system`. `/evaluation`: bảng chính từ `benchmark-ml.json`, tab Colab từ `training-summary.json`. `/settings`: xem trước Top 5 gọi `/api/recommendations` với cài đặt đang sửa (debounce 400ms), lưu bằng `PUT /api/settings`.
- [ ] **Step 3:** typecheck + `npm --prefix FE run build` thành công. Trình duyệt: đổi mô hình TAS-GNN → LightGCN làm bản xem trước đổi và trang Khám phá ghi "LightGCN + TOPSIS"; tắt thời gian → đổi giờ không đổi điểm phù hợp; tắt Neo4j → `/data` hiện thông báo, các trang khác bình thường; tắt `ml.serve` → cài đặt khóa hai mô hình GNN kèm lý do.

### Task 11: Tài liệu và kiểm tra cuối

**Files:**
- Create: `docs/TRA_LOI_GOP_Y.md`
- Modify: `../README.md`, `README.md`, `docs/RUNNING.md`, `../Huong_Dan.md`, `RESEARCH_REPORT_TAS_GNN.md`, `BAO_CAO_TRINH_BAY_DU_AN.md`, `DEPLOYMENT_GUIDE.md`, `FE/README.md`

- [ ] **Step 1:** Viết `TRA_LOI_GOP_Y.md`: 9 mục, mỗi mục gồm câu trả lời, trang web, file code, số liệu lấy từ `benchmark-ml.json`.
- [ ] **Step 2:** Sửa các tài liệu theo spec 5.9; thay mọi đường dẫn `F:\dss` bằng đường dẫn tương đối.
- [ ] **Step 3:** `grep -rn "12,45\|12\.45\|F:\\\\dss" --include=*.md .. ` chỉ còn trong file gắn nhãn phiên bản cũ.
- [ ] **Step 4:** `python -m pytest tests -q`, `npm test`, `npm run typecheck`, `npm run build` đều thành công; đi lại luồng trình duyệt của spec mục 6.
