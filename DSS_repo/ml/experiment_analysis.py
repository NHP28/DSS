"""Quality checks, chronological windows, diagnostics and notebook reporting."""
from __future__ import annotations

import json
import math
import platform
import time
import unicodedata
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import torch


def study_split(events, protocol="global_time"):
    """Keep timestamp ties together; separate warm-user evaluation from fitting."""
    if protocol == "per_user":
        try:
            from poi_model import temporal_split
        except ModuleNotFoundError:
            from ml.poi_model import temporal_split
        train, validation_raw, test_raw = temporal_split(events)
    elif protocol == "global_time":
        a, b = np.quantile(events.ts, [.7, .8], method="lower")
        if a >= b:
            raise ValueError("Need more distinct timestamps for global time windows")
        train = events[events.ts <= a].copy()
        validation_raw = events[(events.ts > a) & (events.ts <= b)].copy()
        test_raw = events[events.ts > b].copy()
        assert train.ts.max() < validation_raw.ts.min() <= validation_raw.ts.max() < test_raw.ts.min()
    else:
        raise ValueError(f"Unsupported protocol: {protocol}")
    fit = pd.concat([train, validation_raw]).sort_values(["user", "ts"], kind="stable")
    validation = validation_raw[validation_raw.user.isin(train.user)].copy()
    test = test_raw[test_raw.user.isin(fit.user)].copy()
    if any(frame.empty for frame in (train, validation, test)):
        raise ValueError("Empty warm-user split; use more users/timestamps")
    metadata = {"name": protocol, "train": len(train), "validation": len(validation), "test": len(test),
        "validation_raw": len(validation_raw), "test_raw": len(test_raw),
        "validation_cold_user_events_excluded": len(validation_raw) - len(validation),
        "test_cold_user_events_excluded": len(test_raw) - len(test),
        "train_end_utc": str(pd.to_datetime(train.ts.max(), unit="s", utc=True)),
        "fit_end_utc": str(pd.to_datetime(fit.ts.max(), unit="s", utc=True)),
        "test_start_utc": str(pd.to_datetime(test.ts.min(), unit="s", utc=True)),
        "catalog_assumption": "Static full catalog; eligibility/core filtering uses the full source (transductive).",
        "history_assumption": "Frozen fit history; test events do not update the graph or seen set."}
    return train, validation, test, fit, metadata


def quality_profile(pois, events, metadata):
    """Report observed coverage, timestamp consistency and declared provenance."""
    counts = events.groupby("item").size().reindex(range(len(pois)), fill_value=0)
    active = pois.l.isin(events.l)
    coverage = pd.DataFrame({"catalog_pois": pois.category.value_counts(),
        "active_pois": pois[active].category.value_counts(),
        "events": events.l.map(pois.set_index("l").category).value_counts()}).fillna(0).astype(int)
    utc = pd.to_datetime(events.ts, unit="s", utc=True)
    if metadata["has_categories"]:
        local = utc.dt.tz_convert(metadata["timezone"])
    else:
        offsets = np.rint(events.l.map(pois.set_index("l").lon).to_numpy() / 15).clip(-12, 12)
        local = pd.Series(pd.to_datetime(events.ts.to_numpy() + offsets * 3600, unit="s", utc=True), index=events.index)
    warnings = []
    for category, row in coverage.iterrows():
        if row.events == 0:
            warnings.append(f"{category}: {row.catalog_pois} catalog POIs, zero interactions; recommendation quality is unverified.")
    if metadata["dataset_id"] == "danang":
        warnings.append("Synthetic interactions/ratings/prices/popularity; results cannot establish real user preference quality.")
    else:
        warnings.extend(["Local time approximated by longitude; timezone boundaries and DST are not modeled.",
                         "Activity core excludes many rare users/POIs; this is not a cold-start benchmark."])
    if metadata.get("is_subset"):
        warnings.append("Random user subset; do not label as the full benchmark.")
    unique_pairs = len(events[["user", "item"]].drop_duplicates())
    result = {"users": int(events.user.nunique()), "pois": len(pois), "events": len(events),
        "missing_required_cells": int(events[["user", "item", "ts", "hour", "day_of_week"]].isna().sum().sum()),
        "duplicate_events": int(events.duplicated(["u", "l", "ts"]).sum()),
        "unreferenced_pois": int((counts == 0).sum()),
        "unique_user_poi_pairs": unique_pairs,
        "sparsity_percent": 100 * (1 - unique_pairs / (events.user.nunique() * len(pois))),
        "repeat_event_percent": 100 * (1 - unique_pairs / len(events)),
        "hour_mismatches": int((local.dt.hour.to_numpy() != events.hour.to_numpy()).sum()),
        "weekday_mismatches": int((local.dt.dayofweek.to_numpy() != events.day_of_week.to_numpy()).sum()),
        "duplicate_coordinate_rows": int(pois.duplicated(["lat", "lon"]).sum()),
        "utc_start": str(utc.min()), "utc_end": str(utc.max()),
        "warnings": warnings, "category_coverage": coverage.to_dict(orient="index"),
        "data_provenance": metadata["data_provenance"], "source_metadata": metadata}
    for key, values in (("user_event_distribution", events.groupby("user").size()), ("poi_event_distribution", counts)):
        result[key] = {label: float(value) if np.isfinite(value) else None
                       for label, value in values.describe().items()}
    ordered = events.join(pois.set_index("l")[["lat", "lon"]], on="l")
    previous_lat = np.radians(ordered.lat.shift().to_numpy())
    previous_lon = np.radians(ordered.lon.shift().to_numpy())
    lat, lon = np.radians(ordered.lat.to_numpy()), np.radians(ordered.lon.to_numpy())
    distance_term = np.sin((lat-previous_lat)/2)**2 + np.cos(lat)*np.cos(previous_lat)*np.sin((lon-previous_lon)/2)**2
    distance = 6371 * 2 * np.arcsin(np.sqrt(np.clip(distance_term, 0, 1)))
    elapsed = ordered.ts.diff().to_numpy()
    same_user = ordered.user.eq(ordered.user.shift()).to_numpy()
    result["movement_flags_over_1000_kmh_and_1_km"] = int((same_user & (elapsed > 0) & (distance > 1)
        & (distance / np.maximum(elapsed, 1) * 3600 > 1000)).sum())
    result["same_timestamp_steps_over_1_km"] = int((same_user & (elapsed == 0) & (distance > 1)).sum())
    if result["movement_flags_over_1000_kmh_and_1_km"] or result["same_timestamp_steps_over_1_km"]:
        warnings.append("Movement diagnostics found implausible-speed or simultaneous-location steps; flags use static catalog coordinates and are not automatic deletion rules.")
    if metadata.get("raw_events") and metadata.get("full_core"):
        result["full_core_raw_event_retention_percent"] = 100 * metadata["full_core"]["events"] / metadata["raw_events"]
    if "district" in pois:
        def normalize(value):
            value = str(value).lower().strip().replace("đ", "d")
            value = "".join(c for c in unicodedata.normalize("NFD", value) if not unicodedata.combining(c))
            for prefix in ("quan ", "huyen "):
                if value.startswith(prefix):
                    value = value[len(prefix):]
            return " ".join(value.split())
        result["district_labels_raw"] = pois.district.value_counts().astype(int).to_dict()
        result["district_labels_normalized"] = pois.district.map(normalize).value_counts().astype(int).to_dict()
        if len(result["district_labels_raw"]) > len(result["district_labels_normalized"]):
            warnings.append("District labels contain spelling/prefix variants; raw values are reported without silently editing the source.")
        if not any(column in pois for column in ("osm_id", "osm_url", "osm_type")):
            warnings.append("Catalog lacks per-row OSM element IDs; source attribution cannot be verified POI by POI from this CSV alone.")
    if result["hour_mismatches"] or result["weekday_mismatches"]:
        raise ValueError("Timestamp and context columns disagree")
    return result


def plot_eda(pois, events, name, output, run_label=""):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(2, 3, figsize=(16, 8), constrained_layout=True)
    events.groupby("user").size().plot.hist(bins=35, ax=axes[0, 0], color="#3b728a", logy=True)
    axes[0, 0].set(title="Events/user", xlabel="Events", ylabel="Users (log)")
    poi_counts = events.groupby("item").size().reindex(range(len(pois)), fill_value=0)
    poi_counts.plot.hist(bins=35, ax=axes[0, 1], color="#bd783f", logy=True)
    axes[0, 1].set(title="Events/POI (including zero)", xlabel="Events", ylabel="POIs (log)")
    active = pois.l.isin(events.l)
    pd.DataFrame({"catalog": pois.category.value_counts(), "with events": pois[active].category.value_counts()}).fillna(0).plot.bar(ax=axes[0, 2], rot=15)
    axes[0, 2].set(title="Category coverage", ylabel="POIs")
    axes[1, 0].scatter(pois.lon, pois.lat, s=2, alpha=.4, color="#3b728a")
    axes[1, 0].set(title="POI coordinates", xlabel="Longitude", ylabel="Latitude")
    heat = pd.crosstab(events.day_of_week, events.hour).reindex(index=range(7), columns=range(24), fill_value=0)
    im = axes[1, 1].imshow(heat / len(events) * 100, aspect="auto", cmap="YlGnBu")
    axes[1, 1].set(title="Weekday x hour", xlabel="Approx. local hour" if name == "gowalla" else "Local hour",
                   yticks=range(7), yticklabels=["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"])
    fig.colorbar(im, ax=axes[1, 1], label="% events", shrink=.7)
    ordered = np.sort(poi_counts.to_numpy())[::-1]
    axes[1, 2].plot(np.arange(1, len(ordered) + 1) / len(ordered), np.cumsum(ordered) / ordered.sum())
    axes[1, 2].plot([0, 1], [0, 1], "--", color="gray")
    axes[1, 2].set(title="Popularity concentration", xlabel="Fraction of POIs (most popular first)", ylabel="Fraction of events")
    fig.suptitle(f"{name}: data quality and EDA | {run_label} | {events.user.nunique():,} users")
    fig.savefig(output / f"{name}_eda.png", dpi=150)
    return fig


def rank_of_target(scores, target):
    """Exact full-catalog rank, resolving equal scores by ascending item ID."""
    value = scores[target]
    if not np.isfinite(value):
        return math.inf
    ids = np.arange(len(scores))
    valid = np.isfinite(scores)
    return 1 + int(np.count_nonzero(valid & ((scores > value) | ((scores == value) & (ids < target)))))


def metrics_from_events(records, scope="novel", ks=(5, 10, 20)):
    selected = records[records.novel] if scope == "novel" else records
    if selected.empty:
        raise ValueError(f"No {scope} events; use a larger dataset/smoke sample")
    ranks = selected[f"rank_{scope}"].to_numpy()
    result = {}
    for k in ks:
        hit = ranks <= k
        result.update({f"HR@{k}": float(hit.mean()),
                       f"NDCG@{k}": float(np.where(hit, 1 / np.log2(ranks + 1), 0).mean()),
                       f"MRR@{k}": float(np.where(hit, 1 / ranks, 0).mean())})
    macro = selected.assign(hit=(ranks <= 10).astype(float)).groupby("user").hit.mean()
    result.update(events=len(selected), users=len(macro), macro_user_HR_at_10=float(macro.mean()),
                  excluded_seen_events=len(records) - len(selected))
    return result


def evaluate_detailed(predict, held_out, seen, n_items, coverage_queries=500, seed=42):
    """Both all-visit and novel-visit ranks from one scoring pass; no sampled negatives."""
    rows, exposed = [], set()
    novel_indices = [i for i, row in enumerate(held_out.itertuples()) if row.item not in seen.get(row.user, set())]
    sample = set(np.random.default_rng(seed).choice(novel_indices, min(coverage_queries, len(novel_indices)), replace=False).tolist())
    for index, row in enumerate(held_out.itertuples()):
        scores = np.array(predict(row), dtype=float, copy=True)
        all_rank = rank_of_target(scores, row.item)
        novel = row.item not in seen.get(row.user, set())
        scores[list(seen.get(row.user, set()))] = -np.inf
        novel_rank = rank_of_target(scores, row.item) if novel else math.inf
        if index in sample:
            finite = np.flatnonzero(np.isfinite(scores))
            if len(finite):
                k = min(10, len(finite))
                threshold = np.partition(scores[finite], -k)[-k]
                candidates = finite[scores[finite] >= threshold]
                exposed.update(candidates[np.lexsort((candidates, -scores[candidates]))[:k]].tolist())
        rows.append({"user": int(row.user), "item": int(row.item), "ts": float(row.ts),
            "hour": int(row.hour), "day_of_week": int(row.day_of_week), "novel": novel,
            "rank_novel": novel_rank, "rank_all": all_rank})
    records = pd.DataFrame(rows)
    novel_metrics = metrics_from_events(records, "novel")
    novel_metrics.update(sample_catalog_coverage_at_10=len(exposed) / n_items,
                         coverage_queries=len(sample))
    return novel_metrics, metrics_from_events(records, "all"), records


def model_predictions(model, frame, batch_size):
    model.eval()
    with torch.inference_mode():
        embeddings = model.embeddings()
    device = model.coords.device
    for start in range(0, len(frame), batch_size):
        batch = frame.iloc[start:start + batch_size]
        context = [torch.as_tensor(batch[c].to_numpy(copy=True), dtype=torch.long, device=device)
                   for c in ("user", "hour", "day_of_week")]
        ts = torch.as_tensor(batch.ts.to_numpy(np.float64, copy=True), device=device)
        with torch.inference_mode():
            scores = model.scores_batch(*context, ts, embeddings).cpu().numpy()
        # Never suspend a generator while a thread-local inference context is active.
        yield from scores


def benchmark_scores(model, frame, batch_size, repeats=10):
    """Cached-embedding batch scoring only: excludes network and graph refresh."""
    batch = frame.iloc[:batch_size]
    device = model.coords.device
    values = [torch.as_tensor(batch[c].to_numpy(copy=True), dtype=torch.long, device=device)
              for c in ("user", "hour", "day_of_week")]
    ts = torch.as_tensor(batch.ts.to_numpy(np.float64, copy=True), device=device)
    def sync():
        if device.type == "cuda":
            torch.cuda.synchronize(device)
    model.eval()
    durations = []
    with torch.inference_mode():
        emb = model.embeddings()
        for _ in range(3):
            model.scores_batch(*values, ts, emb)
        sync()
        for _ in range(repeats):
            start = time.perf_counter()
            model.scores_batch(*values, ts, emb)
            sync()
            durations.append((time.perf_counter() - start) * 1000)
    return {"batch_size": len(batch), "repeats": repeats,
            "cached_scores_batch_ms_p50": float(np.median(durations)),
            "cached_scores_batch_ms_p95": float(np.quantile(durations, .95)),
            "scope": "Cached embeddings, warm batch scoring; excludes CPU transfer, HTTP and graph refresh."}


def model_variants(has_categories, ablation=True):
    variants = {"bpr_mf": (False, False, False), "lightgcn": (False, False, False),
                "tas_gnn": (True, True, has_categories)}
    if ablation:
        variants.update(tas_no_time=(False, True, has_categories), tas_no_space=(True, False, has_categories))
        if has_categories:
            variants["tas_no_category"] = (True, True, False)
    return variants


def run_study(data_dir, output_dir, epochs=20, seed=42, max_users=None, dim=64, layers=3,
              batch_size=1024, eval_batch_size=128, protocol="global_time", ablation=True,
              learning_rate=.001, patience=4, coverage_queries=500, learning_rates=None):
    try:
        from poi_model import (CATEGORIES, FORMAT_VERSION, dataset_metadata, dataset_fingerprints,
                               load_data, seen_items, hourly_counts, fit_model)
    except ModuleNotFoundError:
        from ml.poi_model import (CATEGORIES, FORMAT_VERSION, dataset_metadata, dataset_fingerprints,
                                  load_data, seen_items, hourly_counts, fit_model)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    pois, events, user_ids, poi_ids, fingerprint = load_data(data_dir, max_users)
    metadata = dataset_metadata(data_dir)
    train, validation, test, fit, split_info = study_split(events, protocol)
    seen = seen_items(fit)
    coords = pois[["lat", "lon"]].to_numpy(np.float32)
    categories = pois.category.map(CATEGORIES).fillna(0).to_numpy(np.int64)
    counts = hourly_counts(fit, len(pois))
    device = "cuda" if torch.cuda.is_available() else "cpu"
    if device == "cpu":
        torch.set_num_threads(min(4, torch.get_num_threads()))
    report = {"dataset_id": metadata["dataset_id"], "seed": seed, "device": device,
        "dataset_sha256": fingerprint, "dataset_metadata": metadata, "protocol": split_info,
        "smoke_run": max_users is not None, "is_subset": bool(max_users is not None or metadata.get("is_subset")),
        "hyperparameters": {"epochs_max": epochs, "dim": dim, "layers": layers, "batch_size": batch_size,
                            "learning_rates": list(learning_rates or [learning_rate]), "patience": patience, "selection": "validation novel-event HR@10"},
        "versions": {"python": platform.python_version(), "torch": str(torch.__version__), "numpy": np.__version__, "pandas": pd.__version__},
        "results": {}, "all_event_results": {}, "history": {}, "resources": {}, "model_configs": {}}
    history_sizes = fit.groupby("user").size()
    poi_frequencies = fit.groupby("item").size()
    def save_evaluation(name, predict):
        start = time.perf_counter()
        novel, all_events, records = evaluate_detailed(predict, test, seen, len(pois), coverage_queries)
        report["results"][name], report["all_event_results"][name] = novel, all_events
        report["resources"].setdefault(name, {})["evaluation_seconds"] = time.perf_counter() - start
        records["fit_history"] = records.user.map(history_sizes).fillna(0).astype(int)
        records["poi_fit_events"] = records.item.map(poi_frequencies).fillna(0).astype(int)
        records["category"] = pois.category.to_numpy()[records.item.to_numpy()]
        records.to_csv(output / f"{name}_events.csv", index=False)
    global_counts = counts.sum(0)
    save_evaluation("popularity", lambda row: global_counts)
    save_evaluation("hourly_popularity", lambda row: counts[row.hour])
    # Query location proxy is the last observed fit POI, never the held-out target.
    last_items = fit.sort_values("ts", kind="stable").groupby("user").item.last()
    geo_cache = {}
    def geo_predict(row):
        origin = int(last_items[row.user])
        if origin not in geo_cache:
            if len(geo_cache) >= 128:
                geo_cache.pop(next(iter(geo_cache)))
            lat1, lon1 = np.radians(coords[origin])
            lat2, lon2 = np.radians(coords).T
            a = np.sin((lat2-lat1)/2)**2 + np.cos(lat1)*np.cos(lat2)*np.sin((lon2-lon1)/2)**2
            distance = 6371 * 2 * np.arcsin(np.sqrt(np.clip(a, 0, 1)))
            geo_cache[origin] = 1 + distance / 5.0
        return counts[row.hour] / geo_cache[origin]
    if protocol == "global_time":
        save_evaluation("geo_hourly", geo_predict)
    for name, (temporal, spatial, category_features) in model_variants(bool(metadata["has_categories"]), ablation).items():
        config = dict(n_users=len(user_ids), dim=dim, layers=0 if name == "bpr_mf" else layers,
                      temporal=temporal, spatial=spatial, category_features=category_features)
        report["model_configs"][name] = config
        if device == "cuda":
            torch.cuda.reset_peak_memory_stats()
        print(f"{metadata['dataset_id']} seed={seed}: tuning {name}", flush=True)
        start = time.perf_counter()
        candidates = []
        for lr in learning_rates or [learning_rate]:
            tuned, chosen, history = fit_model(config, coords, categories, train, epochs, seed, device,
                validation=validation, patience=patience, batch_size=batch_size,
                eval_batch_size=eval_batch_size, lr=lr)
            del tuned
            candidates.append({"learning_rate": lr, "selected_epoch": chosen, "history": history,
                               "best_validation_HR10": max(row["validation_HR@10"] for row in history)})
        selected = max(candidates, key=lambda value: value["best_validation_HR10"])
        chosen, history, selected_lr = selected["selected_epoch"], selected["history"], selected["learning_rate"]
        model, _, refit_history = fit_model(config, coords, categories, fit, chosen, seed, device,
                                           batch_size=batch_size, lr=selected_lr)
        report["resources"][name] = {"train_tune_refit_seconds": time.perf_counter() - start,
            "parameters": sum(parameter.numel() for parameter in model.parameters()),
            "peak_cuda_allocated_mib": torch.cuda.max_memory_allocated() / 1024**2 if device == "cuda" else None}
        report["history"][name] = {"selected_epoch": chosen, "selected_learning_rate": selected_lr,
                                  "validation": history, "refit": refit_history, "tuning_candidates": candidates}
        iterator = model_predictions(model, test, eval_batch_size)
        save_evaluation(name, lambda row: next(iterator))
        report["resources"][name].update(benchmark_scores(model, test, eval_batch_size))
        bundle = {"format_version": FORMAT_VERSION, "model_name": name, "model_config": config,
            "state_dict": {key: value.cpu() for key, value in model.state_dict().items()},
            "fit_pairs": torch.as_tensor(fit[["user", "item"]].to_numpy(copy=True), dtype=torch.long),
            "hourly_counts": torch.from_numpy(counts), "user_ids": user_ids, "poi_ids": poi_ids,
            "trained_user_ids": [user_ids[int(u)] for u in sorted(fit.user.unique())],
            "dataset_sha256": fingerprint, "dataset_sha256_aliases": dataset_fingerprints(data_dir)[1],
            "dataset_id": metadata["dataset_id"], "dataset_metadata": metadata, "timezone": metadata["timezone"],
            "seed": seed, "selected_epoch": chosen, "smoke_run": max_users is not None, "protocol": split_info}
        torch.save(bundle, output / f"{name}.pt")
        report["resources"][name]["checkpoint_mib"] = (output / f"{name}.pt").stat().st_size / 1024**2
        del model
    (output / "metrics.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    pd.DataFrame(report["results"]).T.to_csv(output / "comparison.csv")
    return report


def paired_user_bootstrap(experiments, samples=2000, seed=2026):
    """Average seeds per user first; paired resampling estimates user uncertainty."""
    per_user = []
    for path, report in experiments:
        for model in report["results"]:
            frame = pd.read_csv(Path(path) / f"{model}_events.csv", usecols=["user", "novel", "rank_novel"])
            frame = frame[frame.novel]
            user = frame.assign(hit=(frame.rank_novel <= 10).astype(float)).groupby("user").hit.mean()
            per_user.append(user.rename("HR@10").reset_index().assign(model=model, seed=report["seed"]))
    user_table = pd.concat(per_user, ignore_index=True).groupby(["user", "model"])["HR@10"].mean().unstack("model")
    rows = []
    rng = np.random.default_rng(seed)
    for model in user_table.columns:
        if model == "tas_gnn":
            continue
        pair = user_table[["tas_gnn", model]].dropna()
        differences = (pair.tas_gnn - pair[model]).to_numpy()
        if len(differences) < 2:
            continue
        bootstrap = np.array([rng.choice(differences, len(differences), replace=True).mean() for _ in range(samples)])
        lo, hi = np.quantile(bootstrap, [.025, .975])
        rows.append({"reference": model, "users": len(pair), "macro_user_HR10_difference": differences.mean(),
                     "ci95_low": lo, "ci95_high": hi, "resamples": samples})
    return pd.DataFrame(rows)


def plot_study(reports, name, output):
    label = "SMOKE: technical check" if any(report["smoke_run"] for report in reports) else (
        "USER SUBSET" if any(report["is_subset"] for report in reports) else "FULL PROCESSED DATA")
    rows = [{"seed": report["seed"], "model": model, **metrics}
            for report in reports for model, metrics in report["results"].items()]
    frame = pd.DataFrame(rows)
    grouped = frame.groupby("model")
    metrics = ["HR@5", "HR@10", "HR@20", "NDCG@10", "MRR@10"]
    means, stds = grouped[metrics].mean(), grouped[metrics].std()
    fig, axes = plt.subplots(1, 2, figsize=(17, 5), constrained_layout=True)
    means[["HR@10", "NDCG@10"]].plot.bar(yerr=stds[["HR@10", "NDCG@10"]].fillna(0), ax=axes[0], rot=35, capsize=3)
    axes[0].set(title="Mean across seeds; error bars = seed std" if len(reports) > 1 else "Single seed; uncertainty not estimated", ylabel="Score")
    im = axes[1].imshow(means[metrics], cmap="YlGnBu", aspect="auto", vmin=0, vmax=max(.01, means[metrics].to_numpy().max()))
    axes[1].set(xticks=range(len(metrics)), xticklabels=metrics, yticks=range(len(means)), yticklabels=means.index, title="Model x ranking metric (seed mean)")
    for r in range(len(means)):
        for c in range(len(metrics)):
            axes[1].text(c, r, f"{means.iloc[r,c]:.3f}", ha="center", va="center", fontsize=8)
    fig.colorbar(im, ax=axes[1], shrink=.7)
    fig.suptitle(f"{name} | {label} | novel warm-user events | {len(reports)} seeds")
    fig.savefig(Path(output) / f"{name}_comparison.png", dpi=150)
    curves, ax = plt.subplots(1, 2, figsize=(15, 4), constrained_layout=True)
    for model, values in reports[0]["history"].items():
        history = pd.DataFrame(values["validation"])
        ax[0].plot(history.epoch, history.loss, marker=".", label=model)
        ax[1].plot(history.epoch, history["validation_HR@10"], marker=".", label=model)
        chosen = history[history.epoch == values["selected_epoch"]].iloc[0]
        ax[1].scatter([chosen.epoch], [chosen["validation_HR@10"]], s=70, facecolors="none", edgecolors="black")
    ax[0].set(title=f"{name}: training loss, seed {reports[0]['seed']}", xlabel="Epoch", ylabel="BPR loss")
    ax[1].set(title="Validation HR@10; circles = selected epochs", xlabel="Epoch", ylabel="HR@10")
    ax[1].legend(fontsize=8)
    curves.suptitle(label)
    curves.savefig(Path(output) / f"{name}_learning_curves.png", dpi=150)
    return frame, [fig, curves]


def error_slices(path, report, output):
    """Descriptive first-seed slices; no hyperparameter selection from test."""
    frames = []
    example = None
    for model in ("hourly_popularity", "lightgcn", "tas_gnn"):
        frame = pd.read_csv(Path(path) / f"{model}_events.csv")
        frame = frame[frame.novel].copy()
        frame["hit"] = (frame.rank_novel <= 10).astype(float)
        frame["history_group"] = pd.cut(frame.fit_history, [0, 5, 20, 50, np.inf], labels=["1-5", "6-20", "21-50", "51+"])
        frame["poi_group"] = pd.cut(frame.poi_fit_events, [-1, 0, 10, 50, np.inf], labels=["unseen", "1-10", "11-50", "51+"])
        for column in ("hour", "category", "history_group", "poi_group"):
            table = frame.groupby(column, observed=True).agg(events=("hit", "size"), HR10=("hit", "mean")).reset_index()
            table = table.rename(columns={column: "group"}).assign(slice=column, model=model)
            frames.append(table)
        if model == "tas_gnn":
            example = pd.concat([frame[frame.hit == 1].head(3), frame[frame.hit == 0].head(3)])
    result = pd.concat(frames, ignore_index=True)
    result.to_csv(Path(output) / f"{report['dataset_id']}_error_slices.csv", index=False)
    fig, axes = plt.subplots(1, 2, figsize=(15, 4), constrained_layout=True)
    for ax, column in zip(axes, ("hour", "poi_group")):
        table = result[result.slice == column].pivot(index="group", columns="model", values="HR10")
        table.plot.bar(ax=ax, rot=0)
        ax.set(title=f"Novel HR@10 by {column}; seed {report['seed']}", ylabel="HR@10")
    fig.suptitle("SMOKE: technical check" if report["smoke_run"] else "Descriptive first-seed slices")
    fig.savefig(Path(output) / f"{report['dataset_id']}_error_slices.png", dpi=150)
    return result, example, fig
