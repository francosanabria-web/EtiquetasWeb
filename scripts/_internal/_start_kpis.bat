@echo off
REM Helper interno — no ejecutar a mano. Llamado por INICIAR_TODO.bat
cd /d "%~dp0..\backend\kpis"
if not exist ".venv\Scripts\python.exe" (
  echo Creando entorno virtual KPIs...
  python -m venv .venv
)
".venv\Scripts\python.exe" -m pip install -q -r requirements.txt
REM KPIs en modo DB exclusivo: lee maestro_stock y salida_historial de MariaDB
set "KPIS_DB_ENABLED=1"
set "SALIDAS_DB_ENABLED=1"
echo.
echo KPIs en http://localhost:8001 [DB-ONLY: maestro_stock + salida_historial]
echo Espere el mensaje: Datos listos.
echo.
".venv\Scripts\python.exe" -m uvicorn main:app --host 0.0.0.0 --port 8001
pause
