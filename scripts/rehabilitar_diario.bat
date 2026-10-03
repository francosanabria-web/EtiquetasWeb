@echo off
schtasks /change /tn "PanolMailDiario0800_LV" /enable >nul 2>&1
echo Rehabilitado diario para 30/09 >> "%~dp0rehab.log"
