@echo off
title Supervisor Minutas
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0supervisor_minutas.ps1"
pause
