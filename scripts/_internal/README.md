# Helpers internos — scripts/_internal

**NO usar en producción del Server.** Estos son helpers para levantar UN solo módulo en dev sin el supervisor.

## Uso

Para trabajar puntual en un solo espacio sin bajar todo:

`powershell
# 1) Detener supervisor si va a pelear por puerto (opcional si solo debug)
# powershell -ExecutionPolicy Bypass -File scripts\detener_panol.ps1

# 2) Levantar solo el módulo que necesitas
.\scripts\_internal\_start_reportes.bat   # :8017
.\scripts\_internal\_start_salidas.bat    # :8018
.\scripts\_internal\_start_kpis.bat       # :8001
# etc.

# 3) Al terminar, cerrar la ventana y volver al supervisor:
powershell -ExecutionPolicy Bypass -File scripts\instalar_autostart_panol.ps1
`

## Producción

En el Server usar SIEMPRE:

- supervisor_panol.ps1 — único launcher (via tarea PortalPanol)
- estado_panol.ps1 — estado 8 servicios
- detener_panol.ps1 — baja todo (con -Desinstalar quita autostart)

El supervisor ya integra el check if not Test-Path .venv → python -m venv pero el bootstrap inicial de deps se hace con estos helpers (pip install -r requirements.txt). Una vez creados los 8 .venv (Python 3.14), el supervisor los mantiene vivos sin intervención.

## Contenido

- _start_kpis.bat        → KPIs :8001
- _start_minuta.bat      → Minuta :8013
- _start_solicitudes.bat → Solicitudes :8014
- _start_usuarios.bat    → Usuarios :8015
- _start_activos.bat     → Activos :8016
- _start_reportes.bat    → Reportes :8017
- _start_salidas.bat     → Salidas :8018 (lee G:\ master_codes.xlsx, escribe salidas_web)
- _start_email.bat       → Email :8020
- _start_portal.bat      → Portal Vite :5180

> Nota: No ejecutar en Server en background junto al supervisor — pelean por los mismos puertos.
