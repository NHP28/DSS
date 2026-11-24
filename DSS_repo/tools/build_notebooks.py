"""Sinh và chạy ba notebook so sánh baseline trong notebooks/.

    python tools/build_notebooks.py            # sinh lại + chạy, lưu kèm kết quả và biểu đồ
    python tools/build_notebooks.py 02         # chỉ một notebook (01, 02 hoặc 03)
    python tools/build_notebooks.py --no-run   # chỉ sinh file, không chạy

Nội dung notebook nằm ở đây để sửa một chỗ; mở notebook bằng Jupyter/VS Code rồi "Run All" cũng cho cùng kết quả.
"""
import sys
from pathlib import Path

import nbformat
from nbformat.v4 import new_code_cell, new_markdown_cell, new_notebook

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "notebooks"

SETUP = '''\
import sys, time, warnings
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from IPython.display import display

# Tìm thư mục gốc dự án (nơi có src/benchmark_ml.py) dù notebook được mở từ đâu.
ROOT = next(p for p in [Path.cwd(), *Path.cwd().parents] if (p / "src" / "benchmark_ml.py").is_file())
sys.path[:0] = [str(ROOT), str(ROOT / "src")]
import benchmark_ml as bm

warnings.filterwarnings("ignore")
INK, SEA, CORAL, SAND, SKY, MUTED = "#1d2b2f", "#1f6f78", "#c8553d", "#b8860b", "#3d6a9e", "#9aa5a8"
GROUP_COLOR = {"heuristic": SAND, "ml": SKY, "gnn": SEA}
GROUP_NAME = {"heuristic": "Heuristic", "ml": "Machine learning cổ điển", "gnn": "Mạng nơ-ron đồ thị"}
CATEGORY_NAME = {"cafe": "Cà phê", "restaurant": "Ăn uống", "hotel": "Lưu trú", "tourist_spot": "Tham quan"}
CATEGORY_COLOR = {"cafe": SAND, "restaurant": CORAL, "hotel": SKY, "tourist_spot": SEA}
LABEL = {key: label for key, label, _ in bm.MODELS}
GROUP = {key: group for key, _, group in bm.MODELS}
plt.rcParams.update({"figure.dpi": 110, "figure.figsize": (9, 4.2), "axes.spines.top": False, "axes.spines.right": False,
                     "axes.grid": True, "grid.alpha": .25, "axes.titleweight": "bold", "axes.titlesize": 12,
                     "axes.edgecolor": MUTED, "text.color": INK, "axes.labelcolor": INK, "xtick.color": INK, "ytick.color": INK})

bench = bm.prepare()
print(f"{bench.n_users:,} người dùng · {bench.n_items:,} địa điểm · {len(bench.events):,} lượt check-in")
print(f"Train {len(bench.train):,} · Test {len(bench.test):,} · Test tại địa điểm mới (được chấm) {len(bench.novel):,}")


def color_of(key):
    return CORAL if key == "tas_gnn" else GROUP_COLOR[GROUP[key]]


def show_results(ranks, title, metric="HR@10"):
    """Bảng chỉ số (%) và biểu đồ cột của các phương pháp đã có kết quả."""
    table = bm.results_table(ranks)
    display(table.drop(columns=["model", "group"]).rename(columns={"label": "Phương pháp"}).set_index("Phương pháp")
            .style.format("{:.2f}").background_gradient(cmap="YlGn", axis=0))
    ordered = table.sort_values(metric)
    fig, ax = plt.subplots(figsize=(9, .5 * len(ordered) + 1.4))
    bars = ax.barh(ordered.label, ordered[metric], color=[color_of(k) for k in ordered.model])
    ax.bar_label(bars, fmt="%.2f%%", padding=4)
    ax.set(xlabel=f"{metric} (%)", title=title, xlim=(0, ordered[metric].max() * 1.18))
    ax.grid(axis="y", visible=False)
    plt.show()
    return table
'''


def notebook(cells):
    nb = new_notebook(metadata={"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                                "language_info": {"name": "python"}})
    nb.cells = [new_markdown_cell(body) if kind == "md" else new_code_cell(body) for kind, body in cells]
    return nb


NB1 = [
("md", """# 01 · Dữ liệu, giao thức đánh giá và baseline heuristic

**Đồ án:** Ứng dụng mạng nơ-ron đồ thị động tích hợp thông tin thời gian trong hệ thống gợi ý địa điểm cá nhân hóa.

Bộ ba notebook này chạy lại toàn bộ phần so sánh mô hình, từng bước và có biểu đồ:

| Notebook | Nội dung |
|---|---|
| **01** (file này) | Dữ liệu Đà Nẵng, cách chia train/test, 3 baseline heuristic |
| 02 | 4 baseline machine learning cổ điển: User-KNN, Item-KNN, BPR-MF, Gradient Boosting |
| 03 | LightGCN, TAS-GNN và bảng so sánh chung 9 phương pháp |

Chạy theo thứ tự 01 → 02 → 03. Mỗi notebook lưu kết quả của mình vào `outputs/benchmark_ranks/`; notebook 03 gộp lại và ghi file cho trang `/evaluation` của website."""),
("code", SETUP),
("md", """## 1. Giao thức đánh giá

Mọi phương pháp dùng **chung một giao thức**, nên các con số so sánh được với nhau:

1. Check-in của mỗi người dùng được sắp theo thời gian; **80% đầu để huấn luyện, 20% cuối để kiểm tra**.
2. Chỉ chấm các sự kiện test tại **địa điểm người đó chưa từng ghé** trong train (gợi ý nơi mới, không phải đoán lại nơi quen).
3. Mô hình xếp hạng **toàn bộ danh mục** trừ các nơi đã ghé; không lấy mẫu ứng viên.
4. Chấm **tất cả** sự kiện, với giờ và thứ thật của từng sự kiện.

Chỉ số: **HR@K** (địa điểm đúng có nằm trong top K không), **NDCG@K** và **MRR@K** (nằm càng cao càng được điểm)."""),
("code", '''\
per_user = bench.events.groupby("u").size()
fig, axes = plt.subplots(1, 2, figsize=(11, 3.8))
parts = [len(bench.train), len(bench.test) - len(bench.novel), len(bench.novel)]
names = ["Train (80% đầu)", "Test · nơi đã ghé\\n(không chấm)", "Test · nơi mới\\n(được chấm)"]
bars = axes[0].bar(names, parts, color=[SEA, MUTED, CORAL])
axes[0].bar_label(bars, labels=[f"{v:,}" for v in parts], padding=3)
axes[0].set(title="Số lượt check-in theo phần chia", ylabel="Lượt check-in")
axes[0].grid(axis="x", visible=False)
axes[1].hist(per_user, bins=range(per_user.min(), per_user.max() + 2), color=SEA, alpha=.85)
axes[1].axvline(per_user.median(), color=CORAL, ls="--", label=f"Trung vị {per_user.median():.0f} lượt")
axes[1].set(title="Mỗi người dùng có bao nhiêu lượt check-in", xlabel="Số lượt check-in", ylabel="Số người dùng")
axes[1].legend()
plt.tight_layout(); plt.show()'''),
("md", """## 2. Nhìn dữ liệu trước khi chọn baseline

Ba câu hỏi quyết định baseline nào đáng thử: người ta đi đâu **vào giờ nào**, lượt ghé có **dồn vào ít địa điểm** không, và hai lần ghé liên tiếp **cách nhau bao xa**."""),
("code", '''\
train = bench.train.merge(bench.pois[["l", "category"]], on="l")
by_hour = train.pivot_table(index="hour", columns="category", values="u", aggfunc="size", fill_value=0).reindex(range(24), fill_value=0)
by_hour = by_hour[[c for c in CATEGORY_NAME if c in by_hour.columns]]
fig, ax = plt.subplots(figsize=(10, 4))
ax.stackplot(by_hour.index, by_hour.T.values, labels=[CATEGORY_NAME[c] for c in by_hour.columns],
             colors=[CATEGORY_COLOR[c] for c in by_hour.columns], alpha=.9)
ax.set(title="Lượt check-in theo giờ trong ngày, tách theo loại địa điểm (tập train)", xlabel="Giờ", ylabel="Lượt check-in", xticks=range(0, 24, 2))
ax.legend(loc="upper left", ncol=4, frameon=False)
plt.show()
share = (by_hour.T / by_hour.sum(1)).T.fillna(0)
print("Loại địa điểm đông nhất theo giờ:", ", ".join(f"{h}h→{CATEGORY_NAME[share.loc[h].idxmax()]}" for h in (7, 9, 12, 15, 19, 21) if by_hour.loc[h].sum()))'''),
("code", '''\
top = np.argsort(-bench.popularity)[:25]
heat = bench.hourly[:, top] / np.maximum(bench.hourly[:, top].sum(0), 1)
fig, ax = plt.subplots(figsize=(11, 5.2))
image = ax.imshow(heat.T, aspect="auto", cmap="YlOrRd")
ax.set(title="25 địa điểm đông nhất: tỉ lệ lượt ghé theo từng giờ", xlabel="Giờ", xticks=range(0, 24, 2), yticks=range(len(top)))
ax.set_yticklabels([f"{bench.pois.name[i][:26]} · {CATEGORY_NAME[bench.pois.category[i]]}" for i in top], fontsize=8)
ax.grid(False)
fig.colorbar(image, ax=ax, label="Tỉ lệ lượt ghé của địa điểm")
plt.show()'''),
("md", "Mỗi địa điểm có khung giờ riêng của nó. Đây là lý do baseline **phổ biến theo giờ** được đưa vào, và cũng là tín hiệu mà TAS-GNN phải học được."),
("code", '''\
from baselines.feature_gbm import km

order = np.sort(bench.popularity)[::-1]
cumulative = np.cumsum(order) / order.sum()
ev = bench.train.sort_values(["u", "ts"])
prev = ev.groupby("u").l.shift(1)
ok = prev.notna()
a, b = bench.coords[prev[ok].astype(int)], bench.coords[ev.l[ok]]
step_km = km(a[:, 0], a[:, 1], b[:, 0], b[:, 1])

fig, axes = plt.subplots(1, 2, figsize=(11, 3.8))
axes[0].plot(np.arange(1, len(order) + 1), cumulative * 100, color=SEA, lw=2)
half = int(np.searchsorted(cumulative, .5)) + 1
axes[0].axvline(half, color=CORAL, ls="--", label=f"{half} địa điểm đầu = 50% lượt ghé")
axes[0].set(title="Lượt ghé dồn vào bao nhiêu địa điểm", xlabel="Số địa điểm (xếp từ đông nhất)", ylabel="% lượt ghé cộng dồn")
axes[0].legend()
axes[1].hist(step_km, bins=np.linspace(0, 15, 46), color=SEA, alpha=.85)
axes[1].axvline(np.median(step_km), color=CORAL, ls="--", label=f"Trung vị {np.median(step_km):.2f} km")
axes[1].set(title="Khoảng cách giữa hai lần check-in liên tiếp", xlabel="km", ylabel="Số lần")
axes[1].legend()
plt.tight_layout(); plt.show()
print(f"{(bench.popularity == 0).sum()} địa điểm không có lượt ghé nào trong train (chủ yếu là nơi lưu trú).")
print(f"{(step_km <= 1).mean():.0%} lần di chuyển dưới 1 km, {(step_km <= 3).mean():.0%} dưới 3 km.")'''),
("md", """## 3. Ba baseline heuristic

Không có tham số nào phải học, chỉ đếm trên tập train:

| Baseline | Điểm của địa điểm *j* | Thông tin dùng |
|---|---|---|
| **Phổ biến chung** | số lượt ghé *j* | không cá nhân hóa, không thời gian |
| **Phổ biến theo giờ** | số lượt ghé *j* vào đúng giờ đang xét | thời gian |
| **Giờ × khoảng cách liền trước** | (lượt ghé *j* vào giờ đó) / (khoảng cách từ nơi vừa ghé + 0,5 km) | thời gian + **vị trí ngay trước đó** |

Lưu ý: baseline thứ ba được biết người dùng **vừa ở đâu**. Các mô hình còn lại (kể cả TAS-GNN) không dùng thông tin này, nên nó là một mốc tham chiếu mạnh chứ không phải so sánh ngang hàng."""),
("code", '''\
ranks = {}
for key, scorer in bm.heuristic_scorers(bench).items():
    start = time.perf_counter()
    ranks[key] = bm.evaluate(bench, scorer)
    bm.save_ranks(key, ranks[key], 0.0)
    print(f"{LABEL[key]:<32} chấm {len(ranks[key]):,} sự kiện trong {time.perf_counter() - start:.1f} s")
table = show_results(ranks, "Baseline heuristic · HR@10")'''),
("code", '''\
ks = np.arange(1, 51)
fig, ax = plt.subplots(figsize=(9, 4))
for key, style in zip(ranks, ("-", "--", "-.")):
    ax.plot(ks, [(ranks[key] <= k).mean() * 100 for k in ks], style, lw=2, label=LABEL[key], color=INK if key == "hour_prev_distance" else SAND)
ax.set(title="Tỉ lệ trúng khi mở rộng danh sách gợi ý", xlabel="K (độ dài danh sách)", ylabel="HR@K (%)")
ax.legend(frameon=False)
plt.show()
gain = table.set_index("model")["HR@10"]
print(f"Thêm thông tin giờ: {gain['popularity']:.2f}% → {gain['hourly_popularity']:.2f}% (×{gain['hourly_popularity'] / gain['popularity']:.2f}).")
print(f"Thêm vị trí liền trước: → {gain['hour_prev_distance']:.2f}%.")'''),
("md", """## Nhận xét

- Chỉ cần biết **giờ** đã cải thiện rõ so với phổ biến chung: thời gian là tín hiệu thật trong dữ liệu này.
- Biết thêm **vị trí liền trước** cải thiện tiếp một bậc, vì phần lớn lần di chuyển rất ngắn.
- Cả ba đều **không cá nhân hóa**: hai người khác nhau, cùng giờ và cùng chỗ đứng, nhận cùng một danh sách.

Tiếp theo: `02_baseline_machine_learning.ipynb`."""),
]

NB2 = [
("md", """# 02 · Baseline machine learning cổ điển

Bốn phương pháp học từ dữ liệu nhưng **không dùng mạng nơ-ron đồ thị**. Chúng trả lời câu hỏi của Thầy: TAS-GNN so với machine learning thông thường thì thế nào?

| Phương pháp | Họ | Ý tưởng | Dùng thời gian? |
|---|---|---|---|
| **User-KNN** | Lọc cộng tác theo láng giềng | Người giống bạn đã ghé đâu | Không |
| **Item-KNN** | Lọc cộng tác theo láng giềng | Nơi nào hay được ghé cùng nơi bạn đã ghé | Không |
| **BPR-MF** | Phân rã ma trận | Học vector 64 chiều cho người dùng và địa điểm | Không |
| **Gradient Boosting** | Học có giám sát trên đặc trưng | Cây quyết định tăng cường dự đoán xác suất ghé | Có (giờ, thứ) |

Mã của từng mô hình nằm trong `src/baselines/`. Cùng giao thức với notebook 01."""),
("code", SETUP),
("md", "## 1. Ma trận người dùng × địa điểm\n\nBa phương pháp đầu chỉ nhìn ma trận này: ô (*u*, *j*) là số lần người dùng *u* ghé địa điểm *j* trong tập train."),
("code", '''\
C = bench.counts
density = C.nnz / (C.shape[0] * C.shape[1])
sub = (C[:300, :400] > 0).toarray()
fig, ax = plt.subplots(figsize=(10, 4.4))
ax.imshow(sub, aspect="auto", cmap="Greys", interpolation="nearest")
ax.set(title=f"300 người dùng × 400 địa điểm đầu tiên · mật độ toàn ma trận {density:.2%}", xlabel="Địa điểm", ylabel="Người dùng")
ax.grid(False)
plt.show()
print(f"Ma trận {C.shape[0]:,} × {C.shape[1]:,}, {C.nnz:,} ô khác 0. Mỗi người dùng ghé trung bình {C.nnz / C.shape[0]:.1f} địa điểm khác nhau.")'''),
("md", "## 2. User-KNN\n\nĐộ giống nhau giữa hai người dùng là cosine giữa hai hàng của ma trận. Điểm của địa điểm *j* với người dùng *u* là trung bình có trọng số lượt ghé *j* của những người giống *u*."),
("code", '''\
from baselines.user_cf import UserCF

ranks, seconds = {}, {}
start = time.perf_counter()
user_knn = UserCF().fit(bench.counts)
seconds["user_knn"] = time.perf_counter() - start
ranks["user_knn"] = bm.evaluate(bench, lambda chunk: user_knn.predict(chunk.u.to_numpy(int)))
bm.save_ranks("user_knn", ranks["user_knn"], seconds["user_knn"], "cosine trên ma trận số lượt ghé")

best_match = user_knn.W.max(1)
fig, ax = plt.subplots(figsize=(9, 3.6))
ax.hist(best_match, bins=40, color=SKY, alpha=.9)
ax.axvline(np.median(best_match), color=CORAL, ls="--", label=f"Trung vị {np.median(best_match):.2f}")
ax.set(title="Mỗi người dùng giống người gần nhất của mình đến mức nào", xlabel="Cosine với láng giềng gần nhất", ylabel="Số người dùng")
ax.legend(); plt.show()
print(f"User-KNN: huấn luyện {seconds['user_knn']:.2f} s · HR@10 {bm.rank_metrics(ranks['user_knn'])['HR@10']:.2%}")'''),
("md", "## 3. Item-KNN\n\nNgược lại với User-KNN: độ giống nhau tính giữa hai **địa điểm** (hai cột), giữ 50 láng giềng mạnh nhất của mỗi địa điểm. Điểm của *j* là tổng độ giống giữa *j* và các nơi người dùng đã ghé."),
("code", '''\
from baselines.item_knn import ItemKNN

start = time.perf_counter()
item_knn = ItemKNN(k=50).fit(bench.counts)
seconds["item_knn"] = time.perf_counter() - start
ranks["item_knn"] = bm.evaluate(bench, lambda chunk: item_knn.predict(chunk.u.to_numpy(int)))
bm.save_ranks("item_knn", ranks["item_knn"], seconds["item_knn"], "cosine, 50 láng giềng")

anchor = int(np.argmax(bench.popularity))
neighbours = np.argsort(-item_knn.sim[anchor])[:8]
print(f"Láng giềng của địa điểm đông nhất: {bench.pois.name[anchor]} ({CATEGORY_NAME[bench.pois.category[anchor]]}, {bench.pois.district[anchor]})")
display(pd.DataFrame({"Địa điểm": bench.pois.name[neighbours].values, "Loại": bench.pois.category[neighbours].map(CATEGORY_NAME).values,
                      "Quận": bench.pois.district[neighbours].values, "Cosine": item_knn.sim[anchor, neighbours].round(3)}))
print(f"Item-KNN: huấn luyện {seconds['item_knn']:.2f} s · HR@10 {bm.rank_metrics(ranks['item_knn'])['HR@10']:.2%}")'''),
("md", """## 4. BPR-MF

Phân rã ma trận với hàm mất mát Bayesian Personalized Ranking: mỗi người dùng và mỗi địa điểm có một vector 64 chiều, huấn luyện sao cho nơi đã ghé có điểm cao hơn một nơi chưa ghé lấy ngẫu nhiên.

Số epoch và tốc độ học được chọn trên **validation cắt từ train** (phần cuối của mỗi người dùng trong train), không đụng tới test. Sau đó mô hình được huấn luyện lại trên toàn bộ train."""),
("code", '''\
start = time.perf_counter()
bpr, bpr_config, bpr_trials = bm.tune_bpr(bench)
seconds["bpr_mf"] = time.perf_counter() - start
ranks["bpr_mf"] = bm.evaluate(bench, lambda chunk: bpr.predict(chunk.u.to_numpy(int)))
bm.save_ranks("bpr_mf", ranks["bpr_mf"], seconds["bpr_mf"], bm.bpr_note(bpr_config))

trials = pd.DataFrame(bpr_trials)
labels = [f"{int(e)} epoch\\nlr {lr}" for e, lr in zip(trials.epochs, trials.lr)]
fig, axes = plt.subplots(1, 2, figsize=(11, 4))
bars = axes[0].bar(labels, trials["HR@10"] * 100, color=[CORAL if (e, lr) == bpr_config else SKY for e, lr in zip(trials.epochs, trials.lr)])
axes[0].bar_label(bars, fmt="%.2f%%", padding=3)
axes[0].set(title="BPR-MF: chọn cấu hình trên validation", ylabel="HR@10 validation (%)")
axes[0].grid(axis="x", visible=False)

from sklearn.decomposition import PCA
visited = bench.popularity > 0
xy = PCA(2, random_state=0).fit_transform(bpr.V[visited])
for category, name in CATEGORY_NAME.items():
    pick = (bench.pois.category[visited] == category).to_numpy()
    if pick.any():
        axes[1].scatter(xy[pick, 0], xy[pick, 1], s=14, alpha=.7, color=CATEGORY_COLOR[category], label=name)
axes[1].set(title="Vector địa điểm BPR-MF học được (PCA 2 chiều)", xlabel="Thành phần 1", ylabel="Thành phần 2")
axes[1].legend(frameon=False, markerscale=1.5)
plt.tight_layout(); plt.show()
print(f"BPR-MF ({bpr_config[0]} epoch, lr {bpr_config[1]}): {seconds['bpr_mf']:.1f} s kể cả dò tham số · HR@10 {bm.rank_metrics(ranks['bpr_mf'])['HR@10']:.2%}")'''),
("md", """## 5. Gradient Boosting trên đặc trưng

Đây là baseline machine learning "truyền thống" nhất: biến bài toán gợi ý thành **phân loại nhị phân**. Mỗi bộ (người dùng, địa điểm, giờ, thứ) là một dòng đặc trưng; nhãn 1 nếu người dùng thật sự ghé, kèm 4 mẫu âm lấy ngẫu nhiên.

Để không rò rỉ nhãn, đặc trưng của người dùng (tâm hoạt động, tỉ lệ từng loại địa điểm) chỉ tính từ **phần lịch sử đứng trước** các sự kiện được gán nhãn. Độ sâu cây được chọn trên validation cắt từ train."""),
("code", '''\
from baselines.feature_gbm import FEATURES

start = time.perf_counter()
gbm = bm.tune_gbm(bench)
seconds["feature_gbm"] = time.perf_counter() - start
print(f"Tập huấn luyện: {gbm.rows:,} dòng × {len(FEATURES)} đặc trưng · tỉ lệ dương {gbm.y.mean():.1%} · max_depth chọn được = {gbm.depth}")
start = time.perf_counter()
ranks["feature_gbm"] = bm.evaluate(bench, gbm.scorer)
print(f"Chấm {len(ranks['feature_gbm']):,} sự kiện × {bench.n_items} ứng viên trong {time.perf_counter() - start:.0f} s")
bm.save_ranks("feature_gbm", ranks["feature_gbm"], seconds["feature_gbm"], bm.gbm_note(gbm))
print(f"Gradient Boosting: HR@10 {bm.rank_metrics(ranks['feature_gbm'])['HR@10']:.2%}")'''),
("code", '''\
from sklearn.inspection import permutation_importance

FEATURE_NAME = {"hour": "Giờ", "weekday": "Thứ", "weekend": "Cuối tuần", "category": "Loại địa điểm", "log_popularity": "Độ phổ biến (train)",
                "log_hour_popularity": "Độ phổ biến đúng giờ đó", "hour_share": "Tỉ lệ lượt ghé rơi vào giờ đó",
                "km_from_user_centre": "Khoảng cách tới tâm hoạt động của người dùng", "user_category_share": "Tỉ lệ người dùng ghé loại này",
                "log_user_events": "Mức hoạt động của người dùng", "rating": "Điểm đánh giá", "log_price": "Giá trung bình",
                "catalog_popularity": "Độ phổ biến trong danh mục"}
pick = np.random.default_rng(0).choice(len(gbm.y), size=min(20000, len(gbm.y)), replace=False)
importance = permutation_importance(gbm.model, gbm.X[pick], gbm.y[pick], scoring="roc_auc", n_repeats=3, random_state=0)
order = np.argsort(importance.importances_mean)
fig, ax = plt.subplots(figsize=(9, 5))
ax.barh([FEATURE_NAME[FEATURES[i]] for i in order], importance.importances_mean[order], xerr=importance.importances_std[order], color=SKY)
ax.set(title="Gradient Boosting dựa vào đặc trưng nào", xlabel="AUC giảm bao nhiêu khi xáo trộn đặc trưng")
ax.grid(axis="y", visible=False)
plt.show()

trials = pd.DataFrame(gbm.trials)
print("Chọn độ sâu cây trên validation:", ", ".join(f"max_depth={int(d)} → HR@10 {hr:.2%}" for d, hr in zip(trials.max_depth, trials["HR@10"])))'''),
("md", "## 6. Bốn phương pháp đặt cạnh nhau\n\nNếu đã chạy notebook 01, ba baseline heuristic được nạp lại để so cùng."),
("code", '''\
saved, _, _ = bm.load_ranks()
both = {key: saved[key] for key in saved if GROUP[key] in ("heuristic", "ml")}
table = show_results(both, "Heuristic và machine learning cổ điển · HR@10")

fig, ax = plt.subplots(figsize=(8, 3.6))
keys = [k for k in ("user_knn", "item_knn", "bpr_mf", "feature_gbm")]
bars = ax.bar([LABEL[k].replace(" (đặc trưng)", "") for k in keys], [seconds[k] for k in keys], color=SKY)
ax.bar_label(bars, labels=[f"{seconds[k]:.2f} s" for k in keys], padding=3)
ax.set(title="Thời gian huấn luyện trên CPU (kể cả dò tham số)", ylabel="giây", yscale="log")
ax.grid(axis="x", visible=False)
plt.show()'''),
("md", """## Nhận xét

- Ba phương pháp **lọc cộng tác** (User-KNN, Item-KNN, BPR-MF) không biết gì về thời gian và vị trí. Với ma trận thưa như ở trên, cả ba đều thấp hơn baseline phổ biến theo giờ.
- **Gradient Boosting** mạnh hơn hẳn vì được cấp trực tiếp các đặc trưng thời gian, khoảng cách và sở thích theo loại. Biểu đồ đặc trưng cho thấy nó dựa nhiều nhất vào đâu.
- Đây là mốc mà TAS-GNN phải được so với một cách thẳng thắn.

Tiếp theo: `03_so_sanh_voi_gnn.ipynb`."""),
]

NB3 = [
("md", """# 03 · LightGCN, TAS-GNN và bảng so sánh chung

- **TAS-GNN** là mô hình chính của đồ án: xương sống LightGCN 3 lớp, thêm bộ mã hóa thời gian (Fourier + embedding giờ/thứ), cổng thời gian cho người dùng, bộ mã hóa không gian và embedding loại địa điểm.
- **LightGCN** là mô hình đối chứng: cùng đồ thị, không có thời gian và không gian.

Hai mô hình **không huấn luyện lại** ở đây: notebook nạp checkpoint có sẵn trong `outputs/checkpoints/` (huấn luyện trên 70% đầu; đồ thị lan truyền dựng từ 80% đầu, 20% test không lọt vào đồ thị).

Cần chạy notebook 01 và 02 trước để có kết quả của 7 baseline."""),
("code", SETUP),
("code", '''\
import torch
from ml.repo_models import load_repo_models

repo = load_repo_models(ROOT)
info = repo.info
BLOCK_NAME = {"userEmbedding": "Embedding người dùng", "poiEmbedding": "Embedding địa điểm", "timeEncoder": "Bộ mã hóa thời gian",
              "temporalGate": "Cổng thời gian", "spatialEncoder": "Bộ mã hóa không gian", "categoryEmbedding": "Embedding loại địa điểm"}
blocks = pd.Series(info["blocks"]).rename(BLOCK_NAME).sort_values()
fig, ax = plt.subplots(figsize=(9, 3.6))
bars = ax.barh(blocks.index, blocks.values, color=[SEA if "Embedding người" in n or "Embedding địa" in n else CORAL for n in blocks.index])
ax.bar_label(bars, labels=[f"{v:,}" for v in blocks.values], padding=4)
ax.set(title=f"TAS-GNN: {info['parameters']:,} tham số (LightGCN: {info['lightgcnParameters']:,})", xlabel="Số tham số", xlim=(0, blocks.max() * 1.15))
ax.grid(axis="y", visible=False)
plt.show()
extra = info["parameters"] - info["lightgcnParameters"]
print(f"Phần thời gian, không gian và loại địa điểm chỉ thêm {extra:,} tham số ({extra / info['lightgcnParameters']:.1%} so với LightGCN).")'''),
("md", "## 1. Chấm LightGCN và TAS-GNN\n\nThêm một dòng kiểm tra: **cùng checkpoint TAS-GNN nhưng tắt nhánh thời gian lúc suy luận**. Đây không phải ablation huấn luyện lại (bản đó nằm ở `src/ablation_study.py`); nó chỉ cho thấy mô hình đã huấn luyện dựa vào tín hiệu thời gian nhiều đến đâu."),
("code", '''\
scorers = bm.gnn_scorers(repo)
ranks_gnn = {}
for key in ("lightgcn", "tas_gnn"):
    start = time.perf_counter()
    ranks_gnn[key] = bm.evaluate(bench, scorers[key])
    bm.save_ranks(key, ranks_gnn[key], 0.0, "checkpoint trong repo, không huấn luyện lại")
    print(f"{LABEL[key]:<10} chấm {len(ranks_gnn[key]):,} sự kiện trong {time.perf_counter() - start:.1f} s")
no_time = bm.evaluate(bench, lambda chunk: scorers["tas_gnn"](chunk, use_time=False))

ablation = pd.DataFrame({"LightGCN": bm.rank_metrics(ranks_gnn["lightgcn"]), "TAS-GNN · tắt thời gian": bm.rank_metrics(no_time),
                         "TAS-GNN · đầy đủ": bm.rank_metrics(ranks_gnn["tas_gnn"])}).T * 100
display(ablation.style.format("{:.2f}").background_gradient(cmap="YlGn", axis=0))
fig, ax = plt.subplots(figsize=(9, 3.8))
x, width = np.arange(3), .26
for i, (name, color) in enumerate(zip(ablation.index, (SEA, MUTED, CORAL))):
    bars = ax.bar(x + (i - 1) * width, ablation.loc[name, ["HR@5", "HR@10", "HR@20"]], width, label=name, color=color)
    ax.bar_label(bars, fmt="%.1f", padding=2, fontsize=8)
ax.set(title="TAS-GNN phụ thuộc vào nhánh thời gian đến đâu", xticks=x, xticklabels=["HR@5", "HR@10", "HR@20"], ylabel="%")
ax.grid(axis="x", visible=False); ax.legend(frameon=False)
plt.show()'''),
("md", "## 2. Cơ chế thời gian nhìn bằng mắt\n\nCùng một người dùng, cùng một ngày, chỉ đổi **giờ**: top 10 của TAS-GNN thay đổi thế nào? LightGCN không có đầu vào thời gian nên danh sách của nó đứng yên."),
("code", '''\
user = int(bench.train.merge(bench.pois[["l", "category"]], on="l").query("category == 'cafe'").u.value_counts().index[0])
timestamp = float(bench.train.ts.median())
hours = list(range(7, 22))
categories = list(CATEGORY_NAME)
mix = np.zeros((len(categories), len(hours)))
tops = {}
for column, hour in enumerate(hours):
    scores = repo.score("tas_gnn", user, hour, 2, timestamp)
    scores[bench.seen[user]] = -np.inf
    top = np.argsort(-scores)[:10]
    tops[hour] = top
    for row, category in enumerate(categories):
        mix[row, column] = (bench.pois.category[top] == category).sum()

fig, ax = plt.subplots(figsize=(10, 3.8))
bottom = np.zeros(len(hours))
for row, category in enumerate(categories):
    ax.bar(hours, mix[row], bottom=bottom, color=CATEGORY_COLOR[category], label=CATEGORY_NAME[category])
    bottom += mix[row]
ax.set(title=f"Top 10 của TAS-GNN cho người dùng #{user} theo từng giờ (thứ Tư)", xlabel="Giờ", ylabel="Số địa điểm trong top 10", xticks=hours)
ax.grid(axis="x", visible=False); ax.legend(ncol=4, frameon=False, loc="upper center", bbox_to_anchor=(.5, -.2))
plt.show()
history = bench.pois.category[bench.train[bench.train.u == user].l].map(CATEGORY_NAME).value_counts()
print(f"Lịch sử của người dùng #{user}:", ", ".join(f"{name} {count}" for name, count in history.items()))
display(pd.DataFrame({f"{hour} giờ": [f"{bench.pois.name[i][:24]} ({CATEGORY_NAME[bench.pois.category[i]]})" for i in tops[hour][:5]] for hour in (8, 12, 20)},
                     index=[f"#{i}" for i in range(1, 6)]))'''),
("md", "## 3. Bảng so sánh chung 9 phương pháp"),
("code", '''\
ranks, seconds, notes = bm.load_ranks()
missing = [LABEL[key] for key, _, _ in bm.MODELS if key not in ranks]
assert not missing, f"Chưa có kết quả của: {', '.join(missing)}. Hãy chạy notebook 01 và 02 trước."
table = show_results(ranks, "So sánh 9 phương pháp · HR@10 trên toàn bộ sự kiện test")
print("Màu: vàng = heuristic · xanh dương = machine learning cổ điển · xanh lục = LightGCN · cam đỏ = TAS-GNN (mô hình chính)")'''),
("code", '''\
fig, axes = plt.subplots(1, 2, figsize=(12, 4.4))
ks = np.arange(1, 21)
for key, label, group in bm.MODELS:
    main = key == "tas_gnn"
    axes[0].plot(ks, [(ranks[key] <= k).mean() * 100 for k in ks], lw=3 if main else 1.6, color=color_of(key),
                 ls={"popularity": ":", "hourly_popularity": "--", "user_knn": ":", "item_knn": "--", "bpr_mf": "-."}.get(key, "-"),
                 alpha=1 if main else .85, label=label)
axes[0].set(title="HR@K khi K tăng", xlabel="K", ylabel="HR@K (%)", xticks=[1, 5, 10, 15, 20])
axes[0].legend(fontsize=7.5, frameon=False)

ordered = table.sort_values("HR@10", ascending=False)
x, width = np.arange(len(ordered)), .27
for i, (metric, color) in enumerate(zip(("HR@10", "NDCG@10", "MRR@10"), (SEA, SAND, CORAL))):
    axes[1].bar(x + (i - 1) * width, ordered[metric], width, label=metric, color=color)
axes[1].set(title="Ba chỉ số ở K = 10", xticks=x, ylabel="%")
axes[1].set_xticklabels([l.replace(" (đặc trưng)", "").replace("Giờ × khoảng cách liền trước", "Giờ × khoảng cách") for l in ordered.label], rotation=35, ha="right", fontsize=8)
axes[1].grid(axis="x", visible=False); axes[1].legend(frameon=False)
plt.tight_layout(); plt.show()'''),
("md", "## 4. Mô hình nào mạnh ở đâu\n\nTách kết quả theo **khung giờ** của sự kiện và theo **loại địa điểm** đúng, để thấy điểm mạnh và điểm yếu chứ không chỉ một con số trung bình."),
("code", '''\
novel = bench.novel.merge(bench.pois[["l", "category"]], on="l", how="left")
slots = pd.cut(novel.hour, [-1, 4, 10, 13, 17, 22, 24], labels=["Đêm khuya", "Sáng 5–10h", "Trưa 11–13h", "Chiều 14–17h", "Tối 18–22h", "Đêm khuya "])
slots = slots.astype(str).str.strip()
slot_order = [s for s in ["Sáng 5–10h", "Trưa 11–13h", "Chiều 14–17h", "Tối 18–22h", "Đêm khuya"] if (slots == s).sum() >= 50]
focus = ["hourly_popularity", "feature_gbm", "lightgcn", "tas_gnn"]

fig, axes = plt.subplots(1, 2, figsize=(12, 4.2))
x, width = np.arange(len(slot_order)), .2
for i, key in enumerate(focus):
    values = [(ranks[key][(slots == s).to_numpy()] <= 10).mean() * 100 for s in slot_order]
    axes[0].bar(x + (i - 1.5) * width, values, width, label=LABEL[key].replace(" (đặc trưng)", ""), color=color_of(key), alpha=.55 if key == "hourly_popularity" else 1)
axes[0].set(title="HR@10 theo khung giờ của sự kiện", xticks=x, ylabel="HR@10 (%)")
axes[0].set_xticklabels([f"{s}\\n({(slots == s).sum():,})" for s in slot_order], fontsize=8)
axes[0].grid(axis="x", visible=False); axes[0].legend(frameon=False, fontsize=8)

present = [c for c in CATEGORY_NAME if (novel.category == c).sum() >= 50]
x = np.arange(len(present))
for i, key in enumerate(focus):
    values = [(ranks[key][(novel.category == c).to_numpy()] <= 10).mean() * 100 for c in present]
    axes[1].bar(x + (i - 1.5) * width, values, width, color=color_of(key), alpha=.55 if key == "hourly_popularity" else 1)
axes[1].set(title="HR@10 theo loại của địa điểm đúng", xticks=x, ylabel="HR@10 (%)")
axes[1].set_xticklabels([f"{CATEGORY_NAME[c]}\\n({(novel.category == c).sum():,})" for c in present], fontsize=8)
axes[1].grid(axis="x", visible=False)
plt.tight_layout(); plt.show()'''),
("code", '''\
hit = {key: ranks[key] <= 10 for key in ranks}
tas, gbm_hit, light = hit["tas_gnn"], hit["feature_gbm"], hit["lightgcn"]
print(f"Trong {len(tas):,} sự kiện test:")
print(f"  TAS-GNN trúng top 10: {tas.sum():,} · Gradient Boosting: {gbm_hit.sum():,} · LightGCN: {light.sum():,}")
print(f"  TAS-GNN trúng mà Gradient Boosting trượt: {(tas & ~gbm_hit).sum():,} · ngược lại: {(gbm_hit & ~tas).sum():,} · cả hai cùng trúng: {(tas & gbm_hit).sum():,}")
print(f"  TAS-GNN trúng mà LightGCN trượt: {(tas & ~light).sum():,} · ngược lại: {(light & ~tas).sum():,}")
either = (tas | gbm_hit).mean()
print(f"  Nếu ghép được hai mô hình một cách lý tưởng, HR@10 tối đa là {either:.2%}.")'''),
("md", "## 5. Ghi kết quả cho website\n\nGhi `outputs/benchmark_ml_danang.csv` và `FE/public/artifacts/benchmark-ml.json` (trang `/evaluation` đọc file này)."),
("code", '''\
report = bm.write_report(bench, ranks, seconds, notes)
hr = {row["key"]: row["metrics"]["HR@10"] for row in report["models"]}
ranking = sorted(hr, key=hr.get, reverse=True)
print("Đã ghi outputs/benchmark_ml_danang.csv và FE/public/artifacts/benchmark-ml.json\\n")
print("Xếp hạng theo HR@10:")
for place, key in enumerate(ranking, 1):
    print(f"  {place}. {LABEL[key]:<32} {hr[key]:.2%}{'   ← mô hình chính' if key == 'tas_gnn' else ''}")
print(f"\\nTAS-GNN so với LightGCN: {hr['tas_gnn'] / hr['lightgcn'] - 1:+.1%} tương đối.")
print(f"TAS-GNN so với Gradient Boosting: {hr['tas_gnn'] / hr['feature_gbm'] - 1:+.1%} tương đối.")'''),
("md", """## Kết luận

Đọc cùng các con số in ở ô trên:

- **TAS-GNN hơn LightGCN** ở HR@5, HR@10 và HR@20. Mô hình thật sự dùng tín hiệu thời gian: tắt nhánh thời gian lúc suy luận thì HR@10 rơi xuống thấp hơn cả LightGCN (mục 1), và danh sách gợi ý đổi theo giờ đúng với quy luật của dữ liệu (mục 2).
- LightGCN gần như không trúng sự kiện buổi trưa và địa điểm ăn uống (mục 4); TAS-GNN lấy lại được phần này nhờ biết giờ.
- **TAS-GNN hơn cả ba phương pháp lọc cộng tác** (User-KNN, Item-KNN, BPR-MF) và baseline phổ biến theo giờ.
- **TAS-GNN chưa hơn Gradient Boosting và heuristic giờ × khoảng cách.** Hai phương pháp này được cấp trực tiếp tín hiệu khoảng cách (tâm hoạt động của người dùng, hoặc vị trí ngay trước đó), còn TAS-GNN chỉ nhận tọa độ địa điểm qua một bộ mã hóa không gian nhỏ. Đây là hạn chế cần nêu rõ khi bảo vệ, và là hướng cải tiến trực tiếp: đưa khoảng cách tới vị trí hiện tại vào mô hình.
- Trên website, TAS-GNN chỉ làm bước **tạo ứng viên**; khoảng cách, giá và đánh giá được bổ sung ở bước xếp hạng lại AHP-TOPSIS, nên điểm yếu về khoảng cách được bù ở tầng sau.

Dữ liệu check-in là dữ liệu **mô phỏng** trên các địa điểm thật từ OpenStreetMap, nên các con số nói về khả năng học lại quy luật của bộ mô phỏng, chưa phải hành vi du khách thật."""),
]

NOTEBOOKS = {"01_du_lieu_va_baseline_heuristic.ipynb": NB1, "02_baseline_machine_learning.ipynb": NB2, "03_so_sanh_voi_gnn.ipynb": NB3}


def main():
    run = "--no-run" not in sys.argv
    if run:
        from nbclient import NotebookClient
    wanted = [a for a in sys.argv[1:] if not a.startswith("--")]  # ví dụ: 01, 02, 03
    for name, cells in NOTEBOOKS.items():
        if wanted and name[:2] not in wanted:
            continue
        nb = notebook(cells)
        if run:
            print(f"Đang chạy {name} …", flush=True)
            NotebookClient(nb, timeout=3600, kernel_name="python3", resources={"metadata": {"path": str(TARGET)}}).execute()
        nbformat.write(nb, TARGET / name)
        print(f"Đã ghi notebooks/{name}", flush=True)


if __name__ == "__main__":
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8")
    main()
