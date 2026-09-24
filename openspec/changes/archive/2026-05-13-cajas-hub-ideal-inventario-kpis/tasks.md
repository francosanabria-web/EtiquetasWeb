# Tasks: Cajas Hub with Ideal Toolkit, Technician Inventories and KPIs

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | 950-1100 |
| 400-line budget risk | High |
| 800-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR 1 Backend Ideal + API → PR 2 Backend Tecnicos/KPIs → PR 3 Frontend Hub + Ideal/Cards/KPIs |
| Delivery strategy | auto-chain |
| Chain strategy | stacked-to-main |

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: High

### Suggested Work Units

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|------|------|-----------|----------------------|-----------------|-------------------|
| 1 | Backend foundation: DDL cajas_caja_ideal* + store/service/main ideal CRUD | PR 1 | `python -m unittest backend/cajas/tests/test_cajas_ideal.py -v` | `curl GET /api/cajas/ideal` with Bearer | DROP TABLE cajas_caja_ideal_detalle, cajas_caja_ideal |
| 2 | Backend tecnicos-cards + historial + kpis resumen | PR 2 | `python -m unittest backend/cajas/tests/test_cajas_kpis.py -v` | `curl GET /api/cajas/tecnicos-cards?limit=25` | Revert store/service kpis routes only |
| 3 | Frontend hub 3 cards + ideal editor (Buscador) + tecnicos cards + KPIs panel | PR 3 | `tsc --noEmit` + `python -m unittest -v` | Open /admin/cajas, test buscador pick → ideal save → card B drill-down → card C % | Revert apps/web/src/modules/cajas/* + cajasClient.ts |

## Phase 1: Backend Foundation — Caja Ideal (DB + API)

- [ ] 1.1 Add idempotent DDL to `backend/cajas/db.py`: `cajas_caja_ideal` (id, nombre, descripcion, activa, vigente_desde, creado_por, creado_en) + `cajas_caja_ideal_detalle` (id, caja_ideal_id FK CASCADE, herramienta_id FK RESTRICT, cantidad_minima, articulo_codigo) with UNIQUE(caja_ideal_id, herramienta_id), indexes idx_ideal_activa, idx_ideal_vigente — prefix cajas_* only
- [ ] 1.2 Add store layer `backend/cajas/store.py`: `get_ideal_actual()`, `crear_ideal_versionado(data)` (transaction UPDATE activa=0 + INSERT activa=1 + detalle batch), `listar_ideal_versiones(limit,offset)`, `obtener_ideal_detalle(ideal_id)`
- [ ] 1.3 Add service layer `backend/cajas/service.py`: `get_ideal(token)` (cajas:lectura), `put_ideal(token,data)` (cajas:escritura, valida herramienta_codigo exists, cantidad_minima >0, map ValueError→400/409)
- [ ] 1.4 Add routes `backend/cajas/main.py`: `GET /api/cajas/ideal`, `PUT /api/cajas/ideal`, `GET /api/cajas/ideal/versiones` with _token() auth
- [ ] 1.5 Tests RED `backend/cajas/tests/test_cajas_ideal.py`: create ideal via buscador pick, duplicate herramienta →409, concurrent activation singleton, list detalle, auth 401, pagination

## Phase 2: Backend Tecnicos-Cards + Historial + KPIs

- [ ] 2.1 Add store `backend/cajas/store.py`: `listar_tecnicos_cards(q, limit, offset)` — SELECT personal WHERE tipo IN ('tecnico','supervisor','generico','panol') + LEFT JOIN latest cajas_inventarios per tecnico + LEFT JOIN cajas_caja_ideal_detalle to compute faltantes/completitud, paginated
- [ ] 2.2 Add store: `listar_inventarios_por_tecnico(tecnico_id, limit, offset)` — full historial ordered periodo DESC with detalle estados (bueno/regular/malo, presente)
- [ ] 2.3 Add store: `get_kpis_resumen()` + `get_kpis_por_tecnico(tecnico_id)` — computed-on-read: % faltantes = (ideal_count - presente_count)/ideal_count*100, % completitud, limpieza score = count estado='malo'/total, aggregated global + per-tecnico
- [ ] 2.4 Add service + routes `backend/cajas/service.py`/`main.py`: `GET /api/cajas/tecnicos-cards`, `GET /api/cajas/tecnicos/{id}/inventarios`, `GET /api/cajas/kpis/resumen`, `GET /api/cajas/kpis/tecnico/{id}` (lectura)
- [ ] 2.5 Tests RED `backend/cajas/tests/test_cajas_kpis.py`: % faltantes 0/50/100 edge cases, no ideal → hint, historial pagination, limpeza derive, 500+ scale pagination

## Phase 3: Frontend Hub Shell — 3-Card Layout

- [ ] 3.1 Refactor `apps/web/src/modules/cajas/CajasPage.tsx` into hub grid: 3 preview cards (Ideal / Inventario / KPIs) at single route `/admin/cajas`, keep existing CajasTabla/HerramientasTabla as fallback inside Card B collapsed state, no changes to App.tsx/navegacion.ts
- [ ] 3.2 Add `apps/web/src/api/cajasClient.ts`: `getIdeal()`, `putIdeal()`, `getIdealVersiones()`, `getTecnicosCards(params)`, `getTecnicoHistorial(tecnicoId)`, `getKpisResumen()`, types Ideal/IdealDetalle/TecnicoCard/Kpis
- [ ] 3.3 Add shared state + loading skeletons for hub, gate escritura via `permisoDe(usuario,"cajas")==="escritura"`

## Phase 4: Frontend Card A — Caja Ideal Editor + Buscador

- [ ] 4.1 Create `apps/web/src/modules/cajas/IdealCard.tsx`: preview (count herramientas, vigente_desde, activa badge) + Edit button (escritura only)
- [ ] 4.2 Create `IdealEditorModal.tsx`: form nombre/descripcion + detalle list, integrate `BuscadorCatalogo` (import from `modules/solicitudes/BuscadorCatalogo.tsx` with TODO to extract to shared) using `ensureCatalogLoaded`/`filterArticulos`, onPick fills codigo+articulo_codigo, validates UNIQUE client-side, calls putIdeal
- [ ] 4.3 Wire error handling: 409 duplicate → inline message, 401 → auth hint, empty ideal → "Definir caja ideal" CTA

## Phase 5: Frontend Card B — Inventario por Técnico

- [ ] 5.1 Create `TecnicosCards.tsx`: paginated grid (limit 25) of one card per técnico (nombre, caja codigo, % faltantes badge vs ideal, ultimo inventario estado), q search, "Ver historial" action
- [ ] 5.2 Create `TecnicoHistorialModal.tsx`: timeline of inventarios for tecnico_id ordered periodo DESC, each row shows periodo, estado (borrador/cerrado), detalle tabla (herramienta_codigo, cantidad, estado bueno/regular/malo, presente, observaciones: entregadas/renovadas/mal estado)
- [ ] 5.3 Reuse existing `InventarioFormModal` logic for consistency, ensure JOIN personal names display

## Phase 6: Frontend Card C — KPIs Panel

- [ ] 6.1 Create `KpisPanel.tsx`: fetch getKpisResumen, show global % faltantes, % completitud, limpieza compliance (derived from detalle estado), reuse `components/kpis/KpiBarChart`/`KpiDonutChart` patterns
- [ ] 6.2 Per-tecnico KPIs drill-down: click técnico card → overlay KPIs for that tecnico (GET /api/cajas/kpis/tecnico/{id}), show faltantes trend vs ideal
- [ ] 6.3 Handle edge: no ideal defined → empty state with link to Card A, loading/error skeletons

## Phase 7: Integration, Isolation & Verification

- [ ] 7.1 Isolation check: verify `git diff --name-only` touches only `backend/cajas/**` and `apps/web/src/modules/cajas/**` + `apps/web/src/api/cajasClient.ts`; assert no `App.tsx`, `navegacion.ts`, `backend/personal` changes
- [ ] 7.2 DB prefix check: `SHOW TABLES LIKE 'cajas_%'` — all new tables use cajas_* , InnoDB utf8mb4_unicode_ci, FK RESTRICT, indexes exist
- [ ] 7.3 Run `python -m unittest -v` in backend/cajas and `tsc --noEmit` in apps/web — all green; manual smoke: /admin/cajas shows 3 cards, buscador pick saves ideal, tecnico card drill-down shows historial, KPIs % matches ideal
