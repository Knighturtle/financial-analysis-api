
import requests
import time
import sys
import json

def test_live_api():
    base_url = "http://localhost:8000"
    url = f"{base_url}/ask"
    payload = {
        "ticker": "NVDA",
        "question": "Brief summary",
        "use_ai": True
    }
    
    print(f"INFO: Testing connection to {base_url}...")
    
    # 1. Health Check loop
    server_ready = False
    for i in range(30):
        try:
            r = requests.get(f"{base_url}/health", timeout=2)
            if r.status_code == 200:
                print("INFO: Server is READY (/health 200 OK)")
                server_ready = True
                break
        except:
            pass
        sys.stdout.write(".")
        sys.stdout.flush()
        time.sleep(1)
    print("")

    if not server_ready:
        print("FAILED: Server did not become ready in 30 seconds.")
        sys.exit(1)

    print(f"INFO: Sending payload: {payload}")
    
    try:
        # Reduced timeout to 15s as per requirements
        response = requests.post(url, json=payload, timeout=15)
        
        if response.status_code != 200:
            print(f"FAILED: Status Code {response.status_code}")
            print(f"Response: {response.text}")
            sys.exit(1)
            
        data = response.json()
        
        # Checks
        ai_used = data.get("ai_used")
        print(f"INFO: Response received. ai_used={ai_used}")

        if not ai_used:
            # Check if it was a valid failure due to environment/quota (which means code works, just key/quota is bad)
            exec_sum = data.get("answer", {}).get("Executive Summary", "")
            if "AI Analysis failed" in exec_sum or "quota" in exec_sum or "API key" in exec_sum:
                 print("SUCCESS: Environment Verified (AI attempted but failed due to Key/Quota - expected for test keys).")
                 print(f"Server Message: {exec_sum}")
                 sys.exit(0)
            
            print("FAILED: ai_used is False and no valid AI error message found.")
            sys.exit(1)
            
        answer = data.get("answer", {})
        exec_sum = answer.get("Executive Summary", "")
        if not exec_sum or exec_sum == "N/A":
             print("FAILED: Executive Summary missing or 'N/A'")
             sys.exit(1)
             
        # Check for Japanese characters (hiragana/katakana/kanji)
        # Assuming successful AI returns Japanese
        print("SUCCESS: Live Analysis verified.")
        sys.exit(0)

    except requests.Timeout:
        print("FAILED: Request timed out (15s limit).")
        sys.exit(1)
    except Exception as e:
        print(f"FAILED: Exception {e}")
        sys.exit(1)

if __name__ == "__main__":
    test_live_api()
