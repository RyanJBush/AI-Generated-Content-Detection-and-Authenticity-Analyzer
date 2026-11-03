@echo off
cd /d "%~dp0"
if not exist ".venv-ui\Scripts\python.exe" (
  echo The model-free demo environment is missing. Follow Basic installation in INSTALL.md.
  exit /b 1
)
".venv-ui\Scripts\python.exe" -m litmus.local_ui %*
