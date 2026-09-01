# Proposal: Exportar Excel de Minutas de Compras

## Intent

Users select purchase rows and add notes, but there is no editable deliverable for the purchasing team. The import **deletes every row** on re-import. We need export plus non-destructive re-import.

## Scope

### In Scope
- "Exportar Excel" button generating `.xlsx` with selected rows in `fila_excel` ascending order; "Novedades" sheet (A–X + Novedades), sheet-protected (only Novedades editable).
- Selection = elegibles with filter; per-`ref_pedido` checkboxes + "Seleccionar todo".
- Re-import appends rows; conflicts become consulta-pending (no overwrites). Fresh workbook mimicking original widths/styles; no source-byte storage.

### Out of Scope
- Source-byte storage; curated columns; protection; closed sessions

## Capabilities

### New Capabilities
- `minuta-excel-export`: editable "Novedades" Excel from selected elegibles, preserving widths/styles and protecting non-Novedades cells.
- `minuta-novedades-import`: re-imports modified Excel append-only, conflicts by `(sesion_id, ref_pedido, fila_excel)` → pending consulta.

### Modified Capabilities
- None (no existing specs).

## Approach

1. **Export**: build fresh `openpyxl.Workbook`; copy column widths from the uploaded source on-the-fly. Write selected rows sorted `fila_excel ASC` into "Novedades"; protect the sheet; return `.xlsx`.
2. **Re-import**: parse returned Excel; match on `(sesion_id, ref_pedido, fila_excel)`. Identical text → skip; different → consulta-pending; unmatched → ignore as "no reconocidas".
3. **UI**: "Exportar Excel" button beside import zone; grupo-level selection + "Seleccionar todo" + per-fila checkboxes.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `services/minutas-api/excel_parser.py` | Modified | Column-width extraction; export row shape |
| `services/minutas-api/repo_import.py` | Modified | `guardar_importacion(merge=True)`; `listar_filas` by `fila_excel ASC` |
| `services/minutas-api/main.py` | Modified | New `GET /sesiones/{id}/exportar-excel`; re-import `merge` mode |
| `services/minutas-web/src/components/ImportExcelPanel.tsx` | Modified | Add "Exportar Excel" button |
| `services/minutas-web/src/components/PedidosReunionPanel.tsx` | Modified | Per-fila checkboxes + "Seleccionar todo" |
| `services/minutas-web/src/api/client.ts` | Modified | Add `exportarExcel(sesionId)` returning `Blob` |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Large files memory | Med | Read source on-the-fly; stream write |
| openpyxl protection bypassed | Low | Cosmetic; conflicts case-by-case |
| Duplicate notas on re-import | Med | Merge by key with normalized text |
| `fila_excel` collision | Low | Scope to `sesion_id` |
| Date round-trip | Med | Write as strings matching source |

## Rollback Plan

Export undeployed → no impact. Re-import merge gated behind `merge` param; default stays destructive. Revert by removing param and merge path. Column-width fallback to defaults.

## Dependencies

- `openpyxl` is a dependency. Frontend wiring for open sessions.

## Success Criteria

- [ ] Export `.xlsx` ordered by `fila_excel ASC`, columns A–X + Novedades.
- [ ] Re-import keeps existing rows; identical text skipped; conflicts → consulta-pending.
- [ ] "No reconocidas" reported; Novedades editable only.
- [ ] Tests pass for export and merge-import.
