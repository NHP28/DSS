import urllib.request
import urllib.parse
import json

query = """[out:json][timeout:25];
(
  node["amenity"="cafe"](15.90,108.05,16.20,108.35);
);
out body;
"""

servers = [
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
    "https://overpass-api.de/api/interpreter"
]

data = ("data=" + urllib.parse.quote(query)).encode("utf-8")

for url in servers:
    print(f"Testing {url}...")
    try:
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "User-Agent": "DaNangDSSResearch/1.0",
                "Accept": "*/*"
            }
        )
        with urllib.request.urlopen(req, timeout=15) as res:
            res_data = json.loads(res.read().decode("utf-8"))
            elements = res_data.get("elements", [])
            print(f" SUCCESS! Found elements: {len(elements)}")
            if elements:
                name = elements[0].get("tags", {}).get("name", "Unknown")
                print(" Sample 1:", name.encode("utf-8", "ignore").decode("utf-8"))
            break
    except Exception as e:
        print(f" Failed {url}: {e}")
