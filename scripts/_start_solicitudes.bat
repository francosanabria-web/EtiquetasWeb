@echo off
REM Helper interno — llamado por INICIAR_TODO.bat
cd /d "%~dp0..\backend\solicitudes"
if not exist ".venv\Scripts\python.exe" (
  echo Creando entorno virtual Solicitudes...
  python -m venv .venv
)
".venv\Scripts\python.exe" -m pip install -q -r requirements.txt
echo.
echo Solicitudes en http://localhost:8014
echo.
".venv\Scripts\python.exe" -m uvicorn main:app --host 0.0.0.0 --port 8014
pause
