"""Summarise the datasets for the /data page -> FE/public/artifacts/data-profile.json."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from kg_schema import build_rows, normalize_district  # noqa: E402

REAL, SYNTHETIC = "OpenStreetMap", "Mô phỏng"
SCHEMA = {
    "danang_pois_full.csv": [
        ("l", "số nguyên", "Mã địa điểm (0–995)", REAL), ("name", "chuỗi", "Tên địa điểm", REAL),
        ("category", "chuỗi", "cafe · restaurant · hotel · tourist_spot", REAL), ("lat", "số thực", "Vĩ độ", REAL),
        ("lon", "số thực", "Kinh độ", REAL), ("district", "chuỗi", "Quận/huyện", REAL),
        ("rating", "số thực", "Điểm đánh giá 1–5", SYNTHETIC), ("user_ratings_total", "số nguyên", "Số lượt đánh giá", SYNTHETIC),
        ("price_avg", "số thực", "Giá trung bình (đồng)", SYNTHETIC), ("popularity", "số nguyên", "Độ phổ biến 0–100", SYNTHETIC)],
    "danang_checkins_full.csv": [
        ("u", "số nguyên", "Mã người dùng (0–1499)", SYNTHETIC), ("l", "số nguyên", "Mã địa điểm", SYNTHETIC),
        ("ts", "số nguyên", "Thời điểm check-in (Unix giây)", SYNTHETIC), ("datetime", "chuỗi", "Giờ địa phương Asia/Ho_Chi_Minh", SYNTHETIC),
        ("hour", "số nguyên", "Giờ trong ngày 0–23", SYNTHETIC), ("day_of_week", "số nguyên", "Thứ: 0 = thứ Hai … 6 = Chủ nhật", SYNTHETIC),
        ("is_weekend", "0/1", "Cuối tuần", SYNTHETIC)],
    "danang_social_full.csv": [("u1", "số nguyên", "Người dùng thứ nhất", SYNTHETIC), ("u2", "số nguyên", "Người dùng thứ hai (bạn bè)", SYNTHETIC)],
}


def main():
    data = ROOT / "data" / "danang"
    pois = pd.read_csv(data / "danang_pois_full.csv")
    events = pd.read_csv(data / "danang_checkins_full.csv")
    social = pd.read_csv(data / "danang_social_full.csv")
    metadata = json.loads((data / "metadata.json").read_text(encoding="utf-8"))
    category_of = pois.set_index("l").category
    events = events.assign(category=events.l.map(category_of))
    per_user = events.groupby("u").size()
    by_hour_category = events.groupby(["hour", "category"]).size().unstack(fill_value=0).reindex(range(24), fill_value=0)
    rows = build_rows(pois, events, social)
    summary = json.loads((ROOT / "FE" / "public" / "artifacts" / "training-summary.json").read_text(encoding="utf-8"))
    gowalla = next(item for item in summary["datasets"] if item["id"] == "gowalla")
    profile = {
        "danang": {
            "pois": len(pois), "users": int(events.u.nunique()), "checkins": len(events), "friendships": len(rows["friend_of"]),
            "timeRange": metadata["time_range"], "boundingBox": metadata["bounding_box"],
            "density": round(len(events.drop_duplicates(["u", "l"])) / (events.u.nunique() * len(pois)), 5),
            "checkinsPerUser": {"min": int(per_user.min()), "median": float(per_user.median()), "mean": round(float(per_user.mean()), 1), "max": int(per_user.max())},
            "poisWithoutCheckins": int((~pois.l.isin(events.l)).sum()),
            "categories": [{"key": key, "pois": int((pois.category == key).sum()), "checkins": int((events.category == key).sum())}
                           for key in ["cafe", "restaurant", "tourist_spot", "hotel"]],
            "districts": [{"name": name, "pois": int(count)} for name, count in pois.district.map(normalize_district).value_counts().items()],
            "byHour": [{"hour": int(hour), **{key: int(value) for key, value in row.items()}, "total": int(row.sum())} for hour, row in by_hour_category.iterrows()],
            "byWeekday": [int(value) for value in events.groupby("day_of_week").size().reindex(range(7), fill_value=0)],
        },
        "gowalla": {"users": gowalla["users"], "pois": gowalla["pois"], "checkins": gowalla["events"],
                    "source": "Stanford SNAP loc-gowalla, lọc lặp ≥15 POI/người dùng và ≥10 người dùng/POI",
                    "note": "Check-in thật, không có danh mục, giá hay đánh giá."},
        "schema": {name: [{"column": c, "type": t, "meaning": m, "origin": o} for c, t, m, o in columns] for name, columns in SCHEMA.items()},
        "graph": {"nodes": {"User": len(rows["users"]), "POI": len(rows["pois"]), "Category": len(rows["categories"]),
                            "District": len(rows["districts"]), "TimeSlot": len(rows["timeslots"])},
                  "relationships": {"VISITED": len(rows["visited"]), "FRIEND_OF": len(rows["friend_of"]), "IN_CATEGORY": len(rows["in_category"]),
                                    "LOCATED_IN": len(rows["located_in"]), "NEAR": len(rows["near"]), "BUSY_AT": len(rows["busy_at"]),
                                    "ACTIVE_AT": len(rows["active_at"])}},
    }
    assert sum(item["total"] for item in profile["danang"]["byHour"]) == len(events)
    target = ROOT / "FE" / "public" / "artifacts" / "data-profile.json"
    target.write_text(json.dumps(profile, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Wrote {target.relative_to(ROOT)}: {profile['danang']['checkins']:,} check-ins, graph {sum(profile['graph']['nodes'].values()):,} nodes")


if __name__ == "__main__":
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8")
    main()
