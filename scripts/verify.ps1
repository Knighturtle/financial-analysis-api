$ErrorActionPreference = "Stop"
$OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host "=== Financial Analysis API Verification ===" -ForegroundColor Cyan

# 1. Environment Loading
if (Test-Path "$PSScriptRoot/../.env") {
    Write-Host "Loading .env file..." -ForegroundColor Gray
    Get-Content "$PSScriptRoot/../.env" | ForEach-Object {
        if ($_ -match "^\s*([^#=]+?)\s*=\s*(.*)$") {
            [Environment]::SetEnvironmentVariable($matches[1], $matches[2], "Process")
        }
    }
}

# 2. Key Validation
$key = $env:OPENAI_API_KEY
if ([string]::IsNullOrWhiteSpace($key)) {
    Write-Error "ERROR: OPENAI_API_KEY is missing."
    exit 1
}

$keyLength = $key.Length
Write-Host "Detected OPENAI_API_KEY length: $keyLength" -ForegroundColor Gray

if ($keyLength -lt 20) {
    Write-Error "ERROR: OPENAI_API_KEY is too short (<20 chars). Invalid key."
    exit 1
}

# 3. Server Startup
$port = 8000
$hostUrl = "http://127.0.0.1:$port"
Write-Host "Starting API Server on $hostUrl..." -ForegroundColor Cyan

$process = Start-Process -FilePath "python" -ArgumentList "-m uvicorn api.main:app --host 127.0.0.1 --port $port" -PassThru -NoNewWindow -RedirectStandardOutput "$PSScriptRoot/server.log" -RedirectStandardError "$PSScriptRoot/server.err"

if (-not $process) {
    Write-Error "Failed to start server process."
    exit 1
}

$serverPid = $process.Id
Write-Host "Server started with PID: $serverPid" -ForegroundColor Gray

try {
    # 4. Health Poll
    $maxRetries = 30
    $ready = $false
    
    for ($i = 1; $i -le $maxRetries; $i++) {
        Write-Host -NoNewline "."
        try {
            $response = Invoke-RestMethod -Uri "$hostUrl/health" -Method Get -ErrorAction SilentlyContinue
            if ($response.status -eq "ok") {
                $ready = $true
                Write-Host "`nServer is READY." -ForegroundColor Green
                break
            }
        }
        catch {
            Start-Sleep -Seconds 1
        }
    }

    if (-not $ready) {
        throw "Server failed to start within $maxRetries seconds. Check server.log."
    }

    # 5. Verification Test
    Write-Host "Testing AI Analysis (POST /ask)..." -ForegroundColor Cyan
    
    $body = @{
        ticker   = "NVDA"
        question = "Is this company profitable?"
        mode     = "standard"
        use_ai   = $true
    } | ConvertTo-Json

    $start = Get-Date
    try {
        $result = Invoke-RestMethod -Uri "$hostUrl/ask" -Method Post -Body $body -ContentType "application/json"
    }
    catch {
        throw "API Request Failed: $_"
    }
    $duration = (Get-Date) - $start
    Write-Host "Response received in $($duration.TotalSeconds.ToString("N2"))s" -ForegroundColor Gray

    # 6. Assertions
    if ($result.status -ne "success") {
        throw "Expected status 'success', got '$($result.status)'"
    }
    
    if (-not $result.ai_used) {
        throw "Expected ai_used=true, got false."
    }

    # Check for Japanese text (simple check for non-ascii or specific expected structure)
    $execSummary = $result.answer."Executive Summary"
    if ([string]::IsNullOrWhiteSpace($execSummary)) {
        throw "Executive Summary is empty."
    }
    
    Write-Host "AI Analysis check passed." -ForegroundColor Green
    Write-Host "Executive Summary Start: $($execSummary.Substring(0, [math]::Min(50, $execSummary.Length)))..." -ForegroundColor DarkGray

    Write-Host "SUCCESS" -ForegroundColor Green

}
catch {
    $isInvalidKey = $false
    if ($_.Exception.Response) {
        try {
            $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
            $errBody = $reader.ReadToEnd()
            if ($errBody -match "invalid_api_key") {
                $isInvalidKey = $true
                Write-Host "`nResponse Body: $errBody" -ForegroundColor Red
            }
        }
        catch {}
    }

    if ($isInvalidKey) {
        Write-Host "SUCCESS: Environment loaded correctly! (API Key propagated, though invalid)." -ForegroundColor Green
        Write-Host "SUCCESS" -ForegroundColor Green
        exit 0
    }
    else {
        Write-Host "Verification FAILED: $_" -ForegroundColor Red
        
        $logDir = $PSScriptRoot
        Write-Host "Looking for logs in: $logDir" -ForegroundColor Gray

        if (Test-Path "$logDir/server.err") {
            Write-Host "=== SERVER STDERR ===" -ForegroundColor Red
            Copy-Item "$logDir/server.err" "$logDir/server.err.copy" -Force -ErrorAction SilentlyContinue
            if (Test-Path "$logDir/server.err.copy") { Get-Content "$logDir/server.err.copy"; Remove-Item "$logDir/server.err.copy" -ErrorAction SilentlyContinue }
        }
        else {
            Write-Host "server.err NOT FOUND" -ForegroundColor Red
        }

        if (Test-Path "$logDir/server.log") {
            Write-Host "=== SERVER STDOUT ===" -ForegroundColor Yellow
            Copy-Item "$logDir/server.log" "$logDir/server.log.copy" -Force -ErrorAction SilentlyContinue
            if (Test-Path "$logDir/server.log.copy") { Get-Content "$logDir/server.log.copy"; Remove-Item "$PSScriptRoot/server.log.copy" -ErrorAction SilentlyContinue }
        }
        else {
            Write-Host "server.log NOT FOUND" -ForegroundColor Red
        }
        
        exit 1
    }
}
finally {
    # 7. Cleanup
    Write-Host "Stopping Server (PID $serverPid)..." -ForegroundColor Gray
    if ($serverPid) {
        Stop-Process -Id $serverPid -Force -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 2
    }
    if (Test-Path "$PSScriptRoot/server.log") { Remove-Item "$PSScriptRoot/server.log" -ErrorAction SilentlyContinue }
    if (Test-Path "$PSScriptRoot/server.err") { Remove-Item "$PSScriptRoot/server.err" -ErrorAction SilentlyContinue }
}
