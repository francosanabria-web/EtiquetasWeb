@echo off
REM Ejecuta mail diario 08:00 - Reporte gastos dia anterior
cd /d "%~dp0..\backend\reportes"
".venv\Scripts\python.exe" -c "from mail_jobs import run_diario_si_habilitado; print(run_diario_si_habilitado())"
