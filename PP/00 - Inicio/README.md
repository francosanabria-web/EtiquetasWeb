# Sistemas Pañol — Vault de documentación

**Fecha de creación del vault:** 2026-06-26

## Qué es este sistema

Sistemas Pañol es la plataforma de gestión del pañol de Mantenimiento: registro de salidas de material, reportes de gasto, seguimiento de activos fuera de planta, catálogo de artículos, etiquetas de impresión y minutas de reunión semanal. Hoy conviven una **app de escritorio** en producción (`almacen_gui.py`), una **app web móvil** de consulta/conteo (`AppPanolWeb`) y un **monorepo web** en desarrollo (`AppWebSalidas`) que integrará los módulos en un portal único.

## Mapa de módulos (relaciones)

```
                    ┌─────────────────────┐
                    │  almacen_gui (.exe) │  ← producción hoy (Excel + Firebase sync)
                    └──────────┬──────────┘
                               │ merge=True → Firestore
                               ▼
                    ┌─────────────────────┐
                    │  Firestore          │  articulos + config/catalogo
                    └──────────┬──────────┘
                               │ solo lectura (etiquetas-api) / lectura+alias (AppPanolWeb)
           ┌───────────────────┼───────────────────┐
           ▼                   ▼                   ▼
  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐
  │ AppPanolWeb    │  │ etiquetas-api  │  │ (futuro backend│
  │ (Vercel/Host)  │  │ + etiquetas-web│  │  MariaDB)      │
  └────────────────┘  │ + print-agent  │  └────────────────┘
                      └────────────────┘

  ┌────────────────────────────────────────────────────────┐
  │ AppWebSalidas — apps/web (shell :5180)                 │
  │  • Minuta integrada (/minuta)                          │
  │  • Enlaces: Etiquetas (LAN), Buscador (Vercel)        │
  │  • Placeholders: Salidas, Reportes, Activos, KPIs     │
  └────────────────────────────────────────────────────────┘
```

## Cómo está organizado este vault

| Carpeta | Contenido |
|---------|-----------|
| [[00 - Inicio/README\|00 - Inicio]] | Este archivo — punto de entrada |
| [[01 - Estado del Proyecto/Roadmap\|01 - Estado del Proyecto]] | Roadmap, decisiones y backlog |
| [[02 - Módulos/Etiquetas\|02 - Módulos]] | Una nota por módulo funcional |
| [[03 - Documentacion Tecnica/Frontend/Shell_Central\|03 - Documentacion Tecnica]] | Detalle técnico frontend, backend y datos |
| [[04 - App de Escritorio/almacen_gui\|04 - App de Escritorio]] | Monolito Tkinter (producción, no tocar) |
| [[05 - Infraestructura/Stack\|05 - Infraestructura]] | Stack, Firebase, herramientas |

## Repos y rutas clave

| Proyecto | Ruta |
|----------|------|
| Monorepo web (desarrollo) | `C:\Users\Mantenimiento\Desktop\AppWebSalidas` |
| App de escritorio (producción) | `G:\...\pañol v5.0\` + `C:\Users\Mantenimiento\Desktop\LABORATORIO BASE\almacen_gui.py` |
| AppPanolWeb (buscador móvil) | `C:\Users\Mantenimiento\Desktop\panol_movil\AppPanolWeb` |
| Datos maestros (Excel) | `G:\Unidades compartidas\Mantenimiento\MANTENIMIENTO  OZLA 2024-2025\17. Pañol\pañol v5.0\` |

## Cómo leer este vault

1. Empezá por [[01 - Estado del Proyecto/Roadmap]] para ver qué está hecho.
2. Consultá [[02 - Módulos/...]] para el detalle funcional de cada área.
3. Para contratos de datos y APIs, usá [[03 - Documentacion Tecnica/...]].
4. La app de escritorio está documentada aparte hasta completar la migración.

> **Regla:** esta documentación refleja el estado real del código. Las secciones con ⚠️ *Pendiente de verificar* indican algo no confirmado en el repositorio local.
