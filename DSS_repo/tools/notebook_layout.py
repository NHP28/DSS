"""Group the standalone notebook into 20 cells without changing executable code."""
import re
import shlex


def compact_cells(cells):
    def source(cell):
        return "".join(cell["source"])

    def code_at(prefix):
        matches = [i for i, cell in enumerate(cells)
                   if cell["cell_type"] == "code" and source(cell).startswith(prefix)]
        assert len(matches) == 1, (prefix, matches)
        return matches[0]

    def markdown_at(prefix):
        matches = [source(cell) for cell in cells
                   if cell["cell_type"] == "markdown" and source(cell).startswith(prefix)]
        assert len(matches) == 1, prefix
        return matches[0]

    def comment(text):
        return "\n".join("# " + line if line else "#" for line in text.splitlines())

    def markdown(text):
        return {"cell_type": "markdown", "metadata": {}, "source": text.strip().splitlines(keepends=True)}

    def merged_code(indices, title, filename=None, append=False):
        sections = []
        for index in indices:
            body = source(cells[index])
            if filename:
                body = body.partition("\n")[2]
            explanation = source(cells[index - 1]) if index and cells[index - 1]["cell_type"] == "markdown" else ""
            sections.append(comment(explanation) + "\n" + body.rstrip())
        header = (f'%%writefile {"-a " if append else ""}"{{WORK}}/{filename}"\n'
                  if filename else f"# {title}\n")
        return {"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [],
                "source": (header + "\n\n".join(sections) + "\n").splitlines(keepends=True)}

    modules = {}
    for index, cell in enumerate(cells):
        text = source(cell)
        if cell["cell_type"] == "code" and text.startswith("%%writefile "):
            filename = shlex.split(text.splitlines()[0])[-1].rsplit("/", 1)[-1]
            modules.setdefault(filename, []).append(index)
    model = modules["poi_model.py"]
    analysis = modules["poi_analysis.py"]
    assert len(model) == 11 and len(analysis) == 12

    intro = markdown_at("# POI Recommendation")
    intro += "\n\n**Bố cục rút gọn: 20 cell (13 code, 7 Markdown).** Mỗi cell code gộp các bước cùng mục đích; các tiểu mục được giữ bằng comment.\n\n"
    intro += "## 1. Môi trường và cấu hình\n\n" + markdown_at("## 1. Cấu hình").partition("\n")[2].strip()
    source_notes = """## 2. Mã nguồn độc lập theo nhóm chức năng

Các cell bên dưới hiển thị Python trực tiếp, không đóng gói mã thành chuỗi `MODEL_SOURCE`.

- Hai cell model: dữ liệu/kiến trúc và đánh giá/huấn luyện/khôi phục.
- Một cell tải và tiền xử lý dataset.
- Hai cell phân tích: kiểm tra dữ liệu/metric/inference và thí nghiệm/bootstrap/biểu đồ.
- Một cell import các module và tải dữ liệu.

`%%writefile` ghi mới file; `-a` nối phần tiếp theo. Sau khi sửa mã nguồn, chạy lại toàn bộ mục 2 từ trên xuống.
Chạy đến cell import/tải dữ liệu để nạp đầy đủ các định nghĩa. Mã nguồn cũng được đưa vào ZIP kết quả.
Gowalla không có category/rating/giá; giờ địa phương được xấp xỉ theo kinh độ, chưa xử lý timezone/DST chính xác.
"""
    data_notes = """## 3. Chất lượng dữ liệu, EDA và giao thức split

Cell tiếp theo gộp kiểm tra chất lượng, phân bố user/POI, bản đồ, heatmap thứ × giờ,
ma trận tương tác mẫu và kiểm tra train/validation/test theo mốc thời gian chung.
Các bảng luôn ghi số mẫu; smoke/subset được gắn nhãn. Category không có tương tác được cảnh báo, không tạo dữ liệu bù.
"""
    data_notes += "\n\n" + markdown_at("## 5. Giao thức đánh giá").partition("\n")[2].strip()
    methods = re.sub(r"^## 6\.", "## 4.", markdown_at("## 6. Kiến trúc"))
    methods += "\n\n" + markdown_at("### 6.1. Huấn luyện").partition("\n")[2].strip()
    results = re.sub(r"^## 7\.", "## 5.", markdown_at("## 7. Kết quả"))
    results += "\n\n### Ablation và khoảng tin cậy\n\n" + markdown_at("### 7.1. Ablation").partition("\n")[2].strip()
    results += "\n\n### Phân tích lỗi và tài nguyên\n\n" + markdown_at("## 8. Phân tích lỗi").partition("\n")[2].strip()
    conclusion = re.sub(r"^## 9\.", "## 6.", markdown_at("## 9. Kết luận"))
    conclusion += "\n\n### Kiểm tra artifact và tải ZIP\n\n" + markdown_at("## 10. Kiểm tra artifact").partition("\n")[2].strip()
    references = re.sub(r"^## 11\.", "## 7.", markdown_at("## 11. Tài liệu"))

    compact = [
        markdown(intro),
        merged_code([code_at("%pip"), code_at("DATASETS =")], "Môi trường và cấu hình"),
        markdown(source_notes),
        merged_code(model[:6], "Dữ liệu và kiến trúc POIGraph", "poi_model.py"),
        merged_code(model[6:], "Đánh giá, huấn luyện và khôi phục", "poi_model.py", append=True),
        merged_code(modules["poi_datasets.py"], "Tải và chuẩn hóa dữ liệu", "poi_datasets.py"),
        merged_code(analysis[:7], "Chất lượng, EDA, metric và inference", "poi_analysis.py"),
        merged_code(analysis[7:], "Thí nghiệm, bootstrap và phân tích", "poi_analysis.py", append=True),
        merged_code([code_at("if str(WORK.resolve())"), code_at("DATA_DIRS, DATA_CACHE")], "Nạp module và tải dữ liệu"),
        markdown(data_notes),
        merged_code([code_at("QUALITY, quality_rows"), code_at("for name in DATASETS:\n    pois, events, *_ = DATA_CACHE[name]\n    label ="),
                     code_at("fig, axes = plt.subplots(1, len(DATASETS)"), code_at("SPLIT_REPORTS, split_rows")], "Kiểm tra dataset, EDA, ma trận và split"),
        markdown(methods),
        merged_code([code_at("variant_rows ="), code_at("reports, EXPERIMENTS")], "Thiết kế và chạy thí nghiệm"),
        markdown(results),
        merged_code([code_at("rows, all_visit_rows"), code_at("BOOTSTRAP =")], "Tổng hợp nhiều seed, learning curves và bootstrap"),
        merged_code([code_at("resource_rows =")], "Phân tích lỗi, ví dụ và chi phí inference"),
        markdown(conclusion),
        merged_code([code_at("conclusion =")], "Kết luận từ số liệu thực tế"),
        merged_code([code_at("checked =")], "Kiểm tra checkpoint và xuất ZIP"),
        markdown(references),
    ]
    assert len(compact) == 20
    assert sum(cell["cell_type"] == "code" for cell in compact) == 13
    return compact
