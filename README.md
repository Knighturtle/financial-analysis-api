# Semiconductor Financial Analysis (2018–2025) with Forecasts (2026–2028)

This project provides a comparative financial analysis of **AMD, Intel, and NVIDIA** over the period 2018–2025, with simple statistical forecasts extending through 2028. The study focuses on three key indicators—**revenue, net income, and profit margin**—to highlight differences in business performance and long-term competitiveness among major semiconductor companies.

## 📊 Objectives
- Evaluate historical profitability and growth dynamics of AMD, Intel, and NVIDIA.  
- Compute and compare **average profit margins** and **CAGR (Compound Annual Growth Rates)**.  
- Handle cases where Net Income is negative by reporting **“N/A”** for CAGR to ensure methodological transparency.  
- Generate **forecast scenarios (2026–2028)** using log-linear revenue trends and robust margin estimates, with **80% prediction intervals**.  

## 🔑 Key Findings
- **NVIDIA** has achieved structural margin expansion (50%+ by FY2025) and hyper-growth in revenue. Forecasts extend this trajectory, reflecting its leadership in the AI-driven semiconductor cycle.  
- **AMD** maintains mid-teens profitability and steady revenue, but lacks NVIDIA’s operating leverage.  
- **Intel** faces revenue contraction and negative profitability. Net Income CAGR is reported as **N/A** due to non-positive endpoints. Forecasts suggest limited recovery unless margins stabilize.  

## 📂 Repository Structure
- `notebooks/semiconductor_analysis.ipynb` — Jupyter Notebook containing full analysis and visualizations  
- `figures/` — Exported charts (profit margin trends, revenue trajectories, forecasts with intervals)  
- `requirements.txt` — Python dependencies  

## ⚙️ How to Run
```bash
python -m venv .venv
# Activate venv...
pip install -r requirements.txt
jupyter notebook notebooks/semiconductor_analysis.ipynb
```

---
📈 Methods

Revenue forecasts: log-linear regression with residual-based prediction intervals.

Profit margin forecasts: robust linear trends or trailing averages, clipped to [-50%, 80%].

Net income forecasts: product of revenue and profit margin forecasts.

📝 Notes

CAGR is computed only when both endpoints are positive; otherwise, it is reported as N/A.

Forecasts are statistical and do not incorporate exogenous market risks such as supply chain disruptions, capital expenditures, or geopolitical shocks.

## Example Output

### Profit Margin (2018–2025)
![Profit Margin (2018–2025)](figs/cmp_profit_margin_2018_2025.png)

### Revenue (2018–2025)
![Revenue (2018–2025)](figs/cmp_revenue_2018_2025.png)

**FY2025 Profit Margin (Bar)**
![FY2025 Profit Margin](figures/pm_fy2025_bar.png)

**Profit Margin Forecast (2026–2028, 80% PI)**
![Profit Margin Forecast](figures/pm_forecast.png)

**Revenue Forecast (2026–2028, 80% PI)**
![Revenue Forecast](figures/revenue_forecast.png)



---

**Author**
This project was fully implemented by **Knight Lin** to demonstrate skills in data analysis, forecasting, and visualization.

