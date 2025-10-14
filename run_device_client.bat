@echo off
setlocal enableextensions

REM Simple launcher for Windows double-click runs.
REM 1) Set your backend URL below or pass as first argument.
REM 2) Keeps the window open on errors.

if "%~1"=="" (
  set "BACKEND_URL=https://sample-2ang.onrender.com"
) else (
  set "BACKEND_URL=%~1"
)

set "PAUSE_ON_EXIT=1"
set "PROMPT_BACKEND=1"

REM Try to use workspace venv if present
if exist .venv\Scripts\python.exe (
  set "PYEXE=.venv\Scripts\python.exe"
) else (
  set "PYEXE=python"
)

"%PYEXE%" -m pip install -r requirements.txt || goto :end
"%PYEXE%" py_simple\device_client.py --backend "%BACKEND_URL%" --polling --debug

:end
if not "%PAUSE_ON_EXIT%"=="1" goto :eof
pause
