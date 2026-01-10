from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import os
import sys
import asyncio
from dotenv import load_dotenv

# 1. Strict Env Load
load_dotenv(override=True)

# 2. Key Check (Prompt said: Print log but maybe fail? Wait, Prompt said "OPENAI_API_KEY が無い場合は即エラー表示" (Display error immediately if missing). 
# And "AI失敗時はダミー応答を返す" (Dummy response if AI fails). 
# But strict "OPENAI_API_KEY Missing" -> "Fail immediately" at startup.
if not os.getenv("OPENAI_API_KEY"):
    print("CRITICAL: OPENAI_API_KEY is missing. Server cannot start.")
    sys.exit(1)

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional, Dict, Any, List

# Import Engine Components
from engine.ingest_sec import SECIngestor
from engine.metrics import FinancialMetrics
from engine.forecast import Forecaster
from engine.ai_analysis import AIAnalyst

app = FastAPI(title="Financial Analysis API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Engine
sec_ingestor = SECIngestor()
metrics_engine = FinancialMetrics()
forecaster = Forecaster()
ai_analyst = AIAnalyst()

class AskRequest(BaseModel):
    ticker: str
    question: str
    mode: str = "standard"
    use_ai: bool = True

class AskResponse(BaseModel):
    status: str
    ticker: str
    mode: str
    ai_used: bool
    metrics: Dict[str, Any]
    forecast: Optional[Dict[str, Any]]
    sec_excerpt: str
    answer: Dict[str, str]
    warnings: List[str]

@app.on_event("startup")
async def startup_event():
    print("INFO: Server starting up. Environment loaded.")
    if os.getenv("OPENAI_API_KEY"):
         print(f"INFO: OPENAI_API_KEY detected (len={len(os.getenv('OPENAI_API_KEY'))})")

@app.get("/health")
def health_check():
    return {"status": "ok", "message": "Financial Analysis API is ready."}

@app.post("/ask", response_model=AskResponse)
async def ask_financial_question(req: AskRequest):
    """
    Main endpoint for financial analysis.
    Async enabled.
    """
    print(f"INFO: Processing /ask for {req.ticker}")
    warnings = []
    
    # 1. Ingest SEC Data (Run in threadpool to avoid blocking)
    try:
        sec_data = await asyncio.to_thread(sec_ingestor.get_latest_filing_text, req.ticker)
    except Exception as e:
        sec_data = {"status": "error", "warnings": [str(e)]}

    if sec_data.get("status") not in ["success", "warning"]:
         warnings.extend(sec_data.get("warnings", []))
    
    sec_text = sec_data.get("sec_text", "")
    
    # 2. Calculate Metrics
    metrics_res = metrics_engine.calculate_metrics(req.ticker)
    if "error" in metrics_res:
        warnings.append(metrics_res["error"])
        metrics = {}
    else:
        metrics = metrics_res

    # 3. Generate Forecast
    forecast = None
    if metrics:
        forecast = forecaster.generate_forecast(metrics)
        if not forecast:
            warnings.append("Insufficient data for forecasting.")

    # 4. AI Analysis (Async wrapper)
    use_ai_actual = False
    final_answer = {
        "Executive Summary": "N/A",
        "Key Metrics": "N/A",
        "Risks": "N/A",
        "Growth Drivers": "N/A",
        "Red Flags": "N/A",
        "Disclaimer": "Not investment advice."
    }

    if req.use_ai:
        try:
            print("INFO: Starting AI Analysis...")
            # Run blocking AI usage in threadpool
            analysis_result = await asyncio.to_thread(
                ai_analyst.analyze,
                ticker=req.ticker,
                question=req.question,
                metrics=metrics,
                forecast=forecast,
                sec_text=sec_text
            )
            
            final_answer.update(analysis_result)
            use_ai_actual = True
            print("INFO: AI Analysis Completed Successfully.")
            
        except Exception as e:
            print(f"ERROR: AI Analysis Failed: {e}")
            warnings.append(f"AI Failed: {str(e)}")
            # Fallback as requested
            final_answer["Executive Summary"] = "AI Analysis failed to generate. Please check logs/API key."
            # use_ai_actual remains False

    return AskResponse(
        status="success",
        ticker=req.ticker,
        mode=req.mode,
        ai_used=use_ai_actual,
        metrics=metrics,
        forecast=forecast,
        sec_excerpt=sec_text[:500] + "..." if len(sec_text) > 500 else sec_text,
        answer=final_answer,
        warnings=warnings
    )

@app.get("/")
async def serve_ui():
    return FileResponse("static/index.html")

@app.get("/demo")
def demo_redirect():
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/", status_code=302)

# Mount Static Files
app.mount("/static", StaticFiles(directory="static"), name="static")
