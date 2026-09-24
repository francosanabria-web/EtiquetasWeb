## Design Created

**Change**: cajas-hub-ideal-inventario-kpis
**Location**: `openspec/changes/cajas-hub-ideal-inventario-kpis/design.md` (openspec/hybrid) | Engram `sdd/cajas-hub-ideal-inventario-kpis/design` (engram)

### Summary
- **Approach**: Versioned Caja Ideal with singleton-active invariant, per-technician inventory cards, computed-on-read KPIs, and BuscadorCatalogo integration
- **Key Decisions**: 4 decisions documented (versioned ideal, computed KPIs, buscador reuse, single route hub)
- **Files Affected**: 12 new files, 6 modified files
- **Testing Strategy**: Unit + integration tests for backend (TestClient), manual + tsc --noEmit for frontend

### Open Questions
- [ ] Whether to store `creado_por` as FK to personal.id or denormalize nombre
- [ ] Default page size for technician cards endpoint (proposing 50)
- [ ] Whether KPI resumen endpoint should support filtering by periodo parameter

### Next Step
Ready for tasks (sdd-tasks).