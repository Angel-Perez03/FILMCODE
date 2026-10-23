@echo off
setlocal
if not exist "%~dp0frontend\public\instalador\Instalar-FilmCode.cmd" (
  echo Extrae la copia completa del repositorio antes de abrir el asistente.
  pause
  exit /b 1
)
call "%~dp0frontend\public\instalador\Instalar-FilmCode.cmd"
exit /b %errorlevel%
