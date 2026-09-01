# minuta-novedades-import Specification

## Purpose

Re-import a modified "Novedades" Excel workbook, merging changes non-destructively. New novedad text is appended; conflicts (different text on same row) become pending consultations; duplicates and unknown rows are handled gracefully.

## ADDED Requirements

### Requirement: Re-import Endpoint

The system SHALL expose `POST /sesiones/{id}/importar-excel` with query parameter `merge=true` to activate non-destructive merge mode. Without `merge=true`, the existing destructive behavior is preserved.

#### Scenario: Merge mode activated

- GIVEN a session `{id}` with existing filas
- WHEN the client sends `POST /sesiones/{id}/importar-excel?merge=true` with a valid `.xlsx` body
- THEN the system parses the "Novedades" sheet and processes rows via merge logic
- AND existing filas_pedido rows are NOT deleted

#### Scenario: Default destructive mode preserved

- GIVEN a session `{id}`
- WHEN the client sends `POST /sesiones/{id}/importar-excel` (no `merge` param)
- THEN the existing destructive overwrite behavior executes unchanged

### Requirement: Row Matching Key

Merge mode SHALL match imported rows to existing rows using the natural key `(sesion_id, ref_pedido, fila_excel)`. No hidden columns or internal IDs are used.

#### Scenario: Match by composite key

- GIVEN an existing row with `sesion_id=1, ref_pedido="ODOO-001", fila_excel=5`
- WHEN the imported Excel contains a row with the same `ref_pedido` and `fila_excel` values
- THEN the system identifies them as the same row

#### Scenario: No match — unknown row

- GIVEN an imported row with `ref_pedido="ODOO-999"` not present in the session
- WHEN merge processing runs
- THEN the row is reported as "no reconocida" in the response summary

### Requirement: Skip Empty Novedades

If the novedad text for an imported row is empty or whitespace-only, the system SHALL skip that row silently (no insert, no update, no conflict).

#### Scenario: Empty novedad skipped

- GIVEN an imported row with `ref_pedido="ODOO-001", fila_excel=5` and empty novedad text
- WHEN merge processing runs
- THEN the row is counted as "omitidas" in the summary
- AND no notas_fila record is created

### Requirement: Duplicate Detection

If the imported novedad text, when normalized (trim whitespace, collapse multi-spaces, case-insensitive), is identical to an existing notas_fila entry for the same row, the system SHALL skip the row as a duplicate.

#### Scenario: Identical text skipped

- GIVEN an existing nota "Revisar stock" for row `(sesion_id=1, ref_pedido="ODOO-001", fila_excel=5)`
- WHEN the imported Excel has novedad "revisar  stock" (extra space) for the same row
- THEN the row is counted as "omitidas duplicadas" in the summary
- AND no new notas_fila record is created

### Requirement: Conflict — Pending Consulta

If the imported novedad text differs from the existing notas_fila entry for the same row, the system SHALL NOT overwrite. Instead it SHALL create a pending consultation record (a new `notas_fila` entry with `estado='pendiente'` or a dedicated `consultas_pendientes` record) visible for case-by-case review by the pañolero.

#### Scenario: Different text creates consulta

- GIVEN an existing nota "Stock OK" for row `(sesion_id=1, ref_pedido="ODOO-001", fila_excel=5)`
- WHEN the imported Excel has novedad "Falta material" for the same row
- THEN a pending consultation record is created for that row
- AND the existing nota is preserved unchanged
- AND the response summary counts it as "pendientes_consulta"

### Requirement: Preserve Existing Data

Merge mode SHALL NOT delete any existing `filas_pedido` or `notas_fila` records. It SHALL only ADD new consultation records for conflicts. No existing data is modified or removed.

#### Scenario: No deletions during merge

- GIVEN a session with 30 filas and 15 notas
- WHEN merge re-import processes 10 rows (2 new, 3 duplicates, 3 conflicts, 2 unknown)
- THEN all 30 filas and 15 notas remain unchanged
- AND 3 new pending-consulta records are created

### Requirement: Unknown Row Handling

Rows in the imported Excel whose `(ref_pedido, fila_excel)` key does not match any existing row in the session SHALL be reported as "no reconocidas" in the response. They SHALL NOT be inserted as new filas_pedido.

#### Scenario: Unmatched row reported

- GIVEN an imported row with `ref_pedido="ODOO-NEW-001", fila_excel=99` not in the session
- WHEN merge processing runs
- THEN the row appears in the "no reconocidas" list in the response
- AND no filas_pedido record is created

### Requirement: Response Summary

The merge endpoint SHALL return a JSON response containing a summary object with the following counts: `procesadas` (novedades applied as new), `omitidas_duplicadas` (identical text skipped), `pendientes_consulta` (conflicts created), `no_reconocidas` (unmatched rows), and `total_importadas` (rows in the imported sheet).

#### Scenario: Summary returned

- GIVEN a merge import of 20 rows from the Excel
- WHEN processing completes
- THEN the response body contains `{ "procesadas": N, "omitidas_duplicadas": M, "pendientes_consulta": K, "no_reconocidas": U, "total_importadas": 20 }`
- AND N + M + K + U = 20 (all rows accounted for)

### Requirement: File Parsing Robustness

The system SHALL parse only the "Novedades" sheet from the uploaded workbook. If the sheet is missing, the system SHALL return HTTP 400 with an error message indicating the expected sheet was not found.

#### Scenario: Missing Novedades sheet

- GIVEN an uploaded `.xlsx` with no "Novedades" sheet
- WHEN merge import is requested
- THEN the response is HTTP 400 with message "Sheet 'Novedades' not found"

#### Scenario: Multiple sheets — only Novedades parsed

- GIVEN an uploaded `.xlsx` with sheets "Datos" and "Novedades"
- WHEN merge import is requested
- THEN only rows from the "Novedades" sheet are processed

### Requirement: Date Format Preservation

Date values in the imported Excel SHALL be written to the database preserving their string format (`dd/mm/yyyy`). The system SHALL NOT reinterpret date strings as Excel serial numbers or ISO dates.

#### Scenario: Date string preserved

- GIVEN a novedades cell with value "15/03/2026"
- WHEN merge import processes the row
- THEN the stored date value remains "15/03/2026"

### Requirement: Large File Handling

The system SHALL parse the uploaded workbook using streaming row iteration (`iter_rows`), not loading the entire workbook into memory. This applies to both export and re-import paths.

#### Scenario: Large file parsed without OOM

- GIVEN an uploaded `.xlsx` with 10,000 rows
- WHEN merge import processes the file
- THEN processing completes without exceeding memory limits
- AND all rows are processed correctly
