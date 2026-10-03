# Tasks: Maestro Stock Auditoria Import

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~650-780 |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR1 backend DDL+audit writes | PR2 backend endpoints (diff/history/enriched log) | PR3 frontend client+types | PR4 frontend page (persistent diff/filters/CSV/drawer) |
| Delivery strategy | auto-chain |
| Chain strategy | stacked-to-main |
| Decision needed before apply | No (auto-chain proceeds in slices) |

### Suggested Work Units

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|------|------|-----------|----------------------|-----------------|-------------------|
| 1 | Add maestro_stock_audit DDL + transactional audit writes per field (respecting file-type + price-zero rules) | PR1 | `python -m unittest -v backend/salidas/tests/test_maestro_audit.py` | mocked pymysql + sqlite fallback | audit table + writes only; DROP TABLE rolls back |
| 2 | Add GET /import-log/{id}/diff (audit else parse reporte) + GET /{codigo}/history + enrich GET /import-log with counters | PR2 | `python -m unittest -v` | Starlette TestClient mocked DB | new routes only |
| 3 | Add frontend client types and helpers getImportDiff/getCodigoHistory + CSV utils | PR3 | `tsc --noEmit` | TypeScript build | maestroStockClient.ts only |
| 4 | Refactor ActualizacionPage: persistent last import, structured diff table with filters/highlight/export, expandable logs, global label, history drawer + double-touch callout | PR4 | `tsc --noEmit` | Vite build | ActualizacionPage.tsx only |

## Phase 1: Foundation (DDL audit)

- [ ] 1.1 Add DDL for `maestro_stock_audit` to `backend/salidas/routes/maestro_stock.py:_ensure_tables` (idempotent CREATE IF NOT EXISTS with FK attempt + fallback without FK + indexes on codigo/import_log_id/creado_en)
- [ ] 1.2 Add idempotent ALTERs on `maestro_stock_import_log` for enriched counters (`precios_modificados`, `stock_altas`, `stock_bajas`, `stock_min_mod`, `ubic_mod`, `otros_mod`, `precios_propagados`, `propagated_rows`) via information_schema check per column (or CREATE IF migration already)
- [ ] 1.3 Append same DDL to `docs/maestro_stock_migracion_v1.sql` for fresh installs

## Phase 2: Core Backend (audit writes + endpoints)

- [ ] 2.1 Modify `_process_single_file` to emit one `maestro_stock_audit` row per `k in updates` (valor_antes from existing, valor_despues from updates), batched with `import_log_id` after log insert, inside same transaction before final commit; keep `reporte` TEXT for compat; cap pending audits at 5000 per file and log warning if exceeded
- [ ] 2.2 Ensure file-type filtering is respected in audit (detallado audits only stock_minimo/ubicacion; valorizado excludes stock_minimo; general excludes stock/stock_minimo)
- [ ] 2.3 Ensure price-zero business rule is respected: when new price 0 and old >0, skip update and skip audit for that field
- [ ] 2.4 Implement `GET /api/maestro-stock/import-log/{id}/diff` → audit rows if exist else fallback parse of `reporte` TEXT (`~ MOD`/`+ NEW` regex), returns `{ import_log_id, items }` without truncation, with `creado_en` isoformat
- [ ] 2.5 Implement `GET /api/maestro-stock/{codigo}/history?page&limit` → paginated audit by codigo ordered DESC, with permiso check, returns `{ total, page, limit, items }`
- [ ] 2.6 Enrich `GET /api/maestro-stock/import-log` and `get_import_log_by_id` to include enriched counters from audit or from log columns (with graceful fallback to 0 when columns missing)
- [ ] 2.7 Wire routes in `backend/salidas/main.py` (or Starlette router mounting maestro_stock) with correct order: `/import-log/{id}/diff` before `/{codigo}/history`, handle `unknown column alias` pattern already present

## Phase 3: Integration (frontend client + types)

- [ ] 3.1 Add types `ImportDiffRow`, `ImportDiffResult`, `CodigoHistoryResult` and functions `getImportDiff(id)`, `getCodigoHistory(codigo, params?)` to `apps/web/src/api/maestroStockClient.ts` (reuse `fetchJson` + authHeaders pattern)
- [ ] 3.2 Enrich `ImportLog` type to include optional counters (`precios_modificados...propagated_rows`)
- [ ] 3.3 Add helper `toCsv(rows)` / `toTsv(rows)` utils in same module or local to page (no new dep)

## Phase 4: Feature (ActualizacionPage persistent + diff + filters + drawer)

- [ ] 4.1 Make `Limpiar` only clear `files/status/error` not `result` nor `logs`; derive `persistentLast = logs[0]` and always show card for `result ?? persistentLast`; add subtitle distinguishing "Resultado de esta importación" vs "Último import registrado"
- [ ] 4.2 Replace truncated `<pre>` reporte in `result.detalle` and `logs` with `DiffTable` component: columns `código | campo | antes -> después | archivo | tipo`, row highlight, badges for tipo, client-side filters (`filtroCodigo` text input + `filtroCampo` select), no truncation on diff fetch
- [ ] 4.3 Add actions `Copiar` (clipboard TSV) and `Exportar CSV` (Blob anchor download `import-{id}-diff.csv`) on filtered rows
- [ ] 4.4 Add tooltip/label `Sin precio (global)` with `title` explaining global total, not delta, both in top cards and per-file summary
- [ ] 4.5 Make each `Últimas importaciones` row expandable: on expand fetch `getImportDiff(id)` and render inline `DiffTable` + `<details>Ver reporte raw</details>` with full `getImportLogById(id).reporte`
- [ ] 4.6 Update `Última actualización` modal to also render structured diff with same filters instead of only raw reporte
- [ ] 4.7 Add per-codigo history drawer/modal: state `historyCodigo/historyData/page`, button `Ver historia` per diff row and optional search outside table, fetch `getCodigoHistory(codigo)` paginated (limit 20), timeline grouped by `import_log_id/creado_en`, click to jump to that log's diff
- [ ] 4.8 Add double-touch info callout: "Un código puede tocarse en 2 archivos: detallado solo aplica mínimo+ubicación; valorizado stock+resto sin mínimo — por eso M1046MEC aparece 2 veces con campos distintos"
- [ ] 4.9 Remove/raise truncation limits: detalle report now from `diff` not `reporte.slice(4000)`; keep fallback reporte display capped at 4000 only when audit fallback and as collapsed raw

## Phase 5: Testing

- [ ] 5.1 Create `backend/salidas/tests/test_maestro_audit.py` with `unittest` + `unittest.mock.patch('routes.maestro_stock.get_connection')` using an in-memory sqlite/pymysql fake:
  - detallado only audits minimo+ubicacion (precio ignored)
  - valorizado ignores minimo
  - price-zero skip not audited
  - history pagination
  - diff fallback parse when no audit rows
  - large import does not exceed 5000 audit cap
- [ ] 5.2 Run `python -m unittest -v backend/salidas/tests/test_maestro_audit.py` (or `python -m unittest discover`) — must pass without real DB
- [ ] 5.3 Run `tsc --noEmit --project apps/web/tsconfig.json` — must pass (allow existing unrelated errors to stay unchanged but new code must type-check)
- [ ] 5.4 Manual smoke: `POST /import` with 2 files (one detallado with 2 codes, one valorizado with 8) → verify audit rows, diff, history for M1046MEC

## Phase 6: Docs & Cleanup

- [ ] 6.1 Update `docs/maestro_stock_migracion_v1.sql` (already in 1.3) and ensure `openspec` spec `delta` sync will be handled by archive
- [ ] 6.2 Ensure `maestro_stock.py` keeps Spanish code comments for business rules as per `apply.guidelines`
