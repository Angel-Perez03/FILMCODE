@echo off
setlocal
if not exist "%~dp0Instalar-FilmCode.ps1" (
  echo Extrae primero todos los archivos del ZIP en una carpeta.
  pause
  exit /b 1
)
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoLogo -NoProfile -STA -ExecutionPolicy Bypass -File "%~dp0Instalar-FilmCode.ps1"
if errorlevel 1 pause
endlocal
