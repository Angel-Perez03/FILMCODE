@echo off
title FilmCode
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo No se encuentra el Python del proyecto en .venv.
  pause
  exit /b 1
)
if not exist "frontend\dist\index.html" (
  echo Falta compilar la interfaz. Ejecuta npm run build dentro de frontend.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -m videocodigo_web --abrir
if errorlevel 1 pause
