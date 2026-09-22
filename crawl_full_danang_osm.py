import urllib.request
import urllib.parse
import json
import random
import time
import os

def query_category(amenity_type, tourism_type=None):
    if amenity_type:
        node_str = f'node["amenity"="{amenity_type}"](15.90,108.05,16.20,108.35);'
    else:
        node_str = f'node["tourism"="{tourism_type}"](15.90,108.05,16.20,108.35);'
        
    query = f"""
    [out:json][timeout:30];
    (
      {node_str}
    );
    out body 250;
    """
    url = "https://overpass-api.de/api/interpreter"
    data = ("data=" + urllib.parse.quote(query)).encode("utf-8")
    
    for attempt in range(3):
        try:
            req = urllib.request.Request(
                url,
                data=data,
                headers={"User-Agent": f"DaNangPOIBot/{attempt+1}.0"}
            )
            with urllib.request.urlopen(req, timeout=30) as res:
                res_data = json.loads(res.read().decode("utf-8"))
                elements = res_data.get("elements", [])
                print(f" -> Fetched {len(elements)} items for {amenity_type or tourism_type}")
                return elements
        except Exception as e:
            print(f" -> Attempt {attempt+1} failed for {amenity_type or tourism_type}: {e}")
            time.sleep(2)
    return []

def run():
    print("[1] Fetching individual tags to prevent timeouts...")
    categories_tasks = [
        ("cafe", "cafe", None),
        ("cafe", "bar", None),
        ("restaurant", "restaurant", None),
        ("restaurant", "fast_food", None),
        ("hotel", None, "hotel"),
        ("hotel", None, "guest_house"),
        ("hotel", None, "resort"),
        ("tourist_spot", None, "attraction"),
        ("tourist_spot", None, "viewpoint"),
        ("tourist_spot", None, "museum")
    ]
    
    all_elements = []
    for cat_slug, am, tour in categories_tasks:
        items = query_category(am, tour)
        for it in items:
            it["_cat"] = cat_slug
        all_elements.extend(items)
        time.sleep(1)

    print(f"\n[2] Total raw elements fetched: {len(all_elements)}")

    images_cafe = [
        "https://images.unsplash.com/photo-1554118811-1e0d58224f24?w=800&auto=format&fit=crop&q=80",
        "https://images.unsplash.com/photo-1501339847302-ac426a4a7cbb?w=800&auto=format&fit=crop&q=80",
        "https://images.unsplash.com/photo-1559925393-8be0ec4767c8?w=800&auto=format&fit=crop&q=80",
        "https://images.unsplash.com/photo-1521017432531-fbd92d768814?w=800&auto=format&fit=crop&q=80",
        "https://images.unsplash.com/photo-1442512595331-e89e73853f31?w=800&auto=format&fit=crop&q=80",
        "https://images.unsplash.com/photo-1517248135467-4c7edcad34c4?w=800&auto=format&fit=crop&q=80",
        "https://images.unsplash.com/photo-1511920170033-f8396924c348?w=800&auto=format&fit=crop&q=80",
        "https://images.unsplash.com/photo-1495474472287-4d71bcdd2085?w=800&auto=format&fit=crop&q=80",
        "https://images.unsplash.com/photo-1509042239860-f550ce710b93?w=800&auto=format&fit=crop&q=80",
        "https://images.unsplash.com/photo-1447933601403-0c6688de566e?w=800&auto=format&fit=crop&q=80",
        "https://images.unsplash.com/photo-1541167760496-1628856ab772?w=800&auto=format&fit=crop&q=80"
    ]
    images_restaurant = [
        "https://images.unsplash.com/photo-1534422298391-e4f8c172dddb?w=800&auto=format&fit=crop&q=80",
        "https://images.unsplash.com/photo-1504674900247-0877df9cc836?w=800&auto=format&fit=crop&q=80",
        "https://images.unsplash.com/photo-1555396273-367ea4eb4db5?w=800&auto=format&fit=crop&q=80",
        "https://images.unsplash.com/photo-1569718212165-3a8278d5f624?w=800&auto=format&fit=crop&q=80",
        "https://images.unsplash.com/photo-1513104890138-7c749659a591?w=800&auto=format&fit=crop&q=80",
        "https://images.unsplash.com/photo-1546069901-ba9599a7e63c?w=800&auto=format&fit=crop&q=80",
        "https://images.unsplash.com/photo-1517248135467-4c7edcad34c4?w=800&auto=format&fit=crop&q=80",
        "https://images.unsplash.com/photo-1544025162-d76694265947?w=800&auto=format&fit=crop&q=80"
    ]
    images_hotel = [
        "https://images.unsplash.com/photo-1566073771259-6a8506099945?w=800&auto=format&fit=crop&q=80",
        "https://images.unsplash.com/photo-1582719508461-905c673771fd?w=800&auto=format&fit=crop&q=80",
        "https://images.unsplash.com/photo-1571896349842-33c89424de2d?w=800&auto=format&fit=crop&q=80",
        "https://images.unsplash.com/photo-1520250497591-112f2f40a3f4?w=800&auto=format&fit=crop&q=80"
    ]
    images_tourist = [
        "https://images.unsplash.com/photo-1559592413-7cec4d0cae2b?w=800&auto=format&fit=crop&q=80",
        "https://images.unsplash.com/photo-1528127269322-539801943592?w=800&auto=format&fit=crop&q=80",
        "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?w=800&auto=format&fit=crop&q=80",
        "https://images.unsplash.com/photo-1566127444979-b3d2b654e3d7?w=800&auto=format&fit=crop&q=80",
        "https://images.unsplash.com/photo-1509042239860-f550ce710b93?w=800&auto=format&fit=crop&q=80"
    ]

    processed = []
    seen = set()

    for el in all_elements:
        tags = el.get("tags", {})
        name = tags.get("name") or tags.get("name:vi") or tags.get("name:en")
        if not name or len(name.strip()) < 2:
            continue
        
        name = name.strip()
        norm_name = name.lower()
        if norm_name in seen:
            continue
        seen.add(norm_name)

        lat = el.get("lat")
        lon = el.get("lon")
        if not lat or not lon:
            continue

        cat = el.get("_cat", "cafe")
        if cat == "cafe":
            img = random.choice(images_cafe)
            price_avg = random.choice([25000, 30000, 35000, 40000, 45000, 50000, 60000, 75000])
            price_level = 1 if price_avg <= 35000 else (2 if price_avg <= 60000 else 3)
            default_desc = f"Quán cafe {name} không gian thư giãn, đồ uống phong phú tại Đà Nẵng."
        elif cat == "restaurant":
            img = random.choice(images_restaurant)
            price_avg = random.choice([40000, 50000, 70000, 100000, 150000, 200000, 250000, 350000])
            price_level = 1 if price_avg <= 60000 else (2 if price_avg <= 180000 else 3)
            default_desc = f"Nhà hàng {name} ẩm thực đa dạng, hấp dẫn tại TP. Đà Nẵng."
        elif cat == "hotel":
            img = random.choice(images_hotel)
            price_avg = random.choice([400000, 600000, 850000, 1200000, 1800000, 2500000, 4000000])
            price_level = 2 if price_avg <= 800000 else (3 if price_avg <= 2000000 else 4)
            default_desc = f"Khách sạn / nơi lưu trú {name} tiện nghi, vị trí đẹp tại Đà Nẵng."
        else:
            img = random.choice(images_tourist)
            price_avg = random.choice([0, 0, 0, 30000, 50000, 100000, 150000])
            price_level = 1 if price_avg <= 50000 else 2
            default_desc = f"Điểm tham quan, danh thắng, check-in {name} tại TP. Đà Nẵng."

        street = tags.get("addr:street", "")
        housenumber = tags.get("addr:housenumber", "")
        district = tags.get("addr:district", "")
        ward = tags.get("addr:subdistrict", "")

        if not district:
            if lon > 108.23 and lat > 16.05:
                district = "Sơn Trà"
            elif lon > 108.23 and lat <= 16.05:
                district = "Ngũ Hành Sơn"
            elif lon <= 108.23 and lon >= 108.20 and lat >= 16.03:
                district = "Hải Châu"
            elif lon < 108.20 and lon >= 108.16 and lat >= 16.04:
                district = "Thanh Khê"
            elif lon < 108.16 and lat >= 16.05:
                district = "Liên Chiểu"
            elif lat < 16.03 and lon >= 108.17:
                district = "Cẩm Lệ"
            else:
                district = "Hòa Vang"

        address_parts = [housenumber, street, ward, district, "Đà Nẵng"]
        address = ", ".join([p for p in address_parts if p])

        rating = round(random.uniform(4.1, 4.9), 1)
        user_ratings_total = random.randint(50, 4500)
        popularity = random.randint(65, 99)
        match_pref = round(random.uniform(0.75, 0.98), 2)
        opening_hours = tags.get("opening_hours", "07:00 - 22:30")
        phone = tags.get("phone") or tags.get("contact:phone", "")

        processed.append({
            "categorySlug": cat,
            "name": name,
            "address": address,
            "district": district,
            "ward": ward or None,
            "latitude": round(float(lat), 6),
            "longitude": round(float(lon), 6),
            "rating": rating,
            "userRatingsTotal": user_ratings_total,
            "priceAvg": price_avg,
            "priceLevel": price_level,
            "popularity": popularity,
            "matchPreference": match_pref,
            "imageUrl": img,
            "openingHours": opening_hours,
            "phoneNumber": phone or None,
            "description": tags.get("description", default_desc)
        })

    print(f"\n=======================================================")
    print(f"Successfully standardizing {len(processed)} real Da Nang places!")
    print(f"=======================================================")
    
    stats = {}
    for p in processed:
        c = p["categorySlug"]
        stats[c] = stats.get(c, 0) + 1
    print("Breakdown across 4 categories:", stats)

    # Save to JSON
    json_path = "f:/dss/BE_API/src/modules/seed/danang_full_osm_places.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(processed, f, ensure_ascii=False, indent=2)
    print(f"Written to {json_path}")

    # Generate TypeScript file
    ts_content = f"""/**
 * BỘ DỮ LIỆU ĐẦY ĐỦ (FULL {len(processed)} ĐỊA ĐIỂM THỰC TẾ) TẠI TP. ĐÀ NẴNG
 * Tự động đồng bộ và chuẩn hóa từ OpenStreetMap (OSM) & Bản đồ TP. Đà Nẵng
 */

export interface SeedPlaceItem {{
  categorySlug: 'cafe' | 'restaurant' | 'hotel' | 'tourist_spot';
  name: string;
  address: string;
  district: string;
  ward?: string;
  latitude: number;
  longitude: number;
  rating: number;
  userRatingsTotal: number;
  priceAvg: number;
  priceLevel: number;
  popularity: number;
  matchPreference: number;
  imageUrl: string;
  openingHours: string;
  phoneNumber?: string;
  description: string;
}}

export const SEED_CATEGORIES = [
  {{
    name: 'Quán Cafe',
    slug: 'cafe',
    description: 'Các quán cafe đẹp, không gian làm việc, cafe view biển, cafe acoustic tại Đà Nẵng',
    icon: 'coffee',
  }},
  {{
    name: 'Nhà hàng & Ẩm thực',
    slug: 'restaurant',
    description: 'Hải sản tươi sống, đặc sản mì Quảng, bánh xèo, cơm niêu và ẩm thực Đà Nẵng',
    icon: 'utensils',
  }},
  {{
    name: 'Khách sạn & Nghỉ dưỡng',
    slug: 'hotel',
    description: 'Khách sạn ven biển Mỹ Khê, homestay trung tâm thành phố, resort cao cấp',
    icon: 'hotel',
  }},
  {{
    name: 'Điểm du lịch & Check-in',
    slug: 'tourist_spot',
    description: 'Các cây cầu nổi tiếng, bán đảo Sơn Trà, danh thắng Ngũ Hành Sơn, bãi biển, Bà Nà Hills',
    icon: 'map-pin',
  }},
];

export const DANANG_SEED_PLACES: SeedPlaceItem[] = {json.dumps(processed, ensure_ascii=False, indent=2)};
"""
    with open("f:/dss/BE_API/src/modules/seed/danang-places.data.ts", "w", encoding="utf-8") as f:
        f.write(ts_content)
    print("Updated danang-places.data.ts successfully!")

if __name__ == "__main__":
    run()
