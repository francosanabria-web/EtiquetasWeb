# Design: Maestro Stock Auditoria Import

## Overview

Add an append-only audit trail at import time and make the import history persistent, filterable and exportable, without breaking the existing `reporte` TEXT flow or `maestro_stock` business rules.

## Context

- `backend/salidas/routes/maestro_stock.py` owns both business rules and DDL (`_ensure_tables`, `_process_single_file`). The same connection/transaction pattern must be kept.
- `ActualizacionPage.tsx` is the sole import UI; it uses Vite proxy ` /api/maestro-stock -> :8018` and `maestroStockClient.ts`.
- Historical data: `maestro_stock_import_log` already holds `reporte` TEXT but truncated on reads; no structured diff.
- Failure to address truncation and volatility drove user request (M1046MEC double-touch confusion).

## Architecture

```
Excel files (.xlsx)
   |
   v
POST /api/maestro-stock/import (multipart)
   -> _process_single_file per file (sequential, threadpool)
        -> _detectar_columnas, _tipo_archivo
        -> for each codigo: build inc -> filtered by tipo
        -> compare with existing -> updates dict (respects empty/price-zero)
        -> UPDATE/INSERT maestro_stock
        -> NEW: INSERT maestro_stock_audit rows per campo in updates (same conn, before commit)
   -> INSERT maestro_stock_import_log (reporte TEXT kept)
   -> commit

GET /api/maestro-stock/import-log            (list, enriched counters, reporte truncated)
GET /api/maestro-stock/import-log/{id}       (full reporte)
GET /api/maestro-stock/import-log/{id}/diff  (NEW: structured diff from audit else parse reporte)
GET /api/maestro-stock/{codigo}/history      (NEW: paginated audit by codigo)
GET /api/maestro-stock/stats, /              (unchanged)

Frontend:
ActualizacionPage
  - loads logs + stats on mount (already does)
  - persistentCard = logs[0] always (not result)
  - diff = fetch /import-log/{id}/diff on expand or on result arrival
  - filters: codigo substring (client-side on diff), campo select
  - actions: copy TSV, export CSV (Blob)
  - history drawer: fetch /{codigo}/history paginated
```

## Data Model

### maestro_stock_audit (NEW)

```sql
CREATE TABLE IF NOT EXISTS maestro_stock_audit (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  codigo VARCHAR(40) COLLATE utf8mb4_unicode_ci NOT NULL,
  campo VARCHAR(40) COLLATE utf8mb4_unicode_ci NOT NULL,
  valor_antes TEXT COLLATE utf8mb4_unicode_ci NULL,
  valor_despues TEXT COLLATE utf8mb4_unicode_ci NOT NULL,
  archivo_origen VARCHAR(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  tipo_archivo ENUM('detallado','valorizado','general') NOT NULL,
  import_log_id INT UNSIGNED NOT NULL,
  creado_en DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_audit_codigo (codigo),
  KEY idx_audit_import (import_log_id),
  KEY idx_audit_creado (creado_en),
  CONSTRAINT fk_audit_import FOREIGN KEY (import_log_id) REFERENCES maestro_stock_import_log(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

- FK is optional; if engine lacks FK on existing install, create without constraint but keep index. Implementation will try FK, fall back to no-FK.
- `_ensure_tables` will attempt FK version first, catch exception, then create without FK.

### maestro_stock_import_log enrichment

No schema change; just return extra JSON fields already computed in `_process_single_file` return dict: `precios_modificados, stock_altas, stock_bajas, stock_min_mod, ubic_mod, otros_mod, precios_propagados, propagated_rows`. Store duracion_ms already; for audit we add `import_log_id` reuse.

## Backend Changes

### 1. `_ensure_tables(conn)`
Add DDL for audit after existing two tables. Keep idempotent via `CREATE TABLE IF NOT EXISTS`. Add FK handling.

### 2. `_process_single_file(filename, content) -> dict`
Changes:
- Keep existing diff counting.
- After `UPDATE maestro_stock SET ... WHERE codigo=%s`, collect audit payloads in `pending_audits: list[tuple]`.
- After processing all rows but before `INSERT maestro_stock_import_log`, keep `reporte` build.
- After `INSERT ... maestro_stock_import_log`, get `lastrowid` (`cur.lastrowid`). Then `executemany` pending audits with that `import_log_id` and `archivo_origen, tipo`.
- Audit row `valor_antes` is `str(existing.get(k))` or NULL; `valor_despues` is `str(v)` normalized (round floats to 2 decides). Use same before/after used in `reporte` line `f"{k} {old}->{new}"` to keep consistency.
- Commit once after both inserts.

Signature of `pending_audits`: `(codigo, campo, valor_antes, valor_despues, archivo_origen, tipo_archivo, import_log_id)` — but `import_log_id` unknown until after log insert, so hold `(codigo, campo, vAntes, vDesp)` and fill on flush.

Atomicity: single `conn` with one final `commit`; if any audit insert fails, rollback entire file (existing behavior).

### 3. New handlers

#### `GET /api/maestro-stock/import-log/{id}/diff`
```python
async def get_import_diff(request): # path param id
  # verify permiso salidas:lectura if token
  # try SELECT * FROM maestro_stock_audit WHERE import_log_id=%s ORDER BY id
  # if rows: return { import_log_id, items: rows } mapped with iso creado_en
  # else: fetch reporte from maestro_stock_import_log WHERE id=%s
  #       parse lines: for line in reporte.splitlines():
  #         if line.strip().startswith("~ MOD") or line.strip().startswith("+ NEW"):
  #           extract codigo and "k old->new" fragments via regex r"(\w+)\s+([^\s]+)->([^\s,]+)"
  #       return fallback items with tipo_archivo from log's tipo_archivo
```

#### `GET /api/maestro-stock/{codigo}/history`
```python
async def get_codigo_history(request): # path {codigo}
  # q: page, limit (1..100)
  # SELECT COUNT(*) FROM maestro_stock_audit WHERE codigo=%s
  # SELECT * FROM ... WHERE codigo=%s ORDER BY creado_en DESC, id DESC LIMIT %s OFFSET %s
  # return { total, page, limit, items }
```

#### Extend `get_import_log` and `get_import_log_by_id`
- `get_import_log` list view currently selects only base columns and truncates reporte 2000. Extend SELECT to include `codigos_nuevos etc.` plus attempt to include enriched counters by parsing if not stored; simpler: add columns to table? No schema change needed: compute enriched counters are transient in `_process_single_file` but not stored. To avoid schema migration, the list will return `reporte` truncated but new detail `diff` endpoint is canonical. Alternatively, add JSON column `detalle_json`? Decision: no schema change for log; keep counters in audit parse, but also add columns `precios_modificados...` to `maestro_stock_import_log` as nullable INTs via `ALTER TABLE ADD COLUMN IF NOT EXISTS` in `_ensure_tables` (lighter than JSON). That way list can return them without parsing.

Add to `_ensure_tables`:
```sql
ALTER TABLE maestro_stock_import_log ADD COLUMN precios_modificados INT NOT NULL DEFAULT 0 ... etc.
```
Implemented via `information_schema.COLUMNS` check per column, similar to alias migration.

If FK/migration fails, fallback to returning zeroes; UI shows "—" tolerance.

### 4. Routing

Add to Starlette routes mapping (in `backend/salidas/main.py` or wherever `maestro_stock.py` handlers are mounted — check `apps/web/...` proxy). Add:

```python
app.add_route("/api/maestro-stock/import-log/{id:int}/diff", get_import_diff, methods=["GET"])
app.add_route("/api/maestro-stock/{codigo}/history", get_codigo_history, methods=["GET"])
```

Ensure route ordering: `/import-log/{id}/diff` before `/{codigo}/history` to avoid codigo capturing "import-log".

## Frontend Changes

### maestroStockClient.ts

Add types:

```ts
export type ImportDiffRow = {
  id?: number;
  codigo: string;
  campo: string;
  valor_antes: string | null;
  valor_despues: string;
  archivo_origen: string;
  tipo_archivo: string;
  import_log_id: number;
  creado_en: string;
};
export type ImportDiffResult = { import_log_id: number; items: ImportDiffRow[] };
export type CodigoHistoryResult = { total: number; page: number; limit: number; items: ImportDiffRow[] };
export function getImportDiff(id:number): Promise<ImportDiffResult>
export function getCodigoHistory(codigo:string, params?:{page?,limit?}): Promise<CodigoHistoryResult>
```

Update `ImportLog` to include enriched counters optional.

### ActualizacionPage.tsx

Refactor:

- State: `result` (ephemeral) + `logs` (persistent). Derive `persistentLast = logs[0] ?? null` always.
- `Limpiar` -> only `setFiles([]); setStatus('idle'); setError(null); // do NOT clear result nor logs` . Optionally keep result but show persistent card below.
- Cards: keep top 4 cards (MOD/NUEVOS/PROPAGADOS/SIN PRECIO) fed by `result ?? persistentLast`? Better: show `result` when present else `persistentLast` counters, with label "Último import" vs "Import en curso".
- `Detalle por archivo` currently uses `result.detalle[].reporte` truncated. Replace with:
  - Component `DiffTable { diffRows, filterCodigo, filterCampo, onViewHistory }`
  - Fetch diff via `getImportDiff(id)` on expand or when `result` arrives (use `result` instant diff derived from audit-like client parse, then replace with server diff).
  - Filters: `useState filterCodigo`, `useState filterCampo`, `useMemo filtered = diffRows.filter(r => r.codigo.includes(filterCodigoUpper) && (filterCampo==='all' || r.campo===filterCampo))`
  - Highlight: cell bg when `valor_antes !== valor_despues`.
  - Export: `toCsv(filtered)` -> Blob -> download via anchor.
  - Copy: `navigator.clipboard.writeText(filtered.map(...).join('\n'))`.

- Log table: make rows clickable expand -> fetch diff inline. Show enriched counters badges: `ubic_mod`, `stock_altas`, etc. Add column `Acción` -> `Ver diff`.

- Global sin precio: add tooltip/label `(global)` next to value: `<span title="Total con precio <=0">Sin precio (global)</span>`.

- Per-codigo history drawer: new state `historyCodigo`, `historyData`, `historyPage`. On click `Ver historia` in diff row, open overlay calling `getCodigoHistory(codigo)`.

- Explain double-touch: add info callout above diff: "Si un código aparece en detallado y valorizado en el mismo import, solo se aplican los campos permitidos por tipo — por eso M1046MEC cambió mínimo+ubicación en detallado y descripción/stock en valorizado."

Reuse existing `pillColor`, `formatDate`, `truncate`.

No new deps.

## Testing Strategy

- Backend unittest: use `sqlite3` in-memory or mock `pymysql`? Existing project uses `python -m unittest -v` with real MySQL? Prefer `unittest.mock.patch` for `get_connection`. Create tests in `backend/salidas/tests/test_maestro_audit.py`:
  - `test_detallado_only_audits_minimo_ubic`
  - `test_valorizado_ignores_minimo`
  - `test_price_zero_not_audited`
  - `test_history_pagination`
  - `test_diff_fallback_parse`

- Frontend: `tsc --noEmit` only (no jest). Verify build.

## Risks & Mitigations

- Route collision `/import-log/{id}/diff` vs `/{codigo}` — ensure import-log routes registered first.
- FK failure on older MariaDB — fallback creation without FK.
- Enriched columns on `import_log` via ALTER may fail on lack of privilege — swallow and degrade (return fallback zeroes).
- Large diff (2000+ rows) — paginate history, limit diff to 5000.

## Rollout

- PR chain (auto-chain pending):
  - PR1 backend DDL + audit writes
  - PR2 backend endpoints (diff, history, enriched log)
  - PR3 frontend client types
  - PR4 frontend page (persistent card, diff table, filters, CSV, drawer) + docs
- Feature flag: if backend lacks audit table, frontend fetch diff will hit fallback parse and still function.
