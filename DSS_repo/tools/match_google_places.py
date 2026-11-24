"""Ghép 996 địa điểm OSM với Google Maps, chỉ lưu place_id (thứ duy nhất Google cho lưu lâu dài).

    python tools/match_google_places.py --limit 20     # thử 20 địa điểm trước
    python tools/match_google_places.py                # chạy hết; chạy lại sẽ bỏ qua dòng đã có

Cần GOOGLE_PLACES_API_KEY trong apps/api/.env (hoặc biến môi trường) và bật "Places API (New)".
Mỗi địa điểm tốn một lệnh Text Search. Kết quả: data/danang/google_place_ids.csv.
"""
from __future__ import annotations

import argparse
import csv
import math
import os
import sys
import time
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "danang" / "google_place_ids.csv"
FIELDS = ["l", "place_id", "google_name", "distance_m", "similarity"]
MAX_DISTANCE_M, NEAR_M = 250, 60
GENERIC = {"cafe", "ca", "phe", "caphe", "coffee", "quan", "nha", "hang", "restaurant", "hotel", "khach", "san", "the", "da", "nang"}


def plain(text: str) -> str:
    """Lowercase without Vietnamese diacritics or punctuation."""
    text = unicodedata.normalize("NFD", text.replace("đ", "d").replace("Đ", "D"))
    text = "".join(c for c in text if unicodedata.category(c) != "Mn").lower()
    return " ".join("".join(c if c.isalnum() else " " for c in text).split())


def similarity(a: str, b: str) -> float:
    """Name similarity in [0, 1]; generic words like "cafe" or "quán" do not count as a match."""
    a, b = plain(a), plain(b)
    if not a or not b:
        return 0.0
    whole = SequenceMatcher(None, a.replace(" ", ""), b.replace(" ", "")).ratio()
    words_a, words_b = set(a.split()) - GENERIC, set(b.split()) - GENERIC
    if not words_a or not words_b:
        return whole * 0.6
    shared = len(words_a & words_b) / min(len(words_a), len(words_b))
    return max(whole * (0.5 + 0.5 * bool(words_a & words_b)), shared)


def metres(lat1, lon1, lat2, lon2) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, (lat1, lon1, lat2, lon2))
    a = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 2 * 6371000 * math.asin(math.sqrt(a))


def pick_match(name: str, lat: float, lon: float, candidates: list[dict]) -> dict | None:
    """Best Google candidate for an OSM place, or None when nothing is both close and similarly named.

    A wrong photo is worse than no photo, so the bar is: within 250 m with a clearly similar
    name, or within 60 m with a loosely similar one.
    """
    best = None
    for place in candidates:
        location = place.get("location") or {}
        if "latitude" not in location or not place.get("id"):
            continue
        distance = metres(lat, lon, location["latitude"], location["longitude"])
        score = similarity(name, (place.get("displayName") or {}).get("text", ""))
        if distance > MAX_DISTANCE_M or score < (0.45 if distance <= NEAR_M else 0.7):
            continue
        rank = score - distance / 1000
        if best is None or rank > best["rank"]:
            best = {"place_id": place["id"], "google_name": place["displayName"]["text"], "distance_m": round(distance),
                    "similarity": round(score, 2), "rank": rank}
    return best


def api_key() -> str:
    key = os.environ.get("GOOGLE_PLACES_API_KEY", "")
    env = ROOT / "apps" / "api" / ".env"
    if not key and env.is_file():
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.startswith("GOOGLE_PLACES_API_KEY="):
                key = line.split("=", 1)[1].strip()
    return key


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--limit", type=int, default=0, help="chỉ xử lý N địa điểm chưa có kết quả")
    args = parser.parse_args()
    key = api_key()
    if not key:
        sys.exit("Chưa có GOOGLE_PLACES_API_KEY trong apps/api/.env. Xem docs/GOOGLE_PLACES.md.")
    import httpx

    with open(ROOT / "data" / "danang" / "danang_pois_full.csv", encoding="utf-8-sig", newline="") as handle:
        pois = list(csv.DictReader(handle))
    done = {}
    if OUTPUT.is_file():
        with open(OUTPUT, encoding="utf-8-sig", newline="") as handle:
            done = {row["l"]: row for row in csv.DictReader(handle)}
    todo = [poi for poi in pois if poi["l"] not in done]
    if args.limit:
        todo = todo[:args.limit]
    print(f"{len(done)} địa điểm đã có kết quả, xử lý thêm {len(todo)}.", flush=True)

    url = os.environ.get("GOOGLE_PLACES_URL", "https://places.googleapis.com/v1") + "/places:searchText"
    headers = {"X-Goog-Api-Key": key, "X-Goog-FieldMask": "places.id,places.displayName,places.location"}
    matched = 0
    with httpx.Client(timeout=15) as client:
        for index, poi in enumerate(todo, 1):
            lat, lon = float(poi["lat"]), float(poi["lon"])
            body = {"textQuery": poi["name"], "maxResultCount": 5, "languageCode": "vi",
                    "locationBias": {"circle": {"center": {"latitude": lat, "longitude": lon}, "radius": 300.0}}}
            response = client.post(url, json=body, headers=headers)
            if response.status_code in (403, 429):
                print(f"Google từ chối ({response.status_code}): {response.text[:300]}\nDừng ở đây; chạy lại lệnh để tiếp tục.")
                break
            response.raise_for_status()
            match = pick_match(poi["name"], lat, lon, response.json().get("places", []))
            row = {"l": poi["l"], **({k: match[k] for k in FIELDS[1:]} if match else dict.fromkeys(FIELDS[1:], ""))}
            done[poi["l"]] = row
            matched += bool(match)
            if index % 25 == 0 or index == len(todo):
                _write(done)
                print(f"  {index}/{len(todo)} · khớp {matched}", flush=True)
            time.sleep(0.12)
    _write(done)
    total = sum(1 for row in done.values() if row["place_id"])
    print(f"Đã ghi {OUTPUT.relative_to(ROOT)}: {total}/{len(done)} địa điểm khớp với Google.")


def _write(done: dict):
    with open(OUTPUT, "w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(sorted(done.values(), key=lambda row: int(row["l"])))


if __name__ == "__main__":
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8")
    main()
