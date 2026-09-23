@echo off
REM Helper interno — llamado por INICIAR_TODO.bat / supervisor
cd /d "%~dp0..\backend\reportes"
if not exist ".venv\Scripts\python.exe" (
  echo Creando entorno virtual Reportes...
  python -m venv .venv
)
".venv\Scripts\python.exe" -m pip install -q -r requirements.txt

REM Reportes en modo DB exclusivo: lee salida_historial de MariaDB, sin fallback Excel
if not defined REPORTES_DB_ENABLED set REPORTES_DB_ENABLED=1
REM Config.py resuelve DSN desde SALIDAS_DB_* / DB_* env vars (misma DB que salidas)
echo.
echo Reportes (movimientos) en http://localhost:8017 [DB-ONLY: salida_historial]
echo.
".venv\Scripts\python.exe" -c "from config import COLUMNAS, REPORTES_DB_ENABLED; print('DB habilitado:', REPORTES_DB_ENABLED, '| columnas:', len(COLUMNAS))"
echo.
".venv\Scripts\python.exe" -m uvicorn main:app --host 0.0.0.0 --port 8017
pause
