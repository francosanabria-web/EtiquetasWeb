## Exploration: exportar-excel-minuta-5180

### Problem
The current minuta-de-reunión flow (Starlette :8013, `backend/minuta_reunion/` + `apps/web/src/modules/minuta/`) lets users manage pedidos and novedades per reunion, but **cannot produce an editable `.xlsx` deliverable** to hand to the purchasing team ("compras"). The goal is to export the *current* minuta as an Excel file so compras receives a list of pendientes with **estado actual, última novedad, consultas**, and a column to **devolver novedades nuevas**. The returned file must then be mergeable by the backend (duplicate/consulta/no_reconocidas logic), adapted to the `pedidos` table schema (not the dead 5175 COL A-X). A new legibility requirement demands: **everything readable without widening columns, nothing compressed, with hideable columns (Excel hidden flag + UI checkbox toggle)**.

### Current State
1. **Backend (`backend/minuta_reunion/main.py`)**: Starlette app on :8013, no export endpoint. `requirements.txt` has only `starlette==0.49.1` + `uvicorn[standard]==0.49.0`; **openpyxl is NOT declared** (but 3.1.5 is present in the `.venv`). No auth middleware on routes — access control is DB-level only (`owner_email`, `COMPARTIDA_EMAILS`).
2. **DB schema (`db.py`)**:
   - `pedidos`: id, pedido, n_pedido, fecha, oc, sector, reunion_id, activo, consultas, importancia, estado, orden, creado_en, actualizado_en (+ migrated `fecha_esperada`)
   - `novedades`: id, pedido_id, fecha_reunion, texto, sector, creado_en (FK → pedidos CASCADE)
   - `reuniones`: id, sector, fecha, notas_generales, email_enviado_en, titulo, tipo, visibilidad, owner_email, sectores_comprometidos, archivada, creado_en, actualizado_en
   - `pedido_movimientos`: id, pedido_id, sector_origen, sector_destino, fecha, notas, creado_en
   - Key query `listar_pedidos_reunion(reunion_id)` returns rows with `ultima_novedad`, `ultima_novedad_fecha`, `novedad_actual`, `total_novedades`.
3. **Frontend (`apps/web/src/modules/minuta/`)**:
   - `TablaPedidosReunion.tsx`: 13 columns (drag, visto, fecha, n_pedido, oc, fecha_esperada, pedido/descripción, última novedad, consultas, novedad nueva reunión, importancia, estado, acciones). No column-visibility toggle yet.
   - `MinutaReunionPage.tsx`: renders `TablaPedidosReunion` for activos + finalizados, uses `useMinutaSession(reunionId)`.
   - `minutaClient.ts`: `Pedido` type with all DB fields + `ultima_novedad`, `novedad_actual`, `total_novedades`, `novedades[]`, `movimientos[]`. No `exportarExcel` client method.
   - `useMinutaSession.ts`: polling every 4s, debounce 450ms, dirty-until 2800ms. `persistirAlEnviar()` flushes `novedad_actual` via `upsertNovedad`.
   - `types.ts`: `MinutaSesionLocal` with `borradoresNovedad`, `vistosEnReunion`, etc. No column-visibility state.
4. **Vite proxy**: `/api/minuta` → `http://127.0.0.1:8013`, with `timeout: 120_000` and `proxyTimeout: 120_000`. CORS `allow_origins="*"`.
5. **Dead 5175 reference (`openspec/changes/archive/2026-09-01-exportar-excel-minutas-compras/`)**: Was a FastAPI service (`services/minutas-api/`) exporting columns A-X + Novedades from an uploaded source workbook. Logic: `openpyxl.Workbook()` fresh, copy widths from source, lock A-X/unlock Y (protection), `StreamingResponse` over `BytesIO`, natural key `(sesion_id, ref_pedido, fila_excel)` for merge, consultas_pendientes table for conflicts. **This code was reverted and must NOT be touched.** The new implementation reuses its *logic patterns* (openpyxl, protection Y-only, natural-key merge, duplicate/consulta/no_reconocidas) but adapts to Starlette + `pedidos` table + no source workbook.
6. **Existing `openspec/specs/minuta-excel-export/spec.md`**: Belongs to dead 5175 (FastAPI, `sesiones/{id}/exportar-excel`, columns A-X). Not applicable as-is to the new 5180 scope.

### Affected Areas
- `backend/minuta_reunion/main.py` — add `GET /api/minuta/pedidos/exportar-excel?reunion_id=...` (and optionally `POST /api/minuta/pedidos/importar-novedades` merge endpoint). Must use Starlette `StreamingResponse` / `Response`, not FastAPI.
- `backend/minuta_reunion/db.py` — add `listar_pedidos_reunion_export(reunion_id)` query returning rows ordered by `orden ASC`; add `importar_novedades_reunion(reunion_id, rows)` merge logic (match by `pedido_id`, duplicate/consulta/no_reconocidas).
- `backend/minuta_reunion/requirements.txt` — add `openpyxl==3.1.5` (or compatible).
- `apps/web/src/modules/minuta/TablaPedidosReunion.tsx` — add column-visibility checkbox panel; mark columns as `hidden` in Excel output.
- `apps/web/src/modules/minuta/useMinutaSession.ts` — add `columnVisibility` state (persisted in session/localStorage).
- `apps/web/src/api/minutaClient.ts` — add `exportarMinuta(reunionId, visibleCols?)` returning `Promise<Blob>` and `importarNovedadesMinuta(reunionId, blob)` returning merge summary.
- `apps/web/src/modules/minuta/MinutaReunionPage.tsx` — add "Exportar Excel" button + column-visibility toggle UI.
- `apps/web/src/modules/minuta/types.ts` — add `ColumnVisibility` type and `ExportColumn` enum.

### Approaches

#### A. openpyxl fresh workbook + content-based auto-width (recommended)
Build a brand-new `openpyxl.Workbook()`, write pedido fields as columns in the order that matches the UI (estado, n_pedido, oc, fecha, pedido, ultima_novedad, consultas, novedades-nueva-reunion, importancia), calculate column widths from max content length per column (auto-width), set wrapText for text columns, lock all cells except the "Novedades nueva reunión" column (Y), enable sheet protection with empty password, mark optional columns as `hidden=True` based on UI selection. Return via Starlette `StreamingResponse` over `BytesIO`.
- **Pros**: no source file needed (data comes from DB, not uploaded); auto-width satisfies "legible sin agrandar columnas"; protection Y-only matches proven pattern; hidden columns handled via openpyxl `column_dimensions.hidden`; deterministic structure.
- **Cons**: widths are calculated, not copied from a template (no "pañol template" formatting); openpyxl protection is cosmetic; memory footprint grows with row count (acceptable for reunion scale).
- **Effort**: Medium.

#### B. openpyxl fresh workbook + fixed default widths
Same as A but use hardcoded default widths (e.g., 12 for text, 14 for dates) instead of content-based auto-width.
- **Pros**: simpler code; predictable layout.
- **Cons**: cannot satisfy "todo legible sin agrandar columnas, no comprimido" — short columns look empty, long text overflows; fails the explicit legibility requirement.
- **Effort**: Low. **Rejected** for requirement non-compliance.

#### C. Streaming CSV / pure streaming XLSX
Stream rows as CSV or use an XLSX streaming writer.
- **Pros**: lowest memory for huge files.
- **Cons**: CSV loses cell structure, formatting, sheet protection, hidden-column flags; XLSX streaming (openpyxl does not natively stream writes well) is fragile; protection is harder to guarantee. Rejected because the deliverable must be a formatted, protected, hideable-column `.xlsx`.
- **Effort**: Medium–High. **Rejected** for quality reasons.

### Recommendation
**Approach A** (openpyxl fresh workbook + content-based auto-width) with these specifics:

1. **Export endpoint**: `GET /api/minuta/pedidos/exportar-excel?reunion_id={id}&cols={comma-separated-col-keys}` returning `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` with `Content-Disposition: attachment; filename="minuta-reunion-{reunion_id}-{fecha}.xlsx"`. Session gate: reunion must exist and be non-archived; otherwise 404.
2. **Import/merge endpoint**: `POST /api/minuta/pedidos/importar-novedades?reunion_id={id}` accepting multipart `archivo` (.xlsx), parsing the "Novedades" sheet, matching by `pedido_id`, applying duplicate/consulta/no_reconocidas logic, returning `{procesadas, omitidas_duplicadas, pendientes_consulta, no_reconocidas, total_importadas}`.
3. **Column order** (matching UI): orden, fecha, n_pedido, oc, fecha_esperada, pedido (descripción), ultima_novedad, consultas, novedad_nueva_reunion (editable Y), importancia, estado.
4. **Auto-width**: iterate all rows twice (or keep in memory for typical scale) and set `column_dimensions[col].width = min(max(len(str(cell.value)) for cell in col) + 2, 60)`. Text columns get `wrapText = True`.
5. **Protection**: `sheet.protection.sheet = True`, `sheet.protection.password = ""`, all cells `locked=True` except the "novedad_nueva_reunion" column `locked=False`.
6. **Hideable columns**: columns not in `visibleCols` get `column_dimensions[col].hidden = True`.
7. **Frontend**: add a dropdown/checkbox panel in `TablaPedidosReunion` letting the user toggle column visibility; state persisted in `localStorage` via `useMinutaSession`. The export button sends the visible-column list as `?cols=...`.

### Risks
1. **Starlette vs FastAPI** — `StreamingResponse` comes from `starlette.responses`. openpyxl writes to `BytesIO`; must yield the bytes as an async iterator. Starlette's `StreamingResponse(content)` accepts `AsyncIterable[bytes]` or `Iterator[bytes]`. Must not use FastAPI-specific helpers (e.g., `FastAPI StreamingResponse`).
2. **openpyxl not in requirements.txt** — must add `openpyxl` to `backend/minuta_reunion/requirements.txt`. Currently only in `.venv` by coincidence.
3. **No auth middleware** — `main.py` has no auth middleware. Export/import endpoints rely on DB-level checks only. The `owner_email` / `COMPARTIDA_EMAILS` pattern in `db.py` exists but is not wired into `main.py` routes. Clarify whether export needs permission gating.
4. **Frontend Vite proxy CORS** — proxy is configured with `changeOrigin: true` and `timeout: 120_000`. Binary download returns `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`. CORS `allow_origins="*"` should allow it, but the `Content-Disposition: attachment` header must not trigger a preflight issue (it won't for GET). For the multipart import POST, ensure `Content-Type: multipart/form-data` is allowed.
5. **Legibility (auto width, wrapText, row height)** — openpyxl does not auto-adjust row height for wrapText. Long text will overflow visually unless `row_dimensions.height` is set or `wrapText` + manual height. For legibility, set `wrapText=True` on text cells and compute `row_dimensions.height` from max lines per row.
6. **Hideable columns persistence** — UI checkbox state for column visibility must persist across sessions. Store in `localStorage` (via `useMinutaSession` / `MinutaSesionLocal`) keyed by reunion ID. Excel hidden flags are file-scoped.
7. **Large files** — typical reunion has <200 pedidos; openpyxl in memory is fine. If scale grows, consider streaming write or temp file. Mitigation: keep read-only in-memory for the typical case.
8. **Merge semantics on return** — "devolver novedades nuevas" must be unambiguous: new novedad text → apply; identical text → skip (duplicate); different text on same pedido → consulta-pendiente (keep both, escalate); unknown pedido_id → no_reconocidas. Natural key is `pedido_id` (each pedido row is unique).
9. **Date format round-trips** — `fecha`, `fecha_esperada`, `fecha_reunion` are stored as ISO strings (`YYYY-MM-DD`). Export as date strings or real Excel dates with matching format; avoid Excel reinterpreting as serial numbers.
10. **Archived/legacy reuniones** — `reunion_id=0` pedidos are assigned to "Histórico" reuniones by `_migrar`. Export should include them if they belong to the queried reunion; clarify edge case.

### Alternatives Rejected
- **Approach B (fixed default widths)** — rejected because it cannot satisfy the explicit legibility requirement ("todo legible sin agrandar columnas, no comprimido").
- **Approach C (CSV / streaming XLSX)** — rejected because the deliverable requires cell structure, sheet protection, and hidden-column flags.
- **Store source workbook bytes** — rejected because there is no source workbook; data is generated from SQLite, not uploaded.
- **Hidden `fila_id` column for merge** — rejected because `pedido_id` is already the unique natural key; no hidden columns needed.
- **Extend `novedades` table with `estado` column for consultas** — rejected as premature; the merge endpoint can report consultas in the response summary and create a new `consultas_pendientes` table only if the frontend needs a review panel (out of scope for this slice).
- **Workbook-level protection** — rejected; sheet-level protection on the novedades column is the correct granularity (compras must be able to review/read all columns).

### Open Questions
1. **Merge endpoint scope**: Is `POST /api/minuta/pedidos/importar-novedades` in scope for this slice, or should the "devolver novedades" flow use the existing `upsertNovedad` per-pedido API (one-by-one)? The requirement to "reuse merge por key / duplicate / consulta / no_reconocidas" implies a bulk import endpoint.
2. **Column list**: Which columns are exported by default? Recommendation: all columns visible in `TablaPedidosReunion` except "acciones" and "drag" (non-data columns). The `cols` query param allows filtering.
3. **Permission gating**: Should export be restricted to `owner_email` or `COMPARTIDA_EMAILS`? `main.py` has no auth middleware; clarify before adding one.
4. **Archived reuniones**: Should the export include pedidos from "Histórico" reuniones (`reunion_id` legacy)? Clarify whether `listar_pedidos_reunion` with `solo_activos=False` is the right scope.
5. **Row height for wrapText**: openpyxl does not auto-set row height. Should we compute it from `wrapText` + max line count, or leave it to Excel's default?
6. **Frontend column-visibility UI**: Where to place the toggle? Options: (a) a dropdown menu in `TablaPedidosReunion` toolbar, (b) a separate panel in `MinutaReunionPage`. Recommendation: a small "⚙ Columnas" button in the toolbar.
7. **Session gate**: What reunion `estado` allows export? The `reuniones` table has no `estado` field (only `archivada`). Export likely allowed for any non-archived reunion. Clarify.
8. **Filename convention**: `minuta-reunion-{reunion_id}-{fecha}.xlsx`? Match the dead 5175 pattern `minuta-{semana_iso}.xlsx`?

### Ready for Proposal
Yes — the approach is clear enough to propose. Main decisions to lock in the proposal phase: (a) whether the merge-import endpoint is in-scope or the existing per-pedido `upsertNovedad` suffices, (b) the exact column list and default visibility, (c) permission gating approach, (d) row-height handling for wrapped text.
