# Roadmap — Sistemas Pañol

**Última actualización:** 2026-08-07

## Módulos — estado actual

| Módulo | Estado | Descripción | Notas |
|--------|--------|-------------|-------|
| **Etiquetas** | ✅ Funcionando | Impresión LAN: código, mercadería nueva y rótulo simple; buffer reimpresión; tema claro/oscuro + identidad AppPanolWeb | `services/etiquetas-web` :5173 + `etiquetas-api` :8010 + `print-agent`; incidente cuota FS jun-2026 documentado |
| **Minuta de Reunión** | 🔄 En desarrollo | Reunión + envío mail + historial SQLite | Sync multi-PC 30/07; **2026-08-07:** orden criticidad Crítico→Urgente→Normal en tabla y mail; ver [[02 - Módulos/Minuta_Reunion]] |
| **Solicitud de pedidos** | 🔄 En desarrollo | Pedidos Normal/Urgente + TR, PDF/Excel | Shell `/solicitudes` + API :8014; **fuente de verdad Excel en Drive**; `P-####` auto; proveedor (obligatorio en TR) |
| **Shell central** | 🔄 En desarrollo | Portal de acceso y navegación | `apps/web` :5180; **2026-08-07:** AppShell responsive (top bar + drawer + bottom nav campo ≤768px); autostart `PortalPanol`. Ver [[02 - Módulos/Shell_Central]] |
| **Usuarios / Accesos** | 🔄 En desarrollo | Login real + gestión de usuarios, contraseñas y permisos por módulo | `backend/usuarios` :8015 (SQLite); solo LAN. Ver [[02 - Módulos/Usuarios]] |
| **Salidas / Pañol** | 🔄 En desarrollo | Registro de egresos de material | **2026-08-07:** lee `master_codes` (solo lectura) + escribe en `salidas_web/` con formato tipo escritorio; filas de prueba limpiadas; labels UI. Pendiente sync FS→local y consolidación con historial KPIs. Ver [[02 - Módulos/Salidas]] |
| **Reportes** | 🟡 Operativo | Consultas + Excel Table; mail scaffold OFF | Lee `master_salidas` prod; export layout diario gastos; `MAIL_*_ENABLED=0` |
| **Activos fuera de planta** | 🟡 En desarrollo | Seguimiento por remito/pedido/OC, días fuera | **F2 OK**; F3 editar→alta; F4 auditoría+mail |
| **Catálogo / Config** | 🔄 En desarrollo | Maestro artículos, sync Firebase, correos | Producción en escritorio |
| **KPIs** | ✅ Funcionando | Stock, consumo, reposición | Restaurado 2026-08-06 tras `master_salidas` 0 bytes; barras críticas OK; ⚠️ validar Recharts / historial Drive pre-abr-2026 |
| **Buscador (AppPanolWeb)** | ✅ Funcionando | Consulta, alias, conteo Excel | Externo: `https://apppanol.vercel.app` |
| **Mapa / Ubicación (AppPanolWeb)** | 🔄 En desarrollo | Mapa 2D interactivo del pañol | Layout P1 local; ver [[02 - Módulos/Mapa_Ubicacion]] |
| **Email genérico** | 🔄 En desarrollo | SMTP + contactos desde Excel | `backend/email_service` :8020 |

## Fases de migración

| Fase | Descripción | Estado | Evidencia |
|------|-------------|--------|-----------|
| **Fase 0** | Git + tests | 🔄 En progreso | Repo AppWebSalidas en GitHub |
| **Fase 1** | Extracción de lógica a servicios | 🔄 En progreso | etiquetas-api, kpis, minuta_store, email_service |
| **Fase 2** | Frontend web (shell) | 🔄 En progreso | rutas activas; **shell móvil** (drawer + bottom nav) 2026-08-07 |
| **Fase 3** | MariaDB | ⏳ Pendiente | Diseño pendiente |
| **Fase 4** | Sync Firestore | ⏳ Pendiente | App móvil depende de contrato actual |
| **Fase 5** | Prueba paralela 7 días | ⏳ Pendiente | A ejecutar antes de corte definitivo |

## Hitos recientes
- **2026-08-07:** Minuta — orden por criticidad (Crítico → Urgente → Normal) al ordenar por Importancia y en el mail enviado. Ver [[02 - Módulos/Minuta_Reunion]].
- **2026-08-07:** Shell — AppShell responsive móvil (≤768px): top bar sticky, drawer off-canvas, bottom quick nav (Inicio/Salidas/Activos/Solicitudes), safe-area/100dvh/meta; Salidas cards bajo 900px; Activos cards bajo 768px. Ver [[02 - Módulos/Shell_Central]].
- **2026-08-07:** Reportes — export Excel Table (layout mail diario de gastos); mail diario/mensual scaffold con flags en 0; UI sin subtítulo bajo H1. Ver [[02 - Módulos/Reportes]].
- **2026-08-07:** Salidas — limpieza filas de prueba en `salidas_web`; formato Excel alineado a diarios de escritorio; labels UI con htmlFor/id. Ver [[02 - Módulos/Salidas]].
- **2026-08-07:** Salidas — prueba avanzada: lectura `master_codes` (ARTICULOS+config) solo lectura; escritura en `salidas_web/`; no toca Excel prod ni Firestore. Ver [[02 - Módulos/Salidas]].
- **2026-08-07:** Reportes — fuente por defecto = `master_salidas.xlsx` de producción (mismo path KPIs); `_start_reportes.bat` ya no fuerza `data_prueba`; UI sin labels de prueba. Ver [[02 - Módulos/Reportes]].
- **2026-08-06:** KPIs — sin datos con servicio OK: `master_salidas.xlsx` en 0 bytes. Restaurado desde `salidas_diaria` (~4844 filas); loader tolerante a Excel corrupto; escritura atómica en Salidas. Ver [[02 - Módulos/KPIs]].
- **2026-08-05:** Salidas — análisis + decisiones docs (0 write FS en baja; lectura = patrón etiquetas). Plan 1–5 acordado. Ver Pendientes + [[02 - Módulos/Salidas]].
- **2026-08-05:** Documentado incidente cuota Firestore etiquetas (jun-2026) en Etiquetas + Decisiones + Firebase + Firestore_Contrato (HTTP GET OK; el problema era `.get()` por búsqueda).
- **2026-08-04:** KPIs — usuario confirmó OK: sector, línea Mant., Top 10 monto/cantidad, stock por criticidad (`KpiNamedBarList`). Pendiente validar: gasto mensual, tendencia anual, donut bajo mínimo, artículos en cero, reposición, Ampliar, dark en planta, E2E.

- **2026-08-04:** Salidas — pendientes anotados: búsqueda no usa caché Firestore; falta service account; baja Excel DEMO ya posible. (Supersedido parcialmente por plan 2026-08-05.)
- **2026-08-04:** Reportes Fase 1 — servicio `:8017` + UI `/reportes` (filtros, resumen, export CSV); datos de prueba en `backend/reportes/data/`; store intercambiable para Salidas/SQL.
- **2026-08-04:** Salidas Fase 1 — servicio `:8018` + UI `/salidas` (carga pendiente, finalizar, devoluciones); Excel solo en `data_prueba/`; sync Firebase + caché SQLite diaria; helpers `movimientos.py` para Reportes.
- **2026-08-04:** Etiquetas UI — tema claro/oscuro (`etiquetas_theme`); estética AppPanolWeb; sin «¿Quién imprime?» (`solicitado_por` = `etiquetas-web`). Cerrado pendiente de paralelizar diseño visual.
- **2026-08-04:** Etiquetas — buffer última impresión; preview realista rótulo simple (desborde); flujo `mercaderia_nueva` sin catálogo.
- **2026-08-04:** KPIs — **Top 10 por cantidad** a `KpiNamedBarList` (`pesos={false}`); ambos Top 10 con etiqueta **código — descripción**.
- **2026-08-04:** KPIs — **Top 10 por monto** migrado a `KpiNamedBarList` (misma UX que sector/línea); API top-articulos OK.
- **2026-08-04:** KPIs — **Gasto por sector** arreglado de verdad: lista HTML/CSS (`KpiSectorBarList`) en lugar de Recharts (etiquetas ilegibles + escala dispar); verificado en navegador con datos 2026-08.
- **2026-08-04:** KPIs — layout gastos (superior) / pañol (inferior); gasto por sector en barras; dark mode; fix gráficos de barras.
- **2026-08-04:** Activos — backlog F3/F4/L1–L7 documentado en Pendientes (paralelo a KPIs).
- **2026-08-01:** Activos Fase 1+2 — servicio `:8016`, UI lectura/insights; **marcar regreso** con lock Excel + permiso escritura.
- **2026-08-01:** Activos Fase 1 — servicio propio `:8016`, UI rediseñada (tabs Fuera/Ingresados, filtros, dark mode); independiente de KPIs.
- **2026-07-30:** Minuta sync multi-PC + consolidación reunión vigente panol (id 29); históricos archivados.
- **2026-07-29:** Documentación de presentación actualizada en Desktop (`Sistema Integral de Pañol.docx` / Manual / PPTX): arquitectura híbrida, inventario escritorio, usuarios y supervisores.
- **2026-07-29:** Supervisor portal `PortalPanol` (vigilancia ~20 s + reinicio suave 20:00–22:00); no toca impresión.
- **2026-07-22:** Módulo **Solicitud de pedidos** en shell (`/solicitudes`) + API Starlette :8014 (SQLite, uploads locales, PDF, catálogos editables, catálogo Firestore como AppPanolWeb).
- **2026-07-17:** Layout mapa Pañol 1 (v4) + preview HTML; documentación en vault (`Mapa_Ubicacion`, reporte 2026-07-17). App en Vercel sin cambios.
- KPIs estabilizado con tendencia anual y paneles ampliables.
- Activos fuera de planta separado de KPIs y publicado como módulo propio.
- Minuta con cache por usuario y mejora de destinatarios (nombre + mail en Excel).
- Confirmado en vault escritorio: cambios 2026-07-08 (tipos de correo, precio propagado, flujo salidas).

## ⚠️ Pendiente de verificar

- Política final de permisos por rol (consulta/escritura).
- Implementación de edición con auditoría sobre archivo original de activos.
- URL de producción final y estrategia de despliegue shell.
- Salidas web: si/cuando consolidar `salidas_web` hacia el historial que consumen KPIs / escritorio.

