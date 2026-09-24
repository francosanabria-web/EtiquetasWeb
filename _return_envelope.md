## Change Archived

**Change**: cajas-hub-ideal-inventario-kpis
**Archived to**: `openspec/changes/archive/2026-05-13-cajas-hub-ideal-inventario-kpis/`

### Specs Synced
| Domain | Action | Details |
|--------|--------|---------|
| caja-ideal | Created | Full spec copied from delta (no existing main spec at openspec/spezs/caja-ideal/) |
| infra | Created | Full spec copied from delta (no existing main spec at openspec/spezs/infra/) |
| inventario-por-tecnico | Created | Full spec copied from delta (no existing main spec at openspec/spezs/inventario-por-tecnico/) |
| kpis-cajas | Created | Full spec copied from delta (no existing main spec at openspec/spezs/kpis-cajas/) |

### Archive Contents
- proposal.md ✅
- design.md ✅
- specs/ ✅ (4 domains: caja-ideal, infra, inventario-por-tecnico, kpis-cajas)
- tasks.md ✅ (all tasks complete per verification)
- archive-report.md ✅

### Source of Truth Updated
The following main specs now reflect the new behavior:
- `openspec/spezs/caja-ideal/spec.md`
- `openspec/spezs/infra/spec.md`
- `openspec/spezs/inventario-por-tecnico/spec.md`
- `openspec/spezs/kpis-cajas/spec.md`

### SDD Cycle Complete
The change has been fully planned, implemented, verified, and archived.
Ready for the next change.

### Key Learnings
1. Mechanical filesystem operations (cp/mv + diff -r) are critical for audit integrity; model Read→Write must be avoided for archive copies.
2. When main specs don't exist, delta specs are full specs and should be copied mechanically with shell cp, verified by diff.
3. PASS_WITH_WARNINGS verdict with 2 follow-up warnings (W1 cross-module import, W2 lenient permiso) but no CRITICAL blockers — archive proceeds.
4. 68/68 backend tests pass, tsc --noEmit PASS, isolation verified (only authorized paths changed).
5. Archive folder move with ISO-date prefix convention (YYYY-MM-DD-change-name) works correctly.
6. Engram topic_key upsert behavior preserves single evolving observation per change across sessions.

### Risks
- W1 (buscador cross-module import): Parallel agent editing solicitudes/BuscadorCatalogo could break ideal editor — extract to shared module as documented TODO.
- W2 (verificar_permiso escritura lenient): API should enforce strict escritura match before generic fallback — tighten permission check.
- S2 (limpieza derivation): limpieza score stays 0 until edit path supports malo state — future KPI path enhancement.

### Skill Resolution
paths-injected — sdd-archive + _shared skills loaded per orchestrator-injected block in launch prompt.

### Next Recommended
1. Address W1: Extract BuscadorCatalogo import to shared module
2. Address W2: Tighten verificar_permiso to exact escritura match
3. Monitor S2: Limpieza derivation from inventario detalle estado
4. Proceed with next SDD change