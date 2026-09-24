# Tasks: Cajas Hub Phase 2 Polish

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | 900-1100 |
| 400-line budget risk | High |
| 800-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR 1 Backend Hardening & API → PR 2 Buscador Extraction → PR 3 Frontend Visual Polish |
| Delivery strategy | auto-chain |
| Chain strategy | stacked-to-main |

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: High

### Suggested Work Units

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|------|------|-----------|----------------------|-----------------|-------------------|
| 1 | Backend security hardening, DDL limpieza/asignaciones, CRUD store/service/routes & unit tests | PR 1 | `python -m unittest backend/cajas/tests/test_cajas_limpieza.py backend/cajas/tests/test_cajas_asignaciones.py backend/cajas/tests/test_cajas_permisos.py -v` | `curl -H "Authorization: Bearer <token>" GET /api/cajas/limpieza` | Revert backend/cajas/ schema, store, service, routes, tests; DROP TABLES cajas_limpieza_historial, cajas_asignaciones |
| 2 | Relocate BuscadorCatalogo to shared components and update consumer imports atomically | PR 2 | `tsc --noEmit` | Open IdealEditorModal in web app, verify catalog search & item selection | Move BuscadorCatalogo.tsx back to modules/solicitudes/ and restore import paths |
| 3 | Frontend skeletons, empty states with CTAs, KPI charts, vertical timeline stepper & micro-transitions | PR 3 | `tsc --noEmit` | Open /admin/cajas, verify skeletons on load, empty states, charts, and historial stepper | Revert apps/web/src/modules/cajas/*, SidebarNav.tsx, ModuloCard.tsx, cajasClient.ts |

## Phase 1: Backend Security & DDL Foundation

- [x] 1.1 `backend/cajas/db.py`: Refactor `verificar_permiso` to require exact suffix `:lectura` (nivel in lectura/escritura) and `:escritura` (nivel == escritura), removing catch-all `if nivel != "sin_acceso"` [PermisosEstrictos]
- [x] 1.2 `backend/cajas/db.py`: Add idempotent DDL `cajas_limpieza_historial` (id, caja_id FK RESTRICT, tecnico_id FK RESTRICT, fecha, estado ENUM, responsable_id, observaciones) with indexes on (caja_id, fecha) and (estado, fecha) [LimpiezaAsignaciones]
- [x] 1.3 `backend/cajas/db.py`: Add idempotent DDL `cajas_asignaciones` (id, caja_id FK RESTRICT, tecnico_id FK RESTRICT, desde, hasta, activa, UNIQUE uq_caja_activa) [LimpiezaAsignaciones]

## Phase 2: Backend Store, Service & API Routes

- [x] 2.1 `backend/cajas/store.py`: Add CRUD functions for `limpieza_historial` (list, create, update, delete) and `asignaciones` (list, assign with transaction closing active, close, delete) [LimpiezaAsignaciones]
- [x] 2.2 `backend/cajas/service.py`: Add business logic for `/api/cajas/limpieza` and `/api/cajas/asignaciones` with exact permission checks and state transition validations (409 on invalid transitions) [LimpiezaAsignaciones]
- [x] 2.3 `backend/cajas/main.py`: Register routes GET/POST/PATCH/DELETE for `/api/cajas/limpieza` and `/api/cajas/asignaciones` with token auth [LimpiezaAsignaciones]
- [x] 2.4 RED Tests `backend/cajas/tests/`: Add unit tests for strict permisos rejection without suffix, limpieza CRUD & 409 non-pending delete, and asignaciones transaction closing previous active row [PermisosEstrictos, LimpiezaAsignaciones]

## Phase 3: Frontend Shared Buscador Extraction

- [ ] 3.1 Relocate file: Create `apps/web/src/components/shared/BuscadorCatalogo.tsx` (identical source) and remove `apps/web/src/modules/solicitudes/BuscadorCatalogo.tsx` [BuscadorShared]
- [ ] 3.2 Update imports: Re-point `IdealEditorModal.tsx` and all solicitudes components to `../shared/BuscadorCatalogo` and verify `tsc --noEmit` passes [BuscadorShared]

## Phase 4: Frontend Visual Polish & KPI Charts

- [ ] 4.1 `apps/web/src/api/cajasClient.ts`: Add TypeScript interfaces and API client functions for `/api/cajas/limpieza` and `/api/cajas/asignaciones` [LimpiezaAsignaciones]
- [ ] 4.2 `IdealCard.tsx`, `TecnicosCards.tsx`, `KpisPanel.tsx`: Replace plain text "Cargando..." with `KpiSkeletonCard`/`KpiSkeletonGrid` during fetch [HubVisualPolish]
- [ ] 4.3 `IdealCard.tsx`, `TecnicosCards.tsx`, `KpisPanel.tsx`: Add empty state illustrations (project emoji) with CTA buttons ("Definir Caja Ideal", "Cargar técnicos") [HubVisualPolish]
- [ ] 4.4 `KpisPanel.tsx`: Replace hand-rolled `BarList` with `KpiBarChart` for `distribucion_faltantes` and integrate `KpiDonutChart` for completitud vs faltantes [HubVisualPolish]
- [ ] 4.5 `TecnicoHistorialModal.tsx`: Restyle expandable list as vertical CSS timeline stepper using `<ol>/<li>` with colored dots and connector lines [HubVisualPolish]
- [ ] 4.6 `SidebarNav.tsx`, `ModuloCard.tsx`, `navegacion.ts`: Center icon labels, add hover micro-transitions (`translateY(-2px)` + soft shadow) on hub cards, and add TODO comments for future lucide migration [HubVisualPolish]

## Phase 5: Verification & Isolation

- [ ] 5.1 Document technician loading process via existing `/admin/personal` UI without touching `backend/personal/` code [LimpiezaAsignaciones]
- [ ] 5.2 Verification: Run `python -m unittest -v` for backend tests and `tsc --noEmit` for web frontend; verify `git diff --name-only` respects isolation (`backend/personal/` untouched) [PermisosEstrictos, LimpiezaAsignaciones, HubVisualPolish, BuscadorShared]
