import requests
import json

url = "http://127.0.0.1:8000/ai/analyze"
payload = {
    "ticker": "AAPL",
    "metrics": {
        "revenue": 383000000000,
        "net_margin": 0.25,
        "revenue_cagr_3yr": 0.08
    }
}

print(f"Sending POST to {url}...")
try:
    res = requests.post(url, json=payload, timeout=300)
    print(f"Status Code: {res.status_code}")
    print("Response Body:")
    print(json.dumps(res.json(), indent=2, ensure_ascii=False))
except Exception as e:
    print(f"Error: {e}")
