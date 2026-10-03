@echo off
REM Lunes 08:02 - envia sabado separado (Opcion B). Domingo lo manda el diario normal 08:00
cd /d "%~dp0..\backend\reportes"
".venv\Scripts\python.exe" lunes_sabado_runner.py >> "%~dp0lunes_sabado.log" 2>&1
type "%~dp0lunes_sabado.log"
