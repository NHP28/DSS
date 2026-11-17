"""Resolve the explicitly activated local Colab export for both demo APIs."""
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ACTIVE_CONFIG = ROOT / "outputs" / "active_artifact.json"


def active_artifact():
    if ACTIVE_CONFIG.is_file():
        return json.loads(ACTIVE_CONFIG.read_text(encoding="utf-8"))
    return {}


def serving_model_path():
    configured = os.getenv("MODEL_PATH")
    path = configured or active_artifact().get("modelPath", "outputs/colab/tas_gnn.pt")
    return ROOT / path


def model_metadata(bundle):
    return {"runId": bundle.get("run_id"), "seed": bundle.get("seed"),
            "selectedEpoch": bundle.get("selected_epoch"),
            "protocol": bundle.get("protocol"),
            "trainedUsers": len(bundle.get("trained_user_ids", bundle.get("user_ids", []))),
            "pois": len(bundle.get("poi_ids", []))}
