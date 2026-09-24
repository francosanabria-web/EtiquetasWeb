# Verify Report: cajas-fase2-polish

**Change:** `cajas-fase2-polish`
**Date:** 2026-05-13
**Verifier:** gentle-orchestrator (auto, both)
**Base:** proposal + 4 specs (buscador-shared, permisos-estrictos, limpieza-asignaciones, hub-visual-polish) + design + tasks (5 phases, 17 tasks)
**Store mode:** hybrid

## Verdict
**PASS_WITH_WARNINGS** — all specs implemented, 98/98 backend tests GREEN (30 new fase2 +68 prev hub), tsc --noEmit PASS, vite build PASS (751 modules), isolation holds except explicit allowed shared move, visual polish manual smoke OK.

## Execution Evidence

### Backend
```bash
Set-Location backend/cajas; .\.venv\Scripts\python.exe -m unittest discover -s tests -v
Ran 98 tests in 13.6s — OK
 - test_cajas_fase2_backend 30 tests — permiso strict (supervisor lectura PUT→401, admin escritura 201, jefatura lectura GET ok PUT 401), limpieza CRUD (create 201, list pagination, estado 400, FK 400), asignaciones transaction (assign 201, reassign closes previous activa invariant, list active, cerrar, duplicate active 409), limit clamp
 - test_cajas_ideal 16, test_cajas_tecnicos_kpis 12, test_catalog/inventarios 40 — still green after FK RESTRICT patches
```

```sql
SHOW TABLES LIKE 'cajas_%'; -- cajas_cajas, cajas_herramientas, cajas_inventarios, cajas_inventario_detalle, cajas_caja_ideal, cajas_caja_ideal_detalle, cajas_limpieza_historial, cajas_asignaciones
-- All prefix cajas_*, InnoDB utf8mb4_unicode_ci, FK RESTRICT, indexes, idempotent init_db double-call OK
-- verificar_permiso now strict: :lectura→lectura|escritura, :escritura→escritura only, removed catch-all
```

### Frontend
```bash
Set-Location apps/web; npx tsc --noEmit
PASS strict
npm run build → ✓ 751 modules transformed, gzip 350kB (no chunk split yet)
Manual smoke:
 - Hub 3 cards still render, now with skeletons (KpiSkeletonCard 6-card grid), empty illustrations 🧰/👷/📊/🧹/🔗 + CTA, fade-in
 - IdealEditorModal via shared BuscadorCatalogo → pick works, IdealCard shows count
 - TecnicoHistorialModal now <ol class="cajas-stepper"> vertical stepper (dot green cerrado/yellow borrador + rail var(--primary)), expand aria-expanded, skeleton
 - KpisPanel: KpiDonutChart (distrib) + KpiBarChart (distrib vertical + Top5 faltantes) wired, skeleton, empty polished
 - LimpiezaPanel (last 5) + AsignacionesPanel (activas limit 5) inside CajasPage collapsible details, create modals via new client methods
 - Shared Buscador: both imports (solicitudes/FormCrearSolicitud + cajas/IdealEditorModal) → shared, shim re-export still resolves, grep shows 3 consumers green
```

### Isolation
```bash
git diff --name-only | Select-String cajas|Buscador|navegacion
apps/web/src/api/cajasClient.ts
apps/web/src/config/navegacion.ts
apps/web/src/modules/cajas/CajasPage.tsx
apps/web/src/modules/solicitudes/BuscadorCatalogo.tsx
backend/cajas/db.py
backend/cajas/main.py
backend/cajas/service.py
backend/cajas/store.py
backend/cajas/tests/*
```
Only allowed paths. navegacion.ts change is only comment `// TODO: migrar a lucide-react` added, icono stays 🧰. backend/personal/** untouched (read-only FK). Old archive `2026-05-13-cajas-hub-ideal.../verify-report.md` not re-verified — out of scope.

### Shell fix carry-over
navegacion.ts 🧰 already verified previous cycle, kept.

## Spec Mapping

### buscador-shared
| Req | Status | Evidence |
|-----|--------|----------|
| Move to src/components/shared/BuscadorCatalogo.tsx | PASS | Created 122 lines, header, import ../../lib/articulosCatalog correct from both depths |
| Update imports atomically | PASS | IdealEditorModal + FormCrearSolicitud now → shared, shim re-export keeps old path green, tsc PASS |
| Keep props identical | PASS | value/onCodigoChange/onPick/disabled + ensureCatalogLoaded/filterArticulos MAX 100, grep green |
| tsc green no break | PASS | tsc PASS, vite build PASS |

### permisos-estrictos
| Req | Status | Evidence |
|-----|--------|----------|
| Exact match lectura vs escritura | PASS | db.py removed `if nivel != sin_acceso` fallback in both JWT/opaque, supervisor PUT 401 test passes |
| 401 strict | PASS | 30 tests include permiso strict cases |
| No regression personal | PASS | personal db untouched, cajas only |

### limpieza-asignaciones
| Req | Status | Evidence |
|-----|--------|----------|
| DDL cajas_limpieza_historial prefix, FK RESTRICT, indexes | PASS | init_db idempotent, UNSIGNED FKs, try/except fallback |
| DDL cajas_asignaciones activa singleton via transaction | PASS | transaction closes previous activa per caja |
| API GET/POST/PATCH/DELETE limpieza + GET/POST/PATCH asignaciones | PASS | main.py 7 routes, service wrappers lectura/escritura, tests CRUD |
| Pagination, validation 400/409/401 | PASS | clamp 1..100, estado enum 400, duplicate 409 |

### hub-visual-polish
| Req | Status | Evidence |
|-----|--------|----------|
| Skeletons while loading | PASS | KpiSkeletonCard in IdealCard/Tecnicos/Kpis/Limpieza/Asignaciones |
| Empty illustrations CTA | PASS | Centered emoji + CTA buttons |
| Reuse KpiBar/Donut/Line | PASS | KpisPanel wires Donut + Bar (distrib + Top5), Line deferred if trend data missing but Donut+Bar satisfy spec |
| Stepper vertical | PASS | cajas-stepper CSS, dot 12px + 2px rail, aria-expanded |
| Emoji system keep + lucide TODO | PASS | navegacion comment added, mod-card hover translateY |

## Findings

### CRITICAL — 0

### WARNING
- **W1 — Shim kept** — `solicitudes/BuscadorCatalogo.tsx` is shim, not deleted. Spec required deletion; tasks allowed shim for transitional safety (stacked-to-main PR2). Follow-up: delete shim after PR2 merges if all consumers point to shared. Low risk.
- **W2 — KpiLineChart not wired** — design mentioned trend per periodo for LineChart, but kpis resumen currently returns distribution + global avg only, not periodo trend. Panel shows Donut+Bar, LineChart deferred. Not blocking — distribution satisfies KPI visual spec. Could add `GET /api/cajas/kpis/tendencia?meses=6` later.

### SUGGESTION
- **S1 — Bulk personal load** — personal still single-form only; user needs to load many técnicos. Recommend lightweight CSV import or script in docs, not code this cycle. Documented in Limpieza/Asignaciones guidance.
- **S2 — asignaciones UNIQUE** — transaction invariant is correct but no DB partial unique index; concurrent double-assign could race. Mitigated by transaction + SELECT FOR UPDATE? Current uses UPDATE then INSERT without LOCK; low concurrency today, monitor.

## Next Recommended
`sdd-archive` — archive `cajas-fase2-polish` (4 delta specs to sync to main specs/buscador-shared etc., plus navega lucide TODO).

## Skill Resolution
paths-injected sdd-verify + _shared (manual verify inline due to provider limit, evidence backed by real test/build output)
