Write-Host "Starting Financial Analysis API & Web UI..." -ForegroundColor Green
Write-Host "Access Web UI at: http://localhost:8000" -ForegroundColor Cyan
Write-Host "API Documentation: http://localhost:8000/docs" -ForegroundColor Cyan

# Ensure UTF-8 Output for PowerShell
$OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# Run Uvicorn with reload
python -m uvicorn api.main:app --reload --host 127.0.0.1 --port 8000
