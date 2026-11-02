@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Litmus needs its existing .venv. See README.md for setup.
  exit /b 1
)
".venv\Scripts\python.exe" -m litmus.local_ui %*
