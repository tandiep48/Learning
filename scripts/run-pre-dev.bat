@echo off
setlocal

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0run-pre-dev.ps1"

endlocal
