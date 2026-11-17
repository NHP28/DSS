"""Build the standalone, auto-downloading two-dataset Colab notebook."""
import ast
import json
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
cells = []


def markdown(source):
    cells.append({"cell_type":"markdown", "metadata":{}, "source":textwrap.dedent(source).strip().splitlines(keepends=True)})


def code(source):
    cells.append({"cell_type":"code", "metadata":{}, "execution_count":None, "outputs":[],
                  "source":textwrap.dedent(source).strip().splitlines(keepends=True)})


def module_cells(relative_path, filename, sections):
    """Show each module section as readable Python, preserving the exported source."""
    source = (ROOT / relative_path).read_text(encoding="utf-8")
    lines = source.splitlines(keepends=True)
    definitions = {node.name: node.lineno - 1 for node in ast.parse(source).body
                   if isinstance(node, (ast.FunctionDef, ast.ClassDef))}
    starts = [0 if anchor is None else definitions[anchor]
              for anchor, _ in sections]
    assert starts == sorted(set(starts)), f"Invalid section order: {relative_path}"
    for index, ((_, description), start) in enumerate(zip(sections, starts)):
        end = starts[index + 1] if index + 1 < len(starts) else len(lines)
        markdown(description)
        option = "" if index == 0 else "-a "
        code(f'%%writefile {option}"{{WORK}}/{filename}"\n' + "".join(lines[start:end]).rstrip())
        # Keep adjacent writefile cells separated even if the runner adds no newline.
        cells[-1]["source"][-1] += "\n"


markdown("""
# POI Recommendation — Đà Nẵng + Gowalla

**Mở Google Colab → chọn T4 GPU → Run all. Không cần upload dữ liệu, mount Drive hoặc clone repo.**

Notebook tự tải và train riêng trên hai bộ:

| Bộ dữ liệu | Nguồn | Ý nghĩa |
|---|---|---|
| Đà Nẵng | [GitHub NHP28/DSS](https://github.com/NHP28/DSS), pin commit cố định và SHA256 | POI từ OSM, tương tác và rating/giá/phổ biến mô phỏng |
| Gowalla | [Stanford SNAP](https://snap.stanford.edu/data/loc-gowalla.html) | Check-in thực, benchmark POI; dữ liệu gốc 6.442.890 sự kiện |

Mặc định Gowalla dùng **toàn bộ dữ liệu sau lọc lặp ≥15 POI/user và ≥10 user/POI**, không cắt phần đầu file.
Tải raw, lọc và train bộ này tốn thời gian hơn Đà Nẵng. File đã tải được cache và kiểm tra checksum.
Nếu cần chạy nhanh, đặt `GOWALLA_MAX_USERS = 2000` (tập con được ghi rõ trong báo cáo) hoặc `RUN_MODE = "smoke"`.

Mỗi bộ train **mô hình độc lập**, so sánh popularity, hourly popularity, LightGCN, TAS-GNN.
Không gộp ID/người dùng của hai bộ, không so trực tiếp accuracy giữa hai catalog.

Notebook bổ sung BPR-MF, geo-hourly, ablation, global time split, 3 seed, bootstrap theo user,
kiểm tra chất lượng dữ liệu, ma trận/heatmap, learning curves và phân tích lỗi.
**Câu hỏi nghiên cứu:** các nhánh thời gian/không gian có cải thiện xếp hạng trong cùng giao thức và budget tuning không?

**Đầu ra:** ZIP gồm các thư mục dataset/seed, bảng kết quả, biểu đồ, báo cáo chất lượng, mã nguồn và SHA256 manifest.
Không có bước tự upload dữ liệu/artifact tới dịch vụ khác.
""")
code('''
%pip -q install "numpy>=1.26,<3" "pandas>=2.2,<4" "matplotlib>=3.8,<4" "torch>=2.6,<3"
import json, sys, hashlib, shutil
from pathlib import Path
import numpy as np
import pandas as pd
import torch
print("Python:", sys.version, "PyTorch:", torch.__version__, "CUDA:", torch.cuda.is_available())
''')
markdown("""
## 1. Cấu hình

`RUN_MODE = "full"` chạy cả hai bộ theo cấu hình bên dưới. `smoke` train 24 user, 1 epoch, dim 16, 1 lớp để kiểm tra luồng.
Mọi lượt smoke hoặc subset được ghi nhãn, không gọi là kết quả benchmark đầy đủ.
Chạy nhiều seed để báo cáo mean/std, không chọn seed theo test score.
""")
code('''
DATASETS = ["danang", "gowalla"]
RUN_MODE = "full"  # full | smoke
GOWALLA_MAX_USERS = None  # None: toàn bộ sau lọc; 2000: subset ngẫu nhiên có seed
SEEDS = [42, 123, 2026]
SPLIT_PROTOCOL = "global_time"  # global_time | per_user (đối chiếu giao thức cũ)
RUN_ABLATION = True
LEARNING_RATES = [0.001, 0.003]  # Cùng grid cho mọi model được train
PATIENCE = 4
COVERAGE_QUERIES = 500  # Mẫu cố định, ghi nhãn coverage của mẫu
BOOTSTRAP_SAMPLES = 2000
ACTIVE_SEEDS = SEEDS[:2] if RUN_MODE == "smoke" else SEEDS
ACTIVE_LRS = LEARNING_RATES
EPOCHS = {"danang": 20, "gowalla": 10}
BATCH_SIZES = {"danang": 1024, "gowalla": 4096}
EVAL_BATCH_SIZE = 128  # Hạ xuống 32 nếu thiếu VRAM
DIM, LAYERS = 64, 3
WORK = Path("/content/dss_colab_v2") if Path("/content").exists() else Path("dss_colab_v2")
import uuid
RUN_TAG = f"{RUN_MODE}_{SPLIT_PROTOCOL}_{uuid.uuid4().hex[:8]}"
OUT = WORK / "artifacts" / RUN_TAG
WORK.mkdir(parents=True, exist_ok=True)
OUT.mkdir(parents=True, exist_ok=True)
assert RUN_MODE in {"full", "smoke"}
assert SEEDS and len(set(SEEDS)) == len(SEEDS)
assert DATASETS and set(DATASETS).issubset({"danang", "gowalla"})
assert SPLIT_PROTOCOL in {"global_time", "per_user"}
assert LEARNING_RATES and all(lr > 0 for lr in LEARNING_RATES)
assert BOOTSTRAP_SAMPLES >= 100 and COVERAGE_QUERIES > 0
if RUN_MODE == "full" and not torch.cuda.is_available():
    print("Đang chạy CPU. Nên chọn T4 GPU trước khi train toàn bộ Gowalla.")
''')
markdown("""
## 2. Mã nguồn theo từng chức năng

Mã Python từ `ml/poi_model.py` và `ml/datasets.py` được trình bày trực tiếp trong các cell bên dưới.
Mỗi cell có mục đích riêng để dễ đọc, sửa và đối chiếu với quy trình thí nghiệm.

Các cell dùng `%%writefile` để lưu mã thành `poi_model.py` và `poi_datasets.py` trong `WORK`;
`-a` nghĩa là nối tiếp vào file. **Chạy toàn bộ mục 2 theo thứ tự từ trên xuống** sau mỗi lần sửa mã:
cell đầu của mỗi file ghi mới, các cell sau nối tiếp, cell cuối import các hàm để dùng ở mục 3–10.
Các cell ghi file chưa tải dữ liệu hoặc huấn luyện. Ba file mã nguồn cũng được đưa vào ZIP kết quả.

Gowalla không cung cấp nhãn category/rating/giá: chỉ dùng tọa độ, thời gian, tương tác thực;
model bỏ category embedding và dùng tương tác time × item được học từ train.
Giờ/thứ Gowalla được xấp xỉ UTC + round(longitude/15), **không phải timezone/DST chính xác**.
""")
module_cells("ml/poi_model.py", "poi_model.py", [
    (None, """
    ### 2.1. Thư viện và hằng số của mô hình

    **Mục đích:** khai báo NumPy, Pandas, PyTorch, các nhóm POI (`CATEGORIES`) và phiên bản artifact (`FORMAT_VERSION`).
    Cell này tạo mới `poi_model.py`; chạy lại từ đây khi thay đổi bất kỳ phần mã mô hình nào bên dưới.
    """),
    ("dataset_metadata", """
    ### 2.2. Metadata và dấu vân tay dữ liệu

    **Mục đích:** `dataset_metadata` đọc nguồn gốc, tên file và khả năng có category của từng bộ dữ liệu.
    `dataset_fingerprints` tính SHA256 để nhận diện đúng dữ liệu khi lưu/khôi phục model, hỗ trợ cả newline LF/CRLF.
    """),
    ("seed_everything", """
    ### 2.3. Cố định seed để tái lập thí nghiệm

    **Mục đích:** `seed_everything` đặt seed cho Python, NumPy, PyTorch và cấu hình cuDNN xác định.
    Hàm được gọi trước mỗi lần fit để giảm sai khác do khởi tạo và lấy mẫu ngẫu nhiên.
    """),
    ("load_data", """
    ### 2.4. Đọc, kiểm tra và ánh xạ dữ liệu

    **Mục đích:** `load_data` kiểm tra schema CSV, ID, tọa độ, giờ/thứ và giá trị thiếu; loại sự kiện trùng hoàn toàn.
    Giữ user có ít nhất 5 sự kiện và 3 timestamp khác nhau, ánh xạ raw user/POI ID sang chỉ số liên tục,
    rồi trả về catalog, check-in theo thời gian, ID mapping và fingerprint dùng khi train.
    """),
    ("temporal_split", """
    ### 2.5. Chia tập theo thời gian và lấy mẫu âm

    **Mục đích:** `temporal_split` chia train/validation/test theo từng user với tỷ lệ mục tiêu 70/10/20,
    giữ các sự kiện cùng timestamp trong cùng một tập.
    `seen_items` lập lịch sử POI trong tập fit; `negative_samples` lấy POI chưa ghé để tính BPR loss,
    loại toàn bộ positive của fit khỏi tập lấy mẫu âm.
    """),
    ("POIGraph", """
    ### 2.6. Kiến trúc POIGraph: LightGCN và TAS-GNN

    **Mục đích:** định nghĩa lớp mạng dùng chung cho hai cấu hình so sánh.

    - `build_graph` dựng graph user–POI nhị phân, chuẩn hóa theo bậc nút; `embeddings` lan truyền qua các lớp graph.
    - Nhánh không gian mã hóa tọa độ và thêm category embedding khi dữ liệu có nhãn.
    - `context` mã hóa chu kỳ giờ/ngày trong tuần; các hàm `scores*` kết hợp user, POI và ngữ cảnh để chấm điểm.
    - `loss` tính BPR loss giữa POI positive/negative kèm regularization.

    LightGCN tắt `temporal` và `spatial`; TAS-GNN bật cả hai. Gowalla dùng `category_features=False`.
    """),
    ("hourly_counts", """
    ### 2.7. Baseline và chỉ số xếp hạng

    **Mục đích:** `hourly_counts` đếm tương tác theo giờ để tạo baseline popularity/hourly popularity.
    `evaluate` xếp hạng trên toàn catalog, mask lịch sử fit và chỉ chấm sự kiện có POI mới;
    trả về HR, NDCG, MRR tại các K cùng số event/user và macro-user HR@10.
    """),
    ("model_metrics", """
    ### 2.8. Đánh giá mô hình theo batch

    **Mục đích:** `model_metrics` chuyển model sang chế độ inference, tái sử dụng embedding và chấm điểm
    theo batch để giảm bộ nhớ. Hàm gọi `evaluate` và ghi rõ số sự kiện bị loại vì POI đã có trong lịch sử fit.
    """),
    ("fit_model", """
    ### 2.9. Vòng lặp huấn luyện và early stopping

    **Mục đích:** `fit_model` dựng graph từ tập fit, tối ưu BPR bằng Adam, lấy mẫu âm và chặn gradient lớn.
    Khi có validation, chọn epoch theo HR@10 và dừng sớm sau số epoch không cải thiện;
    trả về model, epoch được chọn và lịch sử loss/validation để báo cáo.
    """),
    ("run_experiment", """
    ### 2.10. Điều phối thí nghiệm và lưu kết quả

    **Mục đích:** `run_experiment` nối các bước đọc dữ liệu, chia tập, chạy baseline và train hai kiến trúc.
    Mỗi kiến trúc được chọn epoch trên validation, refit train+validation rồi đánh giá test.
    Hàm lưu checkpoint `.pt`, ID mapping, graph fit, metadata, `metrics.json` và `comparison.csv` cho từng dataset/seed.
    """),
    ("restore_bundle", """
    ### 2.11. Khôi phục model và hỗ trợ chạy bằng dòng lệnh

    **Mục đích:** `restore_bundle` đọc checkpoint, kiểm tra phiên bản, nạp trọng số và dựng lại graph
    để inference dùng đúng mapping/ngữ cảnh khi train.
    Khối `if __name__ == "__main__"` chỉ chạy khi gọi file Python từ terminal; import ở notebook không kích hoạt khối này.
    """),
])
module_cells("ml/datasets.py", "poi_datasets.py", [
    (None, """
    ### 2.12. Nguồn tải và checksum của hai bộ dữ liệu

    **Mục đích:** khai báo URL Đà Nẵng/Gowalla, commit Đà Nẵng đã pin, SHA256 và phiên bản tiền xử lý.
    Cell này tạo mới `poi_datasets.py`; chạy lại từ đây khi thay đổi phần mã tải/chuẩn hóa dữ liệu.
    """),
    ("sha256_file", """
    ### 2.13. Tải file có cache và kiểm tra toàn vẹn

    **Mục đích:** `sha256_file` tính checksum theo block; `download_file` dùng lại cache hợp lệ,
    tải qua file tạm, kiểm tra dung lượng/SHA256, thử lại khi lỗi và lưu biên nhận tải.
    Các hàm được định nghĩa tại đây; việc tải thực sự bắt đầu ở mục 3.
    """),
    ("prepare_danang", """
    ### 2.14. Chuẩn bị bộ dữ liệu Đà Nẵng

    **Mục đích:** `prepare_danang` tải các CSV/metadata đã pin và ghi `experiment_metadata.json`.
    Metadata phân biệt POI từ OSM với check-in, rating, giá và độ phổ biến được mô phỏng.
    """),
    ("iterative_core", """
    ### 2.15. Lọc và chuẩn hóa check-in Gowalla

    **Mục đích:** `iterative_core` lọc lặp theo số POI/user và user/POI đến hội tụ.
    `preprocess_gowalla` đọc file theo chunk, loại timestamp/GPS lỗi và sự kiện trùng, lọc core,
    lấy mẫu user theo seed nếu có giới hạn rồi xuất `pois.csv`, `checkins.csv` và metadata/checksum.
    Giữ raw ID, xấp xỉ giờ địa phương theo kinh độ và gán category `unknown` vì nguồn không có nhãn.
    """),
    ("prepare_gowalla", """
    ### 2.16. Chuẩn bị Gowalla và tái sử dụng dữ liệu đã xử lý

    **Mục đích:** `prepare_gowalla` điều phối tải raw và tiền xử lý;
    chỉ dùng lại cache khi phiên bản tiền xử lý, checksum raw và checksum CSV đều hợp lệ.
    Khối dòng lệnh cuối file hỗ trợ chuẩn bị dữ liệu khi chạy file Python bên ngoài notebook.
    """),
])
from notebook_sections import add_analysis_cells
add_analysis_cells(markdown, code, module_cells)
from notebook_layout import compact_cells
cells = compact_cells(cells)

notebook = {"nbformat":4, "nbformat_minor":5, "metadata":{
    "colab":{"name":"DSS_POI_Colab.ipynb", "provenance":[]},
    "kernelspec":{"display_name":"Python 3", "language":"python", "name":"python3"},
    "language_info":{"name":"python"}}, "cells":cells}
for index, cell in enumerate(cells):
    cell["id"] = f"dss-{index:02}"
destination = ROOT / "notebooks/DSS_POI_Colab.ipynb"
destination.parent.mkdir(exist_ok=True)
destination.write_text(json.dumps(notebook, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"Generated auto-download notebook ({len(cells)} cells, Danang + Gowalla)")
