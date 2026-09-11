@echo off
REM Helper interno — no ejecutar a mano. Llamado por INICIAR_TODO.bat
cd /d "%~dp0..\apps\web"
echo Portal web en http://localhost:5180
echo.
npm run dev
pause
