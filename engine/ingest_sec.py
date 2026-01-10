
import os
import json
import time
import requests
import re
from typing import Dict, Any, Optional, List
from bs4 import BeautifulSoup
from datetime import datetime

class SECIngestor:
    def __init__(self, data_dir: str = "data"):
        self.data_dir = data_dir
        self.sec_text_dir = os.path.join(data_dir, "sec_text")
        self.sec_cache_dir = os.path.join(data_dir, "sec_cache")
        self.user_agent = os.getenv("SEC_USER_AGENT")
        self.tickers_json_path = os.path.join(self.sec_cache_dir, "company_tickers.json")
        
        # Ensure directories exist
        os.makedirs(self.sec_text_dir, exist_ok=True)
        os.makedirs(self.sec_cache_dir, exist_ok=True)
        
    def _headers(self):
        if not self.user_agent:
            # Return None to signal caller to warn user, or return a clearly invalid one
            # But specific requirement says "warn but continue" (implied logic), 
            # actually requests will fail 403 usually if no proper UA.
            # We will try to use a placeholder if missing but add a warning in response.
            return {"User-Agent": "UnknownUser unknow@example.com"}
        return {"User-Agent": self.user_agent}

    def _requests_get(self, url: str) -> requests.Response:
        """
        Request wrapper with exponential backoff for 429/503.
        """
        retries = 3
        backoff = 1.0
        headers = self._headers()
        
        for i in range(retries):
            try:
                resp = requests.get(url, headers=headers, timeout=10)
                if resp.status_code in [429, 503]:
                    time.sleep(backoff)
                    backoff *= 2
                    continue
                return resp
            except requests.RequestException as e:
                if i == retries - 1:
                    raise e
                time.sleep(backoff)
                backoff *= 2
        return requests.Response() # dummy failure

    def _get_cik(self, ticker: str) -> Optional[str]:
        """
        Resolves Ticker -> CIK.
        Prioritizes local `company_tickers.json` to prevent unnecessary SEC calls.
        """
        ticker = ticker.upper()
        
        # 1. Try Cache First (Always)
        if os.path.exists(self.tickers_json_path):
            try:
                with open(self.tickers_json_path, 'r', encoding='utf-8') as f:
                    tickers_map = json.load(f)
                    
                # Search in cache
                for _, val in tickers_map.items():
                    if val.get("ticker") == ticker:
                        return str(val.get("cik_str")).zfill(10)
            except Exception as e:
                print(f"Cache read error: {e}")
        
        # 2. If not found, Fetch Fresh
        print(f"Fetching company_tickers.json for {ticker} from SEC...")
        retries = 3
        backoff = 2.0
        
        for i in range(retries):
            try:
                resp = self._requests_get("https://www.sec.gov/files/company_tickers.json")
                if resp.status_code == 200:
                    raw_data = resp.json()
                    # Save to cache
                    with open(self.tickers_json_path, 'w', encoding='utf-8') as f:
                        json.dump(raw_data, f)
                    
                    # Search again
                    for _, val in raw_data.items():
                        if val.get("ticker") == ticker:
                            return str(val.get("cik_str")).zfill(10)
                    # If we downloaded but didn't find it, break and return None (invalid ticker?)
                    break
                else:
                    print(f"Attempt {i+1} failed with status {resp.status_code}")
                    time.sleep(backoff)
                    backoff *= 2
            except Exception as e:
                print(f"Error fetching tickers (Attempt {i+1}): {e}")
                time.sleep(backoff)
                backoff *= 2
            
        return None

    def get_latest_filing_text(self, ticker: str) -> Dict[str, Any]:
        """
        Main entry point.
        Finds latest 10-K/20-F, downloads, parses, and returns text.
        """
        if not self.user_agent:
            return {
                "status": "warning",
                "sec_text": "",
                "warnings": ["SEC_USER_AGENT not set in .env. Cannot fetch live data."]
            }

        cik = self._get_cik(ticker)
        if not cik:
            return {
                "status": "error",
                "sec_text": "",
                "warnings": [f"Could not resolve CIK for ticker {ticker}."]
            }

        # Fetch Submissions
        url = f"https://data.sec.gov/submissions/CIK{cik}.json"
        try:
            resp = self._requests_get(url)
            if resp.status_code != 200:
                return {
                    "status": "error",
                    "sec_text": "",
                    "warnings": [f"Failed to fetch submissions for CIK {cik}. Status: {resp.status_code}"]
                }
            submissions = resp.json()
        except Exception as e:
            return {
                "status": "error",
                "sec_text": "",
                "warnings": [f"Error fetching submissions: {str(e)}"]
            }

        # Identify latest 10-K or 20-F
        filings = submissions.get("filings", {}).get("recent", {})
        if not filings:
            return {"status": "error", "sec_text": "", "warnings": ["No filings found."]}

        accession_number = None
        primary_document = None
        form_type = None
        report_date = None

        # Iterate to find a valid 10-K/20-F with sufficient text
        # Limit to recent 3 filings to avoid indefinite scanning
        
        found_text = None
        found_meta = None
        
        count = len(filings.get("accessionNumber", []))
        # Scan up to 5 recent filings
        scan_limit = min(count, 5)
        
        for i in range(scan_limit):
            form = filings["form"][i]
            if form in ["10-K", "20-F", "40-F"]:
                accession_number = filings["accessionNumber"][i]
                primary_document = filings["primaryDocument"][i]
                form_type = form
                report_date = filings["reportDate"][i]
                
                # Try to process this filing
                clean_accession = accession_number.replace("-", "")
                cache_text_filename = f"{ticker}_{clean_accession}.txt"
                cache_text_path = os.path.join(self.sec_text_dir, cache_text_filename)
                
                # Check cache first
                text_content = ""
                if os.path.exists(cache_text_path):
                     try:
                        with open(cache_text_path, "r", encoding="utf-8") as f:
                            text_content = f.read()
                     except:
                        pass
                
                # If not cached or empty, fetch
                if not text_content or len(text_content) < 100:
                    doc_url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{clean_accession}/{primary_document}"
                    print(f"Fetching 10-K from {doc_url}...")
                    try:
                        resp = self._requests_get(doc_url)
                        if resp.status_code == 200:
                            soup = BeautifulSoup(resp.content, "lxml")
                            for script in soup(["script", "style"]):
                                script.extract()
                            raw_text = soup.get_text(separator="\n")
                            # Normalize
                            lines = (line.strip() for line in raw_text.splitlines())
                            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
                            text_content = '\n'.join(chunk for chunk in chunks if chunk)
                            
                            # Cache it
                            with open(cache_text_path, "w", encoding="utf-8") as f:
                                f.write(text_content)
                    except Exception as e:
                        print(f"Failed to fetch filing {accession_number}: {e}")
                        continue

                # Validate content length
                if len(text_content) > 1000:
                    found_text = text_content
                    found_meta = {
                        "ticker": ticker,
                        "cik": cik,
                        "accession": accession_number,
                        "form": form_type,
                        "date": report_date,
                        "url": f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{clean_accession}/{primary_document}"
                    }
                    # Save meta
                    meta_path = os.path.join(self.sec_cache_dir, f"{ticker}_{clean_accession}.json")
                    with open(meta_path, "w", encoding="utf-8") as f:
                        json.dump(found_meta, f)
                    break # Success
                else:
                    print(f"Filing {accession_number} text too short ({len(text_content)} chars). Trying next...")

        if not found_text:
             return {"status": "error", "sec_text": "", "warnings": ["Could not retrieve valid 10-K text (too short or missing)."]}

        return {
            "status": "success",
            "source": "live_sec",
            "sec_text": found_text[:50000], 
            "warnings": []
        }
