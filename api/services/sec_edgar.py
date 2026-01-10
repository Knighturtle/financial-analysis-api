
import os
import json
import time
import requests
from typing import Dict, Any, Optional

class SecService:
    def __init__(self):
        self.user_agent = os.getenv("SEC_USER_AGENT", "FinancialApp/1.0 (contact@example.com)")
        # Simple in-memory cache for CIKs to avoid repeated disk reads/requests in this session
        self.cik_cache = {}

    def _headers(self):
        return {"User-Agent": self.user_agent}

    def _requests_get(self, url: str) -> requests.Response:
        """
        Robust GET with retries and 429 backoff.
        """
        retries = 3
        backoff = 1.0
        for i in range(retries):
            try:
                resp = requests.get(url, headers=self._headers(), timeout=10)
                if resp.status_code == 429:
                    time.sleep(backoff)
                    backoff *= 2
                    continue
                return resp
            except requests.RequestException:
                time.sleep(backoff)
                backoff *= 2
        return requests.Response() # Return empty response object on failure

    def get_cik(self, ticker: str) -> Optional[str]:
        """
        Resolves Ticker -> CIK (10 digits).
        """
        ticker = ticker.upper()
        if ticker in self.cik_cache:
            return self.cik_cache[ticker]

        # 1. Fetch fresh company_tickers.json
        url = "https://www.sec.gov/files/company_tickers.json"
        resp = self._requests_get(url)
        if resp.status_code != 200:
            print(f"Error fetching company_tickers.json: {resp.status_code}")
            return None
        
        data = resp.json()
        for _, val in data.items():
            if val.get("ticker") == ticker:
                cik_str = str(val["cik_str"]).zfill(10)
                self.cik_cache[ticker] = cik_str
                return cik_str
        return None

    def get_latest_10k(self, ticker: str) -> Dict[str, Any]:
        """
        Orchestrates the fetch:
        1. Ticker -> CIK
        2. CIK -> Submissions -> Latest 10-K Accession
        3. Accession -> index.json -> Primary Document (.htm)
        4. Download HTML
        """
        cik = self.get_cik(ticker)
        if not cik:
            return {"error": "Ticker not found or CIK lookup failed.", "status": 404}

        # 2. Get Submissions
        url = f"https://data.sec.gov/submissions/CIK{cik}.json"
        resp = self._requests_get(url)
        if resp.status_code != 200:
            return {"error": f"SEC Submissions API error: {resp.status_code}", "status": 502}
        
        data = resp.json()
        filings = data.get("filings", {}).get("recent", {})
        
        accession = None
        report_date = None
        filing_date = None
        primary_doc = None
        
        # Find latest 10-K
        forms = filings.get("form", [])
        for i, form in enumerate(forms):
            if form == "10-K":
                accession = filings["accessionNumber"][i]
                report_date = filings["reportDate"][i]
                filing_date = filings["filingDate"][i]
                primary_doc = filings["primaryDocument"][i] # Often useful, but we'll double check index.json logic if strictly required, but primaryDocument usually works.
                # User requirement said: "index.jsonのdirectory.itemから .htm/.html を1つ選んで取得"
                # We will respect that requirement to be safe.
                break
        
        if not accession:
             return {"error": "No 10-K filings found for this company.", "status": 404}

        clean_accession = accession.replace("-", "")
        
        # 3. Get index.json to find the correct HTML file confidently
        index_url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{clean_accession}/index.json"
        resp = self._requests_get(index_url)
        if resp.status_code != 200:
             # Fallback: try constructing URL from primaryDocument if index.json fails?
             # But requirement is strict.
             return {"error": "Failed to fetch filing index.json.", "status": 502}

        index_data = resp.json()
        items = index_data.get("directory", {}).get("item", [])
        
        target_file = None
        for item in items:
            name = item.get("name", "")
            # Look for the primary report (usually ends in .htm and likely matches accession or is the main submission)
            # Simple heuristic: First .htm that is NOT an exhibit override if possible, 
            # but usually the first proper .htm is the main doc.
            if name.lower().endswith(".htm") or name.lower().endswith(".html"):
                target_file = name
                break
        
        if not target_file:
            return {"error": "No HTML document found in filing.", "status": 404}

        # 4. Download HTML
        html_url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{clean_accession}/{target_file}"
        resp = self._requests_get(html_url)
        if resp.status_code != 200:
             return {"error": "Failed to download 10-K HTML.", "status": 502}
        
        html_content = resp.text

        return {
            "status": 200,
            "data": {
                "ticker": ticker,
                "cik": cik,
                "filing_date": filing_date,
                "report_date": report_date,
                "accession": clean_accession,
                "html": html_content
            }
        }
