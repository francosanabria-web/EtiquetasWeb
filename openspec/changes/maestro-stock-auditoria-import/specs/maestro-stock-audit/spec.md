# maestro-stock-audit Specification

## Purpose

Provide a per-`codigo` immutable audit trail for every field changed during a `maestro_stock` import, so users can answer "¿qué cambió en M1046MEC?" across time and understand file-type-specific touches.

## Requirements

### Requirement: Audit Table

The system SHALL create `maestro_stock_audit` if not exists with:

```
id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
codigo VARCHAR(40) NOT NULL,
campo VARCHAR(40) NOT NULL,
valor_antes TEXT NULL,
valor_despues TEXT NOT NULL,
archivo_origen VARCHAR(255) NOT NULL,
tipo_archivo ENUM('detallado','valorizado','general') NOT NULL,
import_log_id INT UNSIGNED NOT NULL,
creado_en DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
KEY idx_audit_codigo (codigo),
KEY idx_audit_import (import_log_id),
KEY idx_audit_creado (creado_en)
```

The table SHALL be created idempotently in `_ensure_tables` and referenced in migration docs.

#### Scenario: Table creation idempotent
- GIVEN the table already exists
- WHEN `_ensure_tables` runs again
- THEN no error is thrown and the table remains

### Requirement: Write Audit on Import

For every `codigo` where `updates` is non-empty (after applying business rules: empty never overwrites, price 0 never overwrites existing >0, and file-type filtering detal/valor/general), the system SHALL insert one audit row per `campo in updates` with `valor_antes` = old DB value, `valor_despues` = new value, `archivo_origen` = current filename, `tipo_archivo` = its type, and `import_log_id` = the newly inserted `maestro_stock_import_log` id. Inserts SHALL happen inside the same `conn` transaction, after the `UPDATE/INSERT maestro_stock` but before `conn.commit()` of that file.

#### Scenario: Detallado only audits minimo+ubicacion
- GIVEN `M1046MEC` incoming with `stock_minimo=2, ubicacion=200846, precio=999` from a `detallado` file
- WHEN import runs
- THEN only 2 audit rows are created (`stock_minimo`, `ubicacion`), not `precio_unitario`

#### Scenario: Valorizado audits stock+resto not minimo
- GIVEN same `M1046MEC` from a `valorizado` file with `stock=1, stock_minimo=99`
- WHEN import runs
- THEN only `stock` (and other resto fields) are audited, `stock_minimo` is ignored

#### Scenario: Price-zero skip not audited
- GIVEN existing `M0392FER` price 100 and incoming price 0
- WHEN import runs
- THEN no audit row for `precio_unitario` is created and no update occurs

### Requirement: History Endpoint

The system SHALL expose `GET /api/maestro-stock/{codigo}/history?page=1&limit=20` returning paginated audit rows for that `codigo`, ordered by `creado_en DESC, id DESC`. Each row SHALL include `campo, valor_antes, valor_despues, archivo_origen, tipo_archivo, import_log_id, creado_en`. The handler SHALL check `salidas:lectura` permission when a token is present.

#### Scenario: History paginated
- GIVEN `M1046MEC` has 5 audit rows
- WHEN `GET /api/maestro-stock/M1046MEC/history?limit=2&page=1` is called
- THEN response is `{ total:5, page:1, limit:2, items:[2 newest rows] }`

#### Scenario: No history
- GIVEN `codigo=NOEXISTE` has no audit rows
- WHEN history is fetched
- THEN response is `{ total:0, items:[] }` with HTTP 200

### Requirement: Frontend History Drawer

The history UI SHALL allow opening history for any `codigo` from the diff table (button `Ver historia`) and from the maestro catalog search. It SHALL call `GET /history`, show a timeline grouped by `import_log_id`/`creado_en`, and allow navigation to the import log detail.

#### Scenario: Open history from diff
- GIVEN diff row for `M1046MEC`
- WHEN user clicks `Ver historia`
- THEN a drawer/modal fetches history and shows each change with `antes -> después` and `archivo (tipo)` badge

### Requirement: Backwards Compatibility

Historical imports without audit rows SHALL still be queryable via `/import-log/{id}/diff` fallback parse. New audit rows SHALL NOT retroactively require backfill; audit starts from the next successful import.

#### Scenario: Historical log without audit still shows diff
- GIVEN log id=5 predates audit table
- WHEN `/dif` is requested
- THEN it returns parsed rows from `reporte`, not empty
