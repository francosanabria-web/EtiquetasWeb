# etiquetas-web

Frontend (Vite + React + TypeScript) para encolar etiquetas en `etiquetas-api`.
Es la "cara" que usa el personal del pañol; manda los pedidos a la API y muestra
la cola pendiente en vivo.

## Modos

- **Código**: se busca un código en el catálogo (`GET /catalogo/{codigo}`) y se
  envía una etiqueta con código + descripción + ubicación + QR.
- **Rótulo simple**: solo texto libre.

## Configuración

La URL de la API se define con la variable `VITE_API_URL` (por defecto
`http://localhost:8000`). Para usar desde tablets/otras PCs apuntando a la PC
servidor, crear un archivo `.env.local`:

```
VITE_API_URL=http://192.168.1.50:8000
```

.env.local

## Vercel (proyecto separado)

Root Directory en Vercel: **`services/etiquetas-web`**

| Variable | Dónde | Valor |
|----------|--------|--------|
| `ETIQUETAS_API_ORIGIN` | Vercel → Settings → Env (server) | URL HTTPS de `etiquetas-api` (túnel o hosting) |
| `VITE_API_URL` | Opcional | Dejar vacío en prod → usa `/api` (proxy) |

El proxy en `api/[...path].ts` evita mixed-content (HTTPS Vercel → HTTP LAN).

## Desarrollo

```bash
npm install
npm run dev          # local (http://localhost:5173)
npm run dev:lan      # accesible desde la red local
```

> Para que el navegador pueda llamar a la API desde otro origen, `etiquetas-api`
> tiene CORS habilitado (configurable con `ETIQUETAS_CORS_ORIGINS`).
