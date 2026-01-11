# SEC XBRL Financial Analysis API

A local-first financial analysis tool that fetches **XBRL data** directly from SEC EDGAR (companyfacts), calculates key metrics (Revenue, FCF, ROE, etc.), and generates AI-powered reports using **Ollama** (Local LLM).

## Features

- **SEC XBRL Integration**: Fetches standardized financial data (US-GAAP) from [SEC EDGAR API](https://www.sec.gov/edgar/sec-api-documentation).
- **Auto-Metrics**: Calculates Revenue, Net Margin, Operating Cash Flow, Capex, Free Cash Flow (FCF), ROE, and CAGR.
- **Local AI Analysis**: Generates professional Japanese/English reports using **Ollama** (supports `qwen2.5`, `llama3`, etc.).
- **No Cloud Required**: Designed to run 100% locally (except for SEC data fetching).

## Setup (Local)

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

## Setup (Docker)

If you prefer running the API in a container using **Docker Compose**:

1. **Prerequisites**
   - Docker Desktop installed (Windows/Mac/Linux).
   - **Ollama** running on the HOST machine.

     ```powershell
     ollama serve
     ollama pull qwen2.5:7b
     ```

   - `.env` file must exist with valid `SEC_USER_AGENT`.

2. **Start API**
   This builds the image and starts the `api` service.

   ```powershell
   docker compose up --build -d
   ```

   *Note: Using `host.docker.internal` allows the container to talk to your host's Ollama at port 11434.*

3. **Verify**
   Run the verification script (PowerShell):

   ```powershell
   ./scripts/docker_verify.ps1
   ```

   Or manually:

   ```powershell
   curl http://localhost:8000/health
   ```

4. **Stop**

   ```powershell
   docker compose down
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

## Windows (PS) Quick Test

Run these commands in PowerShell to verify your local setup:

1. **Check Health**:

   ```powershell
   Invoke-RestMethod "http://127.0.0.1:8000/health"
   # OR
   curl.exe "http://127.0.0.1:8000/health"
   ```

2. **Get Metrics (XBRL)**:

   ```powershell
   Invoke-RestMethod "http://127.0.0.1:8000/sec/xbrl/metrics?ticker=AAPL&years=4"
   ```

3. **Run AI Analysis**:

   ```powershell
   Invoke-RestMethod -Uri "http://127.0.0.1:8000/ai/analyze/xbrl" `
     -Method Post `
     -ContentType "application/json" `
     -Body '{"ticker": "AAPL"}'
   ```

## Disclaimer

This tool uses public SEC data. Not investment advice.
