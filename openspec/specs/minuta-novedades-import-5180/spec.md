# minuta-novedades-import-5180 Specification

## Purpose

Bulk import/merge of returned novedades from the exported `.xlsx`, keyed by `pedido_id`, applying duplicate/consulta/no_reconocidas logic non-destructively. Returns a merge summary with counts for each outcome category.

## Requirements

### Requirement: Import Endpoint

The system SHALL expose `POST /api/minuta/pedidos/importar-novedades?reunion_id={id}` accepting multipart `archivo` (.xlsx). It SHALL parse only the "Novedades" sheet and match rows by `pedido_id`.

#### Scenario: Successful merge import

- GIVEN a reunion `{id}` that exists and is non-archived
- WHEN the client sends a valid `.xlsx` with Novedades sheet
- THEN the system parses the sheet, matches by pedido_id, and returns a merge summary

#### Scenario: Missing Novedades sheet

- GIVEN an uploaded `.xlsx` without a "Novedades" sheet
- WHEN the import is requested
- THEN the response is HTTP 400 with message "Sheet 'Novedades' not found"

#### Scenario: Reunion not found

- GIVEN no reunion with the given `{id}` exists
- WHEN the import is requested
- THEN the response is HTTP 404

### Requirement: Row Matching by pedido_id

Merge mode SHALL match imported rows to existing pedidos using `pedido_id` as the natural key. Each pedido row is unique; no hidden columns or composite keys are needed.

#### Scenario: Match by pedido_id

- GIVEN an imported row with `pedido_id=5`
- WHEN merge processing runs
- THEN the system identifies the corresponding pedido in the reunion

#### Scenario: No match — no_reconocida

- GIVEN an imported row with `pedido_id=999` not present in the reunion
- WHEN merge processing runs
- THEN the row is reported as "no_reconocidas" in the summary
- AND no new pedido is created

### Requirement: Duplicate Detection

If the imported novedad text, normalized (trim, collapse multi-spaces, case-insensitive), is identical to the existing novedad text for the same `pedido_id`, the system SHALL skip the row as a duplicate.

#### Scenario: Identical text skipped

- GIVEN an existing novedad "Revisar stock" for pedido `pedido_id=5`
- WHEN the imported Excel has novedad "revisar  stock" for the same pedido
- THEN the row is counted as "omitidas_duplicadas"
- AND no new novedad is inserted

### Requirement: Conflict — Pending Consulta

If the imported novedad text differs from the existing novedad for the same `pedido_id`, the system SHALL NOT overwrite. It SHALL create a pending consultation record. The existing novedad is preserved unchanged.

#### Scenario: Different text creates consulta

- GIVEN an existing novedad "Stock OK" for pedido `pedido_id=5`
- WHEN the imported Excel has novedad "Falta material" for the same pedido
- THEN a pending consultation record is created
- AND the existing novedad is preserved
- AND the summary counts it as "pendientes_consulta"

### Requirement: Empty Novedad Handling

If the novedad text for an imported row is empty or whitespace-only, the system SHALL skip that row silently.

#### Scenario: Empty novedad skipped

- GIVEN an imported row with `pedido_id=5` and empty text
- WHEN merge processing runs
- THEN the row is counted as "omitidas"
- AND no novedad record is created

### Requirement: Non-Destructive Merge

Merge mode SHALL NOT delete any existing pedido or novedad records. It SHALL only ADD new consultation records for conflicts and insert new novedades for matching text.

#### Scenario: No deletions during merge

- GIVEN a reunion with 10 pedidos and 8 novedades
- WHEN merge processes 5 rows (2 new, 1 duplicate, 1 conflict, 1 no_reconocida)
- THEN all 10 pedidos and 8 novedades remain unchanged
- AND 1 new novedad and 1 pending-consulta record are created

### Requirement: Response Summary

The endpoint SHALL return a JSON summary with `procesadas`, `omitidas_duplicadas`, `pendientes_consulta`, `no_reconocidas`, and `total_importadas`. The sum of all categories SHALL equal `total_importadas`.

#### Scenario: Complete summary returned

- GIVEN an import of 10 rows
- WHEN processing completes
- THEN the response contains `{procesadas, omitidas_duplicadas, pendientes_consulta, no_reconocidas, total_importadas: 10}`
- AND procesadas + omitidas_duplicadas + pendientes_consulta + no_reconocidas = 10
