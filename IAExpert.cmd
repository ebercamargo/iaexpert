@echo off
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Iniciar-IAExpert.ps1"
if errorlevel 1 (
  echo.
  echo IAExpert nao iniciou. Consulte a mensagem acima.
  pause
)
