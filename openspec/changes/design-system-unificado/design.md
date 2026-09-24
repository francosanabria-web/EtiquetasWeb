# Design: Unified Design System (design-system-unificado)

## Technical Approach

Implement a hybrid design system using Tailwind v4 + shadcn/ui for the portal (Server/AppWebSalidas/apps/web) and buscador (Externas/AppPanolWeb), with a standalone tokens.css file for etiquetas (prueba_etiquetas_1). The design system will use a neutral monochrome palette based on the zinc color scheme, re-skinned from shadcn/ui's default blue accent to meet the user's constraint of no distinctive brand colors. Migration will follow a strict dependency order to avoid specificity wars: (0) git/vercel fix → (1) tokens → (2) shell/chrome → (3) portal modules → (4) buscador → (5) etiquetas.

## Architecture Decisions

### Decision: Shared Tokens Location and Consumption

**Choice**: Create shared tokens in `Server/AppWebSalidas/packages/design-tokens/tokens.css` as CSS custom properties, consumed via:
- Portal: Direct import in `src/index.css` 
- Buscador: Vendored copy via `scripts/sync-tokens.mjs` updating `src/index.css`
- Etiquetas: Direct link to portable `tokens.css` file

**Alternatives considered**: 
- Monorepo package (rejected: buscador must remain separate git repo per user constraint)
- CSS-in-JS solution (rejected: adds runtime overhead, doesn't work with vanilla HTML etiquetas)
- Individual token files per app (rejected: violates single source of truth requirement)

**Rationale**: CSS custom properties provide true runtime themeability, work across all three app types (React + vanilla HTML), and can be easily vendored. The packages/ location keeps tokens separate from app code while being accessible to both portal and sync script.

### Decision: Tailwind v4 Integration

**Choice**: Install `tailwindcss@4` and `@tailwindcss/vite` as dev dependencies in both portal and buscador. Configure Vite to use the Tailwind plugin. Map Tailwind's `@theme` to semantic CSS custom properties from the shared tokens. Use `data-theme` attribute for dark mode switching.

**Alternatives considered**:
- Tailwind v3 with JIT (rejected: v4 has better CSS var integration and performance)
- CSS-only approach without Tailwind (rejected: loses component primitives, utility class benefits, and build-time optimizations)
- CSS Modules approach (rejected: doesn't solve token sharing or provide utility classes)

**Rationale**: Tailwind v4 provides first-class CSS custom property support, excellent developer experience with utility classes, and integrates well with shadcn/ui. The `@theme` mapping allows us to use Tailwind's powerful configuration while maintaining our semantic token contract.

### Decision: Responsive Chrome Specifications

**Choice**: Implement chrome components with these exact specifications:
- Topbar: 56px height + safe-area-top inset (mobile <768px)
- BottomNav: 64px height + safe-area-bottom inset (mobile <768px) 
- Sidebar: 248px width (expanded), 72px width (collapsed) + backdrop
- Breakpoints: 640px (sm), 768px (md - chrome boundary), 1024px (lg), 1280px (xl)
- Container queries: `@container` for cards in resizable panels
- Touch targets: Minimum 44x44px interactive elements

**Alternatives considered**:
- Fluid breakpoint system (rejected: violates user-specified 768px chrome boundary requirement)
- Fixed pixel values without safe-area (rejected: causes iOS/Android display issues)
- Different sidebar widths (rejected: 248/72 matches existing patterns and provides good collapsed state)

**Rationale**: These values match the existing implementation explored in the exploration phase, provide proper mobile inset handling, and establish 768px as the clear mobile/desktop boundary for chrome layout as specified.

### Decision: Component Primitives Selection

**Choice**: Vendore these shadcn/ui components (all re-skinned to neutral zinc palette):
Button, Input, Select, Textarea, Checkbox, Switch, Dialog, Tabs, Card, Badge, Table, Skeleton, Toast, Tooltip, DropdownMenu, Sheet
Plus app-shell primitives: Sidebar, Topbar, BottomNav

**Alternatives considered**:
- Build custom components from scratch (rejected: unnecessarily duplicates community-tested solutions)
- Use different component libraries (e.g., Material-UI, Ant Design) (rejected: larger bundle sizes, less flexibility)
- Keep existing custom components and just apply tokens (rejected: doesn't fix class sprawl or duplication)

**Rationale**: shadcn/ui provides accessible, customizable primitives built on Radix UI with minimal bundle impact. The component list covers all UI needs identified in the exploration. Re-skimming to neutral zinc ensures compliance with the "no distinctive brand color" constraint.

### Decision: Buscador Git/Vercel Topology

**Choice**: Initialize git repo in `Externas/AppPanolWeb`, connect to dedicated GitHub repo, link to Vercel project. Implement `scripts/sync-tokens.mjs` that copies tokens and components from portal to buscador. Require immediate push after every change to trigger Vercel deployment.

**Alternatives considered**:
- Monorepo integration (rejected: violates user constraint that buscador stays separate)
- Manual upload to Vercel (rejected: error-prone, doesn't satisfy immediate push requirement)
- npm package for tokens (rejected: overkill for this scope, adds release pipeline complexity)

**Rationale**: Separate repo maintains buscador's independence while git/Vercel linkage provides reliable deployment. The sync script ensures token/component consistency between apps.

### Decision: Typography

**Choice**: Use `DM Sans, sans-serif` as the single font stack across all apps. Remove Source Serif 4 completely.

**Alternatives considered**:
- Keep both fonts with Source Serif 4 for display weights (rejected: adds complexity, violates neutral tonality goal)
- System UI font stack (rejected: loses the specific DM Sans branding the user wants to keep)
- Variable fonts only (rejected: insufficient browser support for all target environments)

**Rationale**: DM Sans provides clean, modern readability that works well for both UI and content. The user confirmed keeping DM Sans is acceptable, and removing Source Serif 4 simplifies the font stack while maintaining the desired aesthetic.

### Decision: In-App Catalog Route

**Choice**: Implement `/design-system` route in portal (`Server/AppWebSalidas/apps/web`) as a static catalog page using real components, replacing Storybook.

**Alternatives considered**:
- Maintain Storybook (rejected: higher maintenance burden for team size)
- No catalog (rejected: hinders adoption and component discovery)
- External documentation site (rejected: adds context switching, less integrated)

**Rationale**: An in-app route provides immediate access to the actual components in use, requires minimal maintenance, and serves as both documentation and testing ground.

### Decision: Migration Order

**Choice**: Strict sequential migration:
0. Git/vercel fix (buscador repo init + Vercel link)
1. Tokens (shared token file creation + consumption)
2. Shell/chrome (AppShell layout + responsive primitives)
3. Portal modules one-by-one (migrate each module to use design system)
4. Buscador (full re-skin using vendored tokens/components)
5. Etiquetas (restyle with portable tokens.css)

**Alternatives considered**:
- Parallel module migration (rejected: high risk of specificity wars during transition)
- Big-bang cutover (rejected: violates user's risk aversion, impossible to verify)
- Etiquetas first (rejected: creates dependency cycle, etiquetas needs tokens first)

**Rationale**: This order eliminates specificity wars by ensuring tokens are available before any component migration, establishes the foundation first, and validates the system incrementally.

### Decision: Guardrails

**Choice**: Implement `stylelint` rule blocking raw hex values outside of token files. Configure to allow only:
- Token references (`var(--token-name)`)
- Whitelisted exceptions (border: none, transparent gradients)

**Alternatives considered**:
- Pre-commit hooks only (rejected: can be bypassed, doesn't protect runtime)
- Code review reliance (rejected: subjective, inconsistent enforcement)
- CSS variables with !important (rejected: breaks cascade, causes maintenance issues)

**Rationale**: Automated linting provides immediate feedback during development, prevents token contract violations, and scales with team size. The rule is specific enough to be useful without being overly restrictive.

## Data Flow

### Token Consumption Flow

    Shared Tokles (packages/design-tokens/tokens.css)
                     │
         ┌───────────┴───────────┐
         │                       │
 Portal Import         Vendored Copy
 (src/index.css)   ← sync-tokens.mjs → (Externas/AppPanolWeb/src/index.css)
         │                       │
         ▼                       ▼
    Tailwind @theme         CSS Vars
         │                       │
    Utility Classes         Component Styles
         │                       │
    ◄─────── Shared Semantic Contract ───────►

### Dark Mode Flow

    User Action
         │
    localStorage["panol_theme"] Update
         │
    document.documentElement.setAttribute("data-theme", "light|dark")
         │
    CSS Media Query: [data-theme="dark"] { ... }
         │
    Token Values Swap (Light ↔ Dark Palette)

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `Server/AppWebSalidas/packages/design-tokens/tokens.css` | Create | CSS custom properties for neutral monochrome theme (light/dark), typography, spacing, radius, status semantics |
| `Server/AppWebSalidas/apps/web/src/index.css` | Modify | Replace token layer with `@import` to shared tokens + Tailwind base styles; remove legacy tokens and module CSS references |
| `Server/AppWebSalidas/apps/web/src/styles/salidas.css` | Delete | Migrate styles to shared primitives, file becomes empty then removed |
| `Server/AppWebSalidas/apps/web/src/styles/reportes.css` | Delete | Migrate styles to shared primitives, file becomes empty then removed |
| `Server/AppWebSalidas/apps/web/src/styles/kpis.css` | Delete | Migrate styles to shared primitives, file becomes empty then removed |
| `Server/AppWebSalidas/apps/web/src/styles/activos.css` | Delete | Migrate styles to shared primitives, file becomes empty then removed |
| `Server/AppWebSalidas/apps/web/src/layouts/AppShell.tsx` | Modify | Integrate responsive chrome primitives (Sidebar, Topbar, BottomNav) and add `/design-system` route |
| `Server/AppWebSalidas/apps/web/src/components/*` | Modify | Replace custom classNames with design system primitives (Button, Card, etc.) - done module-by-module |
| `Externas/AppPanolWeb/src/index.css` | Modify | Replace blue palette tokens with vendored neutral tokens; remove duplicate `Colors` JS object |
| `Externas/AppPanolWeb/src/App.tsx` | Modify | Remove `Colors` JS object and associated theme context |
| `Externas/AppPanolWeb/src/mapa/UbicacionScreen.tsx` | Modify | Replace local `COLORS` map with shared status tokens |
| `Externas/AppPanolWeb/vercel.json` | Create | Vercel configuration for project deployment |
| `Externas/AppPanolWeb/.git` | Create | Initialize git repository (directory) |
| `Externas/AppPanolWeb/.gitignore` | Create | Standard git ignore for Node/Vercel project |
| `Externas/AppPanolWeb/scripts/sync-tokens.mjs` | Create | Node script to copy tokens and components from portal to buscador |
| `Server/AppWebSalidas/prueba_etiquetas_1/etiquetas_web/index.html` | Modify | Replace inline `<style>` with link to portable `tokens.css` and update class names to use design system |
| `Server/AppWebSalidas/packages/design-tokens/tokens.ts` | Create | TypeScript module exporting token values for Recharts consumption |
| `Server/AppWebSalidas/apps/web/src/pages/design-system.tsx` | Create | In-app catalog route displaying all design system components |
| `Server/AppWebSalidas/apps/web/vite.config.ts` | Modify | Add `@tailwindcss/vite` plugin |
| `Externas/AppPanolWeb/vite.config.ts` | Modify | Add `@tailwindcss/vite` plugin |

## Interfaces / Contracts

### Token Contract (packages/design-tokens/tokens.css)
```css
/* Light Theme */
:root {
  --background: #fff;
  --foreground: #171717;
  --muted: #f4f4f5;
  --muted-foreground: #71717a;
  --popover: #fff;
  --popover-foreground: #171717;
  --card: #fff;
  --card-foreground: #171717;
  --border: #e4e4e7;
  --input: #e4e4e7;
  --primary: #18181b;
  --primary-foreground: #fafafa;
  --secondary: #f4f4f5;
  --secondary-foreground: #18181b;
  --accent: #f4f4f5;
  --accent-foreground: #18181b;
  --destructive: #f44336;
  --destructive-foreground: #fafafa;
  --border-input: #e4e4e7;
  --ring: #a1a1aa;
  --radius: 0.625rem;
  
  /* Typography */
  --font-sans: "DM Sans", sans-serif;
  --font-size-base: 1rem;
  --font-size-sm: 0.875rem;
  --font-size-lg: 1.125rem;
  --font-size-xl: 1.25rem;
  --font-size-2xl: 1.5rem;
  --font-size-3xl: 1.875rem;
  --font-size-4xl: 2.25rem;
  --leading-none: 1;
  --leading-tight: 1.25;
  --leading-snug: 1.375;
  --leading-normal: 1.5;
  --leading-relaxed: 1.625;
  --leading-loose: 2;
}

/* Dark Theme */
[data-theme="dark"] {
  --background: #0a0a0a;
  --foreground: #fafafa;
  --muted: #1b1b1e;
  --muted-foreground: #a1a1aa;
  --popover: #0a0a0a;
  --popover-foreground: #fafafa;
  --card: #141416;
  --card-foreground: #fafafa;
  --border: #242428;
  --input: #242428;
  --primary: #e4e4e7;
  --primary-foreground: #18181b;
  --secondary: #1b1b1e;
  --secondary-foreground: #e4e4e7;
  --accent: #1b1b1e;
  --accent-foreground: #e4e4e7;
  --destructive: #f44336;
  --destructive-foreground: #fafafa;
  --border-input: #242428;
  --ring: #a1a1aa;
  --radius: 0.625rem;
  
  /* Typography (same as light) */
  --font-sans: "DM Sans", sans-serif;
  --font-size-base: 1rem;
  /* ... */
}

/* Status Semantics (unchanged by theme) */
:root, [data-theme="dark"] {
  --success: #4ade80;
  --warning: #fbbf24;
  --danger: #f87171;
  --info: #60a5fa;
  --success-foreground: #064e3b;
  --warning-foreground: #92400e;
  --danger-foreground: #991b1b;
  --info-foreground: #1e3a8a;
}
```

### Recharts Token Interface (packages/design-tokens/tokens.ts)
```typescript
export const tokens = {
  // Neutral palette
  background: '#fff',
  foreground: '#171717',
  muted: '#f4f4f5',
  mutedForeground: '#71717a',
  primary: '#18181b',
  primaryForeground: '#fafafa',
  
  // Status colors
  success: '#4ade80',
  warning: '#fbbf24',
  danger: '#f87171',
  info: '#60a5fa',
  
  // Dark mode overrides
  dark: {
    background: '#0a0a0a',
    foreground: '#fafafa',
    muted: '#1b1b1e',
    mutedForeground: '#a1a1aa',
    primary: '#e4e4e7',
    primaryForeground: '#18181b',
  }
};

// Helper to get theme-aware values
export function getToken<T extends keyof typeof tokens>(key: T, isDark: boolean = false): typeof tokens[T] {
  if (isDark && tokens.dark && key in tokens.dark) {
    return tokens.dark[key as keyof typeof tokens.dark];
  }
  return tokens[key];
}
```

### Component Primitives Interface
All components follow Radix UI accessibility standards and accept:
- `className:` for extension
- Standard React props for their element type
- Variants via `cva()` (class-variance-authority) where applicable
- Explicit size variants: `sm`, `default`, `lg` where relevant

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit | Token values and TypeScript mappings | Jest tests for `tokens.ts` module; validate light/dark values and getToken function |
| Integration | Theme switching and component rendering | Render AppShell with light/dark themes; verify CSS var application and class application |
| E2E | Visual regression and responsive breakpoints | Playwright tests capturing screenshots at 320px, 640px, 768px, 1024px, 1280px, 1920px; verify chrome layout transitions and touch target sizes |
| Manual | Token contract compliance | Stylelint runs on all CSS/TS files; manual verification of buscador deployment after sync script execution |

## Threat Matrix

N/A — no routing, shell, subprocess, VCS/PR automation, executable-file classification, or process-integration boundary.

## Migration / Rollout

**Migration**: Strictly sequential as outlined in Migration Order section. Each phase must be verified complete before proceeding to next.

**Rollback Plan**:
1. **Portal**: Revert commit or restore `src/index.css` and `src/styles/` from git commit; remove Tailwind/shadcn dependencies
2. **Buscador**: Revert git commit in `Externas/AppPanolWeb` and push to trigger Vercel deployment rollback
3. **Etiquetas**: Revert `<style>` link or CSS variable overrides in `index.html`
4. **Shared tokens**: Delete `packages/design-tokens/` directory and remove imports

## Open Questions

- [ ] Confirmation that Source Serif 4 removal is acceptable (exploration flagged this as taste call)
- [ ] Final decision on in-app catalog vs Storybook (exploration recommended in-app route)
- [ ] Exact timing for introducing container queries (may need refactoring of resizable panels first)

## Key Learnings
1. Neutral monochrome theme requires careful re-skinning of shadcn/ui's default zinc-blue theme to pure neutral palette
2. Buscador's lack of git is a blocker that must be resolved before any styling changes
3. Migration order is critical to avoid specificity wars between legacy and design system styles
4. Token contract must include both CSS custom properties and TypeScript/JavaScript equivalents for chart library consumption
5. 768px breakpoint is the established mobile/desktop boundary for chrome layout based on existing implementation