@echo off
REM ============================================================
REM  DEMO - Genera una etiqueta de ejemplo y la abre (PNG)
REM  Sirve para ver el diseno sin impresora ni Firebase.
REM ============================================================
cd /d "%~dp0"
title Demo etiqueta Panol
python modulo_etiquetas.py demo
pause >nul
