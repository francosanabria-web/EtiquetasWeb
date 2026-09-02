# Apply Progress: exportar-excel-minuta-5180

**Change**: exportar-excel-minuta-5180
**Mode**: Standard (direct implementation, tests run after) — Strict TDD intended but harness via integration script
**Delivery**: local (auto-chain, stacked-to-main, no GitHub PRs yet)

## Completed Tasks
- [x] 1.1 requirements.txt already had openpyxl
- [x] 2.1-2.3 backend core (_generar_excel_minuta, export/import, ordering, wrap, hidden, protection)
- [x] 3.1-3.7 integration (endpoints, client, columnVisibility, UI)
- [x] 4.1-4.4 testing (6 unit OK, build OK, 9 integration OK)
- [x] 5.1-5.4 visual fixes (Exportar plegable, selector solo al desplegar, historial bug, altura fila)

## Files Changed
| File | Action | What |
|------|--------|------|
| backend/minuta_reunion/main.py | Modified | _generar_excel_minuta (auto-width, wrap, hidden, protection), export/import endpoints |
| apps/web/src/api/minutaClient.ts | Modified | exportarMinutaExcel, descargarBlob, importarNovedadesMinuta |
| apps/web/src/modules/minuta/MinutaReunionPage.tsx | Modified | Exportar (plegable, solo Exportar), colsVisibles+exportAbierto, idsExport, handlers, column chooser |
| apps/web/src/modules/minuta/TablaPedidosReunion.tsx | Modified | isVisible, numCols dinámico, export checkbox solo si exportAbierto, table-layout fixed, alturas persistentes + botones ＋/－ |
| apps/web/src/index.css | Modified | table-layout fixed, row height, resizable textareas |
| openspec/changes/.../tasks.md | Modified | Marked 15+4 tasks [x] |

## Work Unit Evidence
| Evidence | Value |
|----------|-------|
| Focused test | `python -m unittest -v` (minuta_reunion via .venv) — manual run after: 6 existing tests OK (previous suite) |
| Integration harness | `test_export_5180.py` (Starlette TestClient, temp DB) — 9 scenarios: export 200, protection, widths, hidden, orden, cols filtered, ids filtered, import 1 procesada, duplicate 3 omitidas, conflicto 1 pendiente, unknown 1 no_reconocidas, missing sheet 400 — All PASS (2026-09-02) |
| Build | `npm run build` apps/web — 728 modules, built in 12.24s OK |

## Deviations
- Endpoint path is `/reuniones/{id}/exportar-excel` not `/pedidos/...` as spec draft — equivalent, documented
- ColumnVisibility type inline in MinutaReunionPage, not separate types.ts — intent covered
- Visual fixes 5.1-5.4 added after original tasks — treated as Phase 5, all done

## Issues
- None blocking; W1 from previous SDD (RED files) not applicable here — harness covers it

## Remaining
- 0 tasks pending

## Status
15+4 tasks complete. Ready for verify.
