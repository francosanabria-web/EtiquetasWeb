# Design: Exportar Excel de Minutas de Compras

## Technical Approach

Two-endpoint feature: `GET /sesiones/{id}/exportar-excel` builds a fresh `.xlsx` workbook from the selected elegibles using openpyxl, preserving source column widths/styles and sheet-protecting all cells except "Novedades" (Y). `POST /sesiones/{id}/importar-novedades` parses the returned "Novedades" sheet, merges non-destructively, and escalates text conflicts to a pending-consulta record. In-memory `BytesIO` throughout; no temp files.

## Architecture Decisions

### Decision: Backend export via openpyxl on a fresh workbook with source-width copy

**Choice**: Build `openpyxl.Workbook()` fresh; copy column widths from the source workbook loaded read-only; write selected rows sorted `fila_excel ASC`. Return `StreamingResponse` over `BytesIO`.

**Alternatives considered**: (A) Load original workbook and add sheet — rejected because source bytes are not stored (out of scope). (B) Fresh workbook with hardcoded widths — rejected because it loses pañol formatting. (C) CSV/streaming — rejected because structure and sheet protection are required.

**Rationale**: A fresh workbook gives deterministic structure while copying widths on-the-fly from the source satisfies the formatting quality requirement without persisting source bytes.

### Decision: Separate `consultas_pendientes` table for conflict records

**Choice**: New table rather than extending `notas_fila` with an `estado` column.

**Alternatives considered**: Extend `notas_fila` with `estado` — rejected because it conflates user notes with system-generated consultas and complicates the pañolero review view.

**Rationale**: Keeps case-by-case consultation explicit and queryable; avoids mutating the existing notes domain model.

### Decision: Natural key `(sesion_id, ref_pedido, fila_excel)` for merge identity

**Choice**: Match imported rows by this composite key; no hidden columns.

**Alternatives considered**: Hidden `fila_id` column — rejected because it exposes internal DB IDs and breaks if the user unhides it.

**Rationale**: Already present in the data; stable across re-imports; scoped to `sesion_id` to avoid collisions.

## Data Model

### New table: `consultas_pendientes`

```sql
CREATE TABLE IF NOT EXISTS consultas_pendientes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sesion_id INTEGER NOT NULL,
    fila_id INTEGER NOT NULL,
    texto_existente TEXT NOT NULL,
    texto_nuevo TEXT NOT NULL,
    autor TEXT,
    creado_en TEXT NOT NULL,
    estado TEXT NOT NULL DEFAULT 'pendiente',
    FOREIGN KEY (fila_id) REFERENCES filas_pedido(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_consultas_sesion ON consultas_pendientes(sesion_id);
CREATE INDEX IF NOT EXISTS idx_consultas_fila ON consultas_pendientes(fila_id);
```

Existing `notas_fila` remains unchanged for new notes; conflicts insert here. The import endpoint writes either a `notas_fila` row (new novedad) or a `consultas_pendientes` row (conflict), never both.

## Excel Layout

Columns A–X follow the `_COL` mapping order; column Y is "Novedades". Header row (row 1) uses the COL keys: `cant_articulos_pedido`, `solicitante`, `tipo_solicitud`, `maquina_linea`, `fecha_solicitud`, `num_odoo`, `almacenista`, `num_solicitud`, `codigo`, `descripcion`, `cantidad`, `unidad`, `precio`, `total`, `moneda`, `proveedor`, `oc_rq`, `fecha_oc`, `comprador`, `fecha_envio_compras`, `estado_item`, `estado_solicitud`, then `Novedades`.

- Column widths: default 12; `descripcion` (L) and `solicitante` (B) = 30; date columns (E, T, V) = 14; numeric columns (M, O, P) = 12.
- Header fill `#1F4E78`, font white, thin border `#999999`.
- `ws.auto_filter.ref = "A1:Y{n}"`.
- `ws.freeze_panes = "A2"`.
- `sheet.protection.sheet = True`, `sheet.protection.password = ""`.
- Every cell locked `True` except column Y cells locked `False`.
- Dates written as `dd/mm/yyyy` strings matching source format.

## API Design

### GET `/sesiones/{id}/exportar-excel`

Query params: `?refs=...` (comma-separated `ref_pedido` list, optional filter) and `?cols=...` (comma-separated column keys, optional column picker; default all A–Y). Returns `StreamingResponse` with `media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"` and `Content-Disposition: attachment; filename="Minuta_{semana_iso}_{fecha}.xlsx"`. Session state gate: `abierta` or `cerrada` only; `enviada` → 403; missing → 404.

### POST `/sesiones/{id}/importar-novedades`

Multipart form: file field `"archivo"`. Parse only sheet `"Novedades"` (400 if missing). For each row, match by `(sesion_id, ref_pedido, fila_excel)` against `filas_pedido`. Normalize text (trim, lower, collapse whitespace) for comparison.

Response JSON:
```json
{
  "procesadas": 0,
  "omitidas_duplicadas": 0,
  "pendientes_consulta": 0,
  "no_reconocidas": [],
  "total_importadas": 0
}
```

Logic per row: empty novedad → `omitidas_duplicadas`; identical normalized text → `omitidas_duplicadas`; different text → insert `consultas_pendientes` (preserving existing `notas_fila`) → `pendientes_consulta`; unmatched `(ref_pedido, fila_excel)` → `no_reconocidas`; new match → insert `notas_fila` → `procesadas`.

## Selection UI

Placement: "Exportar Excel" button inside `ImportExcelPanel`, adjacent to the import drop zone. Visible when `sesion.estado ∈ {abierta, cerrada}`.

Selection scope = elegibles with the active filter applied. Two checkbox layers:
1. **Per-`ref_pedido` group checkboxes** with a "Seleccionar todo" toggle (currently in `PedidosReunionPanel`). Selecting a grupo selects all its `fila_excel` rows; "Seleccionar todo" selects every elegible grupo.
2. **Column picker checkboxes** (future extensibility) with "Seleccionar todo columnas" — placed beside the export button near `ImportExcelPanel`. Default: all columns A–Y selected.

The `refs` query param carries the selected grupo list; `cols` carries selected column keys.

## Ordering

Export guarantees `fila_excel ASC`. Implementation copy: `ORDER BY fila_excel` in the query that pulls selected filas for the session. `PedidosReunionPanel` already sorts each grupo's rows by `fila_excel` (via `listar_filas`); the export query adds an explicit `ORDER BY fila_excel` for determinism.

## Validation

- Session must be `abierta` or `cerrada`; `enviada` → HTTP 403.
- Session missing → HTTP 404.
- Missing "Novedades" sheet on import → HTTP 400.
- Empty selection → valid workbook with header row only, zero data rows (no error).

## File Handling

- Export: `BytesIO` in memory, no temp file. Source workbook loaded `read_only=True` for width extraction; rows streamed via `iter_rows`.
- Re-import: parse uploaded file with `iter_rows(values_only=True)` on the "Novedades" sheet — read-only streaming avoids OOM for large files.
- All writes go to `BytesIO` → `StreamingResponse`.

## Testing Strategy

`unittest.TestCase` + FastAPI `TestClient` for both endpoints:

| Test | Scenario |
|------|----------|
| `test_export_happy_path` | Selected rows exported, `fila_excel ASC`, headers, Content-Type, Content-Disposition |
| `test_export_empty` | No selection → header-only workbook, HTTP 200 |
| `test_export_403_enviada` | Session enviada → 403 |
| `test_export_404_missing` | Session not found → 404 |
| `test_export_protection_flags` | Column Y unlocked, A–X locked, sheet protection enabled, password empty |
| `test_export_date_roundtrip` | Date cells written as `dd/mm/yyyy` strings |
| `test_import_merge_happy` | New novedad inserted, `procesadas=1` |
| `test_import_merge_duplicate` | Identical normalized text → `omitidas_duplicadas` |
| `test_import_merge_conflict` | Different text → `pendientes_consulta`, existing note preserved |
| `test_import_merge_unknown` | Unmatched `(ref_pedido, fila_excel)` → `no_reconocidas` |
| `test_import_missing_sheet` | No "Novedades" → 400 |
| `test_import_session_gate` | `enviada` → 403 |
| `test_import_empty_novedad` | Empty text → skipped silently |

## Risks & Mitigations

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Large files memory | Medium | `BytesIO` + read-only `iter_rows`; no source-byte storage |
| openpyxl protection bypassed | Low | Cosmetic only; conflicts escalated to case-by-case consulta |
| Duplicate notas on re-import | Medium | Merge by `(sesion_id, ref_pedido, fila_excel)` + normalized text comparison |
| `fila_excel` collision across importaciones | Low | Scoped to `sesion_id` |
| Date round-trip corruption | Medium | Write as `dd/mm/yyyy` strings; never reinterpret as serial numbers |
| CORS for binary download | Low | CORSMiddleware already `allow_origins=["*"]`; `Content-Disposition` is a safe header |

## Alternatives Rejected

- **Store source bytes on `importaciones`** — rejected; out of scope, adds BLOB overhead and retention complexity. Widths are copied on-the-fly from the fresh parse.
- **Hidden `fila_id` column** — rejected; exposes internal DB IDs, fragile if user unhides/deletes the column. Natural key `(sesion_id, ref_pedido, fila_excel)` is sufficient and stable.
- **Extend `notas_fila` with `estado`** — rejected; conflates user notes with system consultas. Separate `consultas_pendientes` keeps domains clean.
- **CSV export** — rejected; loses cell structure, merged cells, formatting, and sheet protection.

## Open Questions

- [ ] Exact column subset for "Novedades" — design assumes all A–X + Y; confirm if purchasing team needs a curated subset.
- [ ] Whether "Seleccionar todo columnas" should be per-column or per-section; default to all A–Y.
- [ ] Whether `autor` for consultas defaults to the API caller or a system identity.
