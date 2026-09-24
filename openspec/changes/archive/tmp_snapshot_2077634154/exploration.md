# Exploration: Cajas — Hub con Caja Ideal, Inventario por Técnico y KPIs

## Problem / Current Gap

Today the module (`/admin/cajas`, `CajasPage.tsx`) is two flat paginated tables
(cajas + herramientas) plus `InventariosPage.tsx` showing inventory records.
There is:

- No hub/landing with preview cards.
- No concept of a canonical "caja ideal" (baseline toolkit any technician should carry).
- No per-technician drill-down card showing the full inventory history of their
  assigned box (delivered, renewed, damaged, missing).
- No KPIs (e.g. % missing vs ideal, cleaning-history compliance).

Backend (`backend/cajas/`) currently exposes CRUD for `cajas_cajas`,
`cajas_herramientas`, `cajas_inventarios` + `cajas_inventario_detalle`. All
tables are prefixed `cajas_*`, InnoDB utf8mb4_unicode_ci. `personal` is already
JOINed read-only as `LEFT JOIN personal p_tec ON inv.tecnico_id = p_tec.id` —
proving the reusable-data pattern (FK to `personal.id`, no duplication) is the
established convention.

## Current State (verified from code)

- `backend/cajas/db.py` — `init_db()` idempotent `CREATE TABLE IF NOT EXISTS`;
  auth: JWT + opaque-token fallback over `backend/usuarios` sqlite sessions,
  `verificar_permiso(token, "cajas:lectura|escritura")`.
- `backend/cajas/store.py` — parametrized PyMySQL access, `UPPER(TRIM(codigo))`
  uniqueness, `"" → NULL` coercion, pagination limit/offset, FK reference
  checks before delete (409 on RESTRICT).
- `backend/cajas/service.py` — thin layer; permission check + map
  `ValueError → (msg, status)`. Inventarios have `estado IN (borrador|cerrado)`
  and transactional creation with `cajas_inventario_detalle` children.
- `backend/cajas/main.py` — Starlette routes under `/api/cajas/*`, port ~8021,
  CORS + Bearer header.
- Frontend: `apps/web/src/modules/cajas/CajasPage.tsx` (datagrids),
  `InventariosPage.tsx`, `cajasClient.ts`; permission via
  `permisoDe(usuario, "cajas")` and `RequirePermiso` in App routing
  (`navegacion.ts` id `cajas`, ruta `/admin/cajas`).
- Buscador: `apps/web/src/modules/solicitudes/BuscadorCatalogo.tsx` is a
  self-contained component using `lib/articulosCatalog.ts`
  (`ensureCatalogLoaded` + `filterArticulos`) over the Firestore `articulos`
  collection; it takes generic props (`value`, `onCodigoChange`, `onPick`)
  and is already importable from any module — **no need to duplicate logic**,
  but it currently lives inside `modules/solicitudes`, so importing it from
  `modules/cajas` creates a cross-module import (acceptable short-term;
  long-term move to a shared `modules/_shared/` or `lib/ui` location).

## Affected Areas (and file-ownership for isolation)

- `backend/cajas/db.py` — add `CREATE TABLE IF NOT EXISTS` for new tables.
- `backend/cajas/store.py` — new query layer for ideal box, técnico summary, KPIs.
- `backend/cajas/service.py`, `main.py` — new routes under `/api/cajas/...`.
- `backend/cajas/tests/` — new tests (pattern: real MariaDB connection +
  cleanup of cajas_* tables, mirroring `test_inventarios.py`).
- `apps/web/src/modules/cajas/CajasPage.tsx` — refactor landing into 3-card hub,
  keep existing grid as content of card B.
- `apps/web/src/modules/cajas/` — new files: `HubPage.tsx` (or keep CajasPage
  as hub), `IdealCard.tsx`, `IdealEditorModal.tsx`, `TecnicosCards.tsx`,
  `TecnicoHistorialModal.tsx`, `KpisPanel.tsx`.
- `apps/web/src/api/cajasClient.ts` — add client functions for new endpoints.

Must NOT touch: `backend/personal`, `backend/usuarios`, `backend/salidas`,
other frontend modules. Personal consumption remains read-only JOIN by
`personal.id`.

## Approaches

### A) UX — hub structure

1. **Composite hub page with internal tab/panel state** — one route
   `/admin/cajas` renders three cards; each card expands to an inline panel or
   modal with its own data.
   - Pros: minimal routing change; no new navigation entries; fast delivery.
   - Cons: single component grows; deep-linking to a specific card is harder.
   - Effort: Low.
2. **Nested routes** `/admin/cajas/{ideal,inventario,kpis}` with hub as index.
   - Pros: deep-linkable; smaller components; future-proof for per-card permisos.
   - Cons: touch `App.tsx`/`navegacion.ts` (shared file — coordination with
     parallel agent required); slightly more boilerplate.
   - Effort: Medium.

**Tentative choice:** keep single route `/admin/cajas` for slice 1 (avoid
touching shared `App.tsx`/`navegacion.ts` and colliding with the parallel
agent), but structure components so promoting to nested routes later is a
mechanical move.

### B) DB — ideal box persistence

1. **Singleton row** `cajas_caja_ideal` (one active row) +
   `cajas_caja_ideal_detalle(herramienta_id, cantidad_minima)`.
   - Pros: trivial "current ideal" lookup; matches requirement "una caja
     ideal genérica"; UNIQUE enforced.
   - Cons: no history of ideal changes (KPI comparisons against past periods
     become fuzzy).
2. **Versioned ideal**: `cajas_caja_ideal(id, nombre, activa, vigente_desde)` +
   detalle; current = latest `activa=1`.
   - Pros: KPI periods comparable point-in-time; supports future per-rubro
     variants without schema change.
   - Cons: more logic (resolve "current" on read), risk of concurrent
     activations → mitigate with transaction + partial unique (`activa=1`).
   - Effort: Medium.

**Tentative choice:** versioned table with singleton-invariant enforced in a
transaction (`UPDATE ... SET activa=0; INSERT ... activa=1`) — sustainable for
the "gran escala" goal, still a lean slice.

### C) KPIs — computation strategy

1. **Computed on read** with SQL aggregation: for each técnico,
   `LEFT JOIN ideal_detalle` vs latest closed inventario per caja →
   % faltantes, plus limpieza events from `cajas_inventario_detalle.estado`.
   - Pros: no denormalization; always consistent; zero write-path cost.
   - Cons: N+1 risk at 500+ técnicos → must paginate and index
     `(caja_id, periodo)`, `(inventario_id)`, `(herramienta_id)`.
   - Effort: Low–Medium.
2. **Persisted KPI snapshots** `cajas_kpi_snapshots(técnico_id, periodo,
   faltantes_pct, ...)`.
   - Pros: O(1) dashboard; historical trend trivial.
   - Cons: write amplification, recompute jobs, staleness semantics.
   - Effort: Medium.

**Tentative choice:** computed-on-read with proper indexes and server-side
pagination; revisit snapshots only if profiling shows pain at scale.

## Proposed data model (sketch)

```sql
cajas_caja_ideal (
  id INT PK AI, nombre VARCHAR(120) NOT NULL,
  activa TINYINT(1) NOT NULL DEFAULT 0,
  vigente_desde DATETIME NOT NULL,
  creado_por VARCHAR(100) NULL, creado_en DATETIME NOT NULL,
  INDEX idx_ideal_activa (activa)
)
cajas_caja_ideal_detalle (
  id INT PK AI,
  caja_ideal_id INT NOT NULL,
  herramienta_id INT NOT NULL,
  cantidad_minima INT NOT NULL DEFAULT 1,
  UNIQUE KEY uq_ideal_herramienta (caja_ideal_id, herramienta_id),
  CONSTRAINT fk_ideal_cab FOREIGN KEY (caja_ideal_id) REFERENCES cajas_caja_ideal(id) ON DELETE CASCADE,
  CONSTRAINT fk_ideal_herr FOREIGN KEY (herramienta_id) REFERENCES cajas_herramientas(id) ON DELETE RESTRICT
)
-- optional for cleaning history KPI if not derivable from inventario_detalle.estado:
cajas_limpieza_historial (
  id INT PK AI, tecnico_id INT NOT NULL, caja_id INT NOT NULL,
  fecha DATE NOT NULL, resultado VARCHAR(20) NOT NULL, observaciones TEXT NULL,
  INDEX idx_limp_tec_fecha (tecnico_id, fecha)
)
```

Reusable-data rule kept: inventarios already reference `personal.id` via JOIN;
new tables reference only `cajas_*` and `personal.id` — no personal data copy.

New endpoints (proposal sketch):
- `GET /api/cajas/ideal` (+ `/{id}`), `PUT /api/cajas/ideal` (idempotent full
  replace transaction), `POST` optional for new version.
- `GET /api/cajas/tecnicos-cards?limit&offset&q=` — per-técnico summary:
  caja code, periodo último inventario, % faltantes vs ideal.
- `GET /api/cajas/tecnicos/{personal_id}/inventarios?limit&offset` — full
  history with detalle.
- `GET /api/cajas/kpis/resumen?periodo=` — aggregated KPIs.

## Risks

- **Concurrent ideal edits**: two escritura users swapping `activa` → mitigate
  with single transaction + optimistic version column or `GET_LOCK`.
- **Firestore catalog latency**: `ensureCatalogLoaded` caches in-memory; ideal
  editor must not refetch per open; reuse singleton from
  `lib/articulosCatalog.ts`.
- **FK RESTRICT deletes**: deleting a herramienta referenced by ideal or
  inventario_detalle must 409 with clear message (pattern already exists in
  store.py lines ~232/477).
- **Scale**: 500+ técnicos → server-side pagination mandatory on the cards
  endpoint; aggregate query must hit covering index on
  `cajas_inventarios(caja_id, periodo)` and `cajas_inventario_detalle
  (inventario_id)`.
- **Cross-module import**: importing `BuscadorCatalogo` from
  `modules/solicitudes` couples cajas→solicitudes; if another agent refactors
  solicitudes the import may break — consider extracting to
  `apps/web/src/lib/ui/BuscadorCatalogo.tsx` (flag in proposal; doing it in
  this change touches solicitudes path only as a MOVE, needs coordination or
  a thin re-export file left behind).
- **Parallel agent interference**: keep every change strictly inside the
  allowed path set (see Affected Areas); do NOT edit `App.tsx`,
  `navegacion.ts`, or other backend modules.
- **KPI freshness**: computed-on-read may be expensive on first load;
  consider small in-memory cache (60s) server-side.

## Recommendation

Lean slice for proposal (fits well under the 800-line review budget if split
in 2 PRs):

1. Slice 1 (backend): new tables + ideal-box idempotent CRUD + técnico-cards
   list + KPI aggregate endpoint + tests.
2. Slice 2 (frontend): redesign `CajasPage.tsx` into 3-card hub; card A ideal
   editor with embedded catalog searcher (reuse `ensureCatalogLoaded`);
   card B existing grid + per-técnico cards + history modal; card C KPI panel
   with % faltantes vs ideal.

Defer: limpieza historial table (only if not derivable from inventario
estado), KPI snapshots, per-rubro ideal variants, nested routing.

## Ready for Proposal

Yes. Enough verified context exists (tables, auth, patterns, frontend wiring,
buscador contract) to write proposal + specs + design without further
exploration. Open question worth confirming with user before design: whether
"historial de limpieza" is a NEW table (`cajas_limpieza_historial`) or derived
from inventario states; exploration assumes derive-first.
