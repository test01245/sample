param(
  [string]$BackendUrl = "https://sample-2ang.onrender.com",
  [switch]$Polling = $true,
  [switch]$Debug = $true,
  [switch]$Insecure = $false
)

$env:PAUSE_ON_EXIT = "1"
$env:PROMPT_BACKEND = "1"
$env:BACKEND_URL = $BackendUrl

# Prefer workspace venv if present
$py = Join-Path ".venv" "Scripts/python.exe"
if (-not (Test-Path $py)) { $py = "python" }

& $py -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) {
  Write-Host "pip install failed" -ForegroundColor Red
  if ($env:PAUSE_ON_EXIT -eq "1") { Read-Host "Press Enter to exit" }
  exit 1
}

$flags = @()
if ($Polling) { $flags += "--polling" }
if ($Debug) { $flags += "--debug" }
if ($Insecure) { $flags += "--insecure" }

& $py "py_simple/device_client.py" --backend $BackendUrl @flags

if ($env:PAUSE_ON_EXIT -eq "1") { Read-Host "Press Enter to exit" }
