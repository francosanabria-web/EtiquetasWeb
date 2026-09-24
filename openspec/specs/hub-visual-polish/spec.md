# Delta for HubVisualPolish

## ADDED Requirements

### Requirement: KpiSkeletonCard Loading States

The system MUST render `KpiSkeletonCard` (or custom skeleton) as the loading state for each hub card during data fetch. Three hub cards MUST show skeletons simultaneously while their data loads:

- **IdealCard** (Card A): Must show `KpiSkeletonCard` or equivalent while `ideal` data fetches
- **TecnicosCards** (Card B): Must show `KpiSkeletonCard` or equivalent while `tecnicos` data fetches
- **KpisPanel** (Card C): Must show skeleton while `kpisResumen` data fetches

The skeleton MUST use consistent styling with the card's existing `sol-table-wrap` layout and display a pulse/placeholder animation indicating loading activity.

- GIVEN the hub page loads with no cached data
- WHEN the IdealCard component mounts
- THEN a skeleton card is rendered in place of the ideal content
- AND the skeleton persists until the ideal data resolves
- GIVEN TecnicosCards mounts
- THEN skeleton cards render for each técnico grid cell while data loads
- GIVEN KpisPanel mounts
- THEN a skeleton occupies the panel space until KPIs data resolves

### Requirement: Empty Illustration + CTA States

The system MUST show an empty illustration + Call-to-Action (CTA) when no data is available for each hub card:

- **IdealCard**: WHEN `ideal` is null/empty (no Caja Ideal defined), SHOW an illustration component with CTA "Definir Caja Ideal"
- **TecnicosCards**: WHEN no técnicos are available (empty list), SHOW an illustration with CTA to add technicians (via personal module)
- **KpisPanel**: WHEN no KPI data exists (no ideal, no inventarios), SHOW empty state illustration with CTA

The illustration MUST use the project's emoji icon system (🧰, 📦, 📊 etc.) with a TODO note for future lucide migration. The CTA button MUST follow the existing `btn-primary` style and navigate to the appropriate creation flow.

- GIVEN IdealCard with no ideal
- WHEN the empty state is rendered
- THEN an illustration component displays with the project emoji and CTA button
- AND the CTA onClick calls `onDefineIdeal` or navigates to the ideal editor
- GIVEN TecnicosCards with items.length === 0
- WHEN the empty state renders
- THEN illustration + CTA "Cargar técnicos" appears
- GIVEN KpisPanel with kpis.ideal_count === 0
- WHEN the empty state renders
- THEN illustration displays "No hay Caja Ideal definida — define una para calcular KPIs" with CTA

### Requirement: KPI Charts Reuse (KpiBarChart, KpiDonutChart, KpiLineChart)

The system MUST reuse existing `KpiBarChart`, `KpiDonutChart`, and `KpiLineChart` components for KPI data visualization instead of hand-rolled `BarList`/divs. The `KpisPanel` MUST render these chart components with data from `getKpisResumen`:

- **KpiBarChart**: Render `distribucion_faltantes` buckets as vertical bar chart. Data shape: `{ rango: string, count: number }` for each bucket `("0-25", "25-50", "50-75", "75-100")`.
- **KpiDonutChart**: Render completitud vs faltantes distribution. Data shape: `{ labels: [...], datasets: [...] }` using recharts DonutChart.
- **KpiLineChart**: Render per-period trend from `kpisResumen`. The backend MUST expose a small `tendencia` field in `getKpisResumen` response with per-period `faltantes_pct` values (GROUP BY periodo over `cajas_inventarios`). If not available, the line chart renders a horizontal line at the average.

Each chart component accepts props matching its existing TypeScript interface and uses the `recharts` library (already a dependency, v2.15). No new chart dependencies are introduced.

- GIVEN KpisPanel has `distribucion_faltantes` data
- WHEN `KpiBarChart` renders
- THEN it displays 4 bars corresponding to the buckets with correct heights and colors
- GIVEN the same data + donut data
- WHEN `KpiDonutChart` renders
- THEN it shows completitud vs faltantes segments with legend
- GIVEN per-period trend data is available
- WHEN `KpiLineChart` renders
- THEN it shows a line chart with period on X-axis and faltantes_pct on Y-axis

### Requirement: Vertical Timeline Stepper for Historial

The system MUST render the `TecnicoHistorialModal` list as a vertical CSS timeline stepper (dot + line) with estado-colored indicators. The stepper MUST:

- Use a left vertical rail (`<ol>` or `<div>`) with connector lines between items
- Render a colored dot at each step representing the `estado` badge:
  - `cerrado` → red/gray dot (sol-estado-cancelado)
  - `borrador` → green dot (sol-estado-cumplido)
  - Other → neutral dot
- Each step shows the `periodo` label and the `estado` badge
- Reuses existing `sol-estado` badge CSS palette
- Is a11y compliant: uses semantic `<ol>/<li>` elements with proper `role` attributes
- No new dependencies (CSS-only timeline using existing classes)

The existing `TecnicoHistorialModal` flat list of expandable cards with `sol-estado` badges MUST be restyled into this vertical timeline format while preserving all the same data (periodo, estado, observaciones, detalle items).

- GIVEN the historial modal opens for a técnico
- WHEN the timeline renders
- THEN a vertical left rail with connector lines appears
- AND each step has a colored dot matching the inventario's estado
- AND the periodo label and estado badge are visible per step
- AND clicking a step expands/collapses the detalle for that inventario
- The timeline uses CSS only (no new JS libraries); transitions on hover of step items

### Requirement: Hover Transition and SidebarNav+ModuloCard Centering

The system MUST add subtle hover micro-transitions on hub cards and ensure SidebarNav+ModuloCard center correctly:

- **Card hover**: Each hub card MUST have a `transition: transform 0.2s ease, box-shadow 0.2s ease` style on hover, with a lift effect (`transform: translateY(-2px)`) and soft shadow
- **SidebarNav**: The `SidebarNav` component MUST center its icon labels correctly (existing `.nav-icon` emoji rendering). No layout shift on hover.
- **ModuloCard**: The `ModuloCard` component MUST center its icon properly. A TODO comment MUST document that lucide icon migration is out of scope for this change.
- **Emoji icon system**: Retain current emoji-based `icono` strings in `config/navegacion.ts`. Add a TODO comment block documenting the lucide migration intention for future scope.

- GIVEN a user hovers over a hub card
- WHEN the mouse is over the card
- THEN the card lifts slightly (`transform: translateY(-2px)`) and shows a soft shadow
- GIVEN SidebarNav renders nav items
- WHEN the page loads
- THEN emoji icons display correctly without shift
- GIVEN ModuloCard renders a module
- WHEN the module has an icon prop
- THEN the emoji displays with a TODO comment: "# TODO: migrar a lucide-react cuando se actualice el contrato del icono (out of scope Fase 2)"

## MODIFIED Requirements

### Requirement: KpisPanel BarList → KpiBarChart Integration

The system MUST replace the hand-rolled `BarList` component in `KpisPanel` with the existing `KpiBarChart` component for displaying `distribucion_faltantes`. The `BarList` inline styles and manual width calculations are REMOVED. The `KpiBarChart` renders the same distribution data using the recharts library, providing consistent chart styling, hover tooltips, and accessible `<svg>` output.

- GIVEN the current `KpisPanel` renders `BarList` with div-based bars
- WHEN `BarList` is replaced with `KpiBarChart`
- THEN the distribution bars are rendered via `<Bar>` component from recharts
- AND the colors, labels, and value displays match the existing `BarList` design (0-25 green, 25-50 yellow, 50-75 orange, 75-100 red)
- AND the `KpiBarChart` accepts `distribucion` prop: `Record<string, number>`
- AND the width/height/svg dimensions are handled by the component, removing inline pixel styles from `KpisPanel`
- Previously: `BarList` was a hand-rolled `div` with `%` width and manual color mapping

### Requirement: IdealCard Empty State → Illustration + CTA

The system MUST update `IdealCard` empty state to show an illustration component + CTA button instead of plain text hint. WHEN the ideal is null/empty, the card renders an illustration (using the project emoji system with TODO for lucide) with a "Definir Caja Ideal" CTA button that calls `onEdit`/`onDefineIdeal`. The empty state must also keep the "Sin definir" badge and hint text as a fallback.

- GIVEN IdealCard with no ideal
- WHEN the empty state renders
- THEN an illustration component with project emoji displays
- AND a "Definir Caja Ideal" button appears that calls the edit flow
- AND the "Sin definir" badge and hint remain as fallback text

### Requirement: TecnicosCards Empty State → Illustration + CTA

The system MUST update `TecnicosCards` empty state to show illustration + CTA when `items.length === 0`. WHEN no technicians are available, the grid area renders an illustration with emoji + CTA "Cargar técnicos" that navigates to the personal module's alta flow. The previous "Sin resultados" hint text is replaced.

- GIVEN TecnicosCards with no items
- WHEN the empty state renders
- THEN illustration + CTA "Cargar técnicos" appears
- AND the previous "Sin resultados para..." hint is removed

### Requirement: KpisPanel Empty State Refinement

The system MUST refine `KpisPanel` empty state to show illustration + CTA when `kpis.ideal_count === 0` or when no data exists. The current "Sin datos" plain text hint is replaced with an illustration component and a prominent "Definir Caja Ideal" CTA. The global técnico count stats may still display beneath the illustration as informational context.

- GIVEN KpisPanel with no ideal or no kpis data
- WHEN the empty state renders
- THEN illustration + CTA "Definir Caja Ideal" displays
- AND the "Sin datos" hint is removed
- AND total técnico stats remain visible below the illustration as context

## REMOVED Requirements

### Requirement: Hand-BarList in KpisPanel

The hand-rolled `BarList` component defined inline within `KpisPanel.tsx` IS REMOVED. Its functionality (distribution bar rendering) is replaced by the imported `KpiBarChart` from the recharts library. The `BarList` function with its manual `div` width calculations, inline color mappings, and `fontSize: "0.85rem"` styling is eliminated from the codebase.

- GIVEN the `BarList` function is removed from `KpisPanel`
- WHEN `KpisPanel` renders
- THEN `KpiBarChart` is used instead for distribution display
- AND no inline `BarList` definition exists in the file

### Requirement: Plain Text Loading States

Plain text "Cargando…" loading states in hub cards ARE REPLACED with `KpiSkeletonCard` components. The following files lose their inline `p className="sol-hint">Cargando…</p>` patterns and gain skeleton card renderings instead.

- GIVEN the cards previously showed "Cargando…" text
- WHEN the skeleton loads
- THEN `KpiSkeletonCard` or equivalent replaces the text
- AND the skeleton uses the card's existing styling classes

## RENAMED Requirements

No requirements renamed in this spec.