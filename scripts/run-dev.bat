@echo off
setlocal

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0run-dev.ps1"

endlocal
