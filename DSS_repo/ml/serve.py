"""Internal inference HTTP service. NestJS owns catalog, filters, DSS and persistence.

Model source, in priority order: MODEL_PATH, outputs/active_artifact.json (imported Colab
export), then the checkpoints that ship in outputs/checkpoints.
"""
import os
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Literal
from zoneinfo import ZoneInfo

import numpy as np
import torch
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from ml.artifacts import ROOT, active_artifact, model_metadata, serving_model_path
from ml.poi_model import restore_bundle
from ml.repo_models import MIN_FOLDIN_HISTORY, load_repo_models

state = {}


@asynccontextmanager
async def lifespan(app):
    torch.set_num_threads(min(4, torch.get_num_threads()))
    path = serving_model_path()
    if (os.getenv("MODEL_PATH") or active_artifact()) and path.is_file():
        model, bundle = restore_bundle(path)
        with torch.inference_mode():
            embeddings = model.embeddings()
        trained_users = set(bundle.get("trained_user_ids", bundle["user_ids"]))
        state.update(model=model, bundle=bundle, embeddings=embeddings,
                     users={u: i for i, u in enumerate(bundle["user_ids"]) if u in trained_users})
    else:
        repo = load_repo_models(ROOT)
        if repo is not None:
            state.update(repo=repo)
    yield
    state.clear()


app = FastAPI(title="DSS internal model inference", lifespan=lifespan)


class ScoreRequest(BaseModel):
    userId: int | None = Field(default=None, ge=0)
    hour: int = Field(default=8, ge=0, le=23)
    dayOfWeek: int = Field(default=0, ge=0, le=6)
    model: Literal["tas_gnn", "lightgcn", "hourly_popularity", "popularity"] = "tas_gnn"
    useTime: bool = True
    historyPoiIds: list[int] | None = Field(default=None, max_length=500)


def now():
    return datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).timestamp()


def normalized(values):
    values = np.asarray(values, dtype=float)
    return (values - values.min()) / max(float(np.ptp(values)), 1e-9)


@app.get("/health")
def health():
    if "repo" in state:
        repo = state["repo"]
        return {"ready": True, "model": "tas_gnn", "models": repo.available, "origin": repo.origin,
                "info": repo.info, "smokeRun": False,
                "artifact": {"runId": "repo_checkpoint", "seed": None, "selectedEpoch": None, "protocol": "per_user_80_20",
                             "trainedUsers": len(repo.user_ids), "pois": len(repo.poi_ids)}}
    bundle = state.get("bundle", {})
    return {"ready": bool(state), "model": bundle.get("model_name"),
            "models": [bundle["model_name"]] if state else [], "origin": "colab_artifact" if state else None,
            "info": {"embeddingDim": bundle["model_config"].get("dim"), "layers": bundle["model_config"].get("layers")} if state else None,
            "artifact": model_metadata(bundle) if state else None,
            "smokeRun": bundle.get("smoke_run", False)}


def score_repo(request: ScoreRequest):
    repo = state["repo"]
    history = [p for p in dict.fromkeys(request.historyPoiIds or [])]
    source, values = None, None
    if request.model in repo.available:
        try:
            if repo.knows(request.userId):
                values = repo.score(request.model, request.userId, request.hour, request.dayOfWeek, now(), request.useTime)
                source = request.model
            elif len(history) >= MIN_FOLDIN_HISTORY:
                values = repo.score(request.model, None, request.hour, request.dayOfWeek, now(), request.useTime, history)
                source = f"{request.model}_foldin"
        except ValueError as error:
            raise HTTPException(400, str(error)) from error
    if values is None:
        if request.model == "popularity":
            values, source = repo.popularity, "popularity"
        else:
            values, source = repo.hourly_counts[request.hour], "hourly_popularity"
    return {"source": source, "smokeRun": False, "models": repo.available, "origin": repo.origin,
            "useTime": bool(request.useTime and source.startswith("tas_gnn")),
            "artifact": health()["artifact"], "datasetSha256": repo.dataset_sha256,
            "datasetSha256Aliases": repo.dataset_sha256_aliases,
            "scores": [{"poiId": p, "score": float(v)} for p, v in zip(repo.poi_ids, normalized(values))]}


@app.post("/score")
def score(request: ScoreRequest):
    if not state:
        raise HTTPException(503, "Chưa có model. Kiểm tra outputs/checkpoints hoặc MODEL_PATH.")
    if "repo" in state:
        return score_repo(request)
    model, bundle = state["model"], state["bundle"]
    user = state["users"].get(request.userId)
    counts = bundle["hourly_counts"]
    if request.model == "popularity":
        values, source = counts.sum(0).numpy().astype(float), "popularity"
    elif user is None or request.model == "hourly_popularity":
        values, source = counts[request.hour].numpy().astype(float), "hourly_popularity"
    else:
        with torch.inference_mode():
            # Only within-hour fraction is consumed; hour/weekday come from query.
            values = model.scores(user, request.hour, request.dayOfWeek, now(), state["embeddings"]).numpy()
        source = bundle["model_name"]
    return {"source": source, "smokeRun": bundle.get("smoke_run", False),
            "models": [bundle["model_name"]], "origin": "colab_artifact", "useTime": source == bundle["model_name"],
            "artifact": model_metadata(bundle),
            "datasetSha256": bundle["dataset_sha256"],
            "datasetSha256Aliases": bundle.get("dataset_sha256_aliases", []),
            "scores": [{"poiId": p, "score": float(v)} for p, v in zip(bundle["poi_ids"], normalized(values))]}
