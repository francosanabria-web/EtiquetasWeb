@echo off
REM Helper interno — llamado por INICIAR_TODO.bat / supervisor
cd /d "%~dp0..\backend\activos"
if not exist ".venv\Scripts\python.exe" (
  echo Creando entorno virtual Activos...
  python -m venv .venv
)
".venv\Scripts\python.exe" -m pip install -q -r requirements.txt
echo.
echo Activos fuera de planta en http://localhost:8016
echo.
".venv\Scripts\python.exe" -m uvicorn main:app --host 0.0.0.0 --port 8016
pause
