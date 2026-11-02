import requests
import json
import time
import os
import sys
import pandas as pd
import math

# Fix Windows console UTF-8 encoding
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

OUTPUT_DIR = r"f:\dss\DSS_repo\data\danang"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Đà Nẵng Bounding Box: [min_lat, min_lon, max_lat, max_lon]
BBOX = "15.90,108.05,16.20,108.35"

# Danh mục cần thu thập
CATEGORY_QUERIES = [
    # (Category_Group, Key, Value, Sub_Category)
    ("cafe", "amenity", "cafe", "cafe"),
    ("cafe", "amenity", "bar", "bar"),
    ("cafe", "amenity", "pub", "pub"),
    ("cafe", "amenity", "ice_cream", "ice_cream"),
    ("restaurant", "amenity", "restaurant", "restaurant"),
    ("restaurant", "amenity", "fast_food", "fast_food"),
    ("restaurant", "amenity", "food_court", "food_court"),
    ("hotel", "tourism", "hotel", "hotel"),
    ("hotel", "tourism", "guest_house", "guest_house"),
    ("hotel", "tourism", "hostel", "hostel"),
    ("hotel", "tourism", "resort", "resort"),
    ("hotel", "tourism", "motel", "motel"),
    ("tourist_spot", "tourism", "attraction", "attraction"),
    ("tourist_spot", "tourism", "viewpoint", "viewpoint"),
    ("tourist_spot", "tourism", "museum", "museum"),
    ("tourist_spot", "tourism", "theme_park", "theme_park"),
    ("tourist_spot", "tourism", "gallery", "gallery"),
    ("tourist_spot", "historic", "monument", "monument"),
    ("tourist_spot", "historic", "memorial", "memorial"),
    ("shopping", "shop", "mall", "shopping_mall"),
    ("shopping", "shop", "supermarket", "supermarket"),
    ("shopping", "shop", "bakery", "bakery"),
    ("entertainment", "leisure", "park", "park"),
    ("entertainment", "leisure", "water_park", "water_park")
]

OVERPASS_SERVERS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter"
]

def fetch_osm(key, value, bbox=BBOX):
    query = f"""
    [out:json][timeout:60];
    (
      node["{key}"="{value}"]({bbox});
      way["{key}"="{value}"]({bbox});
    );
    out center tags;
    """
    for server in OVERPASS_SERVERS:
        try:
            resp = requests.post(server, data={"data": query}, timeout=45, headers={"User-Agent": "DaNangGNNProject/1.0"})
            if resp.status_code == 200:
                data = resp.json()
                elements = data.get("elements", [])
                return elements
            elif resp.status_code == 429:
                time.sleep(3)
        except Exception as e:
            time.sleep(2)
            continue
    return []

def determine_district(lat, lon):
    # Heuristic sơ bộ theo tọa độ quận của Đà Nẵng
    if lon > 108.24 and lat >= 16.08:
        return "Sơn Trà"
    elif lon > 108.23 and lat < 16.08:
        return "Ngũ Hành Sơn"
    elif lat >= 16.03 and lat <= 16.09 and lon >= 108.20 and lon <= 108.24:
        return "Hải Châu"
    elif lon < 108.20 and lat >= 16.04 and lat <= 16.08:
        return "Thanh Khê"
    elif lat > 16.08 and lon < 108.20:
        return "Liên Chiểu"
    elif lat < 16.03 and lon >= 108.18 and lon <= 108.24:
        return "Cẩm Lệ"
    else:
        return "Hòa Vang"

def main():
    print("=== BẮT ĐẦU CÀO TOÀN BỘ POI ĐÀ NẴNG TỪ OSM ===")
    seen_ids = set()
    pois = []

    for cat_group, key, val, sub_cat in CATEGORY_QUERIES:
        print(f" -> Đang quét: [{cat_group}] {key}={val}...", end="", flush=True)
        elements = fetch_osm(key, val)
        print(f" Tìm thấy {len(elements)} kết quả.")
        
        for el in elements:
            osm_id = el.get("id")
            if osm_id in seen_ids:
                continue
            seen_ids.add(osm_id)

            tags = el.get("tags", {})
            name = tags.get("name") or tags.get("name:en") or tags.get("name:vi")
            if not name:
                # Bỏ qua địa điểm không có tên
                continue

            lat = el.get("lat") or el.get("center", {}).get("lat")
            lon = el.get("lon") or el.get("center", {}).get("lon")
            if not lat or not lon:
                continue

            street = tags.get("addr:street", "")
            housenumber = tags.get("addr:housenumber", "")
            district_tag = tags.get("addr:district", "")
            district = district_tag if district_tag else determine_district(lat, lon)
            
            address = f"{housenumber} {street}".strip()
            if not address:
                address = f"{district}, Đà Nẵng"

            pois.append({
                "osm_id": osm_id,
                "name": name,
                "category": cat_group,
                "sub_category": sub_cat,
                "latitude": round(lat, 6),
                "longitude": round(lon, 6),
                "district": district,
                "address": address,
                "opening_hours": tags.get("opening_hours", ""),
                "website": tags.get("website", ""),
                "phone": tags.get("phone", tags.get("contact:phone", ""))
            })
        time.sleep(1)

    df_poi = pd.DataFrame(pois)
    # Gán poi_id chuẩn từ 0 đến N-1
    df_poi = df_poi.reset_index().rename(columns={"index": "poi_id"})
    
    out_csv = os.path.join(OUTPUT_DIR, "danang_pois.csv")
    out_json = os.path.join(OUTPUT_DIR, "danang_pois.json")
    
    df_poi.to_csv(out_csv, index=False, encoding="utf-8-sig")
    df_poi.to_json(out_json, orient="records", force_ascii=False, indent=2)
    
    print("\n=== HOÀN TẤT BƯỚC 1: TẬP POI ĐÀ NẴNG ===")
    print(f"Tổng số POIs thu thập được: {len(df_poi)}")
    print(df_poi["category"].value_counts())
    print(f"Đã lưu tại: {out_csv}")

if __name__ == "__main__":
    main()
