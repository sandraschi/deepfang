@echo off
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start.ps1"
if %ERRORLEVEL% neq 0 (
  echo [ERROR] DeepFang exited with code %ERRORLEVEL%.
  pause
)
