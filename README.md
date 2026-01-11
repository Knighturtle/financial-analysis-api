# SEC XBRL Financial Analysis API

A local-first financial analysis tool that fetches **XBRL data** directly from SEC EDGAR (companyfacts), calculates key metrics (Revenue, FCF, ROE, etc.), and generates AI-powered reports using **Ollama** (Local LLM).

## Features

- **SEC XBRL Integration**: Fetches standardized financial data (US-GAAP) from [SEC EDGAR API](https://www.sec.gov/edgar/sec-api-documentation).
- **Auto-Metrics**: Calculates Revenue, Net Margin, Operating Cash Flow, Capex, Free Cash Flow (FCF), ROE, and CAGR.
- **Local AI Analysis**: Generates professional Japanese/English reports using **Ollama** (supports `qwen2.5`, `llama3`, etc.).
- **No Cloud Required**: Designed to run 100% locally (except for SEC data fetching).

## Setup

1. **Install Dependencies**

   ```powershell
   pip install -r requirements.txt
   ```

2. **Configure Environment**
   Copy `.env.example` to `.env`.

   **Critical**: Set `SEC_USER_AGENT` to "YourName <contact@email.com>" as required by SEC API.

   ```ini
   SEC_USER_AGENT=YourName contact@example.com
   OLLAMA_URL=http://127.0.0.1:11434
   LLM_PROFILE=finance
   OUTPUT_LANG=ja
   ```

3. **Install Ollama Model**

   ```powershell
   ollama pull qwen2.5:7b
   ```

4. **Run Server**

   ```powershell
   python -m uvicorn src.main:app --reload
   ```

## API Usage

### 1. Get Financial Metrics (XBRL)

Fetches raw numerical data.

```bash
curl "http://127.0.0.1:8000/sec/xbrl/metrics?ticker=AAPL&years=4"
```

### 2. AI Analysis (End-to-End)

Fetches metrics and generates an AI report.

**PowerShell Example**:

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/ai/analyze/xbrl" `
  -Method Post `
  -ContentType "application/json" `
  -Body '{"ticker": "NVDA"}'
```

Returns JSON with `executive_summary`, `key_metrics_commentary`, `risks_summary`, etc.

## Disclaimer

This tool uses public SEC data. Not investment advice.
