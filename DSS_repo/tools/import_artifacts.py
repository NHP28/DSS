"""Verify a full Colab ZIP, activate its Da Nang models and export FE reports."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import statistics
import sys
from pathlib import Path
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd
import torch

from ml.artifacts import ACTIVE_CONFIG
from ml.poi_model import dataset_fingerprints, restore_bundle

# This export kept format_version=1 despite changing the spatial embeddings.
# Identify its reviewed runtime explicitly instead of guessing from tensor shapes.
SUPPORTED_RUNTIME = "10bf03cd1160445afbf5f6bdc33f4a228ac4f7e8e1e04a46c209b863a6aa6cd5"


def sha256(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def checked_path(root, name):
    path = (root / name).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError(f"Path outside artifact directory: {name}")
    return path


def write_json(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def training_summary(folder, config, run_id):
    quality = json.loads((folder / "dataset_quality.json").read_text(encoding="utf-8"))
    splits = json.loads((folder / "split_audit.json").read_text(encoding="utf-8"))
    datasets = []
    for name in config["datasets"]:
        reports = [json.loads(path.read_text(encoding="utf-8")) for path in
                   [folder / name / "metrics.json", *sorted((folder / name).glob("seed_*/metrics.json"))]]
        if sorted(report["seed"] for report in reports) != sorted(config["seeds"]):
            raise ValueError(f"Incomplete seed reports: {name}")
        models = []
        for model in reports[0]["results"]:
            metrics = {}
            for metric in ("HR@10", "NDCG@10", "MRR@10"):
                values = [report["results"][model][metric] for report in reports]
                metrics[metric] = {"mean": statistics.mean(values),
                                   "std": statistics.stdev(values) if len(values) > 1 else 0}
            models.append({"name": model, "metrics": metrics})
        datasets.append({"id": name, "users": quality[name]["users"],
                         "pois": quality[name]["pois"], "events": quality[name]["events"],
                         "split": splits[name], "models": sorted(models, key=lambda m: -m["metrics"]["HR@10"]["mean"]),
                         "categoryCoverage": quality[name].get("category_coverage", {})})
    return {"runId": run_id, "runMode": config["run_mode"], "protocol": config["protocol"],
            "seeds": config["seeds"], "servingDataset": "danang", "servingModel": "tas_gnn",
            "servingSeed": 42, "datasets": datasets}


def import_artifacts(archive_path):
    archive_path = Path(archive_path).resolve()
    run_id = archive_path.stem.removesuffix("_artifacts")
    folder = ROOT / "outputs" / "imported" / run_id
    with ZipFile(archive_path) as archive:
        for member in archive.infolist():
            checked_path(folder, member.filename)
        archive.extractall(folder)
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    for name, expected in manifest.items():
        if sha256(checked_path(folder, name)) != expected:
            raise ValueError(f"SHA256 mismatch: {name}")
    if sha256(folder / "poi_model.py") != SUPPORTED_RUNTIME:
        raise ValueError("Unknown Colab model runtime; add a compatible versioned loader before activation")
    config = json.loads((folder / "experiment_config.json").read_text(encoding="utf-8"))
    if config["protocol"] != "global_time" or config["run_mode"] != "full":
        raise ValueError("Expected a full global_time export")

    data_dir = ROOT / "data" / "danang"
    raw, aliases = dataset_fingerprints(data_dir)
    catalog = pd.read_csv(data_dir / "danang_pois_full.csv").sort_values("l").l.tolist()
    destination = folder / "serving" / "danang"
    destination.mkdir(parents=True, exist_ok=True)
    torch.set_num_threads(min(4, torch.get_num_threads()))
    for name in ("tas_gnn", "lightgcn"):
        bundle = torch.load(folder / "danang" / f"{name}.pt", map_location="cpu", weights_only=True)
        expected = {bundle["dataset_sha256"], *bundle.get("dataset_sha256_aliases", [])}
        if bundle["dataset_id"] != "danang" or bundle["poi_ids"] != catalog or not expected.intersection([raw, *aliases]):
            raise ValueError("Artifact does not match the local Da Nang dataset/catalog")
        if bundle["seed"] != 42 or bundle.get("smoke_run"):
            raise ValueError("Serving requires the full, preselected seed 42 models")
        bundle.update(model_architecture="spatial_history_v2", run_id=run_id,
                      dataset_sha256_aliases=sorted(expected | {raw, *aliases}))
        path = destination / f"{name}.pt"
        temporary = path.with_suffix(".pt.tmp")
        torch.save(bundle, temporary)
        model, _ = restore_bundle(temporary)
        with torch.inference_mode():
            predictions = model.scores(0, 8, 0, 0)
        if predictions.shape != (len(catalog),) or not torch.isfinite(predictions).all():
            raise ValueError(f"Invalid model predictions: {name}")
        temporary.replace(path)

    summary = training_summary(folder, config, run_id)
    public = ROOT / "FE" / "public" / "artifacts" / run_id
    public.mkdir(parents=True, exist_ok=True)
    for name in ("research_summary.md", "all_datasets_comparison.csv", "multi_seed_summary.csv",
                 "danang_comparison.png", "danang_learning_curves.png", "danang_eda.png",
                 "gowalla_comparison.png", "gowalla_learning_curves.png", "gowalla_eda.png"):
        shutil.copy2(folder / name, public / name)
    summary.update(assetBase=f"/artifacts/{run_id}", verifiedFiles=len(manifest))
    write_json(public.parent / "training-summary.json", summary)
    active = {"runId": run_id, "modelPath": (destination / "tas_gnn.pt").relative_to(ROOT).as_posix(),
              "lightgcnPath": (destination / "lightgcn.pt").relative_to(ROOT).as_posix(),
              "archiveSha256": sha256(archive_path), "verifiedFiles": len(manifest)}
    write_json(ACTIVE_CONFIG, active)
    return active


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    args = parser.parse_args()
    print(json.dumps(import_artifacts(args.archive), ensure_ascii=True, indent=2))
