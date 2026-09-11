@echo off
REM Helper interno — no ejecutar a mano. Llamado por INICIAR_TODO.bat
cd /d "%~dp0..\backend\kpis"
if not exist ".venv\Scripts\python.exe" (
  echo Creando entorno virtual KPIs...
  python -m venv .venv
)
".venv\Scripts\python.exe" -m pip install -q -r requirements.txt
echo.
echo KPIs en http://localhost:8001
echo Espere el mensaje: Datos listos.
echo.
".venv\Scripts\python.exe" -m uvicorn main:app --host 0.0.0.0 --port 8001
pause
