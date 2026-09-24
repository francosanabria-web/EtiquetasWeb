# Proposal: Cajas Hub Phase 2 Polish

## Intent

Harden security and data integrity in Cajas Hub (shared catalog search, strict permission checks, explicit cleaning event logs, explicit caja-technician assignments) and deliver UI polish (skeletons, recharts integration, vertical timeline stepper).

## Scope

### In Scope
- Move `BuscadorCatalogo` to `src/components/shared/BuscadorCatalogo.tsx` and re-point consumer imports.
- Harden `db.verificar_permiso` in `backend/cajas` to enforce exact `:lectura`/`:escritura` matches without generic fallbacks.
- Create `cajas_limpieza_eventos` table for audit logging item cleaning events.
- Create versioned `cajas_asignaciones` table for explicit caja-technician assignments.
- Document technician loading process via existing `personal` module UI/API.
- Add `KpiSkeletonCard` loading states, empty illustrations, and modal CSS transitions across Cajas Hub cards.
- Integrate `KpiBarChart` and `KpiDonutChart` into `KpisPanel`.
- Convert `TecnicoHistorialModal` list into a vertical CSS timeline stepper.

### Out of Scope
- Lucide icon migration (retains current emoji navigation system; TODO documented).
- Per-period trend line chart (`KpiLineChart`) in KPI panel.
- QR codes, per-rubro ideal variants, or bulk technician import endpoints.
- Any modifications to `backend/personal/` source code.

## Capabilities

### New Capabilities
- `cajas-limpieza`: Audit log and tracking for item cleaning events and status transitions.
- `cajas-asignaciones`: Versioned assignments linking technicians to Cajas.

### Modified Capabilities
- `cajas-inventory`: Require strict scope matching for permissions and re-point shared catalog search component.

## Approach

1. Extract `BuscadorCatalogo.tsx` into `src/components/shared/` and update `solicitudes` and `cajas` imports atomically.
2. Refactor `backend/cajas/db.py:verificar_permiso` to require exact scope matches (`:escritura` -> level `escritura`, `:lectura` -> level `lectura` or `escritura`).
3. Execute idempotent DDL for `cajas_limpieza_eventos` and `cajas_asignaciones` with `ON DELETE RESTRICT` FKs and appropriate indexes. Add corresponding store, service, and API client routes.
4. Replace text loading states with `KpiSkeletonCard`, swap `BarList` with `KpiBarChart`/`KpiDonutChart`, and style history items into a vertical CSS timeline stepper.

## Alternatives Considered

- **Lucide icons vs Emojis**: Kept emojis to avoid extra dependencies and multi-module churn.
- **Derived cleaning vs Table**: Added `cajas_limpieza_eventos` to log audit events while keeping KPI formulas intact.
- **Singleton vs Versioned assignment**: Selected versioned assignments (`desde`/`hasta`) to preserve historical accuracy.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `backend/cajas/` | Modified | Add tables, endpoints, strict permission verification |
| `apps/web/src/components/shared/BuscadorCatalogo.tsx` | New | Shared catalog search modal |
| `apps/web/src/modules/cajas/` | Modified | Skeleton/empty states, KPI charts, timeline stepper, API client |
| `apps/web/src/modules/solicitudes/` | Modified | Update BuscadorCatalogo import path |

## File Isolation

- **Owned**: `backend/cajas/**`, `apps/web/src/modules/cajas/**`, `apps/web/src/components/shared/BuscadorCatalogo.tsx`, `apps/web/src/api/cajasClient.ts`, `apps/web/src/modules/solicitudes/` (import update only).
- **Forbidden**: `backend/personal/**` (READ-ONLY).

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Parallel edit in `solicitudes` | Low | Move file & update imports in a single atomic commit |
| Permission hardening breaking endpoints | Med | Audit call sites to ensure `:lectura`/`:escritura` suffixes |
| Foreign key restriction on technician deletion | Low | Document that assigned technicians cannot be hard deleted |

## Rollback Plan

1. Revert `backend/cajas/db.py` permission checking code.
2. Drop `cajas_limpieza_eventos` and `cajas_asignaciones` tables.
3. Revert `BuscadorCatalogo.tsx` file location and consumer import paths.

## Dependencies

- SQLite/MySQL standard DDL with `FK ON DELETE RESTRICT`.
- `recharts` and existing `KpiSkeletonCard`, `KpiBarChart`, `KpiDonutChart` components.

## Success Criteria

- [ ] `tsc --noEmit` compiles cleanly with shared `BuscadorCatalogo`.
- [ ] `backend/cajas` unit tests pass and reject unsuffixed permission checks with HTTP 401/403.
- [ ] `cajas_limpieza_eventos` and `cajas_asignaciones` CRUD endpoints pass backend unit tests.
- [ ] Cajas Hub cards display skeleton loaders during fetch and vertical timeline stepper in history modal.
