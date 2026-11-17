"""Measure the actual datasets and notebook protocol without retraining models."""
from __future__ import annotations

import hashlib
import json
import sys
import unicodedata
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ml.poi_model import dataset_fingerprints, dataset_metadata, load_data, temporal_split
from ml.datasets import DANANG_SHA256, GOWALLA_SHA256
from ml.experiment_analysis import study_split, quality_profile


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def distribution(values):
    values = np.asarray(values, dtype=float)
    return {name: float(value) for name, value in zip(
        ("min", "p25", "median", "p75", "p90", "p95", "p99", "max"),
        np.quantile(values, (0, .25, .5, .75, .9, .95, .99, 1)))}


def normal_label(value):
    value = str(value).lower().strip().replace("đ", "d")
    value = "".join(c for c in unicodedata.normalize("NFD", value)
                    if not unicodedata.combining(c))
    for prefix in ("quan ", "huyen "):
        if value.startswith(prefix):
            value = value[len(prefix):]
    return " ".join(value.split())


def haversine(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(np.radians, (lat1, lon1, lat2, lon2))
    a = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    return 6371 * 2 * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


def audit_dataset(directory):
    metadata = dataset_metadata(directory)
    raw_pois = pd.read_csv(directory / metadata["poi_file"])
    raw_events = pd.read_csv(directory / metadata["event_file"])
    pois, events, users, items, fingerprint = load_data(directory)
    print(f"Loaded {metadata['dataset_id']}: {len(events):,} events", flush=True)
    user_counts = events.groupby("u").size()
    item_counts = events.groupby("l").size().reindex(pois.l, fill_value=0)
    event_categories = events.l.map(pois.set_index("l").category)
    pair_counts = events.groupby(["u", "l"]).size()
    user_pois = events.groupby("u").l.nunique()
    poi_users = events.groupby("l").u.nunique().reindex(pois.l, fill_value=0)
    item_times = events.groupby("l").ts.min()
    train, validation, test = temporal_split(events)
    fit = pd.concat([train, validation], ignore_index=True)
    fit_pairs = pd.MultiIndex.from_frame(fit[["user", "item"]].drop_duplicates())
    test_pairs = pd.MultiIndex.from_frame(test[["user", "item"]])
    excluded = test_pairs.isin(fit_pairs)
    validation_seen = pd.MultiIndex.from_frame(validation[["user", "item"]]).isin(
        pd.MultiIndex.from_frame(train[["user", "item"]].drop_duplicates()))
    fit_first_edges = np.sort(fit.groupby(["user", "item"]).ts.min().to_numpy())
    later_edges = len(fit_first_edges) - np.searchsorted(fit_first_edges, test.ts, side="right")
    fit_item_first = fit.groupby("item").ts.min()
    time = pd.to_datetime(events.ts, unit="s", utc=True)
    if metadata["dataset_id"] == "danang":
        local = time.dt.tz_convert("Asia/Ho_Chi_Minh")
    else:
        offsets = np.rint(events.l.map(pois.set_index("l").lon).to_numpy() / 15).clip(-12, 12)
        local = pd.to_datetime(events.ts.to_numpy() + offsets * 3600, unit="s", utc=True)
        local = pd.Series(local, index=events.index)
    ordered = events.join(pois.set_index("l")[["lat", "lon"]], on="l")
    same_user = ordered.user.eq(ordered.user.shift()).to_numpy()
    delta = ordered.ts.diff().to_numpy()
    distance = haversine(ordered.lat.shift().to_numpy(), ordered.lon.shift().to_numpy(),
                         ordered.lat.to_numpy(), ordered.lon.to_numpy())
    usable_steps = same_user & (delta > 0)
    flagged_steps = usable_steps & (distance > 1) & (distance / np.maximum(delta, 1) * 3600 > 1000)
    unique_edges = len(pair_counts)
    top_n = max(1, int(np.ceil(len(pois) * .01)))
    cutoffs = train.groupby("user").ts.max().to_frame("train_end")
    cutoffs["validation_start"] = validation.groupby("user").ts.min()
    cutoffs["validation_end"] = validation.groupby("user").ts.max()
    cutoffs["test_start"] = test.groupby("user").ts.min()
    report = {
        "directory": str(directory.relative_to(ROOT)), "metadata": metadata,
        "fingerprint": fingerprint,
        "files": {name: {"bytes": (directory / name).stat().st_size,
                          "sha256": sha256(directory / name)}
                  for name in (metadata["poi_file"], metadata["event_file"])},
        "raw_csv": {
            "pois": len(raw_pois), "events": len(raw_events),
            "missing_poi_cells": raw_pois.isna().sum().astype(int).to_dict(),
            "missing_event_cells": raw_events.isna().sum().astype(int).to_dict(),
            "duplicate_poi_ids": int(raw_pois.l.duplicated().sum()),
            "duplicate_events_u_l_ts": int(raw_events.duplicated(["u", "l", "ts"]).sum()),
            "unknown_poi_references": int((~raw_events.l.isin(raw_pois.l)).sum()),
            "invalid_coordinates": int((~np.isfinite(raw_pois[["lat", "lon"]]).all(axis=1)
                                          | ~raw_pois.lat.between(-90, 90)
                                          | ~raw_pois.lon.between(-180, 180)).sum()),
        },
        "loaded": {
            "users": len(users), "pois": len(items), "events": len(events),
            "events_removed_by_load_data": len(raw_events) - len(events),
            "unique_user_poi_pairs": unique_edges,
            "interaction_density_percent": 100 * unique_edges / (len(users) * len(items)),
            "sparsity_percent": 100 * (1 - unique_edges / (len(users) * len(items))),
            "repeat_event_percent": 100 * (len(events) - unique_edges) / len(events),
            "catalog_pois_without_events": int((item_counts == 0).sum()),
            "events_per_user": distribution(user_counts),
            "unique_pois_per_user": distribution(user_pois),
            "events_per_poi": distribution(item_counts),
            "users_per_poi": distribution(poi_users),
            "top_1_percent_pois_event_share_percent": 100 * float(item_counts.nlargest(top_n).sum()) / len(events),
            "category_counts": pois.category.value_counts().astype(int).to_dict(),
            "category_event_counts": event_categories.value_counts().astype(int).to_dict(),
            "category_pois_with_events": pois[pois.l.isin(events.l)].category.value_counts().astype(int).to_dict(),
            "utc_start": str(time.min()), "utc_end": str(time.max()),
            "local_hour_mismatches": int((local.dt.hour.to_numpy() != events.hour.to_numpy()).sum()),
            "local_weekday_mismatches": int((local.dt.dayofweek.to_numpy() != events.day_of_week.to_numpy()).sum()),
            "timestamp_seconds_all_zero": bool((events.ts % 60 == 0).all()),
            "events_in_shared_user_timestamp_groups": int(events.duplicated(["u", "ts"], keep=False).sum()),
            "shared_user_timestamp_groups": int((events.groupby(["u", "ts"]).size() > 1).sum()),
            "consecutive_steps": int(usable_steps.sum()),
            "steps_over_1000_kmh_and_1_km": int(flagged_steps.sum()),
            "same_timestamp_steps_over_1_km": int((same_user & (delta == 0) & (distance > 1)).sum()),
            "movement_note": "Diagnostic flags from static catalog coordinates; not proof of invalid events or an automatic removal rule.",
            "duplicate_coordinate_rows": int(pois.duplicated(["lat", "lon"]).sum()),
        },
        "protocol": {
            "name": "legacy_per_user",
            "train": len(train), "validation": len(validation), "test": len(test),
            "split_percentages": [100 * len(frame) / len(events) for frame in (train, validation, test)],
            "users_violating_own_temporal_order": int(((cutoffs.train_end >= cutoffs.validation_start)
                                                       | (cutoffs.validation_end >= cutoffs.test_start)).sum()),
            "validation_novel_events": int((~validation_seen).sum()),
            "validation_users_without_novel_events": len(users) - int(validation.loc[~validation_seen, "user"].nunique()),
            "test_novel_events": int((~excluded).sum()),
            "test_excluded_seen_events": int(excluded.sum()),
            "test_excluded_seen_percent": 100 * float(excluded.mean()),
            "test_users_without_novel_events": len(users) - int(test.loc[~excluded, "user"].nunique()),
            "catalog_pois_unseen_in_train": len(items) - int(train.item.nunique()),
            "catalog_pois_unseen_in_fit": len(items) - int(fit.item.nunique()),
            "test_events_with_pois_unseen_in_fit": int((~test.item.isin(fit.item)).sum()),
            "test_events_with_target_first_fit_observation_after_query": int((test.item.isin(fit_item_first.index).to_numpy()
                & (test.ts.to_numpy() < test.item.map(fit_item_first).to_numpy())).sum()),
            "test_events_with_any_future_first_observed_fit_edge_percent": 100 * float((later_edges > 0).mean()),
            "mean_fraction_fit_edges_first_observed_after_test_query_percent": 100 * float(np.mean(later_edges / len(fit_first_edges))),
            "temporal_overlap_note": "Measures graph edge availability relative to each query; does not measure accuracy inflation.",
        },
    }
    if "datetime" in events:
        parsed = pd.to_datetime(events["datetime"], errors="coerce")
        report["loaded"]["datetime_string_vs_local_timestamp_mismatches"] = int((parsed != local.dt.tz_localize(None)).sum())
    if "district" in pois:
        report["loaded"]["district_labels"] = pois.district.value_counts().astype(int).to_dict()
        report["loaded"]["normalized_district_labels"] = pois.district.map(normal_label).value_counts().astype(int).to_dict()
        report["loaded"]["duplicate_normalized_name_coordinate_rows"] = int(pois.assign(
            normalized_name=pois.name.map(normal_label)).duplicated(["normalized_name", "lat", "lon"]).sum())
        report["loaded"]["optional_numeric_ranges"] = {
            column: {"min": float(pois[column].min()), "max": float(pois[column].max()),
                     "unique": int(pois[column].nunique())}
            for column in ("rating", "user_ratings_total", "price_avg", "popularity") if column in pois}
        _, cache_aliases = dataset_fingerprints(directory)
        _, checkout_aliases = dataset_fingerprints(ROOT / "data/danang")
        report["checkout_matches_cached_csv_ignoring_line_endings"] = cache_aliases == checkout_aliases
        previous_report = json.loads((ROOT / "docs/experiments/seed42_cpu.json").read_text(encoding="utf-8"))
        report["previous_full_run_fingerprint"] = previous_report["dataset_sha256"]
        report["previous_full_run_fingerprint_matches_current_aliases"] = previous_report["dataset_sha256"] in cache_aliases
        report["pinned_download_checksums_match"] = {
            filename: sha256(directory / filename) == checksum for filename, checksum in DANANG_SHA256.items()}
    gtrain, gvalidation, gtest, gfit, global_info = study_split(events)
    repeated = pd.MultiIndex.from_frame(gtest[["user", "item"]]).isin(
        pd.MultiIndex.from_frame(gfit[["user", "item"]].drop_duplicates()))
    global_info.update(novel_test_events=int((~repeated).sum()), repeated_test_events=int(repeated.sum()),
                       repeated_test_percent=float(repeated.mean() * 100))
    report["global_time_protocol"] = global_info
    report["upgraded_quality_profile"] = quality_profile(pois, events, metadata)
    return report, {"user_counts": user_counts, "item_counts": item_counts,
                    "hour_weekday": pd.crosstab(events.day_of_week, events.hour).reindex(index=range(7), columns=range(24), fill_value=0)}


def audit_raw_gowalla(path):
    result = {"rows": 0, "invalid_time": 0, "invalid_coordinates": 0,
              "negative_ids": 0, "invalid_any": 0, "null_cells": 0}
    users, pois = set(), set()
    extremes = []
    for index, chunk in enumerate(pd.read_csv(path, sep="\t", header=None,
            names=["u", "time", "lat", "lon", "l"], chunksize=500_000)):
        timestamps = pd.to_datetime(chunk.time, utc=True, errors="coerce")
        invalid_time = timestamps.isna()
        invalid_coords = ~np.isfinite(chunk[["lat", "lon"]]).all(axis=1) | ~chunk.lat.between(-90, 90) | ~chunk.lon.between(-180, 180)
        negative_ids = (chunk.u < 0) | (chunk.l < 0)
        result["rows"] += len(chunk)
        result["invalid_time"] += int(invalid_time.sum())
        result["invalid_coordinates"] += int(invalid_coords.sum())
        result["negative_ids"] += int(negative_ids.sum())
        result["invalid_any"] += int((invalid_time | invalid_coords | negative_ids).sum())
        result["null_cells"] += int(chunk.isna().sum().sum())
        users.update(chunk.u.unique().tolist())
        pois.update(chunk.l.unique().tolist())
        valid = chunk[~invalid_coords]
        extremes.append(valid.groupby("l").agg(lat_min=("lat", "min"), lat_max=("lat", "max"),
                                               lon_min=("lon", "min"), lon_max=("lon", "max")))
        print(f"Audited raw Gowalla chunk {index + 1}: {result['rows']:,} rows", flush=True)
    result.update(users=len(users), pois=len(pois), sha256=sha256(path))
    extrema = pd.concat(extremes).groupby(level=0).agg({"lat_min":"min", "lat_max":"max", "lon_min":"min", "lon_max":"max"})
    diagonal = haversine(extrema.lat_min.to_numpy(), extrema.lon_min.to_numpy(),
                         extrema.lat_max.to_numpy(), extrema.lon_max.to_numpy())
    result["poi_coordinate_bbox_diagonal_over_1_km"] = int((diagonal > 1).sum())
    result["poi_coordinate_bbox_diagonal_km"] = distribution(diagonal)
    result["coordinate_note"] = "Bounding-box diagonal is a screening statistic; not an actual observed movement."
    return result


def plot_comparison(plot_data, destination):
    fig, axes = plt.subplots(2, 3, figsize=(16, 8.5), constrained_layout=True)
    for row, (name, data) in enumerate(plot_data.items()):
        axes[row, 0].hist(data["user_counts"], bins=40, color="#376b89")
        axes[row, 0].set(xlabel="Events per user", ylabel="Users", yscale="log", title=f"{name}: user activity (log y)")
        counts = np.sort(data["item_counts"].to_numpy())[::-1]
        axes[row, 1].plot(np.arange(1, len(counts) + 1) / len(counts) * 100, np.cumsum(counts) / counts.sum() * 100, color="#b6642d")
        axes[row, 1].plot([0, 100], [0, 100], color="gray", linestyle="--", linewidth=.8)
        axes[row, 1].set(xlabel="POIs ordered by popularity (%)", ylabel="Cumulative events (%)", title=f"{name}: interaction concentration")
        values = data["hour_weekday"].to_numpy()
        normalized = values / values.sum() * 100
        im = axes[row, 2].imshow(normalized, aspect="auto", cmap="YlGnBu")
        axes[row, 2].set(xlabel="Local hour", yticks=range(7), yticklabels=["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"], title=f"{name}: weekday x hour (% events)")
        fig.colorbar(im, ax=axes[row, 2], label="Share of events (%)", shrink=.85)
    fig.suptitle("Dataset quality audit: full processed data, before model training", fontsize=15)
    destination.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(destination, dpi=160)
    plt.close(fig)


def main():
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8")
    report = {"audit_date_local": "2026-11-11", "method": "Full CSV quality audit; legacy per-user diagnostics retained for comparison. Updated notebook defaults to global_time. No model retraining in this audit.", "datasets": {}}
    plot_data = {}
    directories = {"danang": ROOT / "outputs/datasets/datasets/danang",
                   "gowalla": ROOT / "outputs/datasets/datasets/gowalla_full"}
    for name, directory in directories.items():
        report["datasets"][name], plot_data[name] = audit_dataset(directory)
    report["raw_gowalla"] = audit_raw_gowalla(ROOT / "outputs/datasets/downloads/loc-gowalla_totalCheckins.txt.gz")
    report["raw_gowalla"]["matches_pinned_sha256"] = report["raw_gowalla"]["sha256"] == GOWALLA_SHA256
    raw = report["raw_gowalla"]
    processed = report["datasets"]["gowalla"]["loaded"]
    report["gowalla_retention_percent"] = {
        key: 100 * processed[key] / (raw["rows"] if key == "events" else raw[key])
        for key in ("users", "pois", "events")}
    for name, data in report["datasets"].items():
        expected = data["metadata"].get("processed_sha256", {})
        data["processed_checksums_match_metadata"] = {file: data["files"][file]["sha256"] == checksum for file, checksum in expected.items()}
    notebook = json.loads((ROOT / "notebooks/DSS_POI_Colab.ipynb").read_text(encoding="utf-8"))
    report["notebook"] = {"cells": len(notebook["cells"]), "code_cells": sum(c["cell_type"] == "code" for c in notebook["cells"]),
        "executed_cells_saved": sum(c.get("execution_count") is not None for c in notebook["cells"]),
        "saved_output_count": sum(len(c.get("outputs", [])) for c in notebook["cells"])}
    destination = ROOT / "docs/experiments/dataset_quality_audit.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    plot_comparison(plot_data, ROOT / "outputs/figures/dataset_quality_audit.png")
    print(f"Saved {destination}", flush=True)
    for name, data in report["datasets"].items():
        print(name, json.dumps({"loaded": data["loaded"], "protocol": data["protocol"]}, ensure_ascii=False))
    print("Gowalla retention (%)", report["gowalla_retention_percent"])


if __name__ == "__main__":
    main()
