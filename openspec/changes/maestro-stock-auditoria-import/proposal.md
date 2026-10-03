# Proposal: Maestro Stock Auditoria Import

## Intent

The `Actualización y datos` import screen shows a volatile, truncated text `reporte` for `POST /api/maestro-stock/import`. Users cannot tell what changed per `codigo` (e.g. `M1046MEC` appears in two files with different file-type rules), cannot filter by code, cannot export the diff, and lose the reference after pressing `Limpiar` or refreshing. The persisted `maestro_stock_import_log` table exists but is rendered as a truncated, non-searchable list without per-field breakdown or per-codigo history. We need persistent, filterable, exportable history and a true audit trail per `codigo`.

## Scope

### In
- Fix `ActualizacionPage.tsx` so the last import summary is **persistent** (derived from `GET /api/maestro-stock/import-log`, not volatile React `result` state). `Limpiar` SHALL only clear selected files, not the displayed last import.
- Replace truncated `<pre>` reporte with a **structured, filterable diff table**: `codigo | campo | antes -> después | tipo_archivo`, with search by codigo and filter by campo, plus copy/export CSV.
- Clarify `848 sin precio` as **global total**, not delta, and show per-file breakdown (`precios_modificados, stock_altas/bajas, stock_min_mod, ubic_mod, otros_mod`) already computed by backend but not shown in the log table.
- Add true **per-codigo audit trail** persisted at import time: new table `maestro_stock_audit` and endpoint `GET /api/maestro-stock/{codigo}/history` + `GET /api/maestro-stock/import-log/{id}/diff` for structured diff.
- Backend idempotent migration for `maestro_stock_audit`, ingestion in `_process_single_file` inside the same transaction, and backfill-safe reads.
- Explain double-touch case (e.g. `M1046MEC` touched by `detallado` for `stock_minimo+ubicacion` and by `valorizado` for the rest) explicitly in UI.

### Out of Scope
- Price propagation logic to `salida_historial` (existing, unchanged).
- Firebase alias sync (`PUT /api/maestro-stock/{codigo}/alias`) — not touched.
- Full revision history UI for every maestro_stock field outside import context (only import-driven audit).
- Migration of historical `reporte` TEXT into structured audit (best-effort parse only if cheap; otherwise audit starts from next import).

## Capabilities

### New Capabilities
- `maestro-import-history`: Persistent, filterable, exportable import history derived from `maestro_stock_import_log` with structured diff, search by codigo, and no truncation.
- `maestro-stock-audit`: Per-codigo immutable audit trail of field-level changes (`codigo, campo, valor_antes, valor_despues, import_log_id, archivo_origen, tipo_archivo`) queryable by codigo.

### Modified Capabilities
- `maestro-stock-import`: Existing import continues to produce `reporte` TEXT for backwards compat, but also writes `maestro_stock_audit` rows in the same transaction.
- `actualizacion-page`: `ActualizacionPage.tsx` now renders persistent last-import card + expandable log rows + per-codigo history modal/drawer.

## Approach

Approach B (complete) — chosen by user:

1. **DB**: `CREATE TABLE IF NOT EXISTS maestro_stock_audit (...)` with `id, codigo, campo, valor_antes, valor_despues, archivo_origen, tipo_archivo, import_log_id, creado_en`, indexes on `codigo` and `import_log_id`. Ensured in `_ensure_tables`. Written inside `_process_single_file` for each `updates` dict entry (one row per changed field per codigo), within same connection/transaction before `maestro_stock_import_log` insert. The `reporte` TEXT is kept for compat.

2. **Backend API**: Add `GET /api/maestro-stock/import-log/{id}/diff` (structured diff from audit or fallback parse), `GET /api/maestro-stock/{codigo}/history` (paginated audit by codigo), extend `GET /api/maestro-stock/import-log` to return `precios_modificados ... otros_mod` + `precios_propagados` (already computed but not all returned), and ensure `GET /api/maestro-stock/import-log` no longer truncates for detail fetch.

3. **Frontend**: 
   - `maestroStockClient.ts` add `getImportDiff(id)`, `getCodigoHistory(codigo, params)`.
   - `ActualizacionPage.tsx`: keep `result` for immediate feedback, but also render `lastLog` from `logs[0]` as the persistent truth; `Limpiar` does not clear `result` persistence — the card stays. Diff table component with `filtroCodigo` input, `filtroCampo` select, highlight `antes != despues`, copy/CSV export. Expandable rows in log table with full diff. "Ver historia" action per codigo opens audit timeline.
   - Disambiguate `M1046MEC` case: badge per file-type and note "detallado solo toca mínimo+ubicación".

4. **Testing**: Unit tests for audit insertion (field-level rows, price-zero rule, file-type filtering), API integration for history/diff, and `tsc --noEmit`.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `backend/salidas/routes/maestro_stock.py` | Modified | Add `maestro_stock_audit` table, write audit rows per field, new endpoints `import-log/{id}/diff` and `{codigo}/history`, enrich `import-log` response |
| `backend/salidas/routes/maestro_stock.py:_ensure_tables` | Modified | DDL for audit table + indexes |
| `backend/salidas/routes/maestro_stock.py:_process_single_file` | Modified | Emit one audit row per `k in updates` with before/after |
| `apps/web/src/api/maestroStockClient.ts` | Modified | Add `getImportDiff`, `getCodigoHistory`, types `ImportDiffRow`, `CodigoHistoryResult` |
| `apps/web/src/modules/actualizacion/ActualizacionPage.tsx` | Modified | Persistent last-import card, diff table, filtros, export CSV, expandable log, per-codigo history drawer, clarify 848 global |
| `docs/maestro_stock_migracion_v1.sql` | Modified | Append audit table DDL for fresh installs |
| `openspec/specs/maestro-import-history` | New | Spec for persistent history |
| `openspec/specs/maestro-stock-audit` | New | Spec for per-codigo audit |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Audit table write doubles rows on duplicate imports | Med | One audit row per field per codigo per import_log_id, inside same TX, with unique per-field emission check |
| Large imports (500+ codes) blow audit table | Low | Audit is append-only with index on codigo; paginate history, cap diff at 5000 rows, keep reporte TEXT truncated at 60k |
| Historical data without audit (pre-migration) | High | Fallback: `GET /diff` parses reporte TEXT line `~ MOD COD: ...` when no audit rows; document that history starts from next import |
| Frontend chained PR exceeds 400 lines | Med | Split per delivery_strategy auto-chain: PR1 backend audit+DDL, PR2 backend endpoints, PR3 frontend client+types, PR4 ActualizacionPage persistent+diff |
| Price-zero rule confusion in audit (0 does not overwrite >0) | Med | Audit only records actual `updates` dict — price-zero skips are not audited, so history matches reality |

## Rollback Plan

Additive only. If audit causes issues, drop `maestro_stock_audit` writes (keep DDL) and revert new endpoints — `maestro_stock_import_log` and `reporte` TEXT remain functional. Frontend falls back to parsing `reporte` (behind feature flag `useAudit`). No data loss on rollback.

## Dependencies

- Existing `maestro_stock` and `maestro_stock_import_log` tables, `get_connection`, `pymysql`, `pandas` (already present).
- Vite proxy `/api/maestro-stock` -> `:8018` (already configured).
- No new npm deps.

## Success Criteria

- [ ] `POST /api/maestro-stock/import` with `M1046MEC` in both `detallado` and `valorizado` creates two `maestro_stock_audit` rows per file-type-appropriate fields (stock_minimo+ubicacion from detallado, resto from valorizado) and does NOT audit price 0->existing>0.
- [ ] `GET /api/maestro-stock/M1046MEC/history` returns paginated audit with `campo, valor_antes, valor_despues, archivo_origen, tipo_archivo, creado_en`.
- [ ] `GET /api/maestro-stock/import-log/{id}/diff` returns structured rows without truncation (fallback parse when no audit).
- [ ] `Limpiar` in ActualizacionPage does not erase the last import card; last import is always visible from `logs[0]`.
- [ ] Diff table supports filter by `codigo` substring and by `campo`, highlights changes, and exports CSV.
- [ ] `848 sin precio` is labeled as global total, not import delta.
- [ ] `python -m unittest -v` and `tsc --noEmit` pass.
