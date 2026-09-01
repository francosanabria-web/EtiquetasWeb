# minuta-excel-export Specification

## Purpose

Export selected purchase rows as an editable `.xlsx` workbook with a "Novedades" sheet preserving original column widths/styles, sheet-protected so only the Novedades column is editable.

## ADDED Requirements

### Requirement: Export Endpoint

The system SHALL expose `GET /sesiones/{id}/exportar-excel` returning a valid `.xlsx` workbook.

- Content-Type: `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`
- Content-Disposition: `attachment; filename="minuta-{semana_iso}.xlsx"`
- Returns HTTP 404 if session does not exist.

#### Scenario: Successful export

- GIVEN a session `{id}` with elegible rows selected
- WHEN the client requests `GET /sesiones/{id}/exportar-excel`
- THEN the response body is a valid `.xlsx` file
- AND the Content-Type header is `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`
- AND the Content-Disposition header contains `attachment`

#### Scenario: Session not found

- GIVEN no session with the given `{id}` exists
- WHEN the client requests `GET /sesiones/{id}/exportar-excel`
- THEN the response is HTTP 404

### Requirement: Selection Scope

The system SHALL export only rows where the user has explicitly selected them via per-`ref_pedido` checkboxes or "Seleccionar todo". Selection is scoped to elegibles with the active filter applied.

#### Scenario: Selected rows exported

- GIVEN a session with 50 elegible rows, 20 selected via checkboxes
- WHEN the export is requested
- THEN only the 20 selected rows appear in the output

#### Scenario: No selection made

- GIVEN a session with elegible rows but none selected
- WHEN the export is requested
- THEN the workbook contains an empty "Novedades" sheet (headers only, zero data rows)

### Requirement: Row Ordering

Rows in the exported sheet SHALL be ordered by `fila_excel ASC`, preserving the original Excel row order.

#### Scenario: Ascending fila_excel order

- GIVEN selected rows with `fila_excel` values 10, 3, 7, 1
- WHEN the export is generated
- THEN rows appear in the sheet as 1, 3, 7, 10

### Requirement: Column Structure

The exported sheet SHALL contain columns A–X (matching the `_COL` mapping order) plus a "Novedades" column appended as column Y, in that exact sequence. A header row SHALL be written as the first row.

#### Scenario: Column order and header

- GIVEN a row with values for columns A–X and a novedad text
- WHEN the row is written to the sheet
- THEN column A is the first data column, column X is the 24th, and column Y is "Novedades"
- AND the header row contains the `_COL` display names followed by "Novedades"

### Requirement: Sheet Protection

The exported sheet SHALL have protection enabled. Only cells in the "Novedades" column (Y) SHALL have `locked=false`. All other cells SHALL have `locked=true` (default).

#### Scenario: Novedades column editable

- GIVEN the exported "Novedades" sheet with protection enabled
- WHEN a user opens the file in Excel
- THEN cells in column Y are editable without a password
- AND cells in columns A–X are locked

#### Scenario: Protection bypass limitation

- GIVEN the exported file opened in a tool that ignores sheet protection
- THEN the protection is cosmetic only; this is an accepted limitation documented in the spec

### Requirement: Column Widths and Styles

Column widths SHALL be copied from the source workbook where available. Where the source width is unavailable, a sensible default SHALL be used. Date columns SHALL be written as formatted strings matching the source format (`dd/mm/yyyy`).

#### Scenario: Source widths preserved

- GIVEN a source workbook where column C has width 18.5
- WHEN the export is generated
- THEN column C in the output sheet has width 18.5

#### Scenario: Missing source width falls back to default

- GIVEN no source workbook is available for width reference
- WHEN the export is generated
- THEN all columns use a default width (e.g., 8.43)

### Requirement: Export Button in UI

An "Exportar Excel" button SHALL be rendered in `ImportExcelPanel`, positioned near the import drop zone. The button SHALL be visible for sessions in `abierta` or `cerrada` state.

#### Scenario: Button visible for open session

- GIVEN a session in `abierta` state
- WHEN the `ImportExcelPanel` renders
- THEN the "Exportar Excel" button is visible and enabled

#### Scenario: Button visible for closed session

- GIVEN a session in `cerrada` state
- WHEN the `ImportExcelPanel` renders
- THEN the "Exportar Excel" button is visible and enabled (read-only export)

### Requirement: Frontend Client Method

`client.ts` SHALL expose `exportarExcel(sesionId: string, opts?: { cols?: string[] }): Promise<Blob>` that performs the GET request and returns the binary blob. An optional `cols` query parameter MAY filter columns (future extensibility; default exports all columns A–Y).

#### Scenario: Download triggered from blob

- GIVEN `exportarExcel` returns a Blob
- WHEN the calling component receives the blob
- THEN it creates an object URL and triggers a browser download via a temporary `<a>` element

### Requirement: Session State Gate

The export endpoint SHALL be available for sessions with `estado` in `{'abierta', 'cerrada'}`. It SHALL return HTTP 403 for sessions in `enviada` state.

#### Scenario: Export denied for enviada session

- GIVEN a session in `enviada` state
- WHEN the export is requested
- THEN the response is HTTP 403

### Requirement: Empty Export Handling

When no rows are selected or the session has no elegible rows, the system SHALL return a valid `.xlsx` with only the header row and zero data rows in the "Novedades" sheet. It SHALL NOT return an error.

#### Scenario: Empty but valid workbook

- GIVEN a session with zero selected rows
- WHEN the export is requested
- THEN the response is a valid `.xlsx` with one sheet containing only the header row
