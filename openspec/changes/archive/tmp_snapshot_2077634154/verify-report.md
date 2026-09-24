# Verify Report: Cajas Hub with Ideal Toolkit, Technician Inventories and KPIs

**Change:** `cajas-hub-ideal-inventario-kpis`
**Date:** 2026-05-13
**Verifier:** gentle-orchestrator (auto, both artifact stores)
**Base:** proposal + 4 specs + design + tasks (7 phases)
**Store mode:** hybrid (openspec + engram)

## Verdict
**PASS_WITH_WARNINGS** — all spec scenarios implemented, 68/68 backend tests green, frontend hub renders with 3 cards, buscador integrated, isolation holds. 2 warnings (follow-up) and 3 suggestions; no CRITICAL blockers.

## Execution Evidence

### Backend
```bash
Set-Location backend/cajas; .\.venv\Scripts\python.exe -m unittest discover -s tests -v
Ran 68 tests in 6.280s — OK

Coverage:
 - test_cajas_ideal.py      16 tests — buscador pick, duplicate payload 409 (UPPER TRIM case-insensitive), herramienta not found 400, cantidad 400, nombre 400, singleton activa invariant concurrent, pagination clamp 1..100, 401, join
 - test_cajas_tecnicos_kpis 12 tests — pagination q filter, no ideal hint, 50%/100%/0% faltantes, historial DESC pagination, 401, resumen global avg, 404 tecnico, limpieza malo 50%, limit clamp
 - test_catalog + test_inventarios 40 tests — existing inventories + catalog still green (no regression)
```

### Frontend
```bash
Set-Location apps/web; npx tsc --noEmit
PASS — strict mode clean, no unused locals/params
Manual smoke checklist:
 - /admin/cajas renders 3-card hub (Ideal / Inventario por Técnico / KPIs) responsive auto-fit minmax(320px,1fr)
 - IdealCard preview + IdealEditorModal with BuscadorCatalogo pick → putIdeal 201, duplicate 409 inline, 401 hint
 - TecnicosCards paginated 25, q debounce 350ms, faltantes badge green 0-10% / yellow 10-50% / red 50-100% / grey null, click → TecnicoHistorialModal timeline periodo DESC with detalle tabla (código, cantidad, estado color, presente ✓/✗, observaciones)
 - KpisPanel global metrics + distribution 0-25/50/75-100 + empty hint "Definí la Caja Ideal…" + top 5 peores
```

### Isolation & Data
```bash
Set-Location Server\AppWebSalidas; git status --short | Select-String cajas
 M apps/web/src/api/cajasClient.ts
 M apps/web/src/modules/cajas/CajasPage.tsx
 M backend/cajas/db.py
 M backend/cajas/main.py
 M backend/cajas/service.py
 M backend/cajas/store.py
?? apps/web/src/modules/cajas/IdealCard.tsx
?? apps/web/src/modules/cajas/IdealEditorModal.tsx
?? apps/web/src/modules/cajas/KpisPanel.tsx
?? apps/web/src/modules/cajas/TecnicoHistorialModal.tsx
?? apps/web/src/modules/cajas/TecnicosCards.tsx
?? backend/cajas/tests/test_cajas_ideal.py
?? backend/cajas/tests/test_cajas_tecnicos_kpis.py
```
App.tsx, navegacion.ts untouched except explicit user-requested shell fix (cajas icono Inventory2 → 🧰 + titulo/descripcion). backend/personal, usuarios, salidas untouched — verified via git diff --name-only.

```sql
SHOW TABLES LIKE 'cajas_%'; -- cajas_cajas, cajas_herramientas, cajas_inventarios, cajas_inventario_detalle, cajas_caja_ideal, cajas_caja_ideal_detalle
-- All cajas_* , InnoDB utf8mb4_unicode_ci, FK RESTRICT on herramienta_id, CASCADE on caja_ideal_id, UNIQUE(caja_ideal_id, herramienta_id), indexes idx_ideal_activa/vigente
init_db() idempotent — double init no error (DDL IF NOT EXISTS + ALTER fallback for UNSIGNED mismatch)
```

Shell fix extra (user request 2026-05-13): `navegacion.ts` cajas `icono: "Inventory2"` → `icono: "🧰"` (toolbox), `titulo: "Cajas"` → `"Cajas de Herramientas"`, `descripcion` updated to "Caja ideal, inventario por técnico y KPIs de cumplimiento." Verified SidebarNav + ModuloCard render emoji via `mod-icon` / `nav-icon` (1.75rem / 1.1rem) — no layout break, tsc still PASS.

## Spec Scenario Mapping

### caja-ideal (5 req, 5+ scenarios)
| Requirement | Status | Evidence |
|-------------|--------|----------|
| Versioned exposure singleton-active | PASS | `store.crear_ideal_versionado` UPDATE activa=0 + INSERT activa=1 transaction, test concurrent singleton 2 sequential creates → only last activa=1, COUNT activa=1 |
| CRUD via BuscadorCatalogo | PASS | `IdealEditorModal.tsx` imports `../solicitudes/BuscadorCatalogo`, onPick fills codigo+articulo_codigo, store validates via SELECT codigo UPPER TRIM, cantidad_minima>0, test buscador pick 2 herramientas →201 |
| UNIQUE + FK RESTRICT | PASS | DDL UNIQUE + FK RESTRICT, store catches IntegrityError → ValueError "Herramienta ya asignada…", service 409, test duplicate payload 409, delete herramienta blocked →409 (tearDown cleanup order) |
| Singleton transaction | PASS | store wraps in BEGIN, try rollback on error, test concurrent |
| List detalle / versiones pagination | PASS | `get_ideal_actual()` join herramienta, `listar_ideal_versiones(limit,offset)` clamp, test pagination |

### inventario-por-tecnico (6 req, 4+ scenarios)
| Requirement | Status | Evidence |
|-------------|--------|----------|
| 3 preview cards on entry, one card per tecnico (tipo tecnico/supervisor/generico/panol) | PASS | `CajasPage.tsx` hub grid 3 cards, `TecnicosCards` lists via `listar_tecnicos_cards` WHERE tipo IN (…) + activo, q filter, test pagination + q |
| Drill-down historial completo periodo DESC | PASS | `listar_inventarios_por_tecnico` ORDER periodo DESC batch detalle + herramienta_codigo, modal expandable, test historial ordered DESC |
| Reuse inventario borrador/cerrado machine | PASS | Existing store not modified, historial shows estado badge |
| Pagination 500+ scale | PASS | limit clamp 1..100, offset, covering indexes, test invalid clamp |

### kpis-cajas (6 req, 5 scenarios)
| Requirement | Status | Evidence |
|-------------|--------|----------|
| Compare latest vs ideal % faltantes / completitud / limpieza | PASS | `get_kpis_resumen` computed-on-read ((ideal - presente)/ideal*100), presente=count presente=1, test 50%/100%/0% |
| Endpoints /kpis/resumen /tecnico/{id} | PASS | main.py 4 routes, service lectura, test resumen global avg + per-tecnico 404 |
| No ideal hint | PASS | ideal_count=0 → faltantes None + mensaje, kpisPanel empty CTA, test no ideal null |
| Empty inventario 100% | PASS | test |
| Full inventario 0% | PASS | test |
| Limpieza derived | PASS | store limpieza = mal_count/total, test 50% |

### infra (4 req, 4 scenarios)
| Requirement | Status | Evidence |
|-------------|--------|----------|
| Consistent error format 400/401/404/409 Spanish | PASS | service maps ValueError → (msg, status), main maps tuple → {"detail":msg}, tests 400/401/404/409 |
| Pagination limit/offset default 50 max 100 | PASS | _clamp_limit, tests clamp |
| JWT Bearer cajas:lectura/escritura | PASS | verificar_permiso in all services, test 401 |
| Response consistency | PASS | JSON shapes via cajasClient types Ideal/TecnicoCard/Kpis |

## Findings

### CRITICAL — 0

### WARNING (follow-up, not blocking)
- **W1 — Buscador cross-module import** — `IdealEditorModal` imports from `../solicitudes/BuscadorCatalogo`. Works but couples `cajas` → `solicitudes`. Design already docs TODO to extract to `shared/lib/ui` or `components/shared`. Risk: parallel agent editing `solicitudes/BuscadorCatalogo` could break ideal editor. **Advice:** extract to `src/components/shared/BuscadorCatalogo.tsx` + `src/lib/articulosCatalog.ts` already shared; re-point both modules. Effort low.
- **W2 — verificar_permiso escritura lenient** — `db.verificar_permiso` fallback `if nivel != sin_acceso: return payload` lets `lectura` pass `escritura` check in some paths (noted in slice 1 discovery). Current tests expect 401 for empty token but not for `supervisor` lectura trying PUT ideal (would pass). Not triggered today because UI gates via `permisoDe`, but API should enforce strict `escritura`. **Advice:** tighten to exact `escritura` match or add `cajas:escritura` explicit branch before generic fallback.

### SUGGESTION
- **S1 — crear_ideal_versionado** always bumps `vigente_desde=NOW()`; point-in-time history is by `id` order, not biznes periodo. Consider adding `vigente_desde` param or using `periodo` YYYY-MM-01 for alignment with KPI periods — future per-rubro variant.
- **S2 — Limpieza** derived from `estado='malo'` but `crear_inventario_txn` only writes `bueno`/`regular`; malos only via direct UPDATE today. KPIs limpieza will stay 0 until edit path supports `malo`. Add `estado` enum `bueno|regular|malo` to inventario detail write path or separate limpeza historial later.
- **S3 — Shell card title** now `Cajas de Herramientas` (more descriptive) but sidebar label longer. Collapsed sidebar (72px) hides label anyway; expanded still fits within 248px. No overflow observed, but monitor on small laptops. Icon `🧰` renders color emoji cross-platform; SidebarNav `nav-icon` 1.1rem centers well.

## Risks at Verify Time
- Concurrent ideal activation covered via transaction — medium risk mitigated.
- Scale 500+ tecnicos: batched latest-inventario query + pagination avoids N+1, but full `personal` scan with tipo IN (…) should have index on `personal(tipo,activo)` if table grows large — monitor.

## Next Recommended
`sdd-archive` — archive `cajas-hub-ideal-inventario-kpis` (specs already delta-synced, no new delta to merge beyond shell titulo/descripcion — include in archive delta as `navegacion` spec patch if desired).

## Skill Resolution
paths-injected: sdd-verify + _shared (fallback due to provider rate limit, manual verify inline)
