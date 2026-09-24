# Shell Central — apps/web

**Última actualización:** 2026-08-07

Módulo de producto: [[02 - Módulos/Shell_Central]].

## Ruta del proyecto

```
C:\Users\Mantenimiento\Desktop\AppWebSalidas\apps\web
```

## Stack

| Capa | Tecnología |
|------|------------|
| Build | Vite **6** |
| UI | React **19** + TypeScript |
| Routing | react-router-dom **7** |
| Auth | Servicio `usuarios` (:8015) + Bearer en shell |
| Estilos | CSS vanilla (`index.css`) + temas claro/oscuro |
| Tipografía | DM Sans + Source Serif 4 |
| Deploy config | `vercel.json` (SPA rewrite) |

## Identidad / UX shell

- Sidebar colapsable (persistido en `localStorage`) — **solo desktop**.
- Modo oscuro: switch en pie del sidebar (`data-theme` en `<html>`).
- Acento verde pañol (`#0e7c66`); fondos con gradiente sutil.
- Clase `.btn-secondary` definida en estilos del shell.

## Responsive / móvil (2026-08-07)

Breakpoint principal: **≤768px** (`AppShell` + `index.css`). Clase `is-mobile` en el shell.

| Pieza | Comportamiento |
|-------|----------------|
| Top bar sticky | Hamburger + marca + título de página actual |
| Sidebar | Off-canvas drawer; cierra al navegar / Escape / backdrop |
| Bottom quick nav | Inicio, Salidas, Activos, Solicitudes (filtrado por permisos) |
| Viewport | `safe-area-inset`, `100dvh`, `viewport-fit=cover` |
| Meta | `theme-color`, `apple-mobile-web-app-*` en `index.html` |
| Touch | Targets ≥44px; inputs `font-size: 16px` en móvil (evita zoom iOS) |
| Padding | Consistente en `sol-page`, `minuta-page`, `rep-page` |

**Desktop:** colapso de sidebar (iconos vs labels) sin cambios. **Móvil:** el colapso se ignora; el drawer siempre muestra labels.

### UI móvil por módulo (además del shell)

| Módulo | Adaptación |
|--------|------------|
| Salidas | Carga pendiente en cards (no tabla) por debajo de **900px** |
| Activos | Listado en cards por debajo de **768px** (checkbox, equipo, días, sector, proveedor) |
| Minuta | ⚠️ Editor no phone-optimized (tabla ancha + drag HTML5) |
| KPIs / Reportes | Orientados a consulta en teléfono; sin rediseño mobile-first |

## Puertos

| Modo | URL |
|------|-----|
| Dev | `http://localhost:5180` |
| Preview | `:5180` (`vite.config.ts`) |

## Variables de entorno

Archivo: `.env.example` / `.env.local`

| Variable | Uso |
|----------|-----|
| `VITE_ETIQUETAS_URL` | Enlace externo módulo etiquetas (LAN) |
| `VITE_EMAIL_API_URL` | API correo (default `http://localhost:8020`) |
| `VITE_BUSCADOR_URL` | AppPanolWeb en Vercel |
| `VITE_SOLICITUDES_API_URL` | Opcional; vacío = proxy `/api/solicitudes` → :8014 |

## Rutas

| Ruta | Componente | Estado |
|------|------------|--------|
| `/login` | `LoginPage` | ✅ Auth real (:8015) |
| `/` | `HomePage` | Cards por permiso |
| `/salidas` | `SalidasPage` | 🔄 En desarrollo (móvil: cards carga) |
| `/reportes` | `ReportesPage` | 🟡 Operativo (consulta) |
| `/activos` | `ActivosFueraPage` + panel | 🔄 F2 OK (móvil: cards listado) |
| `/kpis` | `KpiDashboard` | ✅ Implementado |
| `/minuta` | `MinutaListadoPage` | ✅ Listado reuniones |
| `/minuta/:reunionId` | `MinutaReunionPage` | ✅ Sesión; ⚠️ no phone-optimized |
| `/solicitudes` | `SolicitudesPage` | ✅ Pedidos + TR + PDF |
| `/usuarios` | `UsuariosPage` | ✅ Solo admin |

## Arranque en producción (PC pañol) — supervisor

Paralelo a la red de impresión (`RedImpresionPanol`). **No toca** :8010 / :5173 / print-agent.

| Pieza | Archivo |
|-------|---------|
| Supervisor | `scripts/supervisor_panol.ps1` |
| Autostart (tarea `PortalPanol`) | `scripts/instalar_autostart_panol.ps1` |
| Estado | `scripts/estado_panol.ps1` |
| Frenar | `scripts/detener_panol.ps1` (`-Desinstalar` quita la tarea) |

Servicios vigilados (~20 s): KPIs `:8001`, Minuta `:8013`, Solicitudes `:8014`, Usuarios `:8015`, Email `:8020`, Portal `:5180`.

- Si un puerto cae → se vuelve a levantar.
- Si el puerto escucha pero `/health` está muerto → reinicio de ese servicio (KPIs admite 503 = cargando Excel).
- **Reinicio suave diario:** una vez entre **20:00 y 22:00** (marker `scripts/logs/panol_reinicio_diario.marker`).

⚠️ No usar `INICIAR_TODO.bat` mientras `PortalPanol` esté activo (mismos puertos).

**Nota operativa en el repo:** `COMO_PORTAL.txt` (estado, detener, instalar, URLs).

## Arranque manual (dev / sin tarea)

```
C:\Users\Mantenimiento\Desktop\AppWebSalidas\scripts\INICIAR_TODO.bat
```

Levanta ventanas visibles: KPIs, Minuta, Email, Solicitudes, Usuarios, Portal.

## Auth

Login real vía `/api/usuarios`. Sesión: `localStorage` clave `panol_shell_session` (token Bearer).

## Navegación

Fuente única: `src/config/navegacion.ts` — sidebar + cards inicio + bottom nav móvil (subconjunto de campo).

## Arranque

```powershell
cd "C:\Users\Mantenimiento\Desktop\AppWebSalidas\apps\web"
npm install   # primera vez
npm run dev
```

## Estructura relevante

```
apps/web/src/
├── App.tsx
├── api/emailClient.ts
├── auth/
├── components/     # SidebarNav, ModuloCard
├── config/navegacion.ts
├── layouts/AppShell.tsx
├── modules/minuta/ # Minuta integrada
└── pages/
```

## Pendientes

- Minuta editor phone-optimized (o aviso solo-desktop)
- KPIs/Reportes: UX móvil más allá de consulta
- Opcional: PWA ligera / Add to Home Screen
- Integrar etiquetas como ruta interna (hoy enlace LAN)
- Evaluar segundo reinicio diario o build+preview en lugar de Vite dev

## ⚠️ Pendiente de verificar

- Estado de deploy en Vercel (config presente, producción no confirmada en repo)
- Que el reinicio 20–22 h no interrumpa un uso excepcional fuera de turno
- Uso real en planta del shell móvil (top bar / drawer / bottom nav) en iOS y Android
