import urllib.request
import urllib.parse
import json

def fetch_danang_places(limit=300):
    # Bounding box của Đà Nẵng: 15.90 -> 16.25 Vĩ độ Bắc, 108.05 -> 108.40 Kinh độ Đông
    query = f"""
    [out:json][timeout:45];
    (
      node["amenity"~"cafe|restaurant|fast_food|bar"](15.90,108.05,16.25,108.40);
      node["tourism"~"hotel|attraction|viewpoint|museum|guest_house|resort"](15.90,108.05,16.25,108.40);
    );
    out body {limit};
    """
    
    url = "https://overpass-api.de/api/interpreter"
    data = ("data=" + urllib.parse.quote(query)).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"User-Agent": "DaNangDSSBot/1.0 (academic research)"}
    )
    
    try:
        with urllib.request.urlopen(req, timeout=45) as res:
            res_data = json.loads(res.read().decode("utf-8"))
            elements = res_data.get("elements", [])
            print(f"Total places received from OSM: {len(elements)}")
            valid_places = []
            for el in elements:
                tags = el.get("tags", {})
                name = tags.get("name") or tags.get("name:en") or tags.get("name:vi")
                if not name:
                    continue
                valid_places.append({
                    "name": name,
                    "lat": el.get("lat"),
                    "lng": el.get("lon"),
                    "type": tags.get("amenity") or tags.get("tourism"),
                    "street": tags.get("addr:street", ""),
                    "housenumber": tags.get("addr:housenumber", "")
                })
            print(f"Total named places: {len(valid_places)}")
            for p in valid_places[:10]:
                print(f" - {p['name']} ({p['type']}) @ {p['lat']}, {p['lng']}")
            return valid_places
    except Exception as e:
        print(f"Error fetching from OSM: {e}")
        return []

if __name__ == "__main__":
    fetch_danang_places(200)
