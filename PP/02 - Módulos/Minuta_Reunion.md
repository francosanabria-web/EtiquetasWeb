# Minuta de Reunión

**Estado:** 🔄 En desarrollo  
**Última actualización:** 2026-08-07

## Orden por criticidad en UI y mail (2026-08-07)

- Click en columna **Importancia** ordena por criticidad de negocio (no alfabético): **1. Crítico → 2. Urgente → 3. Normal** (segundo click invierte).
- Dentro de cada nivel se mantiene el `orden` manual.
- `buildMinutaMail` aplica el mismo orden al armar el cuerpo HTML/texto del envío, para leer novedades agrupadas por criticidad.
- Helper compartido: `rankImportancia` en `apps/web/src/api/minutaClient.ts`.

## Layout ancho desktop (2026-08-07)

- `.minuta-page` ya no usa `max-width: 1200px` en PC: `max-width: none` + padding `28px 32px 48px` para aprovechar el panel principal (tablas con muchas columnas).
- Móvil (≤768px): se mantiene padding compacto `16px 14px 28px` en el media query compartido.

## UX móvil (pendiente — 2026-08-07)

- El shell ya da padding consistente (`minuta-page`) y navegación móvil global.
- ⚠️ El **editor de reunión** no está phone-optimized: tabla ancha + drag HTML5. Falta vista card/ítem o aviso de uso en desktop. Ver Pendientes + [[02 - Módulos/Shell_Central]].

## Hotfix 2026-07-31 — borrado accidental + visibilidad

- Supervisor veía/archivaba/eliminaba la reunión **compartida** de pañol (regla vieja: cualquier `compartida` era visible a todos).
- Pedidos+novedades no se perdieron (fueron a Histórico); recuperados en reunión **id 30** `Reunion vigente — Mantenimiento` (46 pedidos, novedades 02/17/23/30-07).
- **Compartida** = solo entre `panol@` y `admin@`. Supervisor/jefatura solo ven las propias.
- Historial desplegable: carga novedades con `GET /pedidos/{id}` al expandir (ya no depende del poll).

## Hecho 2026-07-30 — recuperación + sync compartido

- **Datos:** 39 pedidos (+ novedades históricas, p. ej. 2026-07-23) consolidados en reunión **compartida** id **29** — `Reunion vigente — Mantenimiento`, owner `panol@panol.local`. Resto de reuniones legacy/Histórico **archivadas**.
- **Backup:** `backend/minuta_reunion/data/backup_pre_sync_20260730_090633/`.
- **Sync multi-PC:** campos y novedades se guardan en SQLite al editar (debounce ~450 ms). Polling ~4 s + refetch al foco. `localStorage` solo para destinatarios / vistos.
- **API:** `PUT /api/minuta/pedidos/{id}/novedades` — upsert 1 novedad por `(pedido_id, fecha_reunion)`. Campo `novedad_actual` en el listado de pedidos.
- **UI:** sin panel Históricos en el flujo normal; crear reunión **compartida** (default) o **individual**.

## Hotfix envío de mail 2026-07-23 (contexto)

Los pedidos habían quedado en Histórico y la reunión activa vacía. Mitigado entonces con mover-pedidos; el 30/07 se consolidó de forma definitiva en la reunión 29.

## Flujo actual

1. Login `panol` → `/minuta` → abrir **Reunion vigente — Mantenimiento** (o crear otra compartida/individual).
2. Editar ítems / novedades: se ven en cualquier PC con el mismo usuario o en la reunión compartida (≤ ~4 s).
3. Expandir ítem: historial de novedades por fecha (incluye las del 23/07).
4. Enviar mail: flush final + cuerpo armado desde DB (`novedad_actual` / novedades de la fecha), pedidos ordenados Crítico → Urgente → Normal.

## Esquema

**pedidos:** `reunion_id`, `orden`, `activo`, etc.

**novedades:** una fila por pedido y `fecha_reunion` para el texto de esa reunión (upsert).

**reuniones:** `titulo`, `tipo`, `visibilidad`, `owner_email`, `sectores_comprometidos`, `archivada`, `sector`.

## Pendientes

- Afinar modelo **compartida / individual** (próximo retoque de minutas).
- Validar en dos PCs reales en la próxima reunión de planta.
- SSE/WebSocket si el poll no alcanza.
- Migrar a MariaDB.
