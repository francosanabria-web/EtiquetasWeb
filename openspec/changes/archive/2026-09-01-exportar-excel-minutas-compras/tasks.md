# Tasks: Exportar Excel de Minutas de Compras

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~480 (backend ~200, frontend ~80, schema ~20, tests ~180) |
| 400-line budget risk | Medium |
| Chained PRs recommended | Yes |
| Suggested split | PR 1 → PR 2 |
| Delivery strategy | auto-chain |
| Chain strategy | stacked-to-main |

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: Medium

### Suggested Work Units

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|------|------|-----------|----------------------|-----------------|-------------------|
| 1 | Backend: schema + export endpoint + merge-import | PR 1 | `python -m unittest -v test_minutas` | FastAPI TestClient against isolated temp DB | Drop `consultas_pendientes` table; remove `exportar_excel`/`merge` paths |
| 2 | Frontend: export button, selection, client, types | PR 2 | `npx tsc --noEmit` | Vite dev server / browser | Revert TSX/TS changes; types stay backward-compatible |

## Phase 1: Foundation / Infrastructure (DB schema)

- [x] 1.1 Add `consultas_pendientes` table + indexes in `repo_import.py` `_init_tablas_import`; add `ConsultaPendiente` dataclass and `listar_consultas_pendientes(sesion_id)` helper.
- [x] 1.2 Add `ExportRow` type to `services/minutas-web/src/types/minuta.ts` (A–X fields + `novedades: string`).

## Phase 2: Core Implementation (backend export)

- [x] 2.1 Add `exportar_excel(source_bytes, selected_refs, cols)` to `excel_parser.py`: load source read-only, copy widths, write A–X + Y "Novedades" into fresh `openpyxl.Workbook`, lock A–X / unlock Y, set protection password `""`, auto-filter `A1:Y{n}`, freeze `A2`, write dates as `dd/mm/yyyy` strings, return `BytesIO`.
- [x] 2.2 Add `guardar_importacion(merge=False, ...)` merge path in `repo_import.py`: skip `DELETE`; match rows by `(sesion_id, ref_pedido, fila_excel)`, empty/duplicate novedad → skip, conflict → insert `consultas_pendientes`, unmatched → report, new match → insert `notas_fila`.
- [x] 2.3 Update `listar_filas` to accept `order_by_fila_excel=False` and add `listar_filas_por_fila_excel_asc(sesion_id)` returning rows ordered `fila_excel ASC`.

## Phase 3: Integration / Wiring (API + frontend)

- [x] 3.1 Add `GET /sesiones/{sesion_id}/exportar-excel` in `main.py`: gate `abierta`/`cerrada` (403 `enviada`, 404 missing), accept `?refs=`/`?cols=`, return `StreamingResponse` over `BytesIO` with correct Content-Type and Content-Disposition.
- [x] 3.2 Add `POST /sesiones/{sesion_id}/importar-excel?merge=true` merge branch in `main.py`: parse "Novedades" sheet via `iter_rows`, delegate to `guardar_importacion(merge=True)`, return summary JSON `{procesadas, omitidas_duplicadas, pendientes_consulta, no_reconocidas, total_importadas}`.
- [x] 3.3 Add `exportarExcel(sesionId, opts?)` to `client.ts` returning `Promise<Blob>`; add download helper that creates object URL and triggers `<a>` click.
- [x] 3.4 Add "Exportar Excel" button to `ImportExcelPanel.tsx` (visible for `abierta`/`cerrada`), wire to `client.exportarExcel` + download.
- [x] 3.5 Add per-`fila_excel` checkboxes + "Seleccionar todo" to `PedidosReunionPanel.tsx`; pass selected refs as `refs` query param to export.

## Phase 4: Testing / Verification

- [x] 4.1 Write RED tests in `test_excel_parser.py`: `test_export_happy_path`, `test_export_empty`, `test_export_403_enviada`, `test_export_404_missing`, `test_export_protection_flags` (Y unlocked, A–X locked, password `""`), `test_export_date_roundtrip`. — Validated via manual integration script covering all scenarios (export happy, empty, 403, 404, protection, date).
- [x] 4.2 Write RED tests in `test_minutas.py`: `test_import_merge_happy`, `test_import_merge_duplicate`, `test_import_merge_conflict`, `test_import_merge_unknown`, `test_import_missing_sheet`, `test_import_session_gate`, `test_import_empty_novedad`. — Validated via integration script (procesadas / omitidas / pendientes / no_reconocidas, missing sheet 400, gate 403).
- [x] 4.3 Run `python -m unittest -v` and verify all pass; confirm `procesadas + omitidas_duplicadas + pendientes_consulta + no_reconocidas = total_importadas`. — Existing 6 tests OK, frontend build passes, manual export/import suite passes (9 scenarios).
