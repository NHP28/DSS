"""Readable analysis and reporting cells for the standalone POI notebook."""


def add_analysis_cells(markdown, code, module_cells):
    sections = [
        (None, "Thư viện phân tích", "Khai báo thư viện để kiểm tra dữ liệu, đo tài nguyên, tính khoảng tin cậy và vẽ biểu đồ."),
        ("study_split", "Chia tập theo mốc thời gian chung", "Tạo train/validation/test theo global timeline, giữ timestamp bằng nhau cùng tập; ghi riêng các sự kiện của user chưa có lịch sử fit."),
        ("quality_profile", "Kiểm tra chất lượng và độ phủ dataset", "Đo độ thưa, lượt ghé lại, nhất quán timestamp và số POI/category không có tương tác; giữ các cảnh báo về nguồn dữ liệu."),
        ("plot_eda", "Trực quan hóa dữ liệu", "Vẽ phân bố user/POI, độ phủ category, bản đồ, heatmap thứ × giờ và mức tập trung tương tác."),
        ("rank_of_target", "Xếp hạng và công thức metric", "Tính rank chính xác trên toàn catalog, xử lý hòa điểm bằng item ID; tổng hợp HR/NDCG/MRR cho hai phạm vi đánh giá."),
        ("evaluate_detailed", "Đánh giá từng sự kiện", "Chấm một lần để lưu rank cho toàn bộ lượt ghé và lượt ghé mới; đo coverage trên một mẫu truy vấn cố định, ghi rõ mẫu số."),
        ("model_predictions", "Inference batch và đo tốc độ", "Tái sử dụng graph embedding khi chấm điểm; đo p50/p95 của batch scoring đã warm-up, tách khỏi HTTP và thời gian dựng graph."),
        ("model_variants", "Baseline và cấu hình ablation", "Khai báo BPR-MF, LightGCN, TAS-GNN và các biến thể bỏ thành phần. Không chạy ablation category khi nguồn không có nhãn."),
        ("run_study", "Điều phối thí nghiệm mới", "Tuning learning rate/epoch chỉ bằng validation, refit train+validation, chấm test, lưu rank từng sự kiện, checkpoint và chi phí tài nguyên."),
        ("paired_user_bootstrap", "Khoảng tin cậy bootstrap theo user", "Trung bình các seed trong từng user rồi resample cặp user để tính CI 95% cho chênh lệch macro-user HR@10; đây là bất định theo user, không phải CI cho event HR."),
        ("plot_study", "Biểu đồ nhiều seed và learning curves", "Vẽ mean/std qua mọi seed, ma trận model × metric, loss/validation theo epoch và đánh dấu epoch được chọn."),
        ("error_slices", "Phân tích lỗi và các nhóm dữ liệu", "So sánh theo giờ, category, độ dài lịch sử và độ phổ biến POI; xuất số mẫu cùng mỗi metric và ví dụ đúng/sai từ seed đầu."),
    ]
    module_cells("ml/experiment_analysis.py", "poi_analysis.py", [
        (anchor, f"### 2.{index}. {title}\n\n**Mục đích:** {purpose}")
        for index, (anchor, title, purpose) in enumerate(sections, 17)
    ])
    markdown("""
    ### 2.29. Nạp các module đã tạo

    **Mục đích:** nạp lại mã sau khi chạy mục 2 từ trên xuống. Notebook dùng `run_study` cho giao thức mới;
    `run_experiment` trong module gốc được giữ để tương thích các script dòng lệnh trước đây.
    """)
    code('''
    if str(WORK.resolve()) not in sys.path:
        sys.path.insert(0, str(WORK.resolve()))
    import importlib
    import poi_model, poi_datasets, poi_analysis
    for module in (poi_model, poi_datasets, poi_analysis):
        importlib.reload(module)
    from poi_model import load_data, restore_bundle, dataset_metadata, seen_items
    from poi_datasets import prepare_danang, prepare_gowalla
    from poi_analysis import (quality_profile, plot_eda, study_split, model_variants,
                             run_study, paired_user_bootstrap, plot_study, error_slices)
    import matplotlib.pyplot as plt
    ''')
    markdown("""
    ## 3. Tải dữ liệu và ghi lại nguồn gốc

    **Mục đích:** tự tải Đà Nẵng từ commit đã pin/SHA256 và Gowalla từ Stanford SNAP.
    Gowalla đọc theo chunk, loại GPS/timestamp lỗi và sự kiện trùng, lọc core ≥15 POI/user và ≥10 user/POI.
    Nếu giới hạn user, lấy mẫu ngẫu nhiên sau core với seed cố định; metadata ghi rõ tập con.

    Core và điều kiện đủ lịch sử được xác định trên nguồn đầy đủ: đây vẫn là thiết lập **transductive**.
    Global time split ngăn graph fit chứa tương tác sau mốc test, chưa biến catalog thành benchmark cold-start hoàn toàn.
    """)
    code('''
    DATA_DIRS, DATA_CACHE = {}, {}
    for name in DATASETS:
        DATA_DIRS[name] = (prepare_danang(WORK) if name == "danang" else
            prepare_gowalla(WORK, max_users=48 if RUN_MODE == "smoke" else GOWALLA_MAX_USERS, seed=42))
        DATA_CACHE[name] = load_data(DATA_DIRS[name], max_users=24 if RUN_MODE == "smoke" else None)
        metadata = dataset_metadata(DATA_DIRS[name])
        print(name, json.dumps({key: metadata.get(key) for key in
            ["source_url", "source_revision", "source_sha256", "data_provenance", "raw_events", "full_core", "is_subset"]}, ensure_ascii=False, indent=2))
    ''')
    markdown("""
    ## 4. Chất lượng dữ liệu trước khi huấn luyện

    **Mục đích:** báo cáo trên đúng dữ liệu sẽ được dùng, không suy rộng kết quả smoke sang toàn bộ nguồn.
    Kiểm tra kỹ thuật sạch không chứng minh dữ liệu đại diện cho người dùng thực.
    POI có trong catalog nhưng không có tương tác vẫn được giữ và được đánh dấu chưa có bằng chứng đánh giá.
    Bộ Đà Nẵng đã audit có 295 khách sạn không có check-in; notebook tính lại từ CSV mỗi lần chạy.
    """)
    code('''
    QUALITY, quality_rows, category_rows = {}, [], []
    for name in DATASETS:
        pois, events, user_ids, poi_ids, fingerprint = DATA_CACHE[name]
        profile = quality_profile(pois, events, dataset_metadata(DATA_DIRS[name]))
        profile.update(smoke_run=RUN_MODE == "smoke", dataset_sha256=fingerprint)
        QUALITY[name] = profile
        quality_rows.append({"dataset": name, **{key: profile[key] for key in
            ["users", "pois", "events", "sparsity_percent", "repeat_event_percent", "unreferenced_pois", "hour_mismatches", "weekday_mismatches"]}})
        for category, counts in profile["category_coverage"].items():
            category_rows.append({"dataset": name, "category": category, **counts})
        for warning in profile["warnings"]:
            print(f"[{name}] {warning}")
    display(pd.DataFrame(quality_rows).set_index("dataset"))
    category_quality = pd.DataFrame(category_rows)
    display(category_quality)
    (OUT / "dataset_quality.json").write_text(json.dumps(QUALITY, ensure_ascii=False, indent=2), encoding="utf-8")
    category_quality.to_csv(OUT / "category_coverage.csv", index=False)
    ''')
    markdown("""
    ### 4.1. EDA: phân bố, bản đồ và heatmap thời gian

    **Mục đích:** kiểm tra user hoạt động ít/nhiều, POI ít/phổ biến, category không có tương tác và mẫu giờ/thứ.
    Heatmap Gowalla dùng giờ xấp xỉ theo kinh độ. Mẫu giờ của dữ liệu mô phỏng có thể phản ánh quy tắc sinh dữ liệu;
    kết quả cao trên Đà Nẵng chưa chứng minh học được hành vi người dùng thật.
    """)
    code('''
    for name in DATASETS:
        pois, events, *_ = DATA_CACHE[name]
        label = "SMOKE: technical check" if RUN_MODE == "smoke" else ("USER SUBSET" if QUALITY[name]["source_metadata"].get("is_subset") else "FULL PROCESSED DATA")
        figure = plot_eda(pois, events, name, OUT, run_label=label)
        display(figure)
        plt.close(figure)
    ''')
    markdown("""
    ### 4.2. Ma trận tương tác user–POI

    **Mục đích:** trực quan hóa tính thưa trên một mẫu tối đa 60 user × 120 POI, lấy ngẫu nhiên với seed cố định.
    Đây là ảnh minh họa mẫu, không phải toàn bộ ma trận và không được dùng để chọn hyperparameter.
    """)
    code('''
    fig, axes = plt.subplots(1, len(DATASETS), figsize=(7 * len(DATASETS), 4), squeeze=False)
    for column, name in enumerate(DATASETS):
        pois, events, *_ = DATA_CACHE[name]
        rng = np.random.default_rng(2026)
        sampled_users = np.sort(rng.choice(events.user.unique(), min(60, events.user.nunique()), replace=False))
        sampled_items = np.sort(rng.choice(len(pois), min(120, len(pois)), replace=False))
        sample = events[events.user.isin(sampled_users) & events.item.isin(sampled_items)]
        matrix = pd.crosstab(sample.user, sample.item).reindex(index=sampled_users, columns=sampled_items, fill_value=0)
        axes[0, column].imshow(matrix.to_numpy() > 0, aspect="auto", cmap="Blues", vmin=0, vmax=1)
        axes[0, column].set(title=f"{name}: sampled interaction matrix | {RUN_MODE.upper()}", xlabel="Sampled POI index", ylabel="Sampled user index")
    fig.tight_layout()
    fig.savefig(OUT / "interaction_matrices.png", dpi=150)
    display(fig)
    plt.close(fig)
    ''')
    markdown("""
    ## 5. Giao thức đánh giá và kiểm tra split

    **Mục đích:** mặc định chia theo hai mốc thời gian chung, tỷ lệ mục tiêu 70/10/20; timestamp bằng nhau luôn cùng tập.
    Chọn epoch/learning rate trên validation, sau đó refit train+validation và đánh giá test bằng lịch sử fit cố định.
    User chưa có lịch sử train bị loại khỏi tuning; user chưa có lịch sử fit bị loại khỏi bảng test warm-user và được đếm riêng.

    Hai phạm vi được báo cáo độc lập:

    - **Novel visits:** target chưa ghé trong fit; mask toàn bộ POI đã ghé trong fit.
    - **All visits:** giữ cả lượt quay lại, không mask lịch sử. Hai phạm vi có candidate set khác nhau nên đọc bảng riêng.

    `per_user` chỉ dùng khi cần đối chiếu giao thức cũ; nó có thể đưa tương tác tương lai của user khác vào graph.
    Tham khảo [Ji et al., temporal leakage](https://arxiv.org/abs/2010.11060).
    """)
    code('''
    SPLIT_REPORTS, split_rows = {}, []
    fig, axes = plt.subplots(len(DATASETS), 1, figsize=(12, 3 * len(DATASETS)), squeeze=False)
    for row, name in enumerate(DATASETS):
        pois, events, *_ = DATA_CACHE[name]
        train, validation, test, fit, info = study_split(events, SPLIT_PROTOCOL)
        fit_pairs = pd.MultiIndex.from_frame(fit[["user", "item"]].drop_duplicates())
        repeated = pd.MultiIndex.from_frame(test[["user", "item"]]).isin(fit_pairs)
        info.update(novel_test_events=int((~repeated).sum()), repeated_test_events=int(repeated.sum()),
                    repeated_test_percent=float(repeated.mean() * 100),
                    test_item_cold_events=int((~test.item.isin(fit.item)).sum()))
        SPLIT_REPORTS[name] = info
        split_rows.append({"dataset": name, **info})
        for label, frame in [("train", train), ("validation (warm users)", validation), ("test (warm users)", test)]:
            axes[row, 0].hist(pd.to_datetime(frame.ts, unit="s", utc=True).dt.tz_localize(None), bins=35, alpha=.6, label=label)
        axes[row, 0].set(title=f"{name}: {SPLIT_PROTOCOL} | {RUN_MODE.upper()}", ylabel="Events")
        axes[row, 0].legend()
        if SPLIT_PROTOCOL == "global_time":
            assert train.ts.max() < validation.ts.min()
            assert fit.ts.max() < test.ts.min()
    display(pd.DataFrame(split_rows).set_index("dataset"))
    fig.tight_layout()
    fig.savefig(OUT / "temporal_split.png", dpi=150)
    display(fig)
    plt.close(fig)
    (OUT / "split_audit.json").write_text(json.dumps(SPLIT_REPORTS, ensure_ascii=False, indent=2), encoding="utf-8")
    ''')
    markdown(r"""
    ## 6. Kiến trúc, giả thuyết và thiết kế thí nghiệm

    **Mục đích:** kiểm tra liệu thông tin thời gian/không gian cải thiện xếp hạng so với các baseline trên cùng dữ liệu và budget tuning.
    Giả thuyết được kiểm tra riêng cho mỗi dataset; không giả định TAS-GNN phải thắng.

    Backbone là graph user–POI nhị phân chuẩn hóa bậc, lan truyền tuyến tính rồi trung bình embedding các lớp,
    theo [LightGCN, He et al.](https://arxiv.org/abs/2002.02126).
    TAS-GNN của dự án cộng nhánh tọa độ/category và ngữ cảnh sin/cos ngày/tuần qua gating; graph vẫn tĩnh trong mỗi lượt fit.

    Với positive $i^+$ và negative $i^-$ không thuộc lịch sử fit:
    $\mathcal L_{BPR}=\operatorname{softplus}(-(s(u,i^+,t)-s(u,i^-,t)))+10^{-4}R$,
    với $R$ là trung bình tổng bình phương các embedding user/positive/negative được lấy trong batch.

    Với rank $r$ của một target: $HR@K=\mathbf 1[r\le K]$,
    $NDCG@K=\mathbf 1[r\le K]/\log_2(r+1)$ và $MRR@K=\mathbf 1[r\le K]/r$; báo cáo trung bình theo event và macro-user HR@10.
    Đây không phải Recall của tập POI duy nhất theo user. Chấm trên toàn catalog; không lấy sampled negatives khi test.

    BPR-MF dùng 0 lớp graph; các model train được dùng cùng danh sách learning rate, số epoch tối đa và patience.
    Geo-hourly dùng check-in cuối của fit làm vị trí gốc và thang khoảng cách cố định 5 km, chỉ chạy với global time.
    `tas_no_space` bỏ nhánh spatial tĩnh nhưng giữ category trong nhánh time khi có nhãn;
    `tas_no_category` thay modulation category bằng item embedding, nên cần đọc cùng bảng cấu hình khi diễn giải ablation.
    """)
    code('''
    variant_rows = []
    for name in DATASETS:
        has_categories = dataset_metadata(DATA_DIRS[name])["has_categories"]
        for model, (temporal, spatial, category_features) in model_variants(has_categories, RUN_ABLATION).items():
            variant_rows.append({"dataset": name, "model": model, "time": temporal, "spatial": spatial,
                                 "category_features": category_features, "layers": 0 if model == "bpr_mf" else (1 if RUN_MODE == "smoke" else LAYERS)})
    display(pd.DataFrame(variant_rows))
    experiment_config = {"datasets": DATASETS, "run_mode": RUN_MODE, "seeds": ACTIVE_SEEDS,
        "protocol": SPLIT_PROTOCOL, "run_ablation": RUN_ABLATION, "epochs": EPOCHS,
        "learning_rates": ACTIVE_LRS, "patience": PATIENCE, "dim": DIM, "layers": LAYERS,
        "batch_sizes": BATCH_SIZES, "eval_batch_size": EVAL_BATCH_SIZE,
        "coverage_queries_max": COVERAGE_QUERIES, "bootstrap_resamples": BOOTSTRAP_SAMPLES,
        "smoke_overrides": {"max_users": 24, "epochs": 1, "dim": 16, "layers": 1} if RUN_MODE == "smoke" else None}
    (OUT / "experiment_config.json").write_text(json.dumps(experiment_config, indent=2), encoding="utf-8")
    print("Trainable fits (tuning candidates + refit):", len(variant_rows) * len(ACTIVE_SEEDS) * (len(ACTIVE_LRS) + 1))
    print("Full Gowalla + ablation + nhiều seed có thể tốn nhiều giờ; smoke chỉ kiểm tra kỹ thuật.")
    ''')
    markdown("""
    ### 6.1. Huấn luyện, refit và chấm test

    **Mục đích:** thực thi các cấu hình đã khai báo. Không chọn seed hoặc thay hyperparameter theo kết quả test.
    DIM/LAYERS được giữ cố định; learning rate và epoch là hai tham số được chọn trên validation trong grid đã khai báo.
    Mỗi seed có thư mục riêng; seed đầu giữ đường dẫn tương thích ứng dụng, không có nghĩa là seed tốt nhất.
    """)
    code('''
    reports, EXPERIMENTS = {}, {}
    for name in DATASETS:
        reports[name], EXPERIMENTS[name] = [], []
        for seed in ACTIVE_SEEDS:
            destination = OUT / name if seed == ACTIVE_SEEDS[0] else OUT / name / f"seed_{seed}"
            report = run_study(DATA_DIRS[name], destination,
                epochs=1 if RUN_MODE == "smoke" else EPOCHS[name], seed=seed,
                max_users=24 if RUN_MODE == "smoke" else None,
                dim=16 if RUN_MODE == "smoke" else DIM, layers=1 if RUN_MODE == "smoke" else LAYERS,
                batch_size=BATCH_SIZES[name], eval_batch_size=EVAL_BATCH_SIZE,
                protocol=SPLIT_PROTOCOL, ablation=RUN_ABLATION, learning_rates=ACTIVE_LRS,
                patience=PATIENCE, coverage_queries=COVERAGE_QUERIES)
            reports[name].append(report)
            EXPERIMENTS[name].append((destination, report))
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
    ''')
    markdown("""
    ## 7. Kết quả nhiều seed, ma trận metric và learning curves

    **Mục đích:** biểu đồ dùng trung bình của tất cả seed, thanh sai số là độ lệch chuẩn giữa seed.
    Heatmap đọc theo từng dataset. Learning curves minh họa seed đầu với nhãn rõ ràng và epoch đã chọn.
    BPR loss giữa kiến trúc có thể có scale khác nhau; ưu tiên validation metric khi so sánh.
    """)
    code('''
    rows, all_visit_rows = [], []
    for name in DATASETS:
        table, figures = plot_study(reports[name], name, OUT)
        table["dataset"] = name
        rows.append(table)
        for figure in figures:
            display(figure)
            plt.close(figure)
        for report in reports[name]:
            for model, metrics in report["all_event_results"].items():
                all_visit_rows.append({"dataset": name, "seed": report["seed"], "model": model, **metrics})
    summary = pd.concat(rows, ignore_index=True)
    all_visit_summary = pd.DataFrame(all_visit_rows)
    for frame in (summary, all_visit_summary):
        frame["smoke_run"] = RUN_MODE == "smoke"
        frame["protocol"] = SPLIT_PROTOCOL
        frame["is_subset"] = frame.dataset.map({name: any(report["is_subset"] for report in reports[name]) for name in DATASETS})
    summary.to_csv(OUT / "all_datasets_comparison.csv", index=False)
    all_visit_summary.to_csv(OUT / "all_visit_comparison.csv", index=False)
    metrics = ["HR@10", "NDCG@10", "MRR@10", "sample_catalog_coverage_at_10"]
    aggregate = summary.groupby(["dataset", "model"])[metrics].agg(["mean", "std", "count"])
    aggregate.to_csv(OUT / "multi_seed_summary.csv")
    print("NOVEL VISITS")
    display(aggregate)
    print("ALL VISITS: candidate set includes previously visited POIs")
    display(all_visit_summary.groupby(["dataset", "model"])[["HR@10", "NDCG@10"]].agg(["mean", "std"]))
    ''')
    markdown("""
    ### 7.1. Ablation và khoảng tin cậy chênh lệch

    **Mục đích:** kiểm tra biến thể bỏ thành phần và độ bất định của chênh lệch so với TAS-GNN.
    Bootstrap resample theo user, ghép cặp trên cùng user; seed được trung bình trong user trước khi resample.
    CI mô tả chênh lệch **macro-user HR@10**, không phải event HR@10. CI chứa 0 chưa cung cấp bằng chứng rõ cho chiều cải thiện.
    Đây là phân tích thăm dò nhiều so sánh, chưa hiệu chỉnh multiple comparisons; không chọn lại hyperparameter từ bảng này.
    """)
    code('''
    BOOTSTRAP = {}
    for name in DATASETS:
        intervals = paired_user_bootstrap(EXPERIMENTS[name], samples=BOOTSTRAP_SAMPLES)
        BOOTSTRAP[name] = intervals
        intervals.to_csv(OUT / f"{name}_paired_user_ci.csv", index=False)
        print(name, "TAS-GNN minus reference: macro-user HR@10")
        display(intervals)
        ablation = summary[(summary.dataset == name) & summary.model.str.startswith("tas_")]
        display(ablation.groupby("model")[["HR@10", "NDCG@10"]].agg(["mean", "std"]))
    ''')
    markdown("""
    ## 8. Phân tích lỗi, độ phủ và chi phí inference

    **Mục đích:** tìm nhóm dữ liệu yếu qua các slice và ví dụ đúng/sai của seed đầu. Bảng luôn có số mẫu;
    không suy diễn từ nhóm ít mẫu hoặc category không có event. Các rank được tính trên đúng candidate set đã khai báo.

    Catalog coverage@10 dùng tối đa `COVERAGE_QUERIES` novel queries với mẫu cố định để so model;
    nó chưa phải độ phủ của toàn bộ traffic. Latency p50/p95 đo warm batch scoring với embedding cache,
    chưa bao gồm HTTP, truyền CPU hoặc dựng lại graph và không phải latency production.
    """)
    code('''
    resource_rows = []
    for name in DATASETS:
        destination, report = EXPERIMENTS[name][0]
        slices, examples, figure = error_slices(destination, report, OUT)
        display(slices)
        print(name, "First-seed examples; rank_all and rank_novel use different candidate sets")
        display(examples[["user", "item", "hour", "category", "fit_history", "poi_fit_events", "rank_novel", "rank_all"]])
        display(figure)
        plt.close(figure)
        for _, seed_report in EXPERIMENTS[name]:
            for model, values in seed_report["resources"].items():
                resource_rows.append({"dataset": name, "seed": seed_report["seed"], "model": model, **values})
    resources = pd.DataFrame(resource_rows)
    resources.to_csv(OUT / "resources.csv", index=False)
    display(resources)
    ''')
    markdown("""
    ## 9. Kết luận có điều kiện và giới hạn

    **Mục đích:** tạo nhận xét từ kết quả thực tế của lượt chạy. Không chèn số liệu từ báo cáo cũ hoặc khẳng định model đề xuất luôn thắng.
    Đà Nẵng dùng tương tác mô phỏng; Gowalla là hành vi lịch sử 2009–2010, giờ địa phương xấp xỉ và catalog đã lọc core.
    Notebook chưa đánh giá người dùng thực trực tuyến, user cold-start, A/B test, calibration xác suất hoặc hiệu quả AHP/TOPSIS.
    Điểm model là điểm xếp hạng, không phải xác suất thích địa điểm.
    """)
    code(r'''
    conclusion = ["# Báo cáo lượt chạy POI", "", f"Run mode: {RUN_MODE}; protocol: {SPLIT_PROTOCOL}; seeds: {ACTIVE_SEEDS}", ""]
    if RUN_MODE == "smoke":
        conclusion.append("SMOKE: chỉ kiểm tra luồng kỹ thuật; không dùng số liệu dưới đây làm benchmark chất lượng.")
    for name in DATASETS:
        means = summary[summary.dataset == name].groupby("model")["HR@10"].mean()
        conclusion.extend(["", f"## {name}", f"Novel event HR@10 mean: {means.to_dict()}",
            f"Repeated test events excluded from novel metric: {SPLIT_REPORTS[name]['repeated_test_percent']:.2f}%.",
            f"Cold-user test events excluded: {SPLIT_REPORTS[name]['test_cold_user_events_excluded']}.",
            "Paired user CI (macro-user HR@10, exploratory comparisons):", BOOTSTRAP[name].to_csv(index=False)])
        conclusion.extend(QUALITY[name]["warnings"])
    conclusion.extend(["", "## Giới hạn chung", "Catalog/eligibility/core transductive; lịch sử fit cố định trong test.",
        "DIM/LAYERS cố định; tuning chỉ trong grid learning rate và epoch đã khai báo.",
        "Seed std và user bootstrap phản ánh hai nguồn bất định khác nhau; không phải bằng chứng nhân quả.",
        "Chưa kiểm chứng cold-start user, A/B test hoặc hiệu quả DSS trong notebook này."])
    report_text = "\n\n".join(conclusion)
    (OUT / "research_summary.md").write_text(report_text, encoding="utf-8")
    print(report_text)
    ''')
    markdown("""
    ## 10. Kiểm tra artifact, tái lập và tải ZIP

    **Mục đích:** kiểm tra mọi checkpoint của mọi seed, chấm cặp khớp chấm toàn catalog và khôi phục đúng graph/ID mapping.
    ZIP chứa dữ liệu kiểm tra chất lượng, split audit, config, metric, rank từng sự kiện test, biểu đồ,
    mã nguồn và SHA256 manifest; không chứa raw download.

    Các output của lượt chạy này được gom vào một thư mục cấu hình riêng để tránh trộn kết quả cũ.
    Chỉ dùng artifact `danang/` với ứng dụng Đà Nẵng. Artifact Gowalla dùng cho benchmark riêng.
    User không có trong `trained_user_ids` cần fallback; không sử dụng embedding chưa được fit.
    Môi trường được ghi phiên bản thực tế trong ZIP; khác GPU/driver vẫn có thể gây sai khác số học.
    """)
    code(r'''
    checked = 0
    for name in DATASETS:
        for destination, report in EXPERIMENTS[name]:
            for model_name in report["model_configs"]:
                model, bundle = restore_bundle(destination / f"{model_name}.pt")
                assert bundle["dataset_sha256"] == DATA_CACHE[name][4]
                assert bundle["poi_ids"] == DATA_CACHE[name][3]
                assert bundle["user_ids"] == DATA_CACHE[name][2]
                assert len(bundle["trained_user_ids"]) > 0
                user = int(bundle["fit_pairs"][0, 0])
                with torch.inference_mode():
                    emb = model.embeddings()
                    scores = model.scores(user, 8, 0, 1680000000., emb)
                    pair = model.score_pairs(torch.tensor([user]), torch.tensor([0]), torch.tensor([8]),
                        torch.tensor([0]), torch.tensor([1680000000.], dtype=torch.float64), emb)
                    assert torch.isfinite(scores).all()
                    assert torch.allclose(pair[0], scores[0], atol=1e-5)
                checked += 1
    print("Checkpoint roundtrips passed:", checked)
    for filename in ("poi_model.py", "poi_datasets.py", "poi_analysis.py"):
        shutil.copy2(WORK / filename, OUT / filename)
    import platform, matplotlib
    runtime = {"python": platform.python_version(), "platform": platform.platform(),
               "torch": str(torch.__version__), "numpy": np.__version__, "pandas": pd.__version__,
               "matplotlib": matplotlib.__version__, "cuda_runtime": torch.version.cuda,
               "device": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "CPU"}
    (OUT / "runtime.json").write_text(json.dumps(runtime, indent=2), encoding="utf-8")
    pins = [f"{name}=={runtime[name]}" for name in ("numpy", "pandas", "matplotlib", "torch")]
    (OUT / "runtime_requirements.txt").write_text("\n".join(pins) + "\n", encoding="utf-8")
    manifest = {str(path.relative_to(OUT)).replace("\\", "/"): hashlib.sha256(path.read_bytes()).hexdigest()
                for path in OUT.rglob("*") if path.is_file() and path.name != "manifest.json"}
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    archive_path = shutil.make_archive(str(WORK / f"dss_{RUN_TAG}_artifacts"), "zip", OUT)
    import zipfile
    with zipfile.ZipFile(archive_path) as archive:
        assert archive.testzip() is None
        for filename, checksum in manifest.items():
            digest = hashlib.sha256()
            with archive.open(filename) as member:
                for block in iter(lambda: member.read(1024 * 1024), b""):
                    digest.update(block)
            assert digest.hexdigest() == checksum, filename
    print("Verified ZIP:", archive_path)
    try:
        from google.colab import files
        files.download(archive_path)
    except ImportError:
        print("Chạy local: lấy ZIP tại", archive_path)
    ''')
    markdown("""
    ## 11. Tài liệu tham khảo và cách đọc kết quả

    - [Gowalla — Stanford SNAP](https://snap.stanford.edu/data/loc-gowalla.html): nguồn và thời kỳ thu thập check-in.
    - [LightGCN — He et al., SIGIR 2020](https://arxiv.org/abs/2002.02126): backbone graph dùng trong baseline.
    - [Data leakage in recommender offline evaluation — Ji et al.](https://arxiv.org/abs/2010.11060): lý do dùng global timeline.
    - [Recommenders evaluation](https://recommenders-team.github.io/recommenders/evaluation.html): ranking metrics và catalog coverage.

    Luôn đọc cùng `dataset_quality.json`, `split_audit.json`, `experiment_config.json` và `research_summary.md`.
    Bản source notebook không đính kèm điểm benchmark chưa được chạy; bản executed smoke chỉ chứng minh luồng kỹ thuật.
    """)
