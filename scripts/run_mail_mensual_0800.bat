@echo off
REM Ejecuta mail mensual 08:00 - Reporte mensual dia 1 (mes anterior)
REM Se ejecuta el 1 de cada mes a las 08:00 junto a los dos diarios fijos
cd /d "%~dp0..\backend\reportes"
".venv\Scripts\python.exe" -c "from mail_jobs import run_mensual_si_habilitado; print(run_mensual_si_habilitado())"
