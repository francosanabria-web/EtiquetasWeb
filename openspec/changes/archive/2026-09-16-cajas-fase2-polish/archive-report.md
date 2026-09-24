# Archive Report: cajas-fase2-polish

**Change:** `cajas-fase2-polish`
**Archived:** 2026-05-13 (filesystem 2026-09-16 due to prior hub archive date collision)
**Artifact Store Mode:** hybrid (openspec + engram)

## Final State Summary

### Verification Verdict
**PASS_WITH_WARNINGS** — all 4 specs implemented, 98/98 backend tests green, tsc --noEmit PASS, vite build PASS (751 modules), isolation holds with explicit shim, visual polish manual smoke OK.

### Warnings (follow-up, not blockers)
- **W1 — Shim kept** — `solicitudes/BuscadorCatalogo.tsx` is shim, not deleted. Spec required deletion; tasks allowed shim for transitional safety (stacked-to-main PR2). Delete shim after PR2 merges.
- **W2 — KpiLineChart not wired** — kpis resumen returns distribution + global avg, not periodo trend. Panel shows Donut+Bar, LineChart deferred. Add `GET /api/cajas/kpis/tendencia` later.

### Suggestions (future work)
- **S1 — Bulk personal load** — personal still single-form only. Docs, not code, this cycle. User guidance provided: `/admin/personal` → `+ Nuevo Personal` → `Tipo=técnico`.
- **S2 — asignaciones UNIQUE** — transaction invariant correct but no DB partial unique; low concurrency today, consider SELECT FOR UPDATE if race observed.

### Specs Synced (openspec → main specs)
| Domain | Action | Details |
|--------|--------|---------|
| buscador-shared | Created | Full spec copied from delta, no existing main spec |
| permisos-estrictos | Created | Full spec copied |
| limpieza-asignaciones | Created | Full spec copied (cajas_limpieza_historial + cajas_asignaciones) |
| hub-visual-polish | Created | Full spec copied |

All verified byte-identical via manual diff (specs already present in openspec/specs/ post-archive). Previous hub specs (caja-ideal, inventario-por-tecnico, kpis-cajas, infra) preserved, not overwritten.

### Archive Contents
- proposal.md ✓
- exploration.md ✓
- specs/ ✓ (4 domains)
- design.md ✓
- tasks.md ✓ (17 tasks, 5 phases, all 17 marked complete per verify)
- verify-report.md ✓

### Source of Truth Updated
The following main specs now reflect new behavior:
- openspec/specs/buscador-shared/spec.md
- openspec/specs/permisos-estrictos/spec.md
- openspec/specs/limpieza-asignaciones/spec.md
- openspec/specs/hub-visual-polish/spec.md
Plus previous: caja-ideal, inventario-por-tecnico, kpis-cajas, infra (from 2026-05-13 hub)

### Isolation Verified
git status confirms changes only in:
- backend/cajas/** (db.py strict permiso + 2 DDL, store.py +380, service.py +150, main.py +7 routes, tests/test_cajas_fase2_backend.py + test patches)
- apps/web/src/components/shared/BuscadorCatalogo.tsx (new 122 lines)
- apps/web/src/modules/solicitudes/BuscadorCatalogo.tsx (shim 3 lines)
- apps/web/src/modules/solicitudes/FormCrearSolicitud.tsx (import rewire 1 line)
- apps/web/src/modules/cajas/** (IdealCard/TecnicosCards/KpisPanel/TecnicoHistorialModal skeletons/stepper/charts + LimpiezaPanel + AsignacionesPanel + CajasPage collapsible, index.css stepper)
- apps/web/src/api/cajasClient.ts (+90 limpieza/asignaciones)
- apps/web/src/config/navegacion.ts (lucide TODO comment, icono 🧰 kept)
backend/personal/** untouched (read-only FK). No App.tsx change.

### Rollback Boundaries
- DB: `DROP TABLE IF EXISTS cajas_asignaciones, cajas_limpieza_historial` (order detalle first, preserves caja_ideal etc.)
- Revert permiso: restore `if nivel != "sin_acceso"` fallback in db.py (both JWT/opaque)
- Revert buscador: move BuscadorCatalogo back to modules/solicitudes, restore imports, delete shared + shim
- Revert visual: revert cajas/* panels + index.css stepper + cajasClient types
- Revert navegacion comment

### Tests & Build
- `python -m unittest discover -s tests -v` → 98/98 OK (30 new +68 prev)
- `tsc --noEmit` → PASS
- `vite build` → 751 modules, 13s

### Personal Technicians Load — Guidance (requested)
Personal already supports `tipo=técnico` via existing `PersonalPage.tsx → + Nuevo Personal → Tipo`. No code change needed this cycle. To start cajas, go to `/admin/personal`, create each técnico: Nombre*, Tipo=técnico (or supervisor/generico/panol), Legajo/Email/Área opcional, Activo=Sí. They appear instantly in TecnicosCards/KPIs/Asignaciones dropdowns. For bulk, repeat form or request CSV import script (deferred).

### Next Recommended Steps
1. Address W1 shim deletion after PR2 merges.
2. Consider tendencia endpoint for LineChart.
3. Next SDD could be per-rubro ideal variants or QR/mobile if needed.

### Skill Resolution
paths-injected sdd-archive + _shared; manual archive-report due to provider garble, preserved state per verify-report.

