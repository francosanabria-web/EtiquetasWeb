# Shell Central (Portal web)

**Estado:** 🔄 En desarrollo  
**Última actualización:** 2026-08-07

## Qué hace

Portal único de `apps/web` (`:5180`): login, navegación por permisos, inicio con cards y contenedor (`AppShell`) de todos los módulos web (Salidas, Activos, Solicitudes, Minuta, KPIs, Reportes, etc.).

Detalle técnico: [[03 - Documentacion Tecnica/Frontend/Shell_Central]].

## Hecho 2026-08-07 — shell responsive / móvil

Adaptación del `AppShell` para uso en teléfono (campo), sin cambiar el comportamiento desktop del sidebar colapsable.

### Layout móvil (≤768px)
- **Top bar sticky:** hamburger + marca «Sistemas Pañol» + título de la página actual.
- **Sidebar off-canvas (drawer):** se cierra al navegar, con Escape o al tocar el backdrop.
- **Bottom quick nav** (filtrada por permisos) para módulos de campo: Inicio, Salidas, Activos, Solicitudes.
- **Viewport / PWA-lite meta:** `safe-area-inset`, `100dvh`, `viewport-fit=cover`, `theme-color`, `apple-mobile-web-app`.
- Touch targets ≥44px; inputs a 16px en móvil (evita zoom iOS).
- Clase `.btn-secondary` definida en el shell.
- Padding de página consistente en `sol-page`, `minuta-page`, `rep-page`.

### Desktop
- Sidebar colapsable (labels / iconos) **sin cambios**.
- En móvil el colapso se ignora: el drawer siempre muestra labels.

### Módulos con UI móvil específica
- **Salidas:** carga pendiente en **cards** (en lugar de tabla) por debajo de **900px**. Ver [[02 - Módulos/Salidas]].
- **Activos:** listado en **cards** por debajo de **768px** (checkbox, equipo, días, sector, proveedor). Ver [[02 - Módulos/Activos]].

## Pendientes de este módulo

- [ ] Minuta reunión: editor no optimizado para teléfono (tabla ancha + drag HTML5) — cards/form o aviso solo-desktop. Ver [[02 - Módulos/Minuta_Reunion]] y Pendientes.
- [ ] KPIs / Reportes: quedan orientados a consulta en teléfono (sin rediseño mobile-first).
- [ ] Opcional: PWA ligera / «Add to Home Screen».
- [ ] Integrar Etiquetas como ruta interna (hoy enlace LAN externo).
- [ ] ⚠️ URL de producción final y estrategia de deploy del shell.

## Notas

- Fuente de navegación: `apps/web/src/config/navegacion.ts` (sidebar, cards inicio, bottom nav).
- Auth: servicio `usuarios` `:8015`; permisos filtran sidebar, inicio y bottom nav.
- Supervisor PC pañol: tarea `PortalPanol` (ver doc técnica del shell).
