
$server = Start-Job { 
    . .venv/Scripts/Activate.ps1
    uvicorn api.main:app --port 8000 
}
Write-Host "Started Server..."

try {
    # Give it a moment, but the python script also has logic
    Start-Sleep -Seconds 10
    
    python scripts/verify_live.py
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Verification Failed."
        exit 1
    }
    Write-Host "Verification Passed."
}
finally {
    Stop-Job $server
    Remove-Job $server
    Write-Host "Server Stopped."
}
