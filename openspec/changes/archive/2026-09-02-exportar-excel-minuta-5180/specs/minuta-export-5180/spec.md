# minuta-export-5180 Specification

## Purpose

Export the current minuta-de-reunión to a legible `.xlsx` workbook with content-based auto-width columns, `wrapText` on text cells, sheet protection on the Novedades column only, and hideable columns driven by UI visibility selection. Orders pedido rows by `orden ASC`.

## Requirements

### Requirement: Export Endpoint

The system SHALL expose `GET /api/minuta/pedidos/exportar-excel?reunion_id={id}` returning a valid `.xlsx` workbook via Starlette `StreamingResponse` over `BytesIO`.

#### Scenario: Successful export

- GIVEN a reunion with ID `{id}` that exists and is non-archived
- WHEN the client requests the export endpoint
- THEN the response body is a valid `.xlsx` file with Content-Type `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`
- AND Content-Disposition contains `attachment; filename="minuta-reunion-{id}-{fecha}.xlsx"`

#### Scenario: Reunion not found

- GIVEN no reunion with the given `{id}` exists
- WHEN the export is requested
- THEN the response is HTTP 404

#### Scenario: Archived reunion blocked

- GIVEN a reunion where `archivada=1`
- WHEN the export is requested
- THEN the response is HTTP 404

### Requirement: Column Ordering and Selection

Rows SHALL be ordered by `orden ASC` matching the UI order. Columns SHALL follow the UI sequence: orden, fecha, n_pedido, oc, fecha_esperada, pedido, última_novedad, consultas, novedad_nueva_reunion, importancia, estado. Non-data columns (drag, acciones) SHALL be excluded.

#### Scenario: Rows ordered by orden ASC

- GIVEN pedidos with orden values 3, 1, 2
- WHEN the export is generated
- THEN rows appear in the sheet as 1, 2, 3

### Requirement: Auto-Width and wrapText

The system SHALL calculate column widths from the maximum cell content length per column (`min(max_content_len + 2, 60)`), apply `wrapText=True` on text columns, and set `row_dimensions.height` from the max line count per row.

#### Scenario: Content-based width

- GIVEN column "pedido" with max content length 45 characters
- WHEN the export is generated
- THEN that column width is 47

### Requirement: Sheet Protection

The exported sheet SHALL have `sheet.protection.sheet = True` with an empty password. All cells SHALL have `locked=True` except the "novedad_nueva_reunion" column cells, which SHALL have `locked=False`.

#### Scenario: Novedades column editable, others locked

- GIVEN the exported sheet with protection enabled
- WHEN opened in Excel
- THEN only the Novedades nueva reunión column is editable
- AND all other columns are locked

### Requirement: Hideable Columns

Columns not present in the `cols` query parameter SHALL have `column_dimensions.hidden = True`. The UI persists visible-column selection in `localStorage` keyed by reunion ID and sends `?cols=...`.

#### Scenario: Hidden column

- GIVEN visibleCols excludes "fecha_esperada"
- WHEN the export is generated
- THEN the fecha_esperada column is hidden in the workbook

#### Scenario: All columns visible

- GIVEN visibleCols contains all column keys
- WHEN the export is generated
- THEN no column is hidden

### Requirement: Empty Selection Handling

When no pedidos match the selection or filter, the system SHALL return a valid `.xlsx` with headers and zero data rows. It SHALL NOT return an error.

#### Scenario: Empty but valid workbook

- GIVEN a reunion with zero elegible pedidos
- WHEN the export is requested
- THEN the response is a valid `.xlsx` with one sheet containing only the header row
