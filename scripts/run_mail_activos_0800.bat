@echo off
REM Ejecuta mail activos 08:00 - Activos fuera de planta (sin adjunto)
cd /d "%~dp0..\backend\activos"
".venv\Scripts\python.exe" -c "from mail_activos import run_activos_si_habilitado; print(run_activos_si_habilitado(forzar=True))"
