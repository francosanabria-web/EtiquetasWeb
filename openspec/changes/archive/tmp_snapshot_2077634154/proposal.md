# Proposal: Cajas Hub with Ideal Toolkit, Technician Inventories and KPIs

## Intent
Transform `/admin/cajas` from flat data tables into an operational hub featuring three core cards: canonical "Caja Ideal" baseline, per-technician inventory cards with full history drill-down, and compliance KPIs.

## Scope

### In Scope
- **Card A (Caja Ideal)**: Versioned baseline toolkit editor with embedded catalog search (`BuscadorCatalogo.tsx` over Firestore `articulos`).
- **Card B (Inventario por Técnico)**: Per-technician cards displaying current status, with modal drill-down into full history (delivered, renewed, bad state).
- **Card C (KPIs)**: Indicators comparing technician boxes against active Caja Ideal (% missing, cleaning compliance).
- **Backend Schema & API**: New `cajas_caja_ideal` + `cajas_caja_ideal_detalle` tables (`cajas_*` prefix, InnoDB utf8mb4_unicode_ci, FK RESTRICT, pagination, indexes).

### Out of Scope
- Modifying or duplicating `personal` data (read-only JOIN on `personal.id`).
- Persisted KPI snapshots or per-rubro ideal variants (deferred to future iterations).
- Nested router changes under `/admin/cajas/*` (slice 1 uses single route hub).

### File Ownership & Isolation
| File / Path | Status | Role |
| --- | --- | --- |
| `backend/cajas/db.py` | Owned | DDL for `cajas_caja_ideal` tables |
| `backend/cajas/{store,service,main}.py` | Owned | Endpoints `/api/cajas/ideal`, `/api/cajas/tecnicos-cards`, `/api/cajas/kpis` |
| `backend/cajas/tests/` | Owned | Integration tests for new endpoints |
| `apps/web/src/modules/cajas/*` | Owned | Hub page, cards, editor modal, history modal, KPI panel |
| `apps/web/src/api/cajasClient.ts` | Owned | API client integration |
| `backend/{personal,usuarios,salidas}` | Forbidden | Read-only JOIN on `personal.id` |
| `apps/web/src/{App.tsx, navegacion.ts}` | Forbidden | Untouched (preserves single route `/admin/cajas`) |

## Capabilities

### New Capabilities
- `cajas-hub-ideal-inventario-kpis`: Operational hub with versioned Caja Ideal editor, per-technician inventory history cards, and compliance KPIs.

### Modified Capabilities
- None

## Approach
1. **Single Route Hub**: Renders `/admin/cajas` with 3 preview cards.
2. **Versioned Ideal Toolkit**: Transactional active flag reset (`UPDATE ... SET activa=0; INSERT ... activa=1`) maintaining singleton-active invariant.
3. **Computed-On-Read KPIs**: Fast SQL aggregations joining active ideal vs latest inventory per technician with server-side pagination.
4. **Catalog Search Reuse**: Uses `BuscadorCatalogo.tsx` with cached `articulosCatalog.ts` over Firestore `articulos`.

## Alternatives Considered
- **Nested routes vs Single route**: Single route chosen to prevent parallel agent collisions on shared `App.tsx`/`navegacion.ts`.
- **Singleton row vs Versioned ideal**: Versioned chosen for point-in-time historical KPI comparability.
- **Persisted snapshots vs Computed KPIs**: Computed-on-read chosen to eliminate write amplification and stale cache risk.

## Affected Areas
| Area | Impact | Description |
| --- | --- | --- |
| `backend/cajas/db.py` | Modified | Add `cajas_caja_ideal` and `cajas_caja_ideal_detalle` tables |
| `backend/cajas/store.py` | Modified | Ideal CRUD, technician cards pagination, KPI aggregation queries |
| `backend/cajas/service.py` | Modified | Business logic, `cajas:lectura|escritura` authorization, transactions |
| `backend/cajas/main.py` | Modified | REST API routes under `/api/cajas/*` |
| `apps/web/src/modules/cajas/*` | Modified/New | Refactor `CajasPage.tsx` into Hub with 3 cards & modals |
| `apps/web/src/api/cajasClient.ts` | Modified | API client methods for ideal, cards, KPIs |

## Risks & Mitigations
- **Concurrent Ideal Edits**: Transactional activation reset ensuring a single active ideal version.
- **Scale (500+ Technicians)**: Server-side pagination and SQL indexes on `(activa)`, `(tecnico_id, fecha)`, and `(caja_id)`.
- **Catalog Search Latency**: In-memory caching via `ensureCatalogLoaded`.
- **FK RESTRICT Deletes**: Return HTTP 409 Conflict when deleting tools referenced in ideal detail.

## Rollback Plan
1. Revert backend and frontend application deployments.
2. Execute SQL: `DROP TABLE IF EXISTS cajas_caja_ideal_detalle, cajas_caja_ideal;` (preserves existing `cajas_cajas`, `cajas_herramientas`, and `cajas_inventarios`).

## Dependencies
- Read-only queries to `personal` DB table (`personal.id`).
- Firestore `articulos` collection for catalog searcher.

## Open Questions
- **Limpieza Historial**: Propose deriving cleaning compliance directly from `cajas_inventario_detalle.estado` before introducing a standalone `cajas_limpieza_historial` table.

## Success Criteria
- [ ] Active "Caja Ideal" can be defined and updated via catalog searcher with transactional versioning.
- [ ] Technician cards display % missing vs ideal and open full inventory history modal.
- [ ] KPI panel displays aggregated missing items % and cleaning compliance.
- [ ] Zero changes to forbidden files (`App.tsx`, `navegacion.ts`, `backend/personal`).
- [ ] All new DB structures use `cajas_*` prefix, InnoDB, utf8mb4_unicode_ci.
