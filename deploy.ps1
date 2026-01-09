Write-Host "Deploying Financial Analysis API to C:\dev\financial-analysis-api..."
$source = "$PSScriptRoot"
$dest = "C:\dev\financial-analysis-api"

if (!(Test-Path $dest)) {
    New-Item -ItemType Directory -Force -Path $dest | Out-Null
}

# Copy all files from current dir to destination
Get-ChildItem -Path $source -Exclude "deploy.ps1" | Copy-Item -Destination $dest -Recurse -Force

Write-Host "Deployment complete."
Write-Host "Next steps:"
Write-Host "  cd '$dest'"
Write-Host "  python -m venv .venv"
Write-Host "  .\.venv\Scripts\Activate"
Write-Host "  pip install -r requirements.txt"
Write-Host "  cp .env.example .env"
Write-Host "  # Edit .env with your OpenAI API Key"
Write-Host "  uvicorn api.main:app --reload"
