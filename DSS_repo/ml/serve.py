"""Internal inference HTTP service. NestJS owns catalog, filters, DSS and persistence."""
from contextlib import asynccontextmanager
from datetime import datetime
from zoneinfo import ZoneInfo

import numpy as np
import torch
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from ml.poi_model import restore_bundle
from ml.artifacts import serving_model_path, model_metadata

state = {}


@asynccontextmanager
async def lifespan(app):
    path = serving_model_path()
    if path.is_file():
        torch.set_num_threads(min(4, torch.get_num_threads()))
        model, bundle = restore_bundle(path)
        with torch.inference_mode():
            embeddings = model.embeddings()
        trained_users = set(bundle.get("trained_user_ids", bundle["user_ids"]))
        state.update(model=model, bundle=bundle, embeddings=embeddings,
                     users={u: i for i, u in enumerate(bundle["user_ids"]) if u in trained_users})
    yield
    state.clear()


app = FastAPI(title="DSS internal model inference", lifespan=lifespan)


class ScoreRequest(BaseModel):
    userId: int | None = Field(default=None, ge=0)
    hour: int = Field(default=8, ge=0, le=23)
    dayOfWeek: int = Field(default=0, ge=0, le=6)


@app.get("/health")
def health():
    return {"ready": bool(state), "model": state.get("bundle", {}).get("model_name"),
            "artifact": model_metadata(state["bundle"]) if state else None,
            "smokeRun": state.get("bundle", {}).get("smoke_run", False)}


@app.post("/score")
def score(request: ScoreRequest):
    if not state:
        raise HTTPException(503, "Chưa có artifact Colab. Train notebook và đặt MODEL_PATH.")
    model, bundle = state["model"], state["bundle"]
    user = state["users"].get(request.userId)
    if user is None:
        values = bundle["hourly_counts"][request.hour].numpy().astype(float)
        source = "hourly_popularity"
    else:
        with torch.inference_mode():
            # Only within-hour fraction is consumed; hour/weekday come from query.
            values = model.scores(user, request.hour, request.dayOfWeek,
                                  datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).timestamp(), state["embeddings"]).numpy()
        source = bundle["model_name"]
    values = (values - values.min()) / max(float(np.ptp(values)), 1e-9)
    return {"source": source, "smokeRun": bundle.get("smoke_run", False),
            "artifact": model_metadata(bundle),
            "datasetSha256": bundle["dataset_sha256"],
            "datasetSha256Aliases": bundle.get("dataset_sha256_aliases", []),
            "scores": [{"poiId": p, "score": float(v)} for p, v in zip(bundle["poi_ids"], values)]}
