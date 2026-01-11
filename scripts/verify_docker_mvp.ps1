$ErrorActionPreference = "Stop"

Write-Host "=== Verifying Docker MVP Deployment ===" -ForegroundColor Cyan

# 1. API Health
Write-Host "[1/2] Checking API (http://localhost:8000)..."
try {
    $api = Invoke-RestMethod "http://localhost:8000/health"
    if ($api.status -eq "ok") {
        Write-Host "SUCCESS: API is online." -ForegroundColor Green
    }
    else {
        throw "API returned unexpected status"
    }
}
catch {
    Write-Error "API Check Failed. Is Docker running?"
    exit 1
}

# 2. UI Health
Write-Host "[2/2] Checking UI (http://localhost:8501)..."
try {
    # Streamlit returns 200 OK for the main page
    $response = Invoke-WebRequest "http://localhost:8501" -UseBasicParsing
    if ($response.StatusCode -eq 200) {
        Write-Host "SUCCESS: UI is online." -ForegroundColor Green
    }
    else {
        throw "UI returned status $($response.StatusCode)"
    }
}
catch {
    Write-Error "UI Check Failed."
    exit 1
}

Write-Host "=== All Systems Go! ===" -ForegroundColor Cyan
Write-Host "Open http://localhost:8501 in your browser."
