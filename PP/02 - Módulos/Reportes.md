# Reportes

**Estado:** 🟡 Operativo (web lee prod) / ✅ Funcionando (escritorio)  
**Última actualización:** 2026-08-07

## Qué hace

Consultas **operativas** de movimientos de salidas: listado filtrable, agregaciones básicas (sector, operario, comprobante, mes) y **export Excel Table** (mismo layout que el detalle del mail diario de gastos).

Distinto de **KPIs**: Reportes = consultas/listados fila a fila; KPIs = dashboards de indicadores (agregados, `SECTOR_CALC`, `LINEA`).

En escritorio la pestaña **💸 Reportes** también genera mails de gasto diario/mensual por sector. En web: scaffold de mail **configurado pero desactivado** (`REPORTES_MAIL_*_ENABLED=0`).

## UX móvil (2026-08-07)

- Padding de página alineado al shell (`rep-page`).
- ⚠️ Sigue orientado a **consulta** en teléfono; sin rediseño mobile-first. Ver [[02 - Módulos/Shell_Central]] y Pendientes.

## Datos compartidos con KPIs

| | Reportes | KPIs |
|--|----------|------|
| Fuente | `master_salidas.xlsx` hoja `Movimientos` (mismo path prod por defecto) | Igual + `master_codes` + `salida_activos` |
| Sector | Columna `SECTOR` del Excel (tal cual registro) | `SECTOR_CALC` derivado del **operario** vía mapa config |
| Línea gasto | No (muestra `TIPO_COMPROBANTE`) | `LINEA` normalizada (L1–L7, PAÑOL…) |
| Vista | Tabla + filtros + resumen simple | Gráficos consumo/stock/reposición |
| ¿Mismos números? | **No necesariamente** — misma base de montos, pero sector y vistas distintos | |

## Cómo funciona (técnico)

**Producción hoy (escritorio):** pestaña Reportes en `almacen_gui.py` (mails + Excel multi-hoja).

**Web (shell) — 2026-08-07:**
- UI: `apps/web/src/modules/reportes/ReportesPage.tsx` → ruta `/reportes`
- Cliente: `apps/web/src/api/reportesClient.ts`
- Estilos: `apps/web/src/styles/reportes.css`
- Proxy Vite: `/api/reportes` → `:8017`
- Backend: `backend/reportes/` (Starlette)
- Arranque: `INICIAR_TODO.bat` → `_start_reportes.bat`; `supervisor_panol.ps1`

**Capas:**
- `config.py` — path + columnas + flags mail
- `store.py` — lectura CSV/XLSX **solo lectura**
- `service.py` — filtros, resumen, export
- `exports.py` — Excel Table openpyxl (`TablaGastos`)
- `mail_jobs.py` — scaffold diario/mensual (flags en 0)
- `main.py` — HTTP

## Columnas export / tabla UI (diario de gastos)

Orden del **detalle de retiros** del mail escritorio (`_generar_reporte_gastos_sector`) + `SECTOR` (listado unificado):

1. FECHA  
2. CODIGO  
3. DESCRIPCION  
4. CANTIDAD  
5. PRECIO_UNITARIO  
6. MONTO_TOTAL_SALIDA  
7. TIPO_COMPROBANTE  
8. NUMERO_ORDEN  
9. MAQUINA_SITIO  
10. OPERARIO  
11. SECTOR  

⚠️ En el mail por sector, `SECTOR` no va en el detalle (una hoja/cuadro por sector). En web se agrega al final.

## Endpoints / API

Puerto **8017**. Detalle en [[03 - Documentacion Tecnica/Backend/API]].

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/health` | Estado + path + filas |
| GET | `/api/reportes/movimientos` | Listado filtrado |
| GET | `/api/reportes/resumen` | Totales + agregados |
| GET | `/api/reportes/filtros` | Combos |
| POST | `/api/reportes/refresh` | Recargar (solo lectura) |
| GET | `/api/reportes/export.xlsx` | Excel Table |
| GET | `/api/reportes/export.csv` | Deprecated |
| GET | `/api/reportes/mail/status` | Flags (sin enviar) |
| POST | `/api/reportes/mail/diario/dry-run` | Preview sin enviar |
| POST | `/api/reportes/mail/diario` | Solo si `DIARIO_ENABLED=1` |
| POST | `/api/reportes/mail/mensual` | Solo si `MENSUAL_ENABLED=1` |

## Mail (scaffold desactivado)

Vars: `REPORTES_MAIL_DIARIO_ENABLED=0`, `REPORTES_MAIL_MENSUAL_ENABLED=0`, destinatarios, horas (hint), `PANOL_SMTP_*`.

**Cómo activar:** SMTP + destinatarios + `ENABLED=1` + tarea Windows/supervisor que llame dry-run o POST mail. **Sin scheduler** en el servicio.

⚠️ Cuerpo HTML completo multi-sector del escritorio (resúmenes, día a día, líneas Mant.) aún no portado; scaffold envía resumen simple + adjunto Excel Table.

## Permisos

- Catálogo: módulo `reportes` en `backend/usuarios`
- Nav: admin, panol, jefatura

## Pendientes de este módulo

- [ ] Conectar `store` a API Salidas / SQL
- [ ] Completar HTML mail multi-sector como escritorio
- [ ] Activar envíos (flags + tarea) cuando negocio lo pida
- [ ] Desglose L1–L7 en mail Mant.

## Notas

- Solo lectura de `master_salidas` prod.
- Puerto **8017** (Salidas **8018**).
- UI: solo título «Reportes» (sin subtítulo aclaratorio).
