# Backlog — tareas concretas (sin fecha)

**Última actualización:** 2026-08-07

## KPIs / Excel producción

- [ ] Revisar **historial de versiones de Google Drive** de `master_salidas.xlsx` (versión antigua / “100”) y comparar filas vs rebuild desde diarios.
- [ ] **Escritorio:** hacer atómica `_escribir_excel_formateado` en `almacen_gui.py` (tmp + replace) — pendiente OK explícito para tocar el `.py`.
- [x] Restaurar `master_salidas` desde diarios + endurecer loader KPIs + write atómico Salidas web (2026-08-06).
- [x] Causa raíz documentada: escritura no atómica del escritorio + truncado a 0 (ver [[02 - Módulos/KPIs]]).

## Salidas

> **NO write Firestore en baja.** Catálogo FS = ingreso Excel / futuro HeidiSQL.
> Decisiones: [[01 - Estado del Proyecto/Decisiones]]. Módulo: [[02 - Módulos/Salidas]].

### Hecho 2026-08-07 (prueba avanzada)
- [x] Lectura `master_codes` planta (ARTICULOS + config) solo lectura.
- [x] Escritura egresos en `salidas_web/` (historial + diario).
- [x] Default `SALIDAS_FIREBASE_WRITE=0`; `maestro_writable=false` en planta.
- [x] Verificado health / catálogos / artículo / confirm de prueba sin tocar Excel prod.
- [x] Limpieza filas de prueba (99999/99998, PRUEBA-WEB) en `salidas_web`.
- [x] Formato Excel consolidado (cabecera/anchos/$/freeze como diarios escritorio).
- [x] Labels accesibles en UI Salidas (`htmlFor`/`id`).

### Pendiente
1. [ ] Cablear búsqueda = patrón etiquetas (pull diario FS → SQLite + memoria; `GET /articulo` local).
2. [ ] Credenciales Firebase **solo lectura** en PC pañol (si se usa pull).
3. [ ] ⚠️ Decidir consolidación `salidas_web` → historial prod / KPIs (hoy Reportes lee `master_salidas` prod del escritorio; la web escribe aparte).
4. [ ] Auth token (:8015) en escritura API.
5. [ ] Buscador F3 / por descripción; simulador de costo; MariaDB.

### Backlog módulo
- [ ] Simulador de costo (escritorio).
- [ ] Buscador F3 / por descripción.
- [ ] Auth token (:8015) en escritura API salidas.
- [ ] MariaDB + Excel como export.

## Operación PC pañol — supervisores

- [x] Tarea `PortalPanol` instalada (vigilancia portal + reinicio suave 20:00–22:00).
- [ ] Observar 1–2 días el reinicio nocturno (logs en `scripts/logs/supervisor_panol.log`).
- [ ] ⚠️ No mezclar `INICIAR_TODO.bat` con `PortalPanol` activo.

## Accesos / Usuarios

### Hecho 2026-07-29
- [x] Servicio `usuarios` (:8015, SQLite) con login real, PBKDF2 y token de sesión.
- [x] Gestión desde la app (solo admin): alta/baja, usuario y contraseña, matriz de permisos por módulo.
- [x] Cambio de contraseña propio; permisos aplicados en sidebar/inicio y guard por URL.
- [x] Seed de los 4 usuarios previos con usuarios cortos; login sin credenciales demo.

### Pendiente
- [ ] Exigir el token de sesión en el resto de los servicios (hoy confían en la LAN).
- [ ] Migrar `usuarios.db` a la base central (MariaDB/HeidiSQL).
- [ ] Auditoría de cambios de usuarios (quién / cuándo / qué).

## Minuta de reunión

### Hecho 2026-07-30
- [x] Recuperación: 39 pedidos + novedades consolidados en reunión compartida `panol` (id 29); históricos/legacy archivados.
- [x] Sync multi-PC: campos y novedades se persisten al editar (debounce); polling ~4 s; `PUT .../novedades` upsert por fecha.
- [x] UI sin panel Históricos en el flujo normal; crear reunión compartida/individual por usuario.
- [x] Backup previo en `backend/minuta_reunion/data/backup_pre_sync_20260730_090633/`.

### Pendiente
- [ ] **Afinar compartida / individual** (próximo retoque): reglas de producto, textos UI, quién puede crear compartida, y si admin debe ver individuales ajenas. Hoy: compartida = solo panol+admin; individual = solo el owner.
- [ ] Tiempo real más fino (SSE/WebSocket) si el poll 4 s no alcanza en planta.
- [ ] Migrar `minutas.db` a MariaDB.

## 🔴 PRIORIDAD 1 — Minuta: multi-PC / tiempo real — HECHO (base)

> Mitigado 2026-07-30: fuente de verdad en servidor + poll. Validar en dos PCs reales en la próxima reunión.

---

## Solicitud de pedidos — 🔴 Continuar mañana (pausado 2026-08-05)

> **Pausado 2026-08-05 — retomar mañana.** Análisis hecho; **NO** se implementó código de importación.
> Objetivo: importar historial de pedidos viejos a la **planilla operativa editable** (`solicitudes_pedidos.xlsx`), no como pestaña Historial aparte.
> Ver [[02 - Módulos/Solicitud_Pedidos]] y decisión en [[01 - Estado del Proyecto/Decisiones]].

### Hecho 2026-08-05 (análisis + decisión — sin código)
- [x] Análisis del archivo historial y del destino operativo.
- [x] Decisión de producto: **NO** pestaña Historial solo lectura; **SÍ** merge/import al Excel canónico editable.
- [x] Identificado archivo fuente y hojas a considerar.
- [x] Detectada colisión TR históricos vs TR operativos actuales.

### Fuente y destino (estado conocido)
- **Archivo historial:** `C:\Users\Mantenimiento\Desktop\AppWebSalidas\docs\ejemplos\8.Registro solicitudes Pañol@Pedidos 2025.xlsx`
  - ~2564 ítems / ~1360 pedidos
  - Hojas: `Base datos 2025`, `PP2026`, `Pedidos PDP`, `Pedidos TR`
  - Ignorar hoja `Tabla 26`
- **Destino:** Excel operativo `solicitudes_pedidos.xlsx` (Drive / config del backend solicitudes), editable vía app.
- Planilla operativa ya tiene **P-4545+** y **TR-0001..3** → colisión con TR históricos 1–3.

### ⚠️ Decisiones bloqueantes (confirmar mañana antes de dry-run / import)
1. [ ] **Alcance:** ¿4 hojas o subset? ¿Todos los estados o solo abiertos? ¿El archivo final en `docs/ejemplos` es el OK para importar?
2. [ ] **Tipos:** PP26 / PDP — ¿nuevos tipos de pedido o string en `N_PEDIDO`? TRAB.TERM en Base (¿como P-?). PROV.UNICO. ¿Padding `TR-001` → `TR-0001`?
3. [ ] **Colisión TR:** históricos `TR-001..3` vs operativo actual `TR-0001..3` — ¿renumerar, saltar, prefijo, o otra regla?
4. [ ] **Estados:** mapeo legado → estados actuales; ¿estado por ítem o solo por pedido?
5. [ ] **Campos extra:** ¿perder precio / RQ / comprador / etc. o extender schema? Remito/proveedor distinto por ítem — ¿cómo mapear?
6. [ ] **`CUENTA_CONTABLE`:** obligatoria en operativo, ausente en legado — ¿default / relajar validación / mapear?
7. [ ] **`CREADO_POR`** y normalización de unidades — valores por defecto / reglas.
8. [ ] **Operación:** ventana de backup + parar servicio; ¿incluye historial pre-2025? ¿adjuntos?

### Proceso propuesto (mañana, tras confirmar decisiones)
1. [ ] Freeze operativo (parar servicio / ventana acordada)
2. [ ] Backup de `solicitudes_pedidos.xlsx` (+ `.bak` existente)
3. [ ] Dry-run (reporte de filas, colisiones, campos faltantes) — **sin escribir**
4. [ ] Resolver colisión TR según decisión
5. [ ] Merge al Excel canónico
6. [ ] Actualizar hoja `CONTADORES` (pedido / tr)
7. [ ] Validar en app (`/solicitudes`)
8. [ ] Go-live

### Backlog módulo (sigue pendiente)
- [ ] Migrar de Excel (Drive) a **MariaDB/HeidiSQL** (fase siguiente).
- [ ] Publicar URL / servicio externo para la otra app de Mantenimiento (mismo contrato API).
- [ ] Ampliar sugerencias de área / máquina y de proveedores (`CATALOGOS_EDITABLES.json`).
- [ ] ⚠️ Confirmar si supervisor debe poder cancelar / cumplir sin pasar por pañol.
- [ ] Adjuntos en Drive: revisar rendimiento/concurrencia si crece el volumen.

### Hecho 2026-07-24
- [x] Fuente de verdad = Excel en Drive (lock + escritura atómica + `.bak`).
- [x] `P-####` automático (Normal/Urgente); TR mantiene `TR-####`.
- [x] Campo **proveedor** (obligatorio en TR) con sugerencias.
- [x] Remito/presupuesto editables por cualquier usuario.
- [x] Panel TR con Descripción/Máquina/Cantidad/Proveedor/Presupuesto/Remito/Estado.
- [x] Descarga PDF (sin «(Compras)») y **Excel** de la solicitud.


## AppPanolWeb — Mapa / Ubicación

- [ ] Validar preview Pañol 1 v4 (`docs/preview-panol1.html`) en planta
- [ ] Croquis Pañol 2 (incl. sueltas 11, 16, 21, 37)
- [ ] Implementar pestaña **Ubicación** en local
- [ ] Botón **Ver en mapa** desde buscador
- [ ] Parser ubicaciones tipo piso `100070` (si no matchea regex actual)
- [ ] Modo editable del mapa (pañolero): mover/agregar/títulos
- [ ] Deploy Vercel solo tras prueba local OK

## Puente buscador (AppPanolWeb) → etiquetas — 2026-08-04

> Consulta hecha; **no implementar aún**. Ver [[02 - Módulos/Etiquetas]] y [[03 - Documentacion Tecnica/Frontend/AppPanolWeb]].

- [ ] **etiquetas-web:** soportar deep link / query params para prellenar etiqueta tipo `codigo` (`tipo`, `codigo`, `descripcion`, `ubicacion`, `qr_data`; opcional `auto=1` para enviar a imprimir). Hoy no lee query params.
- [ ] **AppPanolWeb:** botón “Imprimir etiqueta” en resultados del buscador que abra esa URL con `codigo`, `descripcion` (= campo `desc`), `ubicacion` (fallback si vacía, ej. `SIN UBICAR`). ⚠️ Requiere permiso explícito del usuario con la frase exacta **"modificar AppPanolWeb"** (regla permanente).
- [ ] **Obstáculo prod:** AppPanolWeb en HTTPS (Vercel) no puede POST directo a API LAN HTTP (mixed content). Preferir deep link a etiquetas-web HTTP en LAN. POST directo solo viable en LAN/local o con proxy HTTPS a futuro.
- [ ] Payload API de referencia: `POST /etiquetas` tipo `codigo` con `codigo`, `descripcion`, `ubicacion`, `qr_data` (=codigo); opcionales `cantidad`, `solicitado_por`.

## Shell / UX móvil (2026-08-07)

### Hecho
- [x] AppShell responsive ≤768px: top bar sticky, drawer off-canvas, bottom quick nav (Inicio/Salidas/Activos/Solicitudes, por permisos).
- [x] safe-area-inset / 100dvh / viewport-fit=cover / theme-color / apple-mobile-web-app meta.
- [x] Touch targets ≥44px; inputs 16px en móvil; `.btn-secondary`; padding sol/minuta/rep.
- [x] Salidas: carga pendiente en cards bajo 900px.
- [x] Activos: listado en cards bajo 768px.
- [x] Desktop: sidebar colapsable sin cambios (ignorado en móvil).

### Pendiente
- [ ] **Minuta reunión:** editor no phone-optimized (tabla ancha + drag HTML5) — vista card/ítem o aviso solo-desktop. Ver [[02 - Módulos/Minuta_Reunion]].
- [ ] **KPIs / Reportes:** siguen orientados a consulta en teléfono (sin rediseño mobile-first).
- [ ] Opcional: PWA ligera / «Add to Home Screen».

## Integración y UX

- [ ] Integrar **Etiquetas** al shell como ruta interna (hoy enlace externo).
- [ ] Reemplazar auth demo por autenticación real (siguiente paso tras sync minutas).
- [ ] Definir permisos finos por rol (consulta / escritura) aplicados en UI y backend.
- [ ] Configurar alta/baja de usuarios desde archivo editable y luego desde backend / Google Drive local.
- [ ] Aplicar permisos reales a reuniones compartidas por sector (hoy demo).

## Identidad visual (otros frontends)

### Hecho 2026-08-04 — etiquetas-web
- [x] **Paralelizar el diseño visual del módulo de etiquetas (`etiquetas-web`) con el sistema de pañol en general** (tokens/tema alineados a AppPanolWeb búsquedas; ver [[02 - Módulos/Etiquetas]]).
- [x] Identidad profesional en `etiquetas-web`: tema claro/oscuro persistente (`etiquetas_theme`, toggle header); sin UI «¿Quién imprime?» (`solicitado_por` fijo `"etiquetas-web"`).

### Pendiente
- [ ] Identidad en `minutas-web` legado / stack 5175.
- [ ] Identidad en AppPanolWeb.
- [ ] Agregar skills de diseño Cursor para homogeneizar frontends.

## Activos fuera de planta — pendientes

### Hecho
- [x] Fase 1: servicio `:8016` + UI lectura (tabs/filtros/dark) — 2026-08-01.
- [x] Fase 2: marcar regreso + restablecer + formato Excel (lock/tmp/bak) — 2026-08-01.
- [x] Export PDF/Excel por vista (fuera | ingresados).
- [x] Mensaje claro si Excel está abierto (sin Retry en modal).

### Fase 3 (próximo — orden acordado)
- [ ] **Editar** ítems que siguen fuera de planta (campos operativos).
- [ ] **Alta nueva** de salida de activo (CTA "Registrar salida" cuando escriba).
- [x] Restablecer a fuera (ya en Fase 2).

### Fase 4
- [ ] Auditoría de cambios (quién / cuándo / qué).
- [ ] Mail diario de seguimiento desde web.
- [ ] Apagar **solo** el bloque activos del job 07:30 del `.exe`; marcador anti-duplicado compartido.

### UX / backlog
- [ ] Rediseñar indicador claro L1–L7 en ingresados (retirado por poco claro).
- [ ] Validar operación diaria en planta tras Fase 3.

## Minuta (resto)

- [ ] Validar / retirar stack minutas-api/minutas-web legado.
- [ ] Embutir envío SMTP sin proceso aparte.

## KPIs — en curso (2026-08-04)

### Hecho (confirmado por usuario en planta / navegador)
- [x] **Gasto por sector** — `KpiNamedBarList` (HTML/CSS; ya no Recharts).
- [x] **Gasto por línea Mant.** — `KpiNamedBarList`.
- [x] **Top 10 por monto** — `KpiNamedBarList`; etiqueta código + descripción.
- [x] **Top 10 por cantidad** — `KpiNamedBarList` con `pesos={false}`; código + descripción.
- [x] **Stock valorizado por criticidad** — `KpiNamedBarList` + colores por criticidad.

### Hecho (sesión; ⚠️ revalidar en planta light/dark)
- [x] Layout: superior = gastos / inferior = pañol (stock, faltantes, valorizado, reposición).
- [x] Tokens dark mode en shell KPI (`kpis.css` + charts).
- [x] Gasto por sector arriba como barras (antes donut).

### Pendiente — indicadores aún sin confirmar (varios siguen en Recharts)
- [ ] **Gasto mensual (12 meses)** — `KpiLineChart` (Recharts). ⚠️ No validado por usuario.
- [ ] **Tendencia anual por sector** — `KpiMultiLineChart` (Recharts). ⚠️ No validado.
- [ ] **Bajo mínimo vs sobre mínimo** — `KpiDonutChart` (Recharts). ⚠️ No validado.
- [ ] **Artículos en cero** — tabla HTML. ⚠️ No validado.
- [ ] **Reposición** — alertas críticas + tabla + modal "Ver todos". ⚠️ No validado.
- [ ] **Ampliar** (`KpiExpandable`) — altura chart/tabla al expandir. ⚠️ Verificar en cada panel.
- [ ] **Dark mode completo en planta** — hard-refresh `/kpis` light + dark con datos reales del mes.
- [ ] ⚠️ `KpiBarChart` ya no se renderiza (solo exporta tipo `BarItem`); candidata a limpieza / retirar Recharts de barras.
- [ ] Tests E2E del dashboard KPIs.
- [ ] Optimización de bundle (code splitting adicional).
- [ ] Permisos finos de consulta por rol.

> Criterio: ir **uno por uno** con los pendientes de arriba hasta confirmación en planta. No tocar Activos aquí (ver sección Activos).

## Backend / servicios

- [ ] Completar tests de `email_service` y `backend/minuta_reunion`.
- [x] Portar API de Reportes Fase 1 (listado/filtros/CSV) — 2026-08-04; ver [[02 - Módulos/Reportes]].
- [x] Reportes: export Excel Table (layout diario de gastos) — 2026-08-07; CSV deprecado.
- [x] Reportes: scaffold mail diario/mensual con flags OFF — 2026-08-07 (sin scheduler ni envíos reales).
- [ ] Reportes: conectar store a Salidas (`movimientos.py` / API :8018) o SQL.
- [ ] Reportes: completar cuerpo HTML multi-sector del mail escritorio + activar flags/tarea cuando negocio lo pida.
- [ ] ⚠️ Reportes: reiniciar servicio :8017 para tomar `export.xlsx` / `mail/*` (proceso viejo responde 404).
- [ ] Portar resto de APIs de Salidas (escritura producción) desde escritorio.

## Datos y migración

- [ ] ⚠️ Definir esquema MariaDB y plan de migración desde Excel.
- [ ] Contrato Firestore documentado al día (lectura vs escritura).
