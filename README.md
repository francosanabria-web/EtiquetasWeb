# AppWebSalidas — Sistema integrado de pañol

Monorepo en GitHub: desarrollo, pruebas locales y push cuando esté estable.
Repo: https://github.com/francosanabria-web/EtiquetasWeb

## Arquitectura

```
AppWebSalidas/
├── apps/
│   └── web/                      → shell / login (futuro; Vercel si aplica)
├── services/
│   ├── etiquetas-web/            → LAN: localhost + IP PC impresora :5173
│   ├── etiquetas-api/            → LAN: PC impresora :8010
│   ├── kpis-web/                 → LAN: panel KPIs mantenimiento :5174
│   └── print-agent/              → LAN: PC impresora (impresión)
└── scripts/                      → supervisor, monitoreo
```

| Módulo | Dónde corre | Internet |
|--------|-------------|----------|
| **Etiquetas** | Red local del pañol | No |
| **KPIs** | Red local (jefatura/gerencia) | No |
| App móvil pañol | Proyecto / repo propio | Vercel (ya existente) |
| Shell (`apps/web`) | Futuro | A definir |

## Etiquetas — uso diario

1. PC impresora: supervisor (`scripts/instalar_autostart.ps1`).
2. Cualquier PC del pañol: navegador → `http://IP-PC:5173`.

Detalle: `COMO_IMPRIMIR.txt`

## Git — cambios seguros

- Trabajar en ramas `feature/...`, probar local, merge a `main`, `git push`.
- Guía: `docs/FLUJO_DESARROLLO.md`

## Módulos nuevos

Checklist: `docs/NUEVO_MODULO.md`
