## Exploration: exportar-excel-minutas-compras

### Problem
The current flow lets users import a purchases Excel, select rows for the weekly meeting, and add per-row notes ("notas"). There is **no export capability**. Users who finish selecting rows and want to hand the list back to the purchasing team as an editable deliverable have no way to generate it from the system. Additionally, when the purchasing team returns a modified Excel, `repo_import.guardar_importacion` **deletes every row for the session** (`DELETE FROM filas_pedido WHERE sesion_id = ?`) before re-inserting, so any notes added in the meeting are lost and existing data is overwritten rather than merged.

### Current State
1. **Import** (`POST /sesiones/{id}/importar-excel`): `excel_parser.parsear_excel` reads the source workbook with `iter_rows(values_only=True)` in read-only mode across columns A–X of the preferred sheet ("Base datos 2025" / "PP2026" / "Base datos 2026"). Each row becomes a `FilaPedido` carrying `fila_excel` (the original Excel row number), `ref_pedido` (`num_odoo + num_solicitud`), `elegible_reunion`, `cumplida`, and all column values. `repo_import.guardar_importacion` stores them and **wipes the session's existing filas first**.
2. **Selection** (`PUT /sesiones/{id}/seleccion-reunion`): `fijar_seleccion_reunion` marks whole `ref_pedido` groups as `seleccionada=1` (and deselects the rest). The UI (`PedidosReunionPanel`) shows one checkbox per grupo, not per fila.
3. **Notes** (`POST /sesiones/{id}/filas/{fila_id}/notas`): `agregar_nota_fila` inserts into `notas_fila` by `fila_id`.
4. **Listing** (`GET /sesiones/{id}/pedidos`): `listar_pedidos_agrupados` groups by `ref_pedido`, sorts each group's rows by `fila_excel`, then sorts groups by `parse_fecha_orden(fecha_solicitud)`. This is **not** the original Excel row order.
5. **Re-import** currently overwrites everything.

Key structural facts:
- `fila_excel` is the original Excel row number (1-based) — it is the natural ordering anchor but **not** a unique identity across imports (the same row number can appear in different importaciones).
- The unique constraint is `(sesion_id, importacion_id, fila_excel)` — so the natural key for "this exact row in this import" is `(importacion_id, fila_excel)`, and the session-level identity is `(sesion_id, fila_excel)` only within a single import.
- `excel_parser` already streams rows via `iter_rows` rather than loading `max_row`, so large-file reading is already handled.

### Affected Areas
- `services/minutas-api/excel_parser.py` — `FilaPedido` dataclass, `parsear_excel`, `_COL` mapping (A–X). Export must read back `fila_excel` order and only the "novedades" subset.
- `services/minutas-api/repo_import.py` — `guardar_importacion` (must add a merge/non-destructive path), `listar_filas` (must expose `fila_excel`-preserving ordering), `_init_tablas_import` (unique constraint may need adjustment for re-import identity).
- `services/minutas-api/main.py` — needs a new `GET /sesiones/{id}/exportar-excel` endpoint returning a binary `.xlsx`, and the re-import endpoint needs a `merge` mode.
- `services/minutas-web/src/components/ImportExcelPanel.tsx` — add an "Exportar Excel" button beside the import drop zone.
- `services/minutas-web/src/components/PedidosReunionPanel.tsx` — add per-row checkboxes (or a select-all) for export scope; currently only grupo-level checkboxes exist.
- `services/minutas-web/src/api/client.ts` — add `exportarExcel(sesionId, file)` returning a `Blob`.
- `services/minutas-web/src/App.tsx` — wire the export button (visible only for open sessions).
- `services/minutas-web/src/types/minuta.ts` — may need an `ExportRow` / `NovedadesRow` type for the exported sheet shape.

### Approaches

#### A. openpyxl: load original workbook, add "Novedades" sheet, preserve everything
Load the **same** `.xlsx` the user originally uploaded (store a copy keyed by `importacion_id`), create a new worksheet "Novedades", write only the selected rows in `fila_excel` order, copy column widths and styles from the source, set `sheet.protection.sheet = True` / `sheet.protection.enable()`. Re-import reads the "Novedades" sheet, identifies new rows by the absence of an existing `fila_id`, and inserts only those.
- **Pros**: preserves column widths (`anchos`), number formats, date formats (`fecha` columns E/T), cell styles, merged cells — the deliverable looks exactly like the source. Sheet-level protection is respected by Excel.
- **Cons**: the source workbook must be stored/retrieved on re-import (currently `importar_excel` only persists parsed JSON, not the file bytes); memory footprint grows with file size; openpyxl sheet protection can be bypassed by a knowledgeable user (it is not cryptographic).
- **Effort**: Medium.

#### B. openpyxl: build a fresh workbook with only the columns we need
Create a brand-new `openpyxl.Workbook()`, build the "Novedades" sheet from scratch with only the columns to export, set widths programmatically, protect the sheet. Re-import same as A.
- **Pros**: deterministic structure; no need to retain the source file; smaller memory footprint; clean separation between source and deliverable.
- **Cons**: loses all original formatting, `anchos`, date/number styles, conditional formatting — the deliverable will look generic and may confuse the purchasing team used to the pañol template.
- **Effort**: Low.

#### C. Streaming response (XLSX via streaming or CSV)
Stream the export as it is generated instead of holding the whole workbook in memory; or export to CSV for simplicity.
- **Pros**: lowest memory; CSV is universally readable.
- **Cons**: CSV loses all formatting and multi-cell structure; XLSX streaming (openpyxl does not natively stream writes well) is fragile; sheet protection is harder to guarantee on a streamed file.
- **Effort**: Medium–High for XLSX; Low for CSV (but rejected for quality reasons).

#### D. Hidden `fila_id` vs natural key for re-import identity
- **Hidden `fila_id` column**: embed the DB `id` in a hidden column of the export so re-import can match exact rows.
  - **Pros**: exact identity, trivial merge logic.
  - **Cons**: if the user unhides/deletes the column, re-import breaks; exposes internal DB state; fragile across sessions.
- **Natural key `(ref_pedido, fila_excel)`**: re-import matches rows by this composite key against the session's existing data.
  - **Pros**: no hidden columns; survives unhiding; stable across re-imports; matches how the UI already identifies rows.
  - **Cons**: `fila_excel` alone can collide across different `importacion_id` rows within the same session if the source file is re-imported; must scope to `sesion_id`.
  - **Effort**: Low.

### Recommendation
**Approach A (openpyxl, preserve source workbook) + Approach D natural key `(ref_pedido, fila_excel)` scoped to `sesion_id`**.

Rationale:
1. The deliverable must look like the pañol template — preserving `anchos`, date formats, and styles is a quality requirement, not a nice-to-have. Approach B loses that; Approach C (CSV) loses structure.
2. We should store the original uploaded workbook bytes keyed by `importacion_id` (extend `importaciones` table with a `archivo_bytes` BLOB or a temp file path) so re-import can load the exact source and add the "Novedades" sheet on top of it.
3. Re-import identity uses `(sesion_id, ref_pedido, fila_excel)` — this is the natural key already present in the data; no hidden columns needed.
4. Sheet protection (not workbook protection) on the "Novedades" sheet is the right granularity — it lets users add rows/cells while preventing modification of existing purchase data.
5. For the export UI: keep the existing grupo-level selection from `PedidosReunionPanel` as the default scope, and add a "Select All / Deselect All" toggle plus per-fila checkboxes so users can fine-tune which rows become novedades.

### Risks
1. **Large files** — loading the source workbook into memory on export + re-import can be heavy for 10k+ row files. Mitigation: keep read-only mode for parsing, and stream the write; or store the source file on disk (temp path) instead of in SQLite BLOB.
2. **Protection bypass** — openpyxl sheet protection is cosmetic; a user can disable it in Excel. This is acceptable because the policy is "case-by-case consultation" for conflicts, not cryptographic integrity. Document this limitation.
3. **Duplicate notas on re-import** — if a user adds a note to the same row in both the original import and the returned novedades sheet, the backend must not duplicate. Re-import must merge by `(sesion_id, ref_pedido, fila_excel)` and skip existing rows.
4. **Ordering stability** — `fila_excel` gives the original row order, but if the source file has gaps or is re-sorted, the export must still respect `fila_excel` ascending, not DB insertion order. Export query: `ORDER BY fila_excel ASC`.
5. **CORS for binary download** — the export endpoint returns `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`. FastAPI's CORSMiddleware already allows `allow_origins=["*"]` in dev; in production the frontend origin must be whitelisted, and the `Content-Disposition` header must not trigger a CORS preflight issue.
6. **Hidden column visibility** — if the export hides columns the user might not want visible, document the exported columns explicitly. The export should only contain the columns relevant to "novedades" (the purchase team's subset), not all A–X.
7. **Closed sessions** — the user request implies export should work for the current session. Clarify whether export is allowed only when `sesion.estado = 'abierta'` or also for `'cerrada'`/`'enviada'`. Current endpoints guard on `abierta`; export should likely be allowed for `cerrada` too (read-only view of the final state).
8. **Date format round-trips** — `fecha_solicitud`, `fecha_oc`, `fecha_envio_compras` are stored as formatted strings (dd/mm/yyyy). The export must write them as strings or as real Excel dates with the same format; mixing could cause Excel to reinterpret them.

### Alternatives Rejected
- **Approach B (fresh workbook)** — rejected because it loses the pañol template formatting, `anchos`, and date/number styles that the purchasing team expects.
- **Approach C (CSV / streaming)** — rejected because the deliverable must preserve cell structure, merged cells, and formatting; CSV cannot represent the pañol layout.
- **Approach D-alt (hidden `fila_id` column)** — rejected because it exposes internal DB IDs and breaks if the user unhides the column; the natural key `(sesion_id, ref_pedido, fila_excel)` is already present and sufficient.
- **Workbook-level protection instead of sheet-level** — rejected because it would lock the entire workbook including the original data columns, which the purchasing team may need to review. Sheet-level protection on "Novedades" is the correct granularity.

### Open Questions
1. What columns exactly go into the "Novedades" export sheet? All A–X, or a curated subset (e.g., only the columns the purchasing team edits)?
2. Should the export button be available for closed sessions (`cerrada` / `enviada`) or only `abierta`?
3. What does "conflicts need case-by-case consultation" mean concretely? Is it a backend validation rule, or a manual review step for the pañolero?
4. Should the exported file be named automatically (e.g., `minuta-{semana_iso}.xlsx`) or allow a custom name?
5. Is storing the source workbook bytes (or temp file path) acceptable for re-import, or must we re-parse the uploaded file each time?
6. Does "Purchases only fills 'novedades'" mean only the selected rows become novedades, or only rows that have been annotated as novedades?

### Ready for Proposal
Yes — the approach is clear enough to propose. The main decisions to lock in the proposal phase are: (a) whether to store the source workbook bytes or re-derive them, (b) the exact column subset for the "Novedades" sheet, and (c) the session-state gate for the export endpoint.
