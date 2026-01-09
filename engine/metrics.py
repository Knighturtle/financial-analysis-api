import pandas as pd
import numpy as np
import os
from typing import Dict, Any

class FinancialMetrics:
    def __init__(self, data_dir: str = "data"):
        self.data_dir = data_dir

    def calculate_metrics(self, ticker: str) -> Dict[str, Any]:
        """
        Calculates key financial metrics from CSV data.
        Returns a dictionary with current values and historical trends.
        """
        ticker = ticker.upper()
        # Assume standard structure: data/{ticker}_financials.csv or similar
        # Based on user context, often it's a single big CSV or per-ticker CSV.
        # Let's assume per-ticker CSV for robustness or a main CSV.
        # User prompt mentions 'data/financials_sec.csv' in ingest, so let's try to find financial data there.
        
        # Strategy: Look for specific ticker file first, else fallback to master file if exists.
        # Simplification for this task: Check data/financials.csv or similar pattern.
        # User prompt said: "data/ のCSVから主要指標（YoY, CAGR, profit margin等）計算"
        
        # Let's try to load from a master financials file which seems implied by "financials_sec.csv" availability
        # OR look for {ticker}.csv
        
        file_path = os.path.join(self.data_dir, "financials_sec.csv")
        if not os.path.exists(file_path):
             return {"error": "Financial data file not found", "metrics": {}}

        try:
            df = pd.read_csv(file_path)
            # Filter by ticker if column exists
            if 'Ticker' in df.columns:
                company_df = df[df['Ticker'] == ticker].copy()
            elif 'Symbol' in df.columns:
                company_df = df[df['Symbol'] == ticker].copy()
            else:
                 # If no ticker column, assume the file IS the ticker data (less likely for "financials_sec.csv")
                 company_df = df.copy()

            if company_df.empty:
                return {"error": f"No financial data found for {ticker}", "metrics": {}}

            # Sort by date/year if available
            if 'Year' in company_df.columns:
                company_df = company_df.sort_values('Year')
            
            # Helper to get series
            def get_series(col_name):
                # Try partial matching if exact col missing
                if col_name in company_df.columns:
                    return company_df[col_name]
                matches = [c for c in company_df.columns if col_name.lower() in c.lower()]
                if matches:
                    return company_df[matches[0]]
                return pd.Series(dtype=float)

            revenue = get_series("Revenue")
            net_income = get_series("Net Income")
            op_income = get_series("Operating Income")
            equity = get_series("Shareholders Equity") # Or 'Total Equity'
            op_cash_flow = get_series("Operating Cash Flow")
            capex = get_series("Capital Expenditure")
            
            latest_idx = company_df.index[-1]
            
            # --- Metrics Calculation ---
            
            # 1. Net Margin (Net Income / Revenue)
            try:
                net_margin = (net_income.iloc[-1] / revenue.iloc[-1]) if revenue.iloc[-1] != 0 else 0
            except:
                net_margin = 0.0

            # 2. Operating Margin
            try:
                op_margin = (op_income.iloc[-1] / revenue.iloc[-1]) if revenue.iloc[-1] != 0 else 0
            except:
                op_margin = 0.0

            # 3. ROE (Net Income / Equity)
            try:
                roe = (net_income.iloc[-1] / equity.iloc[-1]) if equity.iloc[-1] != 0 else 0
            except:
                roe = 0.0

            # 4. FCF (Op Cash Flow - CapEx)
            # Note: CapEx is often negative. FCF = OCF - (-CapEx) or OCF - CapEx depending on sign convention.
            # Assuming standard accounting where CapEx is absolute or negative. 
            # Safest: OCF - abs(CapEx)
            try:
                ocf_val = op_cash_flow.iloc[-1]
                capex_val = abs(capex.iloc[-1]) if not capex.empty else 0
                fcf = ocf_val - capex_val
            except:
                fcf = 0.0

            # 5. Revenue CAGR (3 years if possible)
            cagr = 0.0
            if len(revenue) >= 4:
                try:
                    start_rev = revenue.iloc[-4]
                    end_rev = revenue.iloc[-1]
                    if start_rev > 0 and end_rev > 0:
                        cagr = (end_rev / start_rev) ** (1/3) - 1
                except:
                    pass
            elif len(revenue) > 1:
                # Fallback to YoY
                try:
                    start_rev = revenue.iloc[0]
                    end_rev = revenue.iloc[-1]
                    period = len(revenue) - 1
                    if start_rev > 0 and end_rev > 0:
                        cagr = (end_rev / start_rev) ** (1/period) - 1
                except:
                    pass

            return {
                "latest_year": int(company_df['Year'].iloc[-1]) if 'Year' in company_df.columns else "N/A",
                "revenue": float(revenue.iloc[-1]) if not revenue.empty else 0,
                "net_income": float(net_income.iloc[-1]) if not net_income.empty else 0,
                "net_margin": float(round(net_margin, 4)),
                "operating_margin": float(round(op_margin, 4)),
                "roe": float(round(roe, 4)),
                "fcf": float(fcf),
                "revenue_cagr_3yr": float(round(cagr, 4)),
                "history": company_df.to_dict(orient='records') # Return full history for forecasting
            }

        except Exception as e:
            return {"error": str(e), "metrics": {}}

