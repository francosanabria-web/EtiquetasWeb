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

- [ ] 1.1 Add `openpyxl==3.1.5` to `backend/minuta_reunion/requirements.txt`

## Phase 2: Core Backend (export legible + hideable + protection + ordering, import merge)

- [ ] 2.1 Add `listar_pedidos_reunion_export(reunion_id)` to `backend/minuta_reunion/db.py` returning rows ordered by `orden ASC` with `ultima_novedad` and `consultas`
- [ ] 2.2 Add `importar_novedades_reunion(reunion_id, rows)` to `backend/minuta_reunion/db.py` matching by `pedido_id` with duplicate/consulta/no_reconocidas logic and summary counts
- [ ] 2.3 Add `_exportar_excel(reunion_id, visible_cols)` helper in `backend/minuta_reunion/db.py` building fresh `openpyxl.Workbook()` with content-based auto-width `min(max_len + 2, 60)`, `wrapText=True`, computed `row_dimensions.height`, sheet protection on Novedades column only (`locked=False` for `novedad_nueva_reunion`, empty password), and `column_dimensions.hidden` for non-visible columns

## Phase 3: Integration (endpoints + frontend button + column visibility + client)

- [ ] 3.1 Add `GET /api/minuta/pedidos/exportar-excel` route in `backend/minuta_reunion/main.py` returning `StreamingResponse` over `BytesIO` with `Content-Type` and `Content-Disposition: attachment; filename="minuta-reunion-{id}-{fecha}.xlsx"`
- [ ] 3.2 Add `POST /api/minuta/pedidos/importar-novedades` route in `backend/minuta_reunion/main.py` accepting multipart `archivo`, parsing "Novedades" sheet, delegating to `importar_novedades_reunion`
- [ ] 3.3 Add `ColumnVisibility` type and `ExportColumn` enum to `apps/web/src/modules/minuta/types.ts`
- [ ] 3.4 Add `exportarMinuta(reunionId, visibleCols?)` returning `Promise<Blob>` and `importarNovedadesMinuta(reunionId, blob)` returning merge summary to `apps/web/src/api/minutaClient.ts`
- [ ] 3.5 Add `columnVisibility` state to `apps/web/src/modules/minuta/useMinutaSession.ts` persisted via `localStorage` keyed by reunion ID
- [ ] 3.6 Add column-visibility checkbox panel to `apps/web/src/modules/minuta/TablaPedidosReunion.tsx` toolbar
- [ ] 3.7 Add "Exportar Excel" button and column-visibility toggle UI to `apps/web/src/modules/minuta/MinutaReunionPage.tsx`

## Phase 4: Testing (unit/integration)

- [ ] 4.1 Create `backend/minuta_reunion/tests/test_export.py` with unit tests for `listar_pedidos_reunion_export` ordering and `importar_novedades_reunion` duplicate/consulta/no_reconocidas logic
- [ ] 4.2 Add integration tests for export endpoint returning valid `.xlsx` with correct Content-Type, hidden columns, sheet protection, and 404 for missing/archived reunion
- [ ] 4.3 Add integration tests for import endpoint 400 without "Novedades" sheet and verify merge summary counts sum to `total_importadas`
- [ ] 4.4 Run `python -m unittest -v` and `tsc --noEmit` to confirm all tests pass and frontend build is clean
