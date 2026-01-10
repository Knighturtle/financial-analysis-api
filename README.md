# Financial Analysis API 10-K Product

This is a production-ready API for financial analysis based on SEC 10-K filings and quantitative metrics.
It provides comprehensive insights including key financial metrics, forecasts, and risk assessments.

## Features

- **SEC Data Ingestion**: Reads 10-K text (local cache with CSV fallback).
- **Financial Metrics**: Calculates Revenue Growth, Net Margin, ROE, FCF, and more.
- **Forecasting**: Simple linear projection for future revenue.
- **AI Analysis**: Generates structured narrative analysis using OpenAI (falls back to rule-based template if Key is missing).

## Setup

1. **Install Dependencies**:

   ```powershell
   python -m pip install -r requirements.txt
   ```

2. **Environment Variables**:
   Copy `.env.example` to `.env` and set your `OPENAI_API_KEY`.

   ```powershell
   cp .env.example .env
   ```

   *Note: works without an API key in fallback mode.*

3. **Run Server**:

   ```powershell
   python -m uvicorn api.main:app --reload
   ```

## Usage

### Health Check

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

### Financial Analysis (/ask)

**PowerShell Example**:

```powershell
$body = @{
  ticker   = "NVDA"
  question = "Summarize the risks"
  mode     = "standard"
  use_ai   = $true
} | ConvertTo-Json

Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/ask -ContentType "application/json" -Body $body
```

**Curl Example**:

```bash
curl -X POST "http://127.0.0.1:8000/ask" \
     -H "Content-Type: application/json" \
     -d '{"ticker": "NVDA", "question": "Analyze risks", "use_ai": true}'
```

### Retrieve Latest 10-K (/sec/10k/latest)

Fetches the raw HTML of the most recent 10-K filing from SEC EDGAR.

**PowerShell Example**:

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/sec/10k/latest?ticker=NVDA"
```

**Curl Example**:

```bash
curl "http://127.0.0.1:8000/sec/10k/latest?ticker=NVDA"
```

### Analyze Latest 10-K (/sec/10k/analyze)

Performs AI-driven analysis on the latest 10-K filing.

**PowerShell Example**:

```powershell
$body = @{
  ticker   = "NVDA"
  focus    = "overview"
  use_ai   = $true
} | ConvertTo-Json

Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/sec/10k/analyze" -ContentType "application/json" -Body $body
```

**Curl Example**:

```bash
curl -X POST "http://127.0.0.1:8000/sec/10k/analyze" \
     -H "Content-Type: application/json" \
     -d '{"ticker": "NVDA", "focus": "overview", "use_ai": true}'
```

## Web UI Access

The project includes a user-friendly Web UI.

- **Home / Dashboard**: [http://127.0.0.1:8000/](http://127.0.0.1:8000/)
- **Demo Page** (Redirects to Home): [http://127.0.0.1:8000/demo](http://127.0.0.1:8000/demo)
- **API Documentation**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

> **Note**: If `use_ai` is enabled but the OpenAI Quota is exceeded, the generic fallback response will be shown. You can uncheck "Use AI Analysis" in the UI to perform a metrics-only analysis.

## Disclaimer

**Not investment advice.** This tool provides automated analysis for informational purposes only. Always verify data with official sources.
