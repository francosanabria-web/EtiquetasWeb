# Scripts — Portal Pañol (Server)

> **Server** C:\Users\Pañol\Desktop\sistemas_panol\Server\AppWebSalidas — **NO imprime**. La impresora USB vive solo en la PC de pañol (RedImpresionPanol). Este servidor corre solo el portal 5180 + 8 backends. Ver sección [Impresión](#impresión) abajo.

## Scripts definitivos (6 core + logs + _internal)

| Archivo | Rol |
|---------|-----|
| supervisor_panol.ps1 | **Único launcher** — mantiene vivos 8001, 8013, 8014, 8015, 8016, 8017, 8018, 8020, 5180. Idempotente, auto-repara /health, reinicio suave 20:00-22:00. Corre oculto vía tarea PortalPanol. |
| instalar_autostart_panol.ps1 | Registra tarea PortalPanol (AtLogOn, Hidden, Restart 999×1min). No requiere admin (RunLevel Limited). La ejecuta y arranca supervisor en ~30-60s. |
| estado_panol.ps1 | Estado 8 backends + Portal + Supervisor + Tarea. Usa /health (acepta 503 CARGANDO para KPIs/Activos/Reportes/Salidas que leen G:\). |
| detener_panol.ps1 | Baja supervisor + 9 puertos.  -Desinstalar borra la tarea (quita autostart). No toca impresión. |
| esperar_servicios.ps1 | Helper usado por INICIAR_TODO legacy (hoy opcional dev). Espera /health 180s y luego poll KPIs hasta estado ok. Se deja por compat dev. |
| ebuild_master_salidas.py | Reconstruye master_salidas.xlsx desde master_codes + salidas_web. No toca G:\ en runtime normal. |

### Uso diario (producción)

`powershell
# Instalar / revivir (una vez, o tras detener -Desinstalar)
powershell -ExecutionPolicy Bypass -File scripts\instalar_autostart_panol.ps1

# Ver estado (el más usado) — debe dar 8× ARRIBA
powershell -ExecutionPolicy Bypass -File scripts\estado_panol.ps1

# Frenar sin borrar autostart (al reiniciar sesión vuelve)
powershell -ExecutionPolicy Bypass -File scripts\detener_panol.ps1

# Frenar Y quitar autostart
powershell -ExecutionPolicy Bypass -File scripts\detener_panol.ps1 -Desinstalar

# Logs
Get-Content scripts\logs\supervisor_panol.log -Tail 50
Get-Content scripts\logs\panol_portal.out.log  -Tail 50
Get-Content scripts\logs\panol_kpis.out.log    -Tail 50
# un .out/.err por servicio: panol_<nombre>.out.log
`

**Tarea Windows**: PortalPanol (\, AtLogOn, Hidden). No toca RedImpresionPanol.

### _internal — helpers de un solo módulo (dev)

scripts\_internal\ contiene los 8 _start_*.bat movidos del root. **No usar en Server en producción** junto al supervisor.

Ver scripts\_internal\README.md para uso puntual: levantar un solo módulo sin bajar todo (ej. _start_reportes.bat en ventana aparte, luego cerrar y volver al supervisor).

El supervisor ya integra if not Test-Path .venv → python -m venv pero el bootstrap inicial de deps (pip install -r requirements.txt) lo hacen estos helpers la primera vez.

## Impresión

**Este Server NO imprime.** 

- ite.config.ts no tiene proxy a 8010 (verificado) — no hay nada que redirigir. Etiquetas es dominio separado (services/etiquetas-*, 5173/8010) y vive solo en la PC de pañol.
- Get-ScheduledTask RedImpresionPanol debe dar **NO EXISTE** en este Server (verificado). Si da RUNNING, es que se instaló por error — desinstalar con detener_impresion.ps1 en la PC que sí imprime.
- Celulares/PCs de planta siguen imprimiendo contra **PC pañol**: http://<IP-pañol>:5173 (misma red LAN), no contra 10.1.103.139:5180 del Server.
- No enviar orden desde Server a pañol sin servicio activo: no hay redirect porque no hay proxy 8010. Si se necesitara en el futuro, sería un proxy explícito o cola, no automático.
- Los 4 scripts de impresión (supervisor_impresion.ps1, instalar_autostart.ps1, estado_impresion.ps1, detener_impresion.ps1) fueron removidos de este Server (backup en C:\Users\Pañol\AppData\Local\Temp\2\opencode\scripts_backup_2026-09-03\) y quedan vivos solo en la PC de pañol. No reinstalarlos aquí.

## Limpieza 2026-09-05

Movidos a _internal\: 8 _start_*.bat. Borrados de scripts\: INICIAR_TODO.bat, INICIAR_MINUTAS.bat, supervisor_minutas.ps1, monitoreo_salud.ps1, instalar_monitoreo.ps1, setup_github.ps1 y los 4 de impresión. Backup en Temp citado. Ver git status / scripts\_internal\README.md.

## Puertos

- 8001 KPIs | 8013 Minuta | 8014 Solicitudes | 8015 Usuarios | 8016 Activos | 8017 Reportes | 8018 Salidas | 8020 Email | 5180 Portal Vite
- Impresión (solo PC pañol): 8010 API etiquetas | 5173 web etiquetas
