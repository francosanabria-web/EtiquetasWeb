# Proposal: Unified Design System (design-system-unificado)

## Intent

Unify design, tonality, theme logic, and responsiveness across all three web frontends (`Server/AppWebSalidas/apps/web`, `Externas/AppPanolWeb`, and `prueba_etiquetas_1`) using a neutral monochrome design system based on Tailwind v4, shadcn/ui, and shared design tokens.

## Scope

### In Scope
- **Shared Tokens**: CSS custom properties for neutral monochrome theme (light/dark) and status semantics.
- **Tailwind v4 + shadcn/ui**: Adopted in portal (`AppWebSalidas/apps/web`) and buscador (`Externas/AppPanolWeb`).
- **Portable Tokens File**: CSS-only custom properties for standalone etiquetas (`prueba_etiquetas_1`).
- **Buscador Git & Vercel Link**: Initialize git repo in `Externas/AppPanolWeb`, connect GitHub remote, verify Vercel deployment link, and vendor tokens/components via `scripts/sync-tokens.mjs`.
- **Responsive Contract**: Mobile/desktop chrome boundary at `768px` (56px topbar, 64px bottom nav, drawer sidebar, safe-area insets, container queries).
- **In-App Catalog Route**: `/design-system` route in portal replacing Storybook.
- **3-Tier Change Model**: Operating rules for post-migration updates (Tier 1 direct inline 1 file, Tier 2 direct delegated 2–5 files, Tier 3 SDD for tokens/cross-app).

### Out of Scope
- Monorepo structural merge (buscador stays separate git repo).
- Backend API or Python microservices modifications.
- Storybook integration.
- Upgrading Firebase SDK versions across apps.

## Capabilities

### New Capabilities
- `design-tokens`: Shared CSS variables for neutral monochrome theme (light/dark), typography scale (DM Sans), spacing, and status semantics across frontends.
- `responsive-chrome`: Standardized viewports (640/768/1024/1280) with 768px mobile chrome boundary and safe-area insets.
- `component-primitives`: Standardized UI components (Button, Input, Card, Modal, Select, Badge, Table, Skeleton) replacing module CSS overrides.
- `design-system-operating-model`: 3-tier routing rules governing future UI edits.

### Modified Capabilities
None

## Approach

- **Hybrid Model**: Tailwind v4 + shadcn/ui for portal and buscador; standalone token CSS for etiquetas.
- **Topology & Prerequisite**: `Server/AppWebSalidas` (portal repo), `Externas/AppPanolWeb` (separate repo after `git init`). **CRITICAL PREREQUISITE**: Initialize git and verify Vercel deployment in `Externas/AppPanolWeb` BEFORE migrating styles. Every buscador commit must be pushed immediately to trigger Vercel deployment.
- **Palette & Typography**: Neutral monochrome (Light: `#ffffff` bg, `#18181b` primary; Dark: `#0a0a0a` bg, `#e4e4e7` primary). Single font stack: `DM Sans, sans-serif` (dropping Source Serif 4).
- **Vendor Sync**: `scripts/sync-tokens.mjs` copies token and component primitives from portal to buscador.

## 3-Tier Operating Model

- **Tier 1 (Direct inline, 1 file)**: Minor structural/content edits using existing primitives (e.g., moving checklist inside a minuta panel). No SDD needed.
- **Tier 2 (Direct delegated, 2–5 files)**: Composing existing primitives into new module screens/filters. No SDD needed.
- **Tier 3 (Full/Light SDD)**: Modifying design tokens, adding UI primitives, or cross-app chrome changes.

## Pending Decisions & Assumptions

1. **Buscador Topology**: Separate repo at `Externas/AppPanolWeb` with vendored tokens synced via script (Assumed default; monorepo deferred).
2. **Typography**: Single font stack `DM Sans, sans-serif` across all apps (Assumed default; Source Serif 4 dropped).
3. **Component Catalog**: In-app `/design-system` route in portal (Assumed default; Storybook skipped).

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `Server/AppWebSalidas/apps/web/src/index.css` | Modified | Replace legacy token layer with Tailwind v4 `@theme` and semantic CSS custom properties |
| `Server/AppWebSalidas/apps/web/src/styles/*.css` | Removed | Migrate `salidas`, `reportes`, `kpis`, `activos` custom CSS into shared primitives |
| `Server/AppWebSalidas/apps/web/src/layouts/AppShell.tsx` | Modified | Integrate responsive chrome primitives and `/design-system` catalog route |
| `Externas/AppPanolWeb/src/index.css` | Modified | Replace blue palette and dual `Colors` JS object with vendored neutral tokens |
| `Externas/AppPanolWeb/src/mapa/UbicacionScreen.tsx` | Modified | Align local `COLORS` map with shared status tokens |
| `Server/AppWebSalidas/prueba_etiquetas_1/etiquetas_web/index.html` | Modified | Link portable `tokens.css` for palette alignment |
| `scripts/sync-tokens.mjs` | New | Script to vendor tokens and shadcn primitives into buscador repo |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Unversioned Buscador code | High | Mandatory `git init` + Vercel link verification before writing code changes |
| Monolithic CSS override conflict | High | Sequential module migration order; eliminate bottom-override patches in `index.css` |
| Recharts JS color hardcoding | Med | Export token values as JS/TS module (`tokens.ts`) for chart component consume |
| Default shadcn blue accent leakage | Med | Explicitly override default shadcn color definitions with neutral zinc scale |

## Rollback Plan

1. **Portal**: Revert commit or restore `src/index.css` and `src/styles/` from git commit.
2. **Buscador**: Revert git commit in `Externas/AppPanolWeb` and push to trigger Vercel deployment rollback.
3. **Etiquetas**: Revert `<style>` link or CSS variable overrides in `index.html`.

## Dependencies

- Tools: `git`, `gh` CLI, Vercel account link.
- NPM packages: `tailwindcss@4`, `@tailwindcss/vite`, `lucide-react`, `clsx`, `tailwind-merge`, `class-variance-authority`.
- Backend Isolation: Firebase auth/catalog boundaries remain unchanged.

## Success Criteria

- [ ] All 3 frontends render a unified neutral monochrome palette (white/black per theme).
- [ ] Portal and Buscador build with Tailwind v4 and consume shared design tokens.
- [ ] Buscador is git-tracked, linked to Vercel, and deploys on every push.
- [ ] Typography is unified on `DM Sans, sans-serif` across all apps.
- [ ] Portal renders in-app component catalog route at `/design-system`.
- [ ] Responsive chrome transitions cleanly at `768px` breakpoint.
