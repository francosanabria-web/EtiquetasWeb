# etiquetas-web

Frontend (Vite + React + TypeScript) para encolar etiquetas en `etiquetas-api`.
Solo se usa en la **red local del pañol** (localhost o IP de la PC impresora).

## Acceso

| Desde | URL |
|-------|-----|
| Misma PC | http://localhost:5173 |
| Otras PCs del pañol | http://IP-PC-IMPRESORA:5173 (ej. http://10.1.102.8:5173) |

Requisito: supervisor activo en la PC impresora (`scripts/instalar_autostart.ps1`).
Ver `COMO_IMPRIMIR.txt` en la raíz del repo.

## Configuración

Crear `services/etiquetas-web/.env.local` en la PC servidor:

```
VITE_API_URL=http://10.1.102.8:8010
```

Reiniciar `npm run dev` (o el supervisor) después de cambiar la IP.

## Modos

- **Código**: catálogo en caché local (`GET /catalogo/{codigo}`).
- **Rótulo simple**: texto libre con tamaño de letra ajustable.

## Desarrollo

```bash
npm install
npm run dev          # http://localhost:5173
npm run dev:lan      # accesible desde otras PCs (0.0.0.0:5173)
```

La API tiene CORS habilitado (`ETIQUETAS_CORS_ORIGINS` en etiquetas-api).
