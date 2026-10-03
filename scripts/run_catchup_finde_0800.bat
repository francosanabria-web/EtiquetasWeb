@echo off
REM Catchup finde 26-28 Sep 2026 - sabado domingo lunes - disparado hoy 29/09 08:00 a pedido
cd /d "%~dp0..\backend\reportes"
echo [%date% %time%] Catchup inicio >> "%~dp0catchup_finde.log"
".venv\Scripts\python.exe" catchup_finde_runner.py >> "%~dp0catchup_finde.log" 2>&1
type "%~dp0catchup_finde.log"
schtasks /change /tn "PanolMailDiario0800_LV" /enable >nul 2>&1
echo [%date% %time%] Catchup fin - diario re-habilitado >> "%~dp0catchup_finde.log"
