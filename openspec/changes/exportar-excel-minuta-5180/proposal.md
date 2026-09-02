# Proposal: Exportar Excel Minuta 5180

## Intent

The minuta-de-reunión flow (Starlette :8013) cannot produce an editable `.xlsx` deliverable for the purchasing team ("compras"). We need an Excel export of the current minuta with estado actual, última novedad, consultas, and a column to return new novedades — readable without widening columns, nothing compressed, with hideable columns and sheet protection on the Novedades field only.

## Scope

### In
- **Exportar Excel** button ("Exportar Excel") generating `.xlsx` from selected pedidos ordered by `orden/importancia`, with estado actual, última novedad, consultas, novedades nueva reunión, etc.
- Selection of elegibles with filter + "Seleccionar todo" per pedido.
- **Importar Novedades** bulk merge (keyed by `pedido_id`) with duplicate/consulta/no_reconocidas logic, non-destructive.
- Auto-width content-based widths, `wrapText`, sheet protection only on Novedades column, hideable columns via `column_visibility`, filename `minuta-reunion-{id}-{fecha}.xlsx`.

### Out of Scope
- Source workbook bytes storage (no source file; data comes from SQLite).
- Archived reuniones export or CSV as primary deliverables (future extensions).
- Auth middleware on routes (DB-level access control remains).

## Capabilities

### New Capabilities
- `minuta-export-5180`: Export current minuta to `.xlsx` with legible auto-width, hideable columns, and sheet protection.
- `minuta-novedades-import-5180`: Bulk import/merge of returned novedades by `pedido_id` with duplicate/consulta/no_reconocidas handling.

### Modified Capabilities
- `minuta-reunion`: Export endpoint (`GET /api/minuta/pedidos/exportar-excel`) and merge endpoint (`POST /api/minuta/pedidos/importar-novedades`) added to the existing Starlette app.

## Approach

Approach A from exploration: fresh `openpyxl.Workbook()`, content-based column widths calculated from max cell content, `wrapText=True` on text columns, all cells locked except the Novedades nueva reunión column (sheet protection with empty password), optional columns marked `hidden=True` based on UI visibility selection. Return via Starlette `StreamingResponse` over `BytesIO`. Frontend adds column-visibility toggle persisted in `localStorage` and sends visible columns as `?cols=...`. Merge endpoint parses the "Novedades" sheet, matches by `pedido_id`, applies duplicate/consulta/no_reconocidas logic.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `backend/minuta_reunion/main.py` | Modified | Add `GET /api/minuta/pedidos/exportar-excel` and `POST /api/minuta/pedidos/importar-novedades` endpoints using Starlette `StreamingResponse` |
| `backend/minuta_reunion/db.py` | Modified | Add `listar_pedidos_reunion_export(reunion_id)` ordered query and `importar_novedades_reunion(reunion_id, rows)` merge logic |
| `backend/minuta_reunion/requirements.txt` | Modified | Add `openpyxl==3.1.5` |
| `apps/web/src/modules/minuta/TablaPedidosReunion.tsx` | Modified | Add column-visibility checkbox panel; mark non-selected columns as hidden in Excel output |
| `apps/web/src/modules/minuta/useMinutaSession.ts` | Modified | Add `columnVisibility` state persisted via localStorage |
| `apps/web/src/api/minutaClient.ts` | Modified | Add `exportarMinuta()` returning `Promise<Blob>` and `importarNovedadesMinuta()` returning merge summary |
| `apps/web/src/modules/minuta/MinutaReunionPage.tsx` | Modified | Add "Exportar Excel" button + column-visibility toggle UI |
| `apps/web/src/modules/minuta/types.ts` | Modified | Add `ColumnVisibility` type and `ExportColumn` enum |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| `openpyxl` not in `requirements.txt` (only in `.venv`) | High | Explicitly add `openpyxl==3.1.5` to requirements |
| Starlette `StreamingResponse` with `BytesIO` for binary download | Med | Use `Response(content=iterator, media_type=...)` with async iterator; avoid FastAPI helpers |
| Row height not auto-adjusting for `wrapText` | Med | Compute `row_dimensions.height` from max line count per row |
| No auth middleware on export/import routes | Med | DB-level checks only (`owner_email`, `COMPARTIDA_EMAILS`); gate by reunion existence + non-archived |
| Column-visibility state persistence across sessions | Low | Persist in `localStorage` keyed by reunion ID |

## Rollback Plan

No persistent state changes. If the export/import endpoints cause issues, remove the new routes from `main.py` routing and revert `requirements.txt`; DB functions in `db.py` are additive (safe to leave). Frontend changes are behind a feature toggle in the component tree if needed.

## Dependencies

- `openpyxl==3.1.5` (add to `backend/minuta_reunion/requirements.txt`; already present in `.venv`)
- Starlette `StreamingResponse` / `Response` from `starlette.responses`
- Vite proxy `/api/minuta` already configured with `timeout: 120_000` and `changeOrigin: true`

## Success Criteria

- [ ] `GET /api/minuta/pedidos/exportar-excel?reunion_id=5180` returns `.xlsx` with correct columns, auto-width, wrapText, hidden columns, and sheet protection on Novedades only
- [ ] Filename follows `minuta-reunion-{id}-{fecha}.xlsx` pattern
- [ ] `POST /api/minuta/pedidos/importar-novedades` returns merge summary with `procesadas`, `omitidas_duplicadas`, `pendientes_consulta`, `no_reconocidas`
- [ ] Frontend column-visibility toggle persists across sessions and drives which columns are hidden in the export
- [ ] All existing tests pass; no regressions in `minuta_reunion` or frontend build
