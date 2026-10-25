@echo off
rem Double-click to start What Else? (or open it if it is already running).
rem The app runs in a minimised window; close that window to stop it.
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Setup needed: python -m venv .venv ^&^& .venv\Scripts\pip install -e ".[dev]"
  pause
  exit /b 1
)
start "What Else?" /min ".venv\Scripts\python.exe" -m whatelse
