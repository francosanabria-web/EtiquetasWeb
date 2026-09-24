# Exploration: design-system-unificado

**Change**: `design-system-unificado` | **Phase**: exploration | **Date**: 2026-09-17
**Primary openspec store**: `Server/AppWebSalidas/openspec/changes/design-system-unificado/` (the git-backed project; the workspace-root `sistemas_panol/openspec/config.yaml` is a placeholder and is noted only).

## Current State

Three frontends, three unrelated styling systems, no shared token source:

### A. Portal principal — `Server/AppWebSalidas/apps/web`
- React 19 + Vite 6, react-router 7, recharts, firebase 11. **No Tailwind, no CSS framework.**
- One monolithic `src/index.css` (~2,520 lines, global classes) + 4 module CSS files (`salidas.css`, `reportes.css`, `kpis.css`, `activos.css`).
- Hand-rolled tokens on `:root, [data-theme="light"]` and `[data-theme="dark"]`: `--bg, --surface, --sidebar*, --text, --muted, --primary, --primary-dark, --border, --danger, --radius, --sidebar-w*`, fonts `--font: "DM Sans"` + `--font-display: "Source Serif 4"`.
- Theme persistence: `localStorage["panol_theme"]` + `document.documentElement.setAttribute("data-theme", ...)` in the shell. Sidebar collapse key `localStorage["panol_sidebar"]`-style key.
- **Theme token leakage**: module CSS hardcodes hex values (`#f4f6f9`, `#1e293b`, `#dbe3ec` in kpis.css; `#1f4e78`, `#f8fafc`, `#f0fdf4`… in index.css), then patches ~15 `[data-theme="dark"]` overrides at the bottom of index.css. Double source of truth.
- Responsive contract partially implemented: `@media (max-width: 768px)` switches to `.mobile-topbar` (56px, safe-area-inset-top), drawer sidebar (`transform: translateX`, backdrop), `.mobile-bottom-nav` (64px, safe-area-inset-bottom); `100dvh`, `-webkit-overflow-scrolling`, 44px touch targets, `font-size:16px` inputs to kill iOS zoom. Breakpoint set in use: **only 768px and one 960px** — no 640/1024/1280 scale.
- Components are custom classNames (`.mod-card`, `.sol-*`, `.minuta-*`, `.usr-*`, `.cajas-*`) — no shared Card/Button/Input primitives; styles vary subtly per module.

### B. Buscador externo — `Externas/AppPanolWeb`
- React 19 + Vite 6, firebase 12, xlsx. Single `src/index.css` (537 lines, global classes).
- Its own token set: `--bg #ecf0f1, --card, --text #2c3e50, --border, --primary #3498db (blue), --stock, --ubic, --icon`. Dark mode via `[data-theme="dark"]`, primary stays blue in both.
- **Duplicate theme logic**: a `Colors: Record<ThemeName, {...}>` JS object in `App.tsx` (~line 37) feeding a React `theme` context AND the CSS custom properties — two sources of truth for one decision. `UbicacionScreen.tsx` has yet another local `COLORS` palette for the map.
- Mobile-only chrome: fixed `.tabbar` bottom, `env(safe-area-inset-*)` handled, `padding-bottom: 88px` on screens. No desktop layout at all.
- **No `.git` directory** (tested: False). No `vercel.json` — Vercel deploys work from a remote repo (implicit) or manual upload; the working copy on this machine is NOT git-tracked. This is a concrete inconsistency: any change must be committed/pushed somewhere, and locally there is no link to that remote.

### C. Etiquetas — `Server/AppWebSalidas/prueba_etiquetas_1`
- `etiquetas_web/index.html`: vanilla single-file app, inline `<style>` with its own flat-UI palette (`--azul #2c3e50 --verde #27ae60 --rojo #c0392b --gris #ecf0f1`), one `@media(max-width:760px)` rule, no theme switch.
- Not integrated into the portal shell; served standalone next to `modulo_etiquetas.py` (print agent).

## Affected Areas

- `Server/AppWebSalidas/apps/web/src/index.css` — replace token layer; keep as theme-bridge or delete progressively.
- `Server/AppWebSalidas/apps/web/src/styles/{salidas,reportes,kpis,activos}.css` — migrate to shared primitives.
- `Server/AppWebSalidas/apps/web/src/components/*` (kpis, activos, shared/BuscadorCatalogo) and `src/modules/*` — restyle to tokens.
- `Server/AppWebSalidas/apps/web/src/layouts/AppShell.tsx` + `components/SidebarNav.tsx` — chrome components (topbar/drawer/bottom-nav) become design-system primitives.
- `Externas/AppPanolWeb/src/index.css`, `src/App.tsx` (remove `Colors` object), `src/mapa/UbicacionScreen.tsx` (replace `COLORS`), + **git setup + Vercel link**.
- `Server/AppWebSalidas/prueba_etiquetas_1/etiquetas_web/index.html` — restyle with shared tokens (portable CSS-variables file) or integrate into portal.
- New: shared tokens artifact (e.g. `packages/design-tokens/` or `shared/tokens.css`) consumed by portal and copied to buscador.

## Design Debt Inventory (tonality conflicts)

| Concern | Portal (A) | Buscador (B) | Etiquetas (C) |
|---|---|---|---|
| Primary accent | teal `#0e7c66` / `#1fa887` | blue `#3498db` | navy `#2c3e50` + green/red |
| Font | DM Sans + Source Serif 4 | system-ui | Segoe UI/Arial |
| Token host | `:root` + css-vars | `:root` css-vars + `Colors` JS object + `COLORS` map | CSS scoped vars |
| Dark mode | full (with patch-overrides) | yes | none |
| Spacing/radius | `--radius: 12px`, ad-hoc per module | 6–15px ad-hoc | 8–12px, `.card` pattern |
| Breakpoints | 768, 960 | none (mobile-only) | 760 |

To honor the user's constraint (**no distinctive brand color; primary must be neutral** — light = whites/grays, dark = near-black/grays), today's teal/blue/navy accents all violate the target contract and must migrate to a neutral scale.

## Approaches

### 1. Tailwind v4 + shadcn/ui + shared token package (user-chosen Option A)
- `packages/design-tokens` (or `shared/ui/tokens.css`) exporting one `@theme` block + `shadcn`-style semantic vars (`--background, --foreground, --card, --primary,*…` mapped to a neutral gray ramp).
- Portal installs `tailwindcss@4` + `@tailwindcss/vite`, shadcn/ui components (Radix primitives). Buscador installs the same and *copies* the vendored `components/ui` + `tokens.css` (it must build standalone for Vercel).
- Pros: industry standard; single semantic contract; dark mode via class/`data-theme`; tree-shaken CSS; fixes duplication by construction.
- Cons: biggest initial migration (2,500+ lines of CSS to replace); shadcn defaults are blue/zinc — must re-skin to neutral; buscador sync is manual.
- Effort: **High** (one-time), Low ongoing.

### 2. Shared CSS-variables only (no Tailwind)
Keep hand-written CSS, extract one `tokens.css` imported everywhere; progressively align values.
- Pros: lowest risk, no build changes, trivially shareable with etiquetas (vanilla).
- Cons: doesn't fix component duplication, class sprawl, or the kpi/index.css override mess; no guardrails.
- Effort: Medium.

### 3. Hybrid (recommended): Option A for the two React apps + tokens-only file for etiquetas
Adopt #1 for portal + buscador; expose `tokens.css` (same `@theme`/vars, no Tailwind dependency) that `etiquetas/index.html` links. Etiquetas keeps vanilla code but adopts values — cheap, no bundler.
- Effort: High but staged.

### Git strategy for the buscador (decision needed at propose phase)
The buscador lives outside the portal's git repo and currently has no local git at all:
- **Option (a) — separate repo (recommended)**: `git init` in `Externas/AppPanolWeb`, push to its own GitHub repo, link Vercel project to it. The shared `tokens.css` + `components/ui` are *vendored copies*; a tiny script (`scripts/sync-tokens.mjs`) copies from portal path and the change checklist demands committing both. Fits the "small app, external service" reality; Vercel integration is trivial.
- **Option (b) — monorepo**: move `Externas/AppPanolWeb` into the `Server/AppWebSalidas` repo (or a new workspace) and deploy Vercel from a subdirectory; tokens then shared via normal imports. Cleaner long-term, but changes deploy topology and requires repo surgery now.
- Option (c) — npm package for tokens: overkill, adds release pipeline.

## Proposed Design Contract (to be refined in design phase)

### Neutral semantic tokens (`:root` `[data-theme]`, Tailwind `@theme` mapping)
- Light: `--background: #fff / #f7f7f8`, `--foreground: #171717`, `--muted: #f4f4f5` / `--muted-foreground: #71717a`, `--card: #fff`, `--border: #e4e4e7`, `--primary: #18181b` (neutral near-black, NOT a brand color), ring `--ring: #a1a1aa`.
- Dark: `--background: #0a0a0a`, `--foreground: #fafafa`, `--muted: #1b1b1e`/--muted-foreground: #a1a1aa, `--card: #141416`, `--border: #242428`, `--primary: #e4e4e7`.
- Status colors kept semantic-only: `--success/--warning/--danger/--info` (single ramp each, muted saturation, used only for estado/stock semantics — incl. existing minuta importance states).
- Type scale: `--font-sans: system/DM Sans` (decide: keep DM Sans for continuity or system-ui for speed — propose keeping DM Sans, drop Source Serif display to one display weight or remove); scale 12/13/14/16/18/20/24/30; line-heights 1.25–1.5.
- Spacing/radius/shadow: Tailwind defaults, `--radius: 0.625rem` base; shadows limited to sm/md/lg.
- Breakpoints: keep Tailwind `sm 640 / md 768 / lg 1024 / xl 1280`; **768 stays the mobile-chrome boundary** to match existing chrome; container queries (`@container`) for cards inside resizable panels.
- Mobile chrome contract: `<768px` → topbar (56px + safe-area-top) + bottom-nav (64px + safe-area-bottom), drawer sidebar with backdrop; `>=768px` → sidebar (248/72 collapsed). Buscador: keep bottom tabbar on all sizes for now (it's phone-first), optionally max-width shell on desktop.
- Component inventory to unify (shadcn basis): Button, Input, Select, Textarea, Checkbox, Switch, Dialog/Modal, Tabs, Card, Badge, Table, Skeleton, Toast, Tooltip, DropdownMenu, Sheet (drawer), plus app-shell primitives (Sidebar, Topbar, BottomNav) — replacing `.btn-*`, `.sol-*`, `.minuta-modal`, `.badge`, `.tab`, `.seg-*`, card variants, etc.

### Routing rule for punctual changes (answers the user's question)
Define an explicit "design-system compliance" routing once the system is live:
- **Tier 1 — Direct inline edit** (1 file, no new tokens/components, no new behavior): e.g., "mover un checklist dentro de la minuta", changing a label, reordering fields. No SDD; just comply with existing tokens/components. Example: moving the minuta contactos checklist into another section = edit one `.tsx`; done.
- **Tier 2 — Direct delegated edit** (2–5 files or one new composed pattern from existing primitives): e.g., a new filter row using existing Input+Select. No SDD proposal; a conventional commit referencing the design contract.
- **Tier 3 — Full/light SDD** (new token, new component primitive, cross-app chrome change, or anything touching the shared token file or the buscador sync): e.g., new KPI card type, new breakpoint behavior, new status color → proposal (possibly "light": proposal+tasks, skip full spec nitty-gritty by orchestrator decision).
- Hard rule: if a change needs a value not in the token contract, the correct path is Tier 3 — never hardcode.

## Risks

- **Buscador has no local git**: deploying changes to it is currently unverifiable; first task must be git setup + Vercel link confirmation before any styling changes land there.
- **Big-bang CSS migration per module**: 2.5k-line index.css with dark-mode patch overrides; partial migration could leave two systems fighting (specificity wars). Mitigate with per-module migration order and token-first for new work.
- **shadcn default theme is zinc-blue**; failing to re-skin to neutral reintroduces "accent color" against the user's constraint.
- **Recharts** colors in KPIs are hardcoded in JS — tokens must be exported to JS too (CSS var read or a `tokens.ts` module) for charts.
- **Etiquetas** is vanilla HTML; no build step; only CSS-var contract is feasible there — accept divergence in *mechanism*, not in *values*.
- Source Serif display font removal is a taste call — flag for user confirmation.
- Dual Firebase versions (11 portal / 12 buscador) — unrelated but noted.

## Tooling / MCP recommendations

- **context7** (already connected — use for Tailwind v4 & shadcn docs during design/apply).
- `tailwindcss@4` + `@tailwindcss/vite` plugin, `class-variance-authority`, `clsx`, `tailwind-merge`, `lucide-react`, `tw-animate-css`; shadcn CLI (`npx shadcn@latest init`).
- **Storybook**: optional; with this team size, a simple internal `/design-system` route (catalog page using the real components) is probably enough — cheaper than Storybook infra. Decide at design phase.
- Prettier for CSS/TS formatting consistency (no linter currently configured).
- Optional: `stylelint` on token files to block raw hex outside tokens (guardrail for the "no ad-hoc values" rule).

## Recommendation

**Approach 3 (hybrid)**: Tailwind v4 + shadcn/ui for portal and buscador, neutral re-skin per the contract above, vendored token+ui copies in buscador with a sync script and its own git repo (option a), tokens-only CSS for etiquetas. Migrate in dependency order: (0) git/vercel fix → (1) tokens → (2) portal shell/chrome → (3) portal modules one by one → (4) buscador re-skin → (5) etiquetas restyle.

## Ready for Proposal

**Yes** — pending two user confirmations to encode in the proposal:
1. Git strategy for buscador: separate repo (a) vs monorepo (b)? (recommend a)
2. Typography: keep DM Sans + drop Source Serif 4, acceptable? And confirm Storybook skip in favor of an in-app catalog route.
