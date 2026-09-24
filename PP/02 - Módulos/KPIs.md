# KPIs

**Estado:** ✅ Funcionando (barras críticas migradas a HTML; Recharts pendiente en líneas/donut)
**Última actualización:** 2026-08-07

## Qué hace

Dashboard ejecutivo de stock, consumo y reposición para jefatura/gerencia.

## UX móvil (2026-08-07)

- Accesible desde el shell móvil (drawer); **no** está en el bottom quick nav de campo.
- ⚠️ Sigue orientado a **consulta** en teléfono; sin rediseño mobile-first. Ver [[02 - Módulos/Shell_Central]] y Pendientes.

## Estado actual (2026-08-04)

### Confirmado OK (usuario)
| Indicador | Render | Notas |
|-----------|--------|-------|
| Gasto por sector | `KpiNamedBarList` | HTML/CSS; escala dispar resuelta |
| Gasto por línea Mant. | `KpiNamedBarList` | Idem |
| Top 10 por monto | `KpiNamedBarList` | Código + descripción |
| Top 10 por cantidad | `KpiNamedBarList` | `pesos={false}`; código + descripción |
| Stock valorizado por criticidad | `KpiNamedBarList` | Colores CRÍTICO / ALTA FRECUENCIA / BASE |

### Hecho en sesión (⚠️ revalidar light/dark en planta)
- Layout superior (gastos) / inferior (pañol).
- Tokens dark mode del shell en `kpis.css`.
- Gasto por sector arriba en barras (ya no donut).

### Pendiente de validar / posible rotura Recharts
| Indicador | Componente | Tech |
|-----------|------------|------|
| Gasto mensual (12 meses) | `KpiLineChart` | Recharts |
| Tendencia anual por sector | `KpiMultiLineChart` | Recharts |
| Bajo mínimo vs sobre mínimo | `KpiDonutChart` | Recharts |
| Artículos en cero | tabla | HTML |
| Reposición (alertas + tabla + modal) | `ReposicionSection` | HTML |
| Botón Ampliar | `KpiExpandable` | — |
| Dark mode completo en planta | — | CSS |
| Tests E2E | — | — |

⚠️ `KpiBarChart` (Recharts) **ya no se usa** en paneles; solo tipa `BarItem`. Candidata a limpieza.

## Layout

1. **Resumen** (cards).
2. **Superior — Gastos y consumo:** gasto mensual; gasto por sector (span 2); gasto por línea Mant. (span 3); tendencia anual; top 10 monto / cantidad.
3. **Inferior — Pañol:** bajo mínimo (donut); stock por criticidad (barras HTML); artículos en cero; reposición.

## Cambios 2026-08-04 (sesión)

- Causa común de barras ilegibles: Recharts vertical + escalas disparadas → barras/etiquetas invisibles.
- Solución: `KpiNamedBarList` (nombre, valor, %, mínimo visible). `KpiSectorBarList` queda wrapper de compatibilidad.
- Migrados a HTML: sector, línea Mant., Top 10 monto, Top 10 cantidad, stock por criticidad.
- Layout gastos / pañol; dark mode tokens; sector arriba como barras.

## Causa raíz del 0 bytes (2026-08-06)

**Confirmado en código de escritorio** (`LABORATORIO BASE/almacen_gui.py`):

- `_escribir_excel_formateado` abre el destino con `pd.ExcelWriter(path, engine='xlsxwriter')` **directo sobre el archivo final**.
- Al abrir, Windows/xlsxwriter **trunca a 0 bytes**. Si Drive sincroniza, Excel tiene el archivo abierto (`~$…`), o el proceso se interrumpe a mitad, queda el vacío.
- Misma función usan: finalizar carga (`_guardar_movimientos_batch`), propagación de precios (`_propagar_precio_movimientos_mes_curso`) y sync diaria.
- El comentario “forma SEGURA (sin xlsxwriter)” en `guardar_archivos_background` es engañoso: igual llama a `_escribir_excel_formateado` (sí usa xlsxwriter).

**Línea de tiempo G: (06/08):**
| Hora | Evento |
|------|--------|
| 07:16:50 | `salidas_05-08-2026.xlsx` escrito (carga/salida) |
| **07:17:09** | `master_salidas.xlsx` → **0 bytes** |
| 07:18:30–07:20:30 | Actualización de stock (119 s; 0 mods; **0 propagaciones**) |
| 07:20:28 | `master_codes.xlsx` guardado |

La corrupción fue **antes** del log de stock (07:17 vs 07:18). Encaja con escritura de historial al finalizar una salida (o reintento) concurrente con Drive/Excel, no con la propagación de esa corrida (que fue 0).

**Prevención:** escritura atómica (`*.tmp` + `os.replace`) en `_escribir_excel_formateado` del escritorio — **pendiente de aplicar** (requiere OK explícito para tocar `almacen_gui.py`). Backend Salidas web ya quedó atómico (2026-08-06).

## Recuperar versión de Drive (“versión 100”)

Google Drive guarda **hasta ~100 versiones** por archivo (o ~30 días). “Versión 100” suele ser la más vieja que Drive aún retiene.

1. Cerrar Excel si tiene abierto `master_salidas` (borrar `~$master_salidas.xlsx` si quedó huérfano).
2. Abrir en el navegador: carpeta `pañol v5.0` en el Shared Drive → clic en `master_salidas.xlsx`.
3. Menú **⋮** (o clic derecho) → **Administrar versiones** / **Manage versions**.
4. Buscar la versión deseada (por fecha/hora **antes** de 06/08 07:17, o la más antigua si es “la 100”).
5. En esa fila: **⋮** → **Descargar** (recomendado) y/ o **Conservar para siempre**.
6. Comparar filas vs el actual (~4844 desde diarios). Si es mejor: renombrar el actual a `master_salidas.xlsx.REBUILD_…` y subir la descargada con **Administrar versiones → Subir nueva versión**, o reemplazar el archivo en G:.
7. Luego `GET http://127.0.0.1:8001/api/kpis/refresh` (o reiniciar KPIs).

⚠️ No hacer “Restaurar” a ciegas sin backup local del rebuild actual.

**Síntoma:** `/health` 200 con `estado: cargando` eterno; endpoints KPI → **503**; `GET /api/kpis/refresh` → **500**.

**Causa:** `master_salidas.xlsx` en `G:\...\pañol v5.0\` quedó en **0 bytes** (corrupto). El loader fallaba con `BadZipFile` y no marcaba error de carga → la UI veía “cargando” para siempre. Stock/consumo dependían de ese archivo.

**Reparación:**
1. Reconstruido `master_salidas.xlsx` desde `salidas_diaria/*.xlsx` + diarios en raíz (~4844 filas, abr–ago 2026). Script: `scripts/rebuild_master_salidas.py`.
2. Backup del vacío: `master_salidas.xlsx.CORRUPTO_*` junto al archivo.
3. Loader KPIs endurecido: valida zip/xlsx real; si `master_salidas` está corrupto, carga `master_codes` + activos igual y health puede devolver `estado: parcial` + `avisos`.
4. Escritura atómica en Salidas (`tmp` + `os.replace`) para no volver a dejar el historial en 0 bytes si Drive interrumpe.

⚠️ Historial anterior a ~18/04/2026 que solo estuviera en el master (no en diarios) puede faltar. Revisar **historial de versiones de Google Drive** del archivo si hace falta recuperar más atrás.

## Arranque

Único script del portal: `scripts\INICIAR_TODO.bat` (KPIs + Minuta + Email + shell :5180). Helpers internos `_start_*.bat` (no usar a mano).

- Si Vite muestra `ETIMEDOUT 127.0.0.1:8001`, el backend aún carga Excel o quedó colgado → volver a ejecutar `INICIAR_TODO.bat`.
- `/health` puede devolver `estado: cargando` mientras lee Excel; endpoints de datos → **503** hasta terminar.
- Tras restaurar Excel: `GET /api/kpis/refresh` o reiniciar el servicio KPIs.

## Nota de dominio

La sección **Activos fuera de planta** vive en `/activos` (`:8016`), no en este dashboard. Pendientes de Activos: ver [[01 - Estado del Proyecto/Pendientes]].

## API

- Servicio: `backend/kpis` puerto `8001`.
- Endpoints KPIs en [[03 - Documentacion Tecnica/Backend/API]].

## Pendientes (continuar después)

1. Validar uno a uno: gasto mensual, tendencia anual, donut bajo mínimo, artículos en cero, reposición, Ampliar.
2. Validar dark mode en PC pañol (hard-refresh `/kpis`).
3. Tests E2E del dashboard.
4. ⚠️ Limpiar `KpiBarChart` si ya no hace falta.
5. Optimización de bundle; permisos finos de consulta por rol.