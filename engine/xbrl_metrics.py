
import os
import json
import time
import requests
import pandas as pd
from typing import Dict, Any, List, Optional
from datetime import datetime

class XBRLMetrics:
    def __init__(self, data_dir: str = "data"):
        self.user_agent = os.getenv("SEC_USER_AGENT")
        self.cache_dir = os.path.join(data_dir, "sec_xbrl_cache")
        os.makedirs(self.cache_dir, exist_ok=True)
        
        # We can reuse the company_tickers.json cache logic or rely on independent resolution
        self.tickers_path = os.path.join(data_dir, "sec_cache", "company_tickers.json")

    def _headers(self):
        return {"User-Agent": self.user_agent or "UnknownUser contact@example.com"}

    def _get_cik(self, ticker: str) -> Optional[str]:
        # Simple lookup using locally cached tickers if available, else fetch
        # For simplicity in this standalone module, let's try to load the common cache file
        ticker = ticker.upper()
        if os.path.exists(self.tickers_path):
            with open(self.tickers_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                for _, val in data.items():
                    if val.get("ticker") == ticker:
                        return str(val.get("cik_str")).zfill(10)
        
        # Fallback fetch
        try:
            r = requests.get("https://www.sec.gov/files/company_tickers.json", headers=self._headers())
            if r.status_code == 200:
                data = r.json()
                # Save it
                os.makedirs(os.path.dirname(self.tickers_path), exist_ok=True)
                with open(self.tickers_path, "w", encoding="utf-8") as f:
                    json.dump(data, f)
                
                for _, val in data.items():
                    if val.get("ticker") == ticker:
                        return str(val.get("cik_str")).zfill(10)
        except:
            pass
        return None

    def get_company_facts(self, ticker: str) -> Dict:
        """
        Fetches companyfacts JSON from SEC. Uses local disk cache.
        """
        cik = self._get_cik(ticker)
        if not cik:
            raise ValueError(f"CIK not found for {ticker}")

        cache_file = os.path.join(self.cache_dir, f"{ticker}_facts.json")
        
        # Check cache (1 day TTL)
        if os.path.exists(cache_file):
            mtime = os.path.getmtime(cache_file)
            if (time.time() - mtime) < 86400:
                with open(cache_file, "r", encoding="utf-8") as f:
                    return json.load(f)

        # Download
        url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
        resp = requests.get(url, headers=self._headers(), timeout=20)
        if resp.status_code != 200:
            raise Exception(f"Failed to fetch XBRL facts: {resp.status_code}")
        
        data = resp.json()
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
            
        return data

    def extract_metrics(self, ticker: str, years: int = 4) -> Dict[str, Any]:
        """
        Extracts key metrics from XBRL data for the last N years (aggregated annual).
        """
        try:
            raw = self.get_company_facts(ticker)
        except Exception as e:
            return {"error": str(e), "metrics": {}}

        us_gaap = raw.get("facts", {}).get("us-gaap", {})
        
        # Metric Definitions (Tag list)
        tags_map = {
            "revenue": ["Revenues", "SalesRevenueNet", "RevenueFromContractWithCustomerExcludingAssessedTax", "RevenueFromContractWithCustomerIncludingAssessedTax"],
            "net_income": ["NetIncomeLoss", "ProfitLoss"],
            "operating_cash_flow": ["NetCashProvidedByUsedInOperatingActivities"],
            "capex": ["PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsToAcquireProductiveAssets"],
            "equity": ["StockholdersEquity", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"]
        }
        
        # Helper to extract annual series
        series_data = {}
        for metric, tags in tags_map.items():
            best_series = {}
            max_year_found = 0
            
            for tag in tags:
                if tag not in us_gaap:
                    continue
                    
                units = us_gaap[tag].get("units", {})
                # usually USD
                for unit_name, records in units.items():
                    # Parse this series
                    current_series = {}
                    for rec in records:
                        # 1. Standard: 'frame' attribute (CYxxxx)
                        if "frame" in rec and len(rec["frame"]) == 6 and rec["frame"].startswith("CY"):
                            try:
                                year = int(rec["frame"][2:])
                                current_series[year] = rec["val"]
                                continue
                            except:
                                pass
                        
                        # 2. Fallback: Form 10-K
                        if rec.get("form") == "10-K" and "end" in rec:
                             try:
                                end_dt = datetime.strptime(rec["end"], "%Y-%m-%d")
                                if end_dt.year not in current_series:
                                    current_series[end_dt.year] = rec["val"]
                             except:
                                pass
                    
                    # Compare with best_series
                    if current_series:
                        curr_max = max(current_series.keys())
                        if curr_max > max_year_found:
                            max_year_found = curr_max
                            best_series = current_series
                            
            series_data[metric] = best_series

        # Determine available years (sort desc)
        # Find common years or just max years across revenue
        rev_years = sorted(series_data["revenue"].keys(), reverse=True)
        target_years = rev_years[:years]
        
        dashboard_metrics = {
            "ticker": ticker,
            "currency": "USD",
            "years": target_years,
            "data": {}
        }
        
        # Build Table
        for y in target_years:
            rev = series_data["revenue"].get(y)
            ni = series_data["net_income"].get(y)
            ocf = series_data["operating_cash_flow"].get(y)
            capex = series_data["capex"].get(y, 0) # default 0 if null
            equity = series_data["equity"].get(y)
            
            # Calculations
            net_margin = (ni / rev) if (ni is not None and rev) else None
            fcf = (ocf - capex) if (ocf is not None) else None
            roe = (ni / equity) if (ni is not None and equity) else None
            
            dashboard_metrics["data"][y] = {
                "revenue": rev,
                "net_income": ni,
                "net_margin": net_margin,
                "operating_cash_flow": ocf,
                "capex": web_capex_sign_fix(capex), # usually positive in raw but conceptually negative
                "fcf": fcf,
                "roe": roe
            }

        # CAGR (3yr)
        dashboard_metrics["revenue_cagr_3yr"] = None
        
        if len(target_years) > 0:
             latest = target_years[0]
             # We need data for (latest - 3)
             past_3 = latest - 3
             
             # Check if we have revenue for both years
             start_rev = series_data["revenue"].get(past_3)
             end_rev = series_data["revenue"].get(latest)
             
             if start_rev is not None and end_rev is not None and start_rev > 0 and end_rev > 0:
                 try:
                     cagr = (end_rev / start_rev) ** (1/3) - 1
                     dashboard_metrics["revenue_cagr_3yr"] = cagr
                 except Exception:
                     pass
        
        return dashboard_metrics

def web_capex_sign_fix(val):
    return val
