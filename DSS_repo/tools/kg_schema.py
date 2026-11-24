"""Turn the Đà Nẵng CSV files into knowledge-graph rows. Pure functions: no database needed.

Nodes:  User, POI, Category, District, TimeSlot
Edges:  (User)-[:VISITED]->(POI)        count, first_ts, last_ts, top_hour
        (User)-[:FRIEND_OF]->(User)     one edge per unordered pair
        (POI)-[:IN_CATEGORY]->(Category)
        (POI)-[:LOCATED_IN]->(District)
        (POI)-[:NEAR]->(POI)            km, the 5 nearest POIs
        (POI)-[:BUSY_AT]->(TimeSlot)    count, share of the POI's visits
        (User)-[:ACTIVE_AT]->(TimeSlot) count
"""
from __future__ import annotations

import unicodedata

import numpy as np
import pandas as pd
from sklearn.neighbors import BallTree

EARTH_KM = 6371.0
NEAR_K = 5
CATEGORY_LABELS = {"cafe": "Cà phê", "restaurant": "Nhà hàng", "hotel": "Khách sạn", "tourist_spot": "Tham quan"}
TIME_SLOTS = [("morning", "Buổi sáng (5–10h)"), ("noon", "Buổi trưa (11–13h)"), ("afternoon", "Buổi chiều (14–17h)"),
              ("evening", "Buổi tối (18–22h)"), ("night", "Đêm khuya (23–4h)")]
# Same table as apps/api/src/database/display.ts.
DISTRICTS = {"hai chau": "Hải Châu", "son tra": "Sơn Trà", "ngu hanh son": "Ngũ Hành Sơn", "lien chieu": "Liên Chiểu",
             "thanh khe": "Thanh Khê", "hoa vang": "Hòa Vang", "cam le": "Cẩm Lệ", "danang": "Hải Châu", "da nang": "Hải Châu"}


def time_slot(hour: int) -> str:
    if 5 <= hour <= 10:
        return "morning"
    if 11 <= hour <= 13:
        return "noon"
    if 14 <= hour <= 17:
        return "afternoon"
    if 18 <= hour <= 22:
        return "evening"
    return "night"


def normalize_district(raw: str) -> str:
    plain = unicodedata.normalize("NFD", raw)
    plain = "".join(c for c in plain if unicodedata.category(c) != "Mn").replace("đ", "d").replace("Đ", "D").lower().strip()
    if plain.startswith("quan "):
        plain = plain[5:].strip()
    if plain in DISTRICTS:
        return DISTRICTS[plain]
    return raw[5:].strip() if raw.lower().startswith("quận ") else raw.strip()


def build_rows(pois: pd.DataFrame, checkins: pd.DataFrame, social: pd.DataFrame) -> dict[str, list[dict]]:
    pois = pois.sort_values("l").reset_index(drop=True)
    district = pois.district.map(normalize_district)
    slots = checkins.hour.map(time_slot)

    visits = checkins.groupby(["u", "l"]).agg(count=("ts", "size"), first_ts=("ts", "min"), last_ts=("ts", "max"),
                                             top_hour=("hour", lambda h: int(h.mode().iloc[0]))).reset_index()
    busy = checkins.assign(slot=slots).groupby(["l", "slot"]).size().rename("count").reset_index()
    busy["share"] = busy["count"] / busy.groupby("l")["count"].transform("sum")
    active = checkins.assign(slot=slots).groupby(["u", "slot"]).size().rename("count").reset_index()

    # Haversine k-nearest neighbours; the first neighbour of each point is itself.
    radians = np.radians(pois[["lat", "lon"]].to_numpy(float))
    distance, index = BallTree(radians, metric="haversine").query(radians, k=NEAR_K + 1)
    ids = pois.l.to_numpy()
    near = []
    for row in range(len(pois)):
        neighbours = [(j, d) for j, d in zip(index[row], distance[row]) if j != row][:NEAR_K]
        near += [{"source": int(ids[row]), "target": int(ids[j]), "km": round(float(d * EARTH_KM), 3)} for j, d in neighbours]

    pairs = {(min(int(a), int(b)), max(int(a), int(b))) for a, b in social.iloc[:, :2].to_numpy() if a != b}
    return {
        "users": [{"id": int(u)} for u in sorted(checkins.u.unique())],
        "pois": [{"id": int(r.l), "name": r.name_, "category": r.category, "lat": float(r.lat), "lon": float(r.lon),
                  "rating": float(r.rating), "price_avg": float(r.price_avg), "popularity": float(r.popularity)}
                 for r in pois.rename(columns={"name": "name_"}).itertuples()],
        "categories": [{"key": key, "label": CATEGORY_LABELS.get(key, key)} for key in sorted(pois.category.unique())],
        "districts": [{"name": name} for name in sorted(district.unique())],
        "timeslots": [{"key": key, "label": label} for key, label in TIME_SLOTS],
        "visited": [{"source": int(r.u), "target": int(r.l), "count": int(r.count), "first_ts": int(r.first_ts),
                     "last_ts": int(r.last_ts), "top_hour": int(r.top_hour)} for r in visits.itertuples()],
        "friend_of": [{"source": a, "target": b} for a, b in sorted(pairs)],
        "in_category": [{"source": int(l), "target": c} for l, c in zip(pois.l, pois.category)],
        "located_in": [{"source": int(l), "target": d} for l, d in zip(pois.l, district)],
        "near": near,
        "busy_at": [{"source": int(r.l), "target": r.slot, "count": int(r.count), "share": round(float(r.share), 4)} for r in busy.itertuples()],
        "active_at": [{"source": int(r.u), "target": r.slot, "count": int(r.count)} for r in active.itertuples()],
    }


def load_frames(data_dir):
    return (pd.read_csv(f"{data_dir}/danang_pois_full.csv"), pd.read_csv(f"{data_dir}/danang_checkins_full.csv"),
            pd.read_csv(f"{data_dir}/danang_social_full.csv"))
