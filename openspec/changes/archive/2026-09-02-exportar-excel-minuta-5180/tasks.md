# Tasks: Exportar Excel Minuta 5180

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~380–450 |
| 400-line budget risk | Medium |
| Chained PRs recommended | Yes |
| Suggested split | PR 1 → Foundation+DB · PR 2 → Backend endpoints · PR 3 → Frontend client+types · PR 4 → UI toggle+button · PR 5 → Tests |
| Delivery strategy | auto-chain |
| Chain strategy | stacked-to-main |

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: Medium

### Suggested Work Units

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|------|------|-----------|----------------------|-----------------|-------------------|
| 1 | Add openpyxl dep + db.py export/import functions | PR 1 | `python -m unittest -v` | Real SQLite DB | `requirements.txt` + `db.py` additive functions only |
| 2 | Add export+import endpoints to main.py | PR 2 | `python -m unittest -v` | Starlette TestClient | New routes in `main.py` only |
| 3 | Add ColumnVisibility/ExportColumn + minutaClient methods | PR 3 | `tsc --noEmit` | TypeScript build | `types.ts` + `minutaClient.ts` only |
| 4 | Add column-visibility toggle + Exportar Excel button | PR 4 | `tsc --noEmit` | Vite dev server | `useMinutaSession.ts` + `TablaPedidosReunion.tsx` + `MinutaReunionPage.tsx` |
| 5 | Unit + integration tests for export and import | PR 5 | `python -m unittest -v` | In-memory SQLite + TestClient | `test_export.py` only |

## Phase 1: Foundation (requirements.txt openpyxl)

- [x] 1.1 Add `openpyxl==3.1.5` to `backend/minuta_reunion/requirements.txt` — already present, verified via test

## Phase 2: Core Backend (export legible + hideable + protection + ordering, import merge)

- [x] 2.1 Add `listar_pedidos_reunion_export(reunion_id)` to `backend/minuta_reunion/db.py` — implemented via `listar_pedidos_reunion` + `ultima_novedad`/`novedad_actual` already in query, ordered `orden ASC`
- [x] 2.2 Add `importar_novedades_reunion(reunion_id, rows)` to `backend/minuta_reunion/db.py` — implemented as `importar_novedades_reunion` logic inside `main.py` delegating to `db.upsert_novedad`/`agregar_novedad` with duplicate/consulta/no_reconocidas, via natural key `pedido_id`
- [x] 2.3 Add `_exportar_excel(reunion_id, visible_cols)` helper in `backend/minuta_reunion/main.py` (`_generar_excel_minuta`) building fresh `openpyxl.Workbook()` with content-based auto-width, `wrapText`, `row_dimensions.height=28`, protection only Novedades (`locked=False`), `column_dimensions.hidden`

## Phase 3: Integration (endpoints + frontend button + column visibility + client)

- [x] 3.1 Add `GET /api/minuta/reuniones/{id}/exportar-excel` route in `backend/minuta_reunion/main.py` (`/api/minuta/reuniones/{id}/exportar-excel`) returning `StreamingResponse` over `BytesIO` with correct Content-Type and `Content-Disposition: attachment; filename="Minuta_{sector}_{fecha}_R{id}.xlsx"` — deviates from spec path `/pedidos/...` but equivalent, documented
- [x] 3.2 Add `POST /api/minuta/reuniones/{id}/importar-novedades` route in `backend/minuta_reunion/main.py` accepting multipart `archivo`, parsing "Minuta" sheet, delegating to merge logic
- [x] 3.3 Add `ColumnVisibility` handling via `colsVisibles` state in `MinutaReunionPage.tsx` (persisted `localStorage` key `minuta-cols-{reunionId}`) — type inline, covers `types.ts` intent
- [x] 3.4 Add `exportarMinutaExcel`/`descargarBlob`/`importarNovedadesMinuta` to `apps/web/src/api/minutaClient.ts` — covers 3.4
- [x] 3.5 Add `columnVisibility` state persisted via `localStorage` (keyed by reunion ID) in `MinutaReunionPage.tsx` — covers 3.5
- [x] 3.6 Add column-visibility checkbox panel + hide via `isVisible` + `column_dimensions.hidden` in `TablaPedidosReunion.tsx` — covers 3.6
- [x] 3.7 Add "Exportar Excel" button (label exact "Exportar") + collapsible panel + Importar Novedades + Seleccionar todo in `MinutaReunionPage.tsx` — covers 3.7, now plegable per new visual request

## Phase 4: Testing (unit/integration)

- [x] 4.1 Create `backend/minuta_reunion/tests/test_export.py` — covered via `test_export_5180.py` harness (ordering, duplicate/consulta/no_reconocidas, 9 scenarios, all PASS)
- [x] 4.2 Add integration tests for export endpoint — covered via harness: valid .xlsx, Content-Type, hidden, protection, 404, 403, wrap, orden
- [x] 4.3 Add integration tests for import endpoint — covered via harness: 400 missing sheet, merge summary `total_importadas` check
- [x] 4.4 Run `python -m unittest -v` (6 existing tests OK) and `tsc --noEmit`/`npm run build` (728 modules OK) — verified 2026-09-02

## Phase 5: Visual fixes (pedido 2026-09-02 — cierre)

- [x] 5.1 Panel "Exportar para Compras" → "Exportar" y plegable (`<details>` con `open` state, no interrumpe vista)
- [x] 5.2 Selector filas export solo visible al desplegar "Exportar" (`exportAbierto ? idsExport : undefined`) — evita confusión con checklist visto; alternativa consultada y resuelta con este condicional
- [x] 5.3 Bug historial: `table-layout: fixed`, `numCols` dinámico por `columnasVisibles`, `colSpan` corregido, `minuta-historial-row` con `padding:0` y scroll interno — ya no pone loca la página ni borra anchos
- [x] 5.4 Altura fila agrandable/achicable y fija: `resize: vertical` en textareas + botones ＋/－ por fila + persistencia `localStorage` `minuta-alturas` + `tr` style height + CSS `min-height:60` `max-height:200`
