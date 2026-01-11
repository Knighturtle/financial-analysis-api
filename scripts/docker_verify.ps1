$ErrorActionPreference = "Stop"

Write-Host "=== Starting Docker Verification ===" -ForegroundColor Cyan

# 1. Start Docker Container (Build if needed)
Write-Host "[1/3] Starting Docker Compose..."
try {
    docker compose up -d --build
    if ($LASTEXITCODE -ne 0) { throw "Docker compose failed" }
}
catch {
    Write-Error "Failed to start Docker. Is Docker Desktop running?"
    exit 1
}

# Wait for service to be ready
Write-Host "Waiting 5 seconds for service startup..."
Start-Sleep -Seconds 5

# 2. Check Health
Write-Host "[2/3] Checking Health Endpoint..."
try {
    $health = Invoke-RestMethod -Uri "http://127.0.0.1:8000/health" -Method Get
    if ($health.status -eq "ok") {
        Write-Host "SUCCESS: API is HEALTHY." -ForegroundColor Green
    }
    else {
        Write-Error "Health check returned unexpected status: $($health.status)"
        exit 1
    }
}
catch {
    Write-Error "Failed to connect to http://127.0.0.1:8000/health. Container might have crashed."
    docker compose logs
    exit 1
}

# 3. Test AI Endpoint (Ollama Connection)
Write-Host "[3/3] Testing AI Endpoint (XBRL + Host Ollama)..."
$body = @{
    ticker = "AAPL"
} | ConvertTo-Json

try {
    # Note: This requires Ollama running on host at port 11434
    $start = Get-Date
    Write-Host "Sending request (timeout 300s)..."
    $response = Invoke-RestMethod -Uri "http://127.0.0.1:8000/ai/analyze/xbrl" `
        -Method Post `
        -Body $body `
        -ContentType "application/json" `
        -TimeoutSec 300
    
    $duration = (Get-Date) - $start
    
    if ($response.executive_summary) {
        Write-Host "SUCCESS: AI provided analysis in $($duration.TotalSeconds) seconds." -ForegroundColor Green
        Write-Host "Sample Output (Exec Summary): $($response.executive_summary.Substring(0, [math]::Min(50, $response.executive_summary.Length)))..."
    }
    else {
        Write-Error "Response received but missing expected keys."
        Write-Host $response
    }

}
catch {
    Write-Error "AI Analysis Request Failed. Check if Ollama is running on host."
    Write-Host "Error Details: $_"
    # Show logs content to debug
    docker compose logs
}

Write-Host "=== Verification Complete ===" -ForegroundColor Cyan
