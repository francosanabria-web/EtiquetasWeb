# Exploration: cajas-fase2-polish

## Problem / Gap

Fase 2 verify left explicit follow-ups: 4 functional hardening items, 4 visual polish items, plus the operational need to load technicians into `personal` before Cajas can be used. All verified against the current codebase.

## Current State (verified)

### Functional
1. **BuscadorCatalogo coupling — CONFIRMED.** `apps/web/src/modules/cajas/IdealEditorModal.tsx:7` imports `../solicitudes/BuscadorCatalogo`. The component lives inside the `solicitudes` module and depends on `../../lib/articulosCatalog` (already shared in `src/lib/`). Props API: `{ value, onCodigoChange, onPick, disabled? }`. Only two consumers: solicitudes internals + `IdealEditorModal`. CSS is the solicitudes `sol-catalog*` classes (global CSS, not module-scoped) — moving the file does not break styling.
2. **verificar_permiso lenient fallback — CONFIRMED.** `backend/cajas/db.py:262-263` and `:273-274`: after the specific `:lectura`/`:escritura` checks, `if nivel != "sin_acceso": return payload` grants ANY non-blocked level for ANY non-suffixed or mismatched permiso string. `backend/personal/db.py:186-188, 199-200` has the IDENTICAL pattern (with an explicit "Compatibilidad" comment). Same shape, so the fix is symmetric; but per isolation constraints we touch ONLY cajas and must not regress personal behavior expectations.
3. **Limpieza is derived only — CONFIRMED.** `limpieza_score` is computed in `store.py` (`malos / total_det * 100`) from `cajas_inventario_detalle.estado = 'malo'`. No limpieza table/events exist. There is no audit trail of who registered a malo item or when it was resolved.
4. **Caja ↔ técnico assignment is implicit — CONFIRMED.** `listar_tecnicos_cards` (`store.py:1207+`) derives the current caja per técnico from the LATEST inventario (`ORDER BY periodo DESC, id DESC`, first row per tecnico). A técnico with no inventario appears without caja; a reassignment is invisible until an inventario is created for the new caja. No `cajas_asignaciones` table exists.

### Visual
1. **Iconography** — `apps/web/src/config/navegacion.ts` holds `icono` as emoji strings (🧰, 📤, 📊…), rendered in `components/SidebarNav.tsx` (`.nav-icon`) and `components/ModuloCard.tsx` (`.mod-icon`). `package.json` deps: react 19, react-router 7, **recharts 2.15**, firebase — **no lucide-react / heroicons**. Adding lucide = new dependency + replacing a string field with a component → touches every module icon; out of lean scope.
2. **3 hub cards polish** — `KpiSkeletonCard`/`KpiSkeletonGrid` already exist in `components/kpis/` (global classes `kpi-skeleton-card/line`, `kpi-grid-2`). `KpisPanel`, `IdealCard`, `TecnicosCards` currently show plain "Cargando…" text. No empty-state illustrations; inline styles dominate in cajas components.
3. **KPI charts** — `components/kpis/KpiBarChart.tsx`, `KpiDonutChart.tsx`, `KpiLineChart.tsx`, `KpiMultiLineChart.tsx` exist (recharts-based) and are used by global KPIs. `KpisPanel` renders a hand-rolled `BarList` (divs + width %) instead of `KpiBarChart`. Backend `getKpisResumen` returns `distribucion_faltantes` buckets and per-técnico rows — no per-period trend series (would need aggregation of `cajas_inventarios.periodo`).
4. **Historial stepper** — `TecnicoHistorialModal` is a flat list of expandable cards with `sol-estado` badges (cerrado/borrador). No stepper/timeline component exists anywhere; minuta module has no reusable timeline to copy.

### Personal (technician load)
- `backend/personal` exposes full CRUD (`/api/personal`) with `tipo IN (tecnico, supervisor, produccion, generico, panol)` and `area_id`. Frontend `modules/personal/PersonalPage.tsx` + `PersonalFormModal.tsx` already offer alta with tipo selector (Técnico default) and area dropdown. **No bulk import** endpoint or UI. So loading technicians works today one-by-one; a script using the existing POST endpoint would cover bulk loads without new backend code.

## Approaches per axis

### A. BuscadorCatalogo extraction
1. **Move to `src/components/shared/BuscadorCatalogo.tsx`, update 2 import sites** — props identical.
   - Pros: minimal diff, single hop, keeps `sol-catalog*` CSS untouched.
   - Cons: solicitudes module loses a file while other modules are being edited (parallel-agent risk).
   - Effort: Low.
2. Re-export shim in solicitudes (`export { default } from "../shared/BuscadorCatalogo"`).
   - Pros: zero risk for solicitudes consumers.
   - Cons: leaves cruft; two public entry points.
   - Effort: Low.
3. Copy instead of move.
   - Cons: duplication — rejected.

**Recommendation: A1.** Fix `IdealEditorModal` import and re-point solicitudes internal imports to the shared path in the same commit so both modules' `tsc` stay green.

### B. Harden verificar_permiso (cajas only)
1. **Strict suffix matching + deny unknown suffixes**: `if sufijo==":escritura" → nivel=="escritura"; if ":lectura" → nivel in (lectura,escritura); else None`. Remove the `nivel != "sin_acceso"` catch-all.
   - Pros: closes the hole; explicit.
   - Cons: if any cajas endpoint calls with a non-suffixed permiso string it breaks — must grep all call sites first.
   - Effort: Low.
2. Same fix mirrored in personal db.py.
   - Cons: violates isolation constraint (personal read-only) — do NOT.
3. Keep catch-all but log/deprecate.
   - Cons: keeps the hole.

**Recommendation: B1, cajas-only.** Verify in `backend/cajas/service.py`/`main.py` that every `verificar_permiso` call uses `:lectura`/`:escritura` suffix (spot-check showed services pass suffixed strings). Personal keeps its identical pattern untouched — align later in a dedicated change.

### C. Limpieza as entity
1. **`cajas_limpieza_eventos`** (id, caja_id FK RESTRICT, tecnico_id FK personal RESTRICT, inventario_detalle_id nullable, fecha DATETIME, estado ENUM('pendiente','realizada','vencida'), observaciones TEXT, indexes on (estado,fecha) and (caja_id)). Keep current derived KPI; events additive.
   - Pros: audit trail without changing KPI math; RESTRICT FKs per convention.
   - Cons: extra writes when closing inventario.
   - Effort: Medium.
2. Full explicit limpieza workflow (replace derived score).
   - Cons: scope explosion, changes KPI semantics.
3. Defer entirely.
   - Cons: violates user-requested scope.

**Recommendation: C1 — create table + emit one event per detalle with estado='malo' when an inventario closes; keep derived KPI as-is.**

### D. Assignment caja ↔ técnico
1. **Versioned `cajas_asignaciones(caja_id, tecnico_id, desde, hasta NULL, UNIQUE(caja_id,tecnico_id,desde))`**, FKs RESTRICT to `cajas_cajas` and `personal`. `tecnicos-cards` prefers active assignment, falls back to latest-inventario derivation.
   - Pros: full history, no singleton bookkeeping bugs, matches versionado pattern already used for caja_ideal.
   - Cons: query slightly more complex (max desde WHERE hasta IS NULL).
   - Effort: Medium.
2. Singleton current row (`UNIQUE(tecnico_id)`, overwrite).
   - Pros: simplest query.
   - Cons: loses history; contradicts the versioned convention of the module.
3. Keep implicit derivation.
   - Cons: cannot answer "what caja SHOULD tecnico X have" without an inventario.

**Recommendation: D1.** Backfill: derive initial assignments from existing latest inventarios (optional script, marked manual step).

### E. Visual 1–4
1. **Icons**: keep emojis now, add TODO note for lucide migration. Migrating = new dep + typing change (`icono: string → LucideIcon`) + touching all 12 modules — NOT lean. Defer.
2. **Cards polish**: reuse `KpiSkeletonCard` for the 3 hub cards' loading states, add consistent empty states with CTA (pattern already in `KpisPanel`), small CSS hover/micro-transitions on cards and modals. No new deps.
3. **KPI charts**: swap `BarList` for existing `KpiBarChart` (distribution buckets data already shaped `{rango,count}`) and optionally `KpiDonutChart` for completitud vs faltantes. Trend (`KpiLineChart`) needs a per-period aggregation the backend doesn't expose — propose a small `tendencia` field in `getKpisResumen` (GROUP BY periodo over `cajas_inventarios`) OR defer trend to a later slice. Lean choice: bar+donut now, line deferred.
4. **Historial stepper**: restyle the existing expandable list as a vertical timeline (CSS-only: left rail, colored dot per estado — green cerrado / yellow borrador, connector line). Reuses `sol-estado` badge palette; no dependency; a11y via `ol/li` semantics. No existing minuta timeline to reuse (verified: none exists).

## Reusable model sketch (new tables)

```sql
CREATE TABLE cajas_limpieza_eventos (
  id INT AUTO_INCREMENT PRIMARY KEY,
  caja_id INT NOT NULL,
  tecnico_id INT NOT NULL,
  inventario_id INT NULL,
  herramienta_id INT UNSIGNED NULL,
  fecha DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  estado ENUM('pendiente','realizada','vencida') NOT NULL DEFAULT 'pendiente',
  observaciones TEXT NULL,
  INDEX idx_limp_estado_fecha (estado, fecha),
  INDEX idx_limp_caja (caja_id),
  CONSTRAINT fk_limp_caja FOREIGN KEY (caja_id) REFERENCES cajas_cajas(id) ON DELETE RESTRICT,
  CONSTRAINT fk_limp_tecnico FOREIGN KEY (tecnico_id) REFERENCES personal(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE cajas_asignaciones (
  id INT AUTO_INCREMENT PRIMARY KEY,
  caja_id INT NOT NULL,
  tecnico_id INT NOT NULL,
  desde DATE NOT NULL,
  hasta DATE NULL,
  UNIQUE KEY uq_asig (caja_id, tecnico_id, desde),
  INDEX idx_asig_tecnico_abierta (tecnico_id, hasta),
  CONSTRAINT fk_asig_caja FOREIGN KEY (caja_id) REFERENCES cajas_cajas(id) ON DELETE RESTRICT,
  CONSTRAINT fk_asig_tecnico FOREIGN KEY (tecnico_id) REFERENCES personal(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```
(Note: match `cajas_cajas.id` signedness — INT signed — checked against existing schema.)

## Risks

- **Parallel agent touching solicitudes**: moving `BuscadorCatalogo` while a solicitudes change is in flight causes merge conflicts on the same file. Coordinate: move + update BOTH consumer imports in one atomic commit.
- **verificar_permiso strictness**: any cajas call site passing an unsuffixed permiso string will start returning 401/403 — must inventory call sites before changing.
- **New FK to `personal`**: locks personal rows from deletion if assigned (RESTRICT) — intended, but document that deleting a técnico with assignment/limpieza history will fail (consistent with existing inventarios behavior).
- **Emoji→lucide temptation**: scope creep magnet; explicitly deferred.
- **tendencia line chart**: requires new backend aggregation; cut from lean slice if it threatens budget.

## Recommended lean slices (~same 3-slice shape)

- **Slice 1 — Hardening & cleanup**: BuscadorCatalogo extraction (A1), verificar_permiso strict (B1), personal-load documentation (no code; technicians already loadable via Personal page; optional helper script excluded from module code). ~250 lines.
- **Slice 2 — Domain entities**: `cajas_limpieza_eventos` (C1) + `cajas_asignaciones` (D1), store/service endpoints, `tecnicos-cards` assignment preference. ~300 lines.
- **Slice 3 — Visual polish**: skeletons/empty states on 3 cards (E2), KpiBarChart/Donut swap (E3), historial stepper CSS (E4). ~250 lines.

## Isolation file list (may touch ONLY)

- `backend/cajas/db.py`, `backend/cajas/store.py`, `backend/cajas/service.py`, `backend/cajas/main.py`, `backend/cajas/tests/**`
- `apps/web/src/components/shared/BuscadorCatalogo.tsx` (new)
- `apps/web/src/modules/cajas/**` (imports + polish)
- `apps/web/src/modules/solicitudes/` — ONLY import re-point lines in files that import BuscadorCatalogo (parallel-agent coordination required)
- `apps/web/src/api/cajasClient.ts`
- `apps/web/src/lib/articulosCatalog.ts` (only if a type tweak is needed — expect none)
- `apps/web/src/config/navegacion.ts` — NOT touched (icons deferred)
- `backend/personal/**` — READ-ONLY reference; do not modify.

## Ready for Proposal

**Yes.** All four functional axes and four visual axes are verified against real code, approaches are decided with an explicit lean deferral (lucide icons, trend chart, bulk CSV). The personal-technicians need is satisfied with existing UI — proposal should include a docs/how-to note, no code.
