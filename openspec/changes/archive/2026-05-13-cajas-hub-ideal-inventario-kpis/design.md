# Design: Cajas Hub with Ideal Toolkit, Technician Inventories and KPIs

## Technical Approach

Create a versioned Caja Ideal baseline with singleton-active invariant, per-technician inventory cards with history drill-down, and computed-on-read KPIs comparing technician inventories against the active ideal. Backend uses MariaDB with cajas_* prefixed tables, frontend reuses BuscadorCatalogo for catalog search, all new endpoints under /api/cajas/* with JWT auth and limit/offset pagination.

## Architecture Decisions

### Decision: Versioned Caja Ideal with Singleton-Active Invariant

**Choice**: Use versioned table `cajas_caja_ideal` with `activa` flag and transactional activation (`UPDATE ... SET activa=0; INSERT ... activa=1`) maintaining exactly one active version.

**Alternatives considered**: 
- Singleton row (one active row only) - rejected for lack of historical KPI comparability
- Separate history table - rejected for increased complexity without benefit

**Rationale**: Versioned approach supports point-in-time KPI comparisons and future per-rubro variants while maintaining lean implementation. Transactional activation prevents race conditions during concurrent edits.

### Decision: Computed-on-Read KPIs with Server-Side Pagination

**Choice**: Calculate KPIs (% faltantes, % completitud, limpieza score) via SQL joins at request time with proper indexing.

**Alternatives considered**:
- Persisted KPI snapshots - rejected due to write amplification and cache staleness risks
- Client-side computation - rejected for N+1 problems at scale (500+ técnicos)

**Rationale**: Computed-on-read ensures consistency without write-path cost. Server-side pagination and covering indexes prevent N+1 issues. Limpieza score derived from `cajas_inventario_detalle.estado` avoids new table.

### Decision: Reuse Existing BuscadorCatalogo with Cross-Module Import

**Choice**: Import `BuscadorCatalogo` directly from `modules/solicitudes` for IdealEditorModal.

**Alternatives considered**:
- Extract to shared `lib/ui` - rejected to avoid touching solicitudes module (coordination risk)
- Duplicate minimal wrapper - rejected for maintenance overhead

**Rationale**: Short-term acceptable with TODO comment to extract later. Component is self-contained with props interface, making future extraction mechanical. Avoids coordination with parallel agent modifying solicitudes.

### Decision: Hub Page with Three Cards on Single Route

**Choice**: Keep `/admin/cajas` as single route rendering HubPage with three cards (Ideal, Tecnicos, KPIs).

**Alternatives considered**:
- Nested routes (`/admin/cajas/{ideal,tecnicos,kpis}`) - rejected to avoid touching shared `App.tsx`/`navegacion.ts`

**Rationale**: Prevents parallel agent collisions on shared navigation files. Component structure designed for future promotion to nested routes.

## Data Flow

### Ideal Activation Transaction
```
User → PUT /api/cajas/ideal → Service 
  → Store: UPDATE cajas_caja_ideal SET activa=0 
  → Store: INSERT cajas_caja_ideal (activa=1, ...) 
  → Store: INSERT cajas_caja_ideal_detalle 
  → Commit → 201 Created
```

### KPI Computation Flow
```
User → GET /api/cajas/kpis/resumen → Service
  → Store: JOIN latest inventario per técnico vs active ideal_detalle
  → Compute: % faltantes = (ideal_count - presente_count)/ideal_count*100
  → Compute: % completitud = presente_count/ideal_count*100
  → Compute: limpieza score from estado='malo' count
  → Return aggregated results
```

### Tecnico Cards with History
```
User → GET /api/cajas/tecnicos-cards → Service
  → Store: SELECT técnicos with tipo filter + pagination
  → For each: JOIN latest inventario + ideal_detalle for % faltantes
  → Return paginated list
User → Click card → GET /api/cajas/tecnicos/{id}/inventarios
  → Store: SELECT inventarios for tecnico ordered by periodo DESC
  → Return full history with detalle
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `backend/cajas/db.py` | Modify | Add `CREATE TABLE IF NOT EXISTS` for `cajas_caja_ideal` and `cajas_caja_ideal_detalle` |
| `backend/cajas/store.py` | Modify | Add query layer for ideal CRUD, technician cards, KPI aggregation, inventory history |
| `backend/cajas/service.py` | Modify | Add business logic layer with auth checks and error mapping for new endpoints |
| `backend/cajas/main.py` | Modify | Add new API routes under `/api/cajas/ideal`, `/api/cajas/tecnicos-cards`, `/api/cajas/kpis/*` |
| `backend/cajas/tests/` | Create | New test file `test_cajas_ideal.py` mirroring `test_inventarios.py` pattern |
| `apps/web/src/modules/cajas/` | Create | New components: `IdealCard.tsx`, `IdealEditorModal.tsx`, `TecnicosCards.tsx`, `TecnicoHistorialModal.tsx`, `KpisPanel.tsx` |
| `apps/web/src/modules/cajas/CajasPage.tsx` | Modify | Refactor into `HubPage.tsx` (keep as CajasPage) with 3-card grid layout |
| `apps/web/src/api/cajasClient.ts` | Modify | Add client functions: `getIdeal`, `putIdeal`, `getTecnicosCards`, `getTecnicoHistorial`, `getKpisResumen` |
| `apps/web/src/lib/articulosCatalog.ts` | Modify | Export `getCatalogFromMemory` for direct cache access in editor |

## Interfaces / Contracts

### Database Schema (db.py)
```sql
-- cajas_caja_ideal table
CREATE TABLE IF NOT EXISTS cajas_caja_ideal (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    descripcion TEXT NULL,
    activa TINYINT(1) NOT NULL DEFAULT 0,
    vigente_desde DATETIME NOT NULL,
    creado_por INT NULL,  -- FK personal.id (read-only JOIN)
    creado_en DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_ideal_activa (activa),
    INDEX idx_ideal_vigente (vigente_desde)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- cajas_caja_ideal_detalle table
CREATE TABLE IF NOT EXISTS cajas_caja_ideal_detalle (
    id INT AUTO_INCREMENT PRIMARY KEY,
    caja_ideal_id INT NOT NULL,
    herramienta_id INT NOT NULL,
    cantidad_minima INT NOT NULL DEFAULT 1,
    articulo_codigo VARCHAR(100) NULL,  -- Denormalized for display
    UNIQUE KEY uq_ideal_herramienta (caja_ideal_id, herramienta_id),
    CONSTRAINT fk_ideal_cab FOREIGN KEY (caja_ideal_id) REFERENCES cajas_caja_ideal(id) ON DELETE CASCADE,
    CONSTRAINT fk_ideal_herr FOREIGN KEY (herramienta_id) REFERENCES cajas_herramientas(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

### API Contracts
```typescript
// GET /api/cajas/ideal
Response: {
  id: number,
  nombre: string,
  descripcion: string | null,
  activa: boolean,
  vigente_desde: string (ISO datetime),
  creado_por: number | null,
  creado_en: string (ISO datetime),
  herramientas: Array<{
    id: number,
    codigo: string,
    descripcion: string | null,
    cantidad_minima: number,
    articulo_codigo: string | null
  }>
}

// PUT /api/cajas/ideal
Request: {
  nombre: string,
  descripcion: string | null,
  detalle: Array<{
    herramienta_codigo: string,
    cantidad_minima: number,
    articulo_codigo: string | null
  }>
}
Response: Same as GET ideal

// GET /api/cajas/tecnicos-cards
Response: {
  items: Array<{
    tecnico_id: number,
    tecnico_nombre: string,
    caja_codigo: string | null,
    ultima_fecha: string | null,
    faltantes_pct: number,
    ultimo_estado: 'borrador' | 'cerrado' | null
  }>,
  total: number
}

// GET /api/cajas/tecnicos/{tecnico_id}/inventarios
Response: Array<Inventario> (existing type from cajasClient.ts)

// GET /api/cajas/kpis/resumen
Response: {
  tecnicos: Array<{
    tecnico_id: number,
    tecnico_nombre: string,
    faltantes_pct: number,
    completitud_pct: number,
    limpieza_score: number  // lower = better
  }>,
  global: {
    promedio_faltantes_pct: number,
    promedio_completitud_pct: number,
    total_tecnicos: number
  }
}
```

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit | Database constraints (UNIQUE, FK RESTRICT), transactional activation | Direct store.py calls with TestClient, mirroring test_inventarios.py |
| Integration | API endpoint validation, auth, error codes | TestClient with full request/response cycle, 401/404/409 cases |
| Backend | Ideal activation singleton invariant, KPI computation accuracy | Real MariaDB connection with cleanup, edge cases (no ideal, empty/full inventario) |
| Frontend | Component rendering, user interactions, state updates | Manual testing + tsc --noEmit (no frontend test runner) |
| Cross-service | BuscadorCatalogo integration, Firestore catalog search | Verify catalog load and filterArticulos usage in IdealEditorModal |

## Threat Matrix

N/A — no routing, shell, subprocess, VCS/PR automation, executable-file classification, or process-integration boundary.

## Migration / Rollout

**Migration**: No data migration required. New tables are created idle.

**Rollout**: Feature flag not needed. Change is additive; existing cajas_* tables unaffected.

**Rollback**: 
1. Revert backend and frontend deployments
2. Execute SQL: `DROP TABLE IF EXISTS cajas_caja_ideal_detalle, cajas_caja_ideal;`
3. Preserves existing `cajas_cajas`, `cajas_herramientas`, `cajas_inventarios`, `cajas_inventario_detalle`

## Open Questions

- [ ] Whether to store `creado_por` as FK to personal.id or denormalize nombre (currently NULLable FK)
- [ ] Default page size for technician cards endpoint (proposing 50 to match existing patterns)
- [ ] Whether KPI resumen endpoint should support filtering by periodo parameter (deferred to future)

## Next Step
Ready for tasks (sdd-tasks).