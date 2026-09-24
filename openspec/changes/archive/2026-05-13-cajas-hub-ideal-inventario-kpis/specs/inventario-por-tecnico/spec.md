# Inventario por Técnico Specification

## Purpose

Per-technician inventory cards displayed on hub entry to /admin/cajas, with full history drill-down modal showing all cajas_inventarios for the técnico ordered by periodo DESC, with detalle estados (bueno/regular/malo, presente, entregadas/renovadas). Card B renders one card per technician (tipo in ('tecnico','supervisor','generico','panol') from personal table), with current caja assignment and summary.

## Requirements

### Requirement: Technician Cards on Hub Entry

The system MUST render hub with 3 preview cards on entry to /admin/cajas. Card B MUST show one card per técnico (tecnico_id from personal where tipo in ('tecnico','supervisor','generico','panol')), with current caja assignment and summary of % missing vs ideal and inventory status.

- GIVEN the user navigates to /admin/cajas
- WHEN the hub page loads
- THEN three preview cards are rendered, one per técnico matching the permitted tipos
- AND each card shows the técnico's name, current caja code, and last periodo
- AND the card shows % faltantes vs the active Caja Ideal

### Requirement: Card Drill-Down Historial Completo

Clicking a card MUST open historial completo: all cajas_inventarios for that tecnico ordered by periodo DESC, with detalle estados (bueno/regular/malo, presente true/false, entregadas/renovadas).

- GIVEN the user clicks a technician card
- WHEN the historial modal opens
- THEN all cajas_inventarios for that tecnico are retrieved ordered by periodo DESC
- AND each inventario includes its detalle with estado (bueno/regular/malo), presente flag, and item counts
- AND the modal shows navigation between different-period inventarios

### Requirement: Reuse Existing Inventory Behavior

The system MUST reuse existing inventory behavior (inventario header+detalle, estado borrador/cerrado) but presented per-técnico rather than per-caja. The same inventario creation, estado transitions, and detalle validation patterns apply, scoped by tecnico_id.

- GIVEN the user creates a new inventario for a technician
- WHEN the inventory creation flow is initiated
- THEN the same inventario header fields are used (caja_id, periodo, tecnico_id, area, supervisor_id, obs_generales, estado)
- AND detalle items follow the same validation (herramienta_codigo, cantidad, presente, estado)
- AND estado transitions follow borrador -> cerrado machine (no revertir una vez cerrado)

### Requirement: Server-Side Pagination for Técnico Cards (Scale 500+)

The system MUST support pagination server-side (limit/offset) for técnico cards (scale 500+). Cards list must not load all 500+ technicians at once; must use SQL-driven paginated endpoint.

- GIVEN the user scrolls or pages through technician cards
- WHEN the request includes limit and offset parameters
- THEN the endpoint returns only the requested page of técnicos
- AND total count is available for pagination control
- AND indexes support efficient COUNT and data queries on personal.tipo and técnico identifiers

### Requirement: Estado Transitions Visible per Técnico

The system MUST display estado transitions visible per técnico, showing borrador/cerrado status of each inventario in the card summary and historial.

- GIVEN the user views a technician card
- WHEN the card shows the last inventario status
- THEN the current estado (borrador or cerrado) is displayed
- AND in the historial, each inventario's estado is visible beside its periodo
- AND disabled state indicators show when transitions are no longer possible

### Requirement: Search/Q Filter for Técnico Cards

The system MUST support search/q filter for technician cards, allowing filtering by técnico name or caja code.

- GIVEN the user types a query in the cards filter input
- WHEN the filter is applied
- THEN the endpoint filters by UPPER(TRIM(p_tec.nombre)) or UPPER(TRIM(caja_codigo))
- AND returns matching technicians only
- AND pagination state is preserved across filters

## Scenarios

#### Scenario: List Técnico Cards Paginated

- GIVEN the user navigates to /admin/cajas with multiple técnicos in the system
- WHEN the hub loads the technician cards
- THEN exactly 3 preview cards are displayed (one per tipo: tecnico, supervisor, generico, panol)
- AND each card shows the current caja assignment and summary
- AND pagination controls are available for scaling to 500+ technicians

#### Scenario: Drill-Down Historial

- GIVEN the user clicks a technician card showing tecnico_id 5
- WHEN the historial modal opens
- THEN all cajas_inventarios for tecnico_id 5 are retrieved ordered by periodo DESC
- AND each inventario includes its complete detalle with herramienta codes, quantities, presente flags, and estados
- AND the user can navigate to previous/next periodo inventarios

#### Scenario: Estado Transitions Visible

- GIVEN the user views a technician card with a cerrado inventario
- WHEN the card displays the inventario status
- THEN "cerrado" is displayed with visual indicator
- AND the user cannot re-open a cerrado inventario (transicion to borrador is prohibited)
- AND borrador inventarios show "borrador" status with edit available

#### Scenario: Search/Q Filter Cards

- GIVEN the user types "Juan" in the technician filter while on /admin/cajas
- WHEN the filter is applied
- THEN only technicians with "Juan" in their name are shown in the cards
- AND pagination reflects the filtered count
- AND the filter clears when the user removes the query text