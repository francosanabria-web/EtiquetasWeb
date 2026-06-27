@echo off
REM ============================================================
REM  PC DE LA IMPRESORA - Escucha la cola de Firebase e imprime
REM  Dejar esta ventana ABIERTA mientras se usa el sistema.
REM ============================================================
cd /d "%~dp0"
title Etiquetas Panol - Escuchando cola de impresion
echo Iniciando escucha de la cola de impresion...
echo (Cerrar esta ventana detiene la impresion automatica)
echo.
python modulo_etiquetas.py escuchar
echo.
echo La escucha se detuvo. Presione una tecla para salir.
pause >nul
