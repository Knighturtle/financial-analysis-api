
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Dict, Any, Optional
import sys
import os
import traceback
import logging

# Ensure engine can be imported if running from root
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from engine.ai_analysis import AIAnalyst
from engine.xbrl_metrics import XBRLMetrics

# Configure Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI(title="SEC XBRL Financial Analysis API")

# Initialize Engines
try:
    analyst = AIAnalyst()
    xbrl_engine = XBRLMetrics()
    logger.info("Engines initialized successfully.")
except Exception as e:
    logger.warning(f"Engine initialization failed: {e}")
    analyst = None
    xbrl_engine = None

class AnalyzeRequest(BaseModel):
    ticker: str
    metrics: Dict[str, Any]
    question: Optional[str] = "General Financial Analysis"
    forecast: Optional[Dict[str, Any]] = {}
    sec_text: Optional[str] = ""

class XBRLAnalyzeRequest(BaseModel):
    ticker: str
    years: Optional[int] = 4
    output_lang: Optional[str] = None

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.get("/sec/xbrl/metrics")
def get_xbrl_metrics(ticker: str, years: int = 4):
    if not xbrl_engine:
         raise HTTPException(status_code=503, detail="XBRL Engine not initialized")
    
    metrics = xbrl_engine.extract_metrics(ticker, years)
    if "error" in metrics:
        raise HTTPException(status_code=500, detail=metrics["error"])
    return metrics

@app.post("/ai/analyze/xbrl")
def analyze_xbrl(req: XBRLAnalyzeRequest):
    if not analyst or not xbrl_engine:
        raise HTTPException(status_code=503, detail="Services not initialized")
    
    # 1. Get Metrics
    metrics_data = xbrl_engine.extract_metrics(req.ticker, req.years)
    if "error" in metrics_data:
        raise HTTPException(status_code=500, detail=f"Metrics fetch failed: {metrics_data['error']}")
    
    # Prune data for AI context (Simplify structure)
    # We pass the 'latest' year metrics + CAGR as 'metrics' dict
    # And maybe pass the full table as 'sec_text' or stringified context?
    
    # Let's find latest year
    try:
        years_list = metrics_data.get("years", [])
        if not years_list:
             raise ValueError("No data years found in XBRL")
        
        latest_year = years_list[0]
        latest_data = metrics_data["data"][latest_year]
        
        # Prepare "metrics" for AI (compatible with existing signature)
        ai_metrics = {
             "revenue": latest_data.get("revenue"),
             "net_margin": latest_data.get("net_margin"),
             "revenue_cagr_3yr": metrics_data.get("revenue_cagr_3yr"),
             "roe": latest_data.get("roe"),
             "fcf": latest_data.get("fcf")
        }
        
        # Prepare "sec_text" (We use the years table as context text instead of 10-K text)
        context_str = f"XBRL Financial Data ({req.ticker}):\n"
        for y in years_list:
             d = metrics_data["data"][y]
             context_str += f"Year {y}: Rev=${d.get('revenue',0):,} Income=${d.get('net_income',0):,} Margin={d.get('net_margin',0):.1%} FCF=${d.get('fcf',0):,}\n"
             
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Data processing failed: {e}")

    try:
        # 2. Call AI
        result = analyst.analyze(
            ticker=req.ticker,
            question="Financial Analysis based on XBRL Data",
            metrics=ai_metrics,
            forecast={}, # No forecast engine connected yet for this flow
            sec_text=context_str, # Pass data table as text context
            output_lang=req.output_lang
        )
        return result
    except Exception as e:
        tb = traceback.format_exc()
        logger.exception(f"XBRL Analysis Error: {e}")
        return JSONResponse(status_code=500, content={"error": "AI_FAILED", "detail": str(e), "traceback": tb})

@app.post("/ai/analyze")
def analyze_financials(req: AnalyzeRequest):
    logger.info(f"Received analysis request for {req.ticker}")
    if not analyst:
        return JSONResponse(status_code=503, content={"error": "Not initialized"})

    try:
        result = analyst.analyze(
            ticker=req.ticker,
            question=req.question,
            metrics=req.metrics,
            forecast=req.forecast,
            sec_text=req.sec_text
        )
        return result
    except Exception as e:
        tb = traceback.format_exc()
        logger.exception(f"Exception during analysis for {req.ticker}")
        return JSONResponse(status_code=500, content={"error": "AI_ANALYZE_FAILED", "message": str(e), "traceback": tb})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
