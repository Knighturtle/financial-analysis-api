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
        Uses local cache `company_tickers.json` if available, else fetches from SEC.
        """
        ticker = ticker.upper()
        
        # Check cache freshness (e.g. 1 day) - simpler: just load if exists
        tickers_map = {}
        if os.path.exists(self.tickers_json_path):
            try:
                with open(self.tickers_json_path, 'r', encoding='utf-8') as f:
                    tickers_map = json.load(f)
            except:
                pass
        
        # Look up in cache
        # Structure of company_tickers.json from SEC is { "0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."}, ... }
        # Transform to { "AAPL": 320193, ... } for easier lookup if needed, or just iterate.
        # But for efficiency let's see if we can find it.
        
        cik = None
        # Quick search in cached map structure
        # If map is raw SEC format dict of dicts
        for _, val in tickers_map.items():
            if val.get("ticker") == ticker:
                return str(val.get("cik_str")).zfill(10)

        # If not found or no cache, fetch
        print(f"Fetching company_tickers.json for {ticker}...")
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
        except Exception as e:
            print(f"Error fetching tickers: {e}")
            
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

        # Iterate safely
        count = len(filings.get("accessionNumber", []))
        for i in range(count):
            form = filings["form"][i]
            if form in ["10-K", "20-F", "40-F"]:
                accession_number = filings["accessionNumber"][i]
                primary_document = filings["primaryDocument"][i] # Usually exact filename
                form_type = form
                report_date = filings["reportDate"][i]
                break
        
        if not accession_number:
             return {"status": "not_found", "sec_text": "", "warnings": ["No 10-K/20-F/40-F found in recent filings."]}

        # Check Cache
        clean_accession = accession_number.replace("-", "")
        # SEC uses formatted accession in URL, but dashed in JSON usually (or vice versa).
        # JSON has dashed: 0000320193-23-000106
        # URL needs dashed: data/320193/000032019323000106/ (No, URL uses dashed usually if accessing archives generic, 
        # BUT for index.json lookup it is different. 
        # Standard URL: https://www.sec.gov/Archives/edgar/data/{cik}/{clean_accession}/{primary_doc}  <-- Note: clean accession (no dashes)
        
        cache_text_filename = f"{ticker}_{clean_accession}.txt"
        cache_text_path = os.path.join(self.sec_text_dir, cache_text_filename)
        
        if os.path.exists(cache_text_path):
            try:
                with open(cache_text_path, "r", encoding="utf-8") as f:
                    return {
                        "status": "success",
                        "source": "cache",
                        "sec_text": f.read(),
                        "warnings": []
                    }
            except:
                pass # Proceed to fetch

        # Fetch HTML
        # URL Construction
        # https://www.sec.gov/Archives/edgar/data/{cik}/{clean_accession}/{primary_document}
        # Note: primaryDocument from submissions json usually works directly.
        
        doc_url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{clean_accession}/{primary_document}"
        
        try:
            resp = self._requests_get(doc_url)
            if resp.status_code != 200:
                return {"status": "error", "sec_text": "", "warnings": [f"Failed to download filing HTML. Status: {resp.status_code}"]}
            
            html_content = resp.content
            
            # Parse HTML to Text
            soup = BeautifulSoup(html_content, "lxml")
            
            # Simple cleanup
            for script in soup(["script", "style"]):
                script.extract()
            
            text = soup.get_text(separator="\n")
            
            # Normalize whitespace
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            clean_text = '\n'.join(chunk for chunk in chunks if chunk)
            
            # Limit size (e.g. 50k chars for AI context fitting optimization, or keep full locally)
            # Let's keep full locally, but return truncated if needed? 
            # Requirement says "save to UTF-8", "return text to ai_analysis"
            
            with open(cache_text_path, "w", encoding="utf-8") as f:
                f.write(clean_text)
            
            # Save Metadata
            meta_path = os.path.join(self.sec_cache_dir, f"{ticker}_{clean_accession}.json")
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump({
                    "ticker": ticker,
                    "cik": cik,
                    "accession": accession_number,
                    "form": form_type,
                    "date": report_date,
                    "url": doc_url
                }, f)

            return {
                "status": "success",
                "source": "live_sec",
                "sec_text": clean_text[:20000], # Return first 20k chars for analysis to avoid huge payloads internally
                "warnings": []
            }
            
        except Exception as e:
            return {"status": "error", "sec_text": "", "warnings": [f"Error processing filing: {str(e)}"]}
