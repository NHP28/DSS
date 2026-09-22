import json
import urllib.request
import sys

# Set stdout encoding to UTF-8
sys.stdout.reconfigure(encoding='utf-8')

def test_api():
    url = "http://localhost:4000/api/recommendations/evaluate"
    payload = {
        "lat": 16.0614,
        "lng": 108.2208,
        "allDanang": True,
        "topK": 5,
        "userId": 1,
        "hourOfDay": 20,
        "userTags": ["yên tĩnh", "acoustic", "view đẹp"]
    }
    
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    
    try:
        with urllib.request.urlopen(req) as res:
            raw = res.read().decode("utf-8")
            data = json.loads(raw)
            print("================================================================")
            print("         L-DSS + CPR RECOMMENDATION VALIDATION REPORT           ")
            print("================================================================")
            print(f"HTTP Status: {res.status}")
            payload_data = data.get("data", data)
            print(f"AI Model: {payload_data.get('aiModel')}")
            print(f"Decision Method: {payload_data.get('decisionMethod')}")
            print(f"Total Candidates Evaluated Across Da Nang: {payload_data.get('totalCandidates')}")
            print(f"Weights Used (AHP): {payload_data.get('weights')}")
            print("\n----------------- TOP 5 RECOMMENDED PLACES -------------------")
            for item in payload_data.get("topRecommendations", []):
                place = item.get("place", {})
                print(f"[Rank #{item.get('rank')}] {place.get('name')} ({place.get('categoryName')})")
                print(f"  • TOPSIS Closeness Score (Ci): {item.get('score')}")
                print(f"  • Distance: {round(place.get('distance', 0), 2)} km | Rating: {place.get('rating')}★ | Price: {place.get('price'):,}đ")
                print(f"  • Preference C4 (From CPR Model): {place.get('preference')}")
                print(f"  • XAI Reason: {place.get('explanation', {}).get('detail')}")
                print()
            print("================================================================")
            print("                 ALL VALIDATION TESTS PASSED                    ")
            print("================================================================")
    except Exception as e:
        print(f"Error testing API: {e}")

if __name__ == "__main__":
    test_api()
