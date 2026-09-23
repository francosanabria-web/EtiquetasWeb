@echo off
REM Helper interno — llamado por INICIAR_TODO.bat / supervisor
cd /d "%~dp0..\backend\reportes"
if not exist ".venv\Scripts\python.exe" (
  echo Creando entorno virtual Reportes...
  python -m venv .venv
)
".venv\Scripts\python.exe" -m pip install -q -r requirements.txt

REM Reportes en modo DB: lee salida_historial si está disponible, fallback Excel
if not defined REPORTES_DB_ENABLED set REPORTES_DB_ENABLED=1
REM No forzar data_prueba: config.py resuelve a master_salidas de producción
REM (mismo path que KPIs) salvo override con REPORTES_MOVIMIENTOS_FILE /
REM REPORTES_DATA_PATH / KPIS_DATA_PATH / SALIDAS_DATA_PATH.
echo.
echo Reportes (movimientos) en http://localhost:8017 [REPORTES_DB_ENABLED=%REPORTES_DB_ENABLED%]
if defined REPORTES_MOVIMIENTOS_FILE (
  echo Override REPORTES_MOVIMIENTOS_FILE=%REPORTES_MOVIMIENTOS_FILE%
) else (
  echo Fuente: resuelta por config.py ^(prod por defecto^)
)
echo.
".venv\Scripts\python.exe" -c "from config import movimientos_path; print('Movimientos:', movimientos_path())"
echo.
".venv\Scripts\python.exe" -m uvicorn main:app --host 0.0.0.0 --port 8017
pause
