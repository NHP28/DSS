"""Automatic, cached data acquisition for the standalone Colab notebook."""
from __future__ import annotations

import argparse
import hashlib
import json
import time
import urllib.error
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

DANANG_REVISION = "a3f6059c0594788e42c9746debf33d803723fb31"
DANANG_BASE = f"https://raw.githubusercontent.com/NHP28/DSS/{DANANG_REVISION}/DSS_repo/data/danang/"
GOWALLA_URL = "https://snap.stanford.edu/data/loc-gowalla_totalCheckins.txt.gz"
GOWALLA_SHA256 = "c1c3e19effba649b6c89aeab3c1f9459fad88cfdc2b460fc70fd54e295d83ea0"
PREPROCESS_VERSION = 1
# Hashes use LF line endings, as stored on GitHub.
DANANG_SHA256 = {
    "danang_pois_full.csv": "d3e6cd55b56ea8c4eadd2f7317268c24a779f4222eeaf775f3446f3fd85576dd",
    "danang_checkins_full.csv": "5c623d4464c92954eb397c224f6aa5779ff4fedca6338a3a0c8779c28502b569",
    "metadata.json": "090d0ba998431eca0186be1ec3d72380d01c0d2f358b52227aa9ae0e18ef1f5d",
}


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def download_file(url, destination, expected_sha256=None, retries=3):
    """Atomic download; cache verified against a pinned hash or recorded receipt."""
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    receipt_path = destination.with_suffix(destination.suffix + ".download.json")
    if destination.is_file():
        checksum = sha256_file(destination)
        if expected_sha256 and checksum == expected_sha256:
            return destination
        if not expected_sha256:
            try:
                receipt = json.loads(receipt_path.read_text()) if receipt_path.is_file() else {}
            except (OSError, ValueError):
                receipt = {}
            if receipt.get("url") == url and receipt.get("sha256") == checksum:
                return destination
    partial = destination.with_suffix(destination.suffix + ".part")
    for attempt in range(retries):
        try:
            print(f"Downloading {url}", flush=True)
            request = urllib.request.Request(url, headers={"User-Agent": "DSS-POI-Colab/1.0"})
            digest, received = hashlib.sha256(), 0
            with urllib.request.urlopen(request, timeout=60) as response, partial.open("wb") as stream:
                length = int(response.headers.get("Content-Length", 0))
                next_log = 25 * 1024 * 1024
                while block := response.read(1024 * 1024):
                    stream.write(block)
                    digest.update(block)
                    received += len(block)
                    if received >= next_log:
                        print(f"  {received / 1024**2:.0f} MiB received", flush=True)
                        next_log += 25 * 1024 * 1024
                if length and received != length:
                    raise ValueError("Incomplete download")
            checksum = digest.hexdigest()
            if expected_sha256 and checksum != expected_sha256:
                raise ValueError(f"SHA256 mismatch: {destination.name}")
            partial.replace(destination)
            receipt_path.write_text(json.dumps({"url": url, "sha256": checksum, "bytes": received}, indent=2), encoding="utf-8")
            return destination
        except (OSError, ValueError, urllib.error.URLError):
            partial.unlink(missing_ok=True)
            if attempt == retries - 1:
                raise
            time.sleep(min(2 ** attempt, 4))


def prepare_danang(work):
    directory = Path(work) / "datasets/danang"
    for name, checksum in DANANG_SHA256.items():
        download_file(DANANG_BASE + name, directory / name, checksum)
    metadata_path = directory / "metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata.update(dataset_id="danang", has_categories=True, timezone="Asia/Ho_Chi_Minh",
                    data_provenance="OSM POIs; synthetic check-ins/ratings/prices/popularity",
                    source_url=DANANG_BASE, source_revision=DANANG_REVISION,
                    poi_file="danang_pois_full.csv", event_file="danang_checkins_full.csv")
    # Keep the pinned metadata file intact so the next cached download stays verifiable.
    (directory / "experiment_metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    return directory


def iterative_core(events, min_user_pois=15, min_poi_users=10):
    while True:
        previous = len(events)
        users = events.groupby("u").l.nunique()
        events = events[events.u.isin(users[users >= min_user_pois].index)]
        pois = events.groupby("l").u.nunique()
        events = events[events.l.isin(pois[pois >= min_poi_users].index)]
        if not len(events):
            raise ValueError("Gowalla filter produced an empty dataset")
        if len(events) == previous:
            return events.copy()


def preprocess_gowalla(raw_file, destination, max_users=None, seed=42,
                       min_user_pois=15, min_poi_users=10):
    """Real coordinates/time only; no fabricated category, price or rating labels."""
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    chunks, raw_count = [], 0
    for index, chunk in enumerate(pd.read_csv(raw_file, sep="\t", header=None,
            names=["u", "time", "lat", "lon", "l"], chunksize=500_000,
            dtype={"u":"int64", "l":"int64", "lat":"float64", "lon":"float64"})):
        parsed = pd.to_datetime(chunk.pop("time"), utc=True, errors="coerce")
        raw_count += len(chunk)
        # as_unit avoids pandas 3's datetime64[us] vs older datetime64[ns] ambiguity.
        chunk["ts"] = parsed.dt.as_unit("ns").astype("int64") // 10**9
        valid = parsed.notna() & np.isfinite(chunk.lat) & np.isfinite(chunk.lon)
        valid &= chunk.lat.between(-90, 90) & chunk.lon.between(-180, 180)
        valid &= (chunk.u >= 0) & (chunk.l >= 0)
        chunks.append(chunk[valid])
        print(f"Read Gowalla chunk {index + 1}", flush=True)
    raw_events = pd.concat(chunks, ignore_index=True)
    del chunks
    valid_count = len(raw_events)
    raw_events = raw_events.drop_duplicates(["u", "l", "ts"])
    deduplicated_count = len(raw_events)
    filtered = iterative_core(raw_events, min_user_pois, min_poi_users)
    del raw_events
    full_counts = {"users":int(filtered.u.nunique()), "pois":int(filtered.l.nunique()), "events":len(filtered)}
    if max_users is not None:
        if max_users < 1:
            raise ValueError("max_users must be positive or None")
        candidates = np.sort(filtered.u.unique())
        sampled = np.random.default_rng(seed).choice(candidates, size=min(max_users, len(candidates)), replace=False)
        filtered = filtered[filtered.u.isin(sampled)].copy()
    # Coordinates are static catalog metadata. Keep raw IDs, store mapping in each model artifact.
    pois = filtered.groupby("l")[["lat", "lon"]].first().sort_index().reset_index()
    pois["category"] = "unknown"
    coords = pois.set_index("l")
    offsets = np.rint(filtered.l.map(coords.lon).to_numpy() / 15).clip(-12, 12).astype("int64")
    local_time = pd.to_datetime(filtered.ts.to_numpy() + offsets * 3600, unit="s", utc=True)
    events = filtered[["u", "l", "ts"]].copy()
    events["hour"] = local_time.hour.to_numpy()
    events["day_of_week"] = local_time.dayofweek.to_numpy()
    events = events.sort_values(["u", "ts"], kind="stable")
    pois.to_csv(destination / "pois.csv", index=False, lineterminator="\n")
    events.to_csv(destination / "checkins.csv", index=False, lineterminator="\n")
    metadata = {"dataset_id":"gowalla", "poi_file":"pois.csv", "event_file":"checkins.csv",
                "has_categories":False, "timezone":"longitude_offset_approximation",
                "data_provenance":"Real public Gowalla check-ins and coordinates from Stanford SNAP; categories unavailable",
                "source_url":GOWALLA_URL, "source_sha256":sha256_file(raw_file),
                "preprocess_version":PREPROCESS_VERSION, "raw_events":raw_count, "raw_valid_events":valid_count,
                "invalid_events_removed":raw_count-valid_count, "duplicate_events_removed":valid_count-deduplicated_count,
                "core":{"min_user_pois":min_user_pois,"min_poi_users":min_poi_users},
                "full_core":full_counts, "sample_max_users":max_users, "sample_seed":seed,
                "is_subset":max_users is not None and max_users < full_counts["users"],
                "num_users":int(events.u.nunique()), "num_pois":len(pois), "num_checkins":len(events)}
    # Check processed files on every cache reuse, in addition to the raw download receipt.
    metadata["processed_sha256"] = {name:sha256_file(destination / name) for name in ("pois.csv", "checkins.csv")}
    (destination / "experiment_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return destination


def prepare_gowalla(work, max_users=None, seed=42):
    work = Path(work)
    raw = download_file(GOWALLA_URL, work / "downloads/loc-gowalla_totalCheckins.txt.gz", GOWALLA_SHA256)
    directory = work / "datasets" / ("gowalla_full" if max_users is None else f"gowalla_{max_users}_seed{seed}")
    metadata_path = directory / "experiment_metadata.json"
    if metadata_path.is_file():
        metadata = json.loads(metadata_path.read_text())
        hashes = metadata.get("processed_sha256", {})
        if (metadata.get("preprocess_version") == PREPROCESS_VERSION and metadata.get("source_sha256") == sha256_file(raw) and hashes
                and all((directory / name).is_file() and sha256_file(directory / name) == checksum for name, checksum in hashes.items())):
            return directory
    return preprocess_gowalla(raw, directory, max_users, seed)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("dataset", choices=["danang", "gowalla", "all"])
    parser.add_argument("--work", default="outputs/datasets")
    parser.add_argument("--gowalla-max-users", type=int)
    args = parser.parse_args()
    if args.dataset in ("danang", "all"):
        print(prepare_danang(args.work))
    if args.dataset in ("gowalla", "all"):
        print(prepare_gowalla(args.work, args.gowalla_max_users))
