# Design: Cajas Hub Phase 2 Polish

## Technical Approach

Implement four functional hardenings and four visual polish items as specified in the proposal. Extract `BuscadorCatalogo` to a shared component, harden permission verification to exact suffix matching, add audit tables for cleaning events and technician assignments, and enhance UI with skeletons, empty states, charts, and a vertical timeline stepper. All changes respect isolation constraints: backend/cajas/* and frontend cajas/modules/* only; backend/personal/* remains read-only.

## Architecture Decisions

### Decision: BuscadorCatalogo Shared Extraction

**Choice**: Move `BuscadorCatalogo.tsx` from `modules/solicitudes/` to `components/shared/` and update imports in `IdealEditorModal.tsx` and solicitudes-internal files atomically. No re-export shim; update all consumers in one commit.

**Alternatives considered**: 
- Re-export shim in solicitudes (leaves dual entry points)
- Copy instead of move (creates duplication)

**Rationale**: Atomic import update keeps tsc green across modules, avoids duplication, and follows the exploration's recommendation (A1). The component is self-contained with identical props API.

### Decision: Exact Suffix Permission Matching

**Choice**: Refactor `backend/cajas/db.py:verificar_permiso` to remove the generic `nivel != "sin_acceso"` catch-all and use explicit suffix checks:
- `:lectura` → nivel in (`lectura`, `escritura`)
- `:escritura` → nivel == `escritura`
- Else → None

**Alternatives considered**:
- Mirror fix in personal db.py (violates isolation constraint)
- Deprecate catch-all with logging (keeps security hole)

**Rationale**: Closes the permission vulnerability while keeping personal behavior unchanged. Exploration confirms all cajas call sites use suffixed strings.

### Decision: Cleaning Event Table

**Choice**: Create idempotent `cajas_limpieza_historial` table with columns: id, caja_id, tecnico_id, fecha, estado, responsable_id, observaciones, plus indexes on (caja_id,fecha) and (estado,fecha). Use `ON DELETE RESTRICT` FKs to cajas_cajas and personal.

**Alternatives considered**:
- Add nullable inventario_detalle_id (not needed for audit)
- Replace derived limpieza score (changes KPI semantics)

**Rationale**: Additive audit trail without altering existing KPI calculations. Matches exploration recommendation (C1).

### Decision: Versioned Technician Assignments

**Choice**: Create idempotent `cajas_asignaciones` table with columns: id, caja_id, tecnico_id, desde, hasta, activa, plus indexes on (caja_id), (tecnico_id), (activa) and unique constraint on (caja_id, activa) to enforce one active assignment per caja. Use `ON DELETE RESTRICT` FKs.

**Alternatives considered**:
- Singleton assignment (loses history)
- Implicit derivation from latest inventario (cannot answer "should have")

**Rationale**: Preserves full history, matches existing versioned pattern (caja_ideal), and supports reassignment workflow. Exploration recommends D1.

### Decision: Frontend Shared Buscador Implementation

**Choice**: Move file to `src/components/shared/BuscadorCatalogo.tsx` and update imports in `modules/cajas/IdealEditorModal.tsx` and any solicitudes-consuming files in the same commit. No runtime shim.

**Alternatives considered**:
- Re-export shim at old location (temporary dual source)
- Keep in solicitudes with relative import (doesn't address coupling)

**Rationale**: Eliminates coupling risk with zero runtime overhead. The exploration confirms styling remains intact due to shared CSS.

### Decision: Loading States with KpiSkeletonCard

**Choice**: Replace plain "Cargando…" text in IdealCard, TecnicosCards, and KpisPanel with `KpiSkeletonCard` (or `KpiSkeletonGrid` for multi-card loading) during data fetch.

**Alternatives considered**:
- Custom skeleton per component (duplication)
- Keep text states (poor UX)

**Rationale**: Reuses existing component, provides consistent placeholder animation, and matches the spec's requirement for skeleton loading states.

### Decision: Empty States with Illustration + CTA

**Choice**: Show illustration (using project emoji system) + primary CTA button when:
- IdealCard: no ideal defined → "Definir Caja Ideal"
- TecnicosCards: empty list → "Cargar técnicos"
- KpisPanel: no ideal or no data → "Definir Caja Ideal"

**Alternatives considered**:
- Text-only hints (lower engagement)
- Modal dialogs (heavier weight)

**Rationale**: Follows existing pattern in KpisPanel, uses zero new dependencies, and guides users to resolution paths.

### Decision: KPI Charts Reuse

**Choice**: Replace hand-rolled `BarList` in KpisPanel with `KpiBarChart` for `distribucion_faltantes` and `KpiDonutChart` for completitud vs faltantes. Defer `KpiLineChart` pending backend trend data.

**Alternatives considered**:
- Keep BarList (inconsistent with recharts usage)
- Add all three charts now (requires backend trend)

**Rationale**: Leverages existing recharts dependencies, improves accessibility to SVG output, and matches spec's lean approach (trend deferred).

### Decision: Vertical Timeline Stepper for Historial

**Choice**: Restyle `TecnicoHistorialModal` expandable list as vertical CSS timeline using `<ol>/<li>` with left rail, colored dots (green for borrador, red for cerrado), and connector lines. Reuse `sol-estado` badge classes.

**Alternatives considered**:
- Horizontal timeline (more vertical space)
- Third-party timeline library (new dependency)

**Rationale**: CSS-only, accessible, reuses existing badge semantics, and matches exploration's E4 recommendation.

### Decision: Hover Transitions and Icon Centering

**Choice**: Add `transition: transform 0.2s ease, box-shadow 0.2s ease` and `transform: translateY(-2px)` on hub card hover. Center icons in `SidebarNav` and `ModuloCard`. Add TODO comment in `navegacion.ts` for lucide migration.

**Alternatives considered**:
- No hover feedback (static feel)
- Icon migration now (out of scope)

**Rationale**: Improves perceived responsiveness with minimal CSS, centers existing emoji system, and documents future work.

### Decision: Cross-cutting Idempotency and Transactions

**Choice**: 
- Table creation uses `IF NOT EXISTS` and includes fallback ALTER for FK mismatches.
- Asignaciones POST uses transaction to close existing active assignment before inserting new one.
- All FKs use `ON DELETE RESTRICT` to preserve referential integrity.
- Buscador extraction coordinates import updates atomically.

**Alternatives considered**:
- Drop/create tables (not idempotent)
- Application-level unico activo check (race condition risk)

**Rationale**: Matches patterns from existing ideal table initialization, prevents constraint violations, and ensures safe concurrent operations.

## Data Flow

### Permission Verification
```
Client → GET/POST /api/cajas/* (with Bearer token)
 → Service → db.verificar_permiso(token, permiso_requerido)
   → JWT/sesion opaca validation → exact suffix check → payload/None
 → Service → 401/403 if None, else proceed
```

### Limpieza Event Lifecycle
```
1. Creation: POST /api/cajas/limpieza {caja_id, tecnico_id, estado?, observaciones?}
   → Service → insert into cajas_limpieza_historial (fecha DEFAULT CURRENT_TIMESTAMP)
   → Return created event with id

2. Update: PATCH /api/cajas/limpieza/{id} {estado, observaciones?}
   → Service → validate estado transition (pendiente → realizada/vencida)
   → Update fila, return updated event

3. Deletion: DELETE /api/cajas/limpieza/{id}
   → Service → only allow if estado = pendiente
   → Soft delete not supported; hard delete removes audit trail (by design)

4. Listing: GET /api/cajas/limpieza?filters&limit&offset
   → Service → SELECT with filters, ORDER BY fecha DESC, paginate
```

### Asignaciones Assignment Workflow
```
Assignment (POST /api/cajas/asignaciones {caja_id, tecnico_id, desde}):
1. Begin transaction
2. IF active assignment exists for caja_id (hasta IS NULL, activa=1):
   → UPDATE that row SET hasta = NOW, activa = 0
3. INSERT new row (caja_id, tecnico_id, desde, hasta=NULL, activa=1)
4. Commit
→ Returns new assignment record

Reassignment closes previous active assignment automatically.
```

### Buscador Data Flow (Frontend Only)
```
User types in search input → onCodigoChange updates value and calls onPick
 onPick selects articulo → sets input value to articulo.codigo
 Component ensures catalog loaded via ensureCatalogLoaded() (memoized)
 filterArticulos splits query on whitespace, matches codigo/desc/alias, caps at 100
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `backend/cajas/db.py` | Modify | Refactor verificar_permiso to exact suffix matching; add idempotent DDL for limpieza_historial and asignaciones tables with FKs and indexes |
| `backend/cajas/store.py` | Modify | Add CRUD functions for limpieza_historial and asignaciones; include transaction for asignaciones activation |
| `backend/cajas/service.py` | Modify | Add business logic layer for new endpoints with auth checks and error mapping |
| `backend/cajas/main.py` | Modify | Add API routes: /api/cajas/limpieza (GET,POST,PATCH,DELETE) and /api/cajas/asignaciones (GET,POST,PATCH,DELETE) |
| `backend/cajas/tests/` | Create | New test files for limpieza and asignaciones CRUD and transactional activation |
| `apps/web/src/components/shared/BuscadorCatalogo.tsx` | Create | Move from modules/solicitudes/; identical source |
| `apps/web/src/modules/solicitudes/BuscadorCatalogo.tsx` | Delete | Remove duplicate after import update |
| `apps/web/src/modules/cajas/IdealCard.tsx` | Modify | Replace "Cargando…" with KpiSkeletonCard; empty state with illustration + CTA |
| `apps/web/src/modules/cajas/TecnicosCards.tsx` | Modify | Replace "Cargando…" with KpiSkeletonGrid; empty state with illustration + CTA |
| `apps/web/src/modules/cajas/KpisPanel.tsx` | Modify | Replace BarList with KpiBarChart/KpiDonutChart; add skeletons; empty state illustration + CTA |
| `apps/web/src/modules/cajas/TecnicoHistorialModal.tsx` | Modify | Restyle as vertical CSS timeline stepper; reuse sol-estado badges |
| `apps/web/src/components/SidebarNav.tsx` | Modify | Ensure icon labels center correctly (no layout shift) |
| `apps/web/src/components/ModuloCard.tsx` | Modify | Center icon properly; add TODO comment for lucide migration |
| `apps/web/src/config/navegacion.ts` | Modify | Add TODO comment documenting lucide migration intention |
| `apps/web/src/api/cajasClient.ts` | Modify | Add TypeScript types and client functions for limpieza and asignaciones endpoints |

## Interfaces / Contracts

### Database Schema (db.py)
```sql
-- cajas_limpieza_historial table
CREATE TABLE IF NOT EXISTS cajas_limpieza_historial (
    id INT AUTO_INCREMENT PRIMARY KEY,
    caja_id INT NOT NULL,
    tecnico_id INT NOT NULL,
    fecha DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    estado ENUM('pendiente','realizada','vencida') NOT NULL DEFAULT 'pendiente',
    responsable_id INT NULL,
    observaciones TEXT NULL,
    INDEX idx_limpieza_caja_fecha (caja_id, fecha),
    INDEX idx_limpieza_estado_fecha (estado, fecha),
    CONSTRAINT fk_limpieza_caja FOREIGN KEY (caja_id) REFERENCES cajas_cajas(id) ON DELETE RESTRICT,
    CONSTRAINT fk_limpieza_tec FOREIGN KEY (tecnico_id) REFERENCES personal(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- cajas_asignaciones table
CREATE TABLE IF NOT EXISTS cajas_asignaciones (
    id INT AUTO_INCREMENT PRIMARY KEY,
    caja_id INT NOT NULL,
    tecnico_id INT NOT NULL,
    desde DATE NOT NULL,
    hasta DATE NULL,
    activa TINYINT(1) NOT NULL DEFAULT 1,
    creado_en DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_asig_caja (caja_id),
    INDEX idx_asig_tecnico (tecnico_id),
    INDEX idx_asig_activa (activa),
    UNIQUE KEY uq_caja_activa (caja_id, activa),
    CONSTRAINT fk_asig_caja FOREIGN KEY (caja_id) REFERENCES cajas_cajas(id) ON DELETE RESTRICT,
    CONSTRAINT fk_asig_tec FOREIGN KEY (tecnico_id) REFERENCES personal(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

### API Contracts
#### Limpieza
- **GET /api/cajas/limpieza**
  - Query: caja_id?, tecnico_id?, estado?, limit?, offset?
  - Response: `{ items: LimpiezaEvent[], total: number }`
  - Errors: 401 (unauthenticated), 403 (insufficient permiso)
- **POST /api/cajas/limpieza**
  - Body: `{ caja_id, tecnico_id, estado?, responsable_id?, observaciones? }`
  - Response: Created event with id, fecha
  - Errors: 400 (missing required), 401/403, 409 (if estado invalid for transition)
- **PATCH /api/cajas/limpieza/{id}**
  - Body: `{ estado?, observaciones? }`
  - Response: Updated event
  - Errors: 404 (not found), 401/403, 409 (if estado not pending or invalid transition)
- **DELETE /api/cajas/limpieza/{id}**
  - Response: 204 on success
  - Errors: 404, 401/403, 409 (if estado not pending)

#### Asignaciones
- **GET /api/cajas/asignaciones**
  - Query: caja_id?, tecnico_id?, activa?, limit?, offset?
  - Response: `{ items: Asignacion[], total: number }`
- **POST /api/cajas/asignaciones**
  - Body: `{ caja_id, tecnico_id, desde }`
  - Response: New assignment record
  - Errors: 400, 401/403, 409 (active assignment exists for same caja-tecnico)
- **PATCH /api/cajas/asignaciones/{id}/cerrar**
  - Body: `{ hasta }` (defaults to NOW)
  - Response: Updated assignment with hasta, activa=0
  - Errors: 404, 401/403, 409 (if already inactive)
- **DELETE /api/cajas/asignaciones/{id}**
  - Response: 204
  - Errors: 404, 401/403, 409 (if activa=1)

### Frontend Props
- `KpiSkeletonCard`: `{ lines?: number; height?: number }`
- `KpiBarChart`: `{ data: BarItem[]; color: string; layout?: 'vertical'|'horizontal'; height?: number; pesos?: boolean }`
- `KpiDonutChart`: `{ data: DonutItem[]; colors: string[]; valueFormatter?: (v)=>string; height?: number }`

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit | Table constraints (FK RESTRICT, UNIQUE), transactional activation logic | Direct store.py calls with unittest, mirroring existing test_inventarios.py patterns |
| Integration | API endpoint validation, auth, error codes (401/403/404/409), pagination | TestClient with full request/response cycle; test edge cases (duplicate assignment, non-potent deletion) |
| Backend | Ideal activation singleton invariant (existing), new table idempotency, FK enforcement | Real MariaDB connection with cleanup; test concurrent asignaciones assignments |
| Frontend | Component rendering, loading states, empty states, chart display, timeline stepper interactions | Manual testing + `tsc --noEmit` (no frontend test runner); verify skeleton appears during fetch, charts render with sample data |
| Cross-service | BuscadorCatalogo integration, Firestore catalog search | Verify catalog load and filterArticulos usage in IdealEditorModal after move |

## Threat Matrix

N/A — no routing, shell, subprocess, VCS/PR automation, executable-file classification, or process-integration boundary.

## Migration / Rollout

**Migration**: No data migration required. New tables are created idle. Existing funcionalidad remains unchanged.

**Rollback**:
1. Revert `backend/cajas/db.py` permission checking code to previous lenient version.
2. Drop `cajas_limpieza_historial` and `cajas_asignaciones` tables.
3. Revert `BuscadorCatalogo.tsx` file location and restore duplicate in solicitudes (or update imports back to relative path).
4. Revert frontend changes to loading states, empty states, charts, and timeline stepper.
5. Remove API client functions for limpieza and asignaciones.

## Open Questions

- [ ] Should `responsable_id` in limpieza_historial default to the authenticated user's ID if omitted?
- [ ] Should the asignaciones activation transaction use database-level constraint (partial unique index) instead of application logic?
- [ ] Whether KpisPanel needs a `KpiSkeletonGrid` for multi-card loading state or individual skeletons suffice.