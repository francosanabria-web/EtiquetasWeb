# Archive Report: cajas-hub-ideal-inventario-kpis

**Change**: cajas-hub-ideal-inventario-kpis
**Archived**: 2026-05-13
**Artifact Store Mode**: hybrid (openspec + engram)

## Final State Summary

### Verification Verdict
**PASS_WITH_WARNINGS** — all spec scenarios implemented, 68/68 backend tests green, frontend hub renders with 3 cards, buscador integrated, isolation holds. 2 warnings (follow-up) and 3 suggestions; no CRITICAL blockers.

### Warnings (follow-up, not blockers)
- **W1 — Buscador cross-module import** — IdealEditorModal imports from ../solicitudes/BuscadorCatalogo. Works but couples cajas → solicitudes. Design docs TODO to extract to shared/lib/ui. Risk: parallel agent editing solicitudes/BuscadorCatalogo could break ideal editor.
- **W2 — verificar_permiso escritura lenient** — db.verificar_permiso fallback allows lectura to pass escritura check in some paths. Not triggered today because UI gates via permisoDe, but API should enforce strict escritura.

### Suggestions (future work)
- **S1 — crear_ideal_versionado** always bumps igente_desde=NOW(); point-in-time history is by id order, not biznes periodo.
- **S2 — Limpieza** derived from estado='malo' but crear_inventario_txn only writes ueno/egular; malos only via direct UPDATE today.
- **S3 — Shell card title** now Cajas de Herramientas (more descriptive) but sidebar label longer.

### Specs Synced (openspec → main specs)
| Domain | Action | Details |
|--------|--------|---------|
| caja-ideal | Created | Full spec copied from delta (no existing main spec) |
| infra | Created | Full spec copied from delta (no existing main spec) |
| inventario-por-tecnico | Created | Full spec copied from delta (no existing main spec) |
| kpis-cajas | Created | Full spec copied from delta (no existing main spec) |

### Archive Contents
- proposal.md ✅
- design.md ✅
- specs/ ✅ (4 domains: caja-ideal, infra, inventario-por-tecnico, kpis-cajas)
- tasks.md ✅ (all tasks complete per verification)

### Source of Truth Updated
The following main specs now reflect the new behavior:
- openspec/spezs/caja-ideal/spec.md
- openspec/spezs/infra/spec.md
- openspec/spezs/inventario-por-tecnico/spec.md
- openspec/spezs/kpis-cajas/spec.md

### Isolation Verified
git status confirms changes only in:
- ackend/cajas/** (db.py, store.py, service.py, main.py, tests/)
- pps/web/src/modules/cajas/** (all new components + CajasPage.tsx)
- pps/web/src/api/cajasClient.ts
- 
avegacion.ts — shell fix only (icono "Inventory2" → "🧰", titulo → "Cajas de Herramientas", descripcion actualizada)

### Rollback Boundaries
- DROP TABLES: cajas_caja_ideal_detalle, cajas_caja_ideal (preserves existing cajas_cajas, cajas_herramientas, cajas_inventarios, cajas_inventario_detalle)
- Revert: pps/web/src/modules/cajas/* + cajasClient.ts
- Revert: 
avegacion.ts cajas icono/titulo/descripcion

### Next Recommended Steps
1. Address W1: Extract BuscadorCatalogo import to shared module
2. Address W2: Tighten erificar_permiso to exact escritura match
3. Monitor S2: Limpieza derivation from inventario detalle estado
4. Continue with next SDD change

**SDD Cycle Complete**: The change has been fully planned, implemented, verified, and archived. Ready for the next change.
