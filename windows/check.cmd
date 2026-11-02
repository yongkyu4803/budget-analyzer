@echo off
setlocal
set "PYTHONUTF8=1"
set "PYTHONDONTWRITEBYTECODE=1"
set "KORDOC_OFFLINE=1"
set "ORT_DISABLE_TELEMETRY=1"
chcp 65001 >nul
"%~dp0runtime\python\python.exe" -X utf8 -B "%~dp0app\portable.py" check %*
exit /b %errorlevel%
