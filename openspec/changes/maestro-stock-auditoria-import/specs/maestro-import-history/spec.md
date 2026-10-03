# maestro-import-history Specification

## Purpose

Provide persistent, filterable, exportable history for `maestro_stock` imports so users never lose the last import reference and can understand per-file, per-field changes (including the double-touch case `M1046MEC` with `detallado` vs `valorizado` rules).

## Requirements

### Requirement: Persistent Last Import

The system SHALL render the last import summary from `GET /api/maestro-stock/import-log` (most recent `id`), not from volatile React `result` state. The `Limpiar` action SHALL only clear selected files, and MUST NOT clear the displayed last import card or the `logs` table.

#### Scenario: Last import remains after Limpiar
- GIVEN a successful import returning `ImportResult` and a `logs` array with most recent `id=42`
- WHEN the user presses `Limpiar`
- THEN the file list is cleared and `status` returns to `idle`, but the persistent card showing `logs[0]` (id 42) remains visible

#### Scenario: Page refresh still shows last import
- GIVEN a prior import with `id=42`
- WHEN the page is reloaded and `GET /api/maestro-stock/import-log` returns `id=42` as first item
- THEN the persistent card and expandable log both show `id=42` without requiring `result`

### Requirement: Structured Diff per Import Log

The system SHALL expose `GET /api/maestro-stock/import-log/{id}/diff` returning structured rows without truncation. When `maestro_stock_audit` rows exist for that `import_log_id`, they SHALL be returned; otherwise the endpoint SHALL fallback to parsing `reporte` TEXT lines starting with `~ MOD` / `+ NEW`.

#### Scenario: Diff from audit table
- GIVEN `import_log_id=42` has 5 rows in `maestro_stock_audit`
- WHEN `GET /api/maestro-stock/import-log/42/diff` is called
- THEN response is `{ items: [{codigo, campo, valor_antes, valor_despues, archivo_origen, tipo_archivo, creado_en}] }` with 5 items

#### Scenario: Fallback parse when no audit (historical)
- GIVEN `import_log_id=10` has zero audit rows but `reporte` contains `~ MOD M1046MEC: ubicacion 2009D->200846`
- WHEN `GET /api/maestro-stock/import-log/10/diff` is called
- THEN response parses that line into `{codigo:"M1046MEC", campo:"ubicacion", valor_antes:"2009D", valor_despues:"200846"}`

### Requirement: Import Log Enrichment

`GET /api/maestro-stock/import-log` (list) SHALL return per-item enriched counters already computed by `_process_single_file`: `precios_modificados, stock_altas, stock_bajas, stock_min_mod, ubic_mod, otros_mod, precios_propagados, propagated_rows` alongside `codigos_nuevos, codigos_modificados, codigos_sin_precio, duracion_ms, reporte`. The list view MAY truncate `reporte` to 2000 chars, but `GET /byId` and `/diff` MUST NOT.

#### Scenario: Enriched counters present
- GIVEN a log with 2 mods (1 ubic)
- WHEN the list is fetched
- THEN each item contains `ubic_mod:1` and not only `codigos_modificados:2`

### Requirement: Filterable Diff Table UI

`ActualizacionPage` SHALL render the structured diff in a table with:
- Input text `Filtro por código` (case-insensitive substring on `codigo`)
- Select `Filtro por campo` (all | descripcion | stock | stock_minimo | ubicacion | precio_unitario | importancia | categoria)
- Highlight for changed cells (`valor_antes` vs `valor_despues` differ)
- Actions: `Copiar` (tab-separated) and `Exportar CSV`

#### Scenario: Filter by codigo
- GIVEN diff has rows for `M1046MEC` and `M0392FER`
- WHEN user types `M1046` in filter
- THEN only rows with `codigo` containing `M1046` are shown

#### Scenario: Export CSV
- GIVEN filtered diff has 2 rows
- WHEN user clicks `Exportar CSV`
- THEN a file `import-42-diff.csv` downloads with headers `codigo,campo,antes,despues,archivo,tipo`

### Requirement: Clarify Global Counters

The `Sin precio` top card and per-log `codigos_sin_precio` SHALL be labeled as `Sin precio (global)` with tooltip `Total de artículos con precio <=0 en maestro_stock` to avoid confusion with import delta.

#### Scenario: Label is global
- GIVEN `stats.sin_precio=848`
- WHEN the card is rendered
- THEN its subtitle says `global` and tooltip explains it is not `delta`

### Requirement: Expandable Log Rows

The `Últimas importaciones` table SHALL make each row expandable to show its full structured diff inline (via `GET /diff` on expand), plus the raw `reporte` TEXT collapsed. The existing `Última actualización` modal SHALL also use the structured diff with the same filters.

#### Scenario: Expand row loads diff
- GIVEN user expands log `id=42`
- WHEN diff fetch completes
- THEN the row shows a mini diff table and a `<details>Ver reporte raw</details>`
