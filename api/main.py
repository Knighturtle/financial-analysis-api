from fastapi import FastAPI

app = FastAPI(title="Financial Analysis API")

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/")
def root():
    return {"message": "API is running. Try /health"}
