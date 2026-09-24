# KPIs por Cajas Specification

## Purpose

Computed-on-read KPI indicators comparing each técnico's latest closed inventario vs active Caja Ideal to compute % faltantes, % completitud, and limpieza historial compliance. Exposes /kpis and /kpis/resumen endpoints aggregated per técnico and global.

## Requirements

### Requirement: KPI Computation vs Active Caja Ideal

The system MUST compare each técnico's latest closed inventario vs active Caja Ideal to compute % faltantes ((ideal_count - presente_count)/ideal_count *100), % completitud, and limpieza historial (derive from detalle estado = 'malo' vs 'bueno' or explicit limpieza field if needed — spec as derived first).

- GIVEN the active Caja Ideal has N herramientas assigned
- WHEN the KPI endpoint computes for a technician's latest closed inventario
- THEN presente_count = number of detalle items with presente = TRUE and estado = 'bueno'
- AND ideal_count = N (total herramientas in active ideal)
- AND faltantes_pct = ((ideal_count - presente_count) / ideal_count) * 100
- AND completitud_pct = (presente_count / ideal_count) * 100
- AND limpieza_score derived from count of detalle with estado = 'malo' — lower score indicates better compliance

### Requirement: /kpis or /kpis/resumen Endpoint Aggregated per Técnico and Global

The system MUST expose /kpis or /kpis/resumen endpoint aggregated per técnico and global. Endpoint returns summary statistics across all técnicos, including overall % faltantes, average completitud, and limpieza trend.

- GIVEN a request to GET /api/cajas/kpis or GET /api/cajas/kpis/resumen
- WHEN the endpoint is called
- THEN it returns aggregated KPIs per técnico with tecnico_id, tecnico_nombre, faltantes_pct, completitud_pct, limpieza_score
- AND a global summary with overall average faltantes_pct, total técnicos counted, and compliance trend
- AND the endpoint uses server-side aggregation with proper indexes for performance at 500+ técnicos

### Requirement: No Ideal Defined -> KPIs Return 0 or Empty with Hint

The system MUST handle the case where no Caja Ideal is defined and return appropriate KPI values (0% faltantes or empty with hint).

- GIVEN no active Caja Ideal exists (all rows have activa=0)
- WHEN the KPI endpoint is called
- THEN it returns faltantes_pct = 0, completitud_pct = 0, or an empty result set with hint "No Caja Ideal definida — define una para calcular KPIs"
- AND the response includes a clear indication that KPIs cannot be computed without an active ideal

### Requirement: Ideal vs Empty Inventario -> 100% Faltantes

The system MUST compute 100% faltantes when the active Caja Ideal exists but the technician has no closed inventarios.

- GIVEN the active Caja Ideal has N herramientas assigned
- WHEN the KPI endpoint computes for a technician with no closed inventarios
- THEN presente_count = 0, ideal_count = N
- AND faltantes_pct = ((N - 0) / N) * 100 = 100%
- AND completitud_pct = 0%
- AND limpieza_score indicates no compliance data available

### Requirement: Ideal vs Full Inventario -> 0%

The system MUST compute 0% faltantes when the technician's inventario has all required herramientas present with good state.

- GIVEN the active Caja Ideal has N herramientas assigned
- WHEN the KPI endpoint computes for a technician whose latest closed inventario has all N herramientas with presente = TRUE and estado = 'bueno'
- THEN presente_count = N, ideal_count = N
- AND faltantes_pct = ((N - N) / N) * 100 = 0%
- AND completitud_pct = 100%
- AND limpieza_score indicates full compliance

## Scenarios

#### Scenario: No Ideal Defined -> KPIs Return 0 or Empty with Hint

- GIVEN there is no active Caja Ideal (all rows have activa=0)
- WHEN the user requests GET /api/cajas/kpis/resumen
- THEN the response includes faltantes_pct = 0 or an empty result set with hint message
- AND the response indicates "No Caja Ideal definida — define una para calcular KPIs"
- AND the system does not error; gracefully handles missing ideal

#### Scenario: Ideal vs Empty Inventario -> 100% Faltantes

- GIVEN an active Caja Ideal with 5 herramientas assigned
- WHEN the KPI endpoint computes for a technician with no inventarios (never created)
- THEN faltantes_pct = 100%
- AND completitud_pct = 0%
- AND the response clearly shows 100% missing items

#### Scenario: Ideal vs Full Inventario -> 0%

- GIVEN an active Caja Ideal with 5 herramientas assigned
- WHEN the KPI endpoint computes for a technician whose latest closed inventario has all 5 detalle items with presente = TRUE and estado = 'bueno'
- THEN faltantes_pct = 0%
- AND completitud_pct = 100%
- AND limpieza_score indicates full compliance

#### Scenario: Ideal vs Partial Inventario -> Partial Faltantes

- GIVEN an active Caja Ideal with 5 herramientas assigned
- WHEN the KPI endpoint computes for a technician whose latest closed inventario has 3 out of 5 items with presente = TRUE and estado = 'bueno', and 2 items missing or with estado = 'malo'
- THEN faltantes_pct = 40% ((5-3)/5*100)
- AND completitud_pct = 60%
- AND limpieza_score reflects the 2 items with 'malo' estado

#### Scenario: Historial Limpieza Trend

- GIVEN the user requests KPIs with a periodo parameter
- WHEN the endpoint returns KPIs grouped by periodo for a technician
- THEN the response includes a trend showing limpieza compliance across recent periods
- AND each period entry shows faltantes_pct, completitud_pct, and mal_count (items with estado = 'malo')
- AND the trend is ordered by periodo DESC for the most recent first