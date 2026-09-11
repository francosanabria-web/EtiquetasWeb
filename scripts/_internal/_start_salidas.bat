@echo off
REM Helper interno — llamado por INICIAR_TODO.bat / supervisor
cd /d "%~dp0..\backend\salidas"

REM Planta: lee master_codes (solo lectura) y escribe en salidas_web.
REM Doble espacio en "MANTENIMIENTO  OZLA" — no quitar.
set "SALIDAS_PANOL_PATH=G:\Unidades compartidas\Mantenimiento\MANTENIMIENTO  OZLA 2024-2025\17. Pañol\pañol v5.0"
set "SALIDAS_MAESTRO_PATH=%SALIDAS_PANOL_PATH%\master_codes.xlsx"
set "SALIDAS_WEB_PATH=%SALIDAS_PANOL_PATH%\salidas_web"
REM No escribir Firestore al confirmar (decisión 2026-08-05)
set "SALIDAS_FIREBASE_WRITE=0"

if not exist ".venv\Scripts\python.exe" (
  echo Creando entorno virtual Salidas...
  python -m venv .venv
)
".venv\Scripts\python.exe" -m pip install -q -r requirements.txt
echo.
echo Salidas (egreso material) en http://localhost:8018
echo Maestro (lectura): %SALIDAS_MAESTRO_PATH%
echo Escritura:         %SALIDAS_WEB_PATH%
echo.
".venv\Scripts\python.exe" -m uvicorn main:app --host 0.0.0.0 --port 8018
pause
