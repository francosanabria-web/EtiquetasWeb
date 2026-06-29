# Checklist — nuevo módulo web (misma lógica que etiquetas)

Copiá este flujo para cada módulo nuevo del día.

## 1. Estructura en el monorepo

```
services/<nombre>-web/          ← frontend Vite + React (Vercel)
services/<nombre>-api/          ← opcional: FastAPI si necesita backend propio
```

Referencia: copiar patrón de `services/etiquetas-web/`.

Archivos mínimos frontend:

- `package.json`, `vite.config.ts`, `tsconfig.json`, `index.html`
- `vercel.json` (framework vite, output dist, SPA rewrite)
- `.env.example` + `.gitignore` (incluir `.env.local`)
- `src/` (App, api.ts, types)

## 2. Desarrollo local

```powershell
cd services\<nombre>-web
npm install
copy .env.example .env.local   # editar URLs
npm run dev
```

Backend (si aplica): tests con `python -m unittest` en la carpeta del API.

## 3. Git (rama feature, no main directo)

```powershell
cd C:\Users\Mantenimiento\Desktop\AppWebSalidas
git checkout main
git pull
git checkout -b feature/<nombre-modulo>
# ... desarrollo y pruebas ...
git add services/<nombre>-web ...
git commit -m "feat(<nombre>): módulo inicial"
git push -u origin feature/<nombre-modulo>
```

Merge a `main` cuando esté probado → ver `docs/FLUJO_DESARROLLO.md`.

## 4. Vercel (proyecto SEPARADO por módulo)

En [vercel.com/new](https://vercel.com/new):

| Campo | Valor |
|-------|--------|
| Repository | `francosanabria-web/EtiquetasWeb` (mismo monorepo) |
| **Root Directory** | `services/<nombre>-web` |
| Project name | distinto por módulo (ej. `salidas-panol`) |

Variables de entorno: según módulo (patrón proxy `/api` + `*_API_ORIGIN` en servidor si hay backend LAN).

## 5. Etiquetas — estado actual (referencia)

| Pieza | Estado |
|-------|--------|
| GitHub `main` | ✅ Sincronizado |
| Vercel frontend | ✅ URL pública |
| LAN (supervisor) | ✅ Impresión local |
| `ETIQUETAS_API_ORIGIN` en Vercel | ⏳ Opcional: solo si querés catálogo/impresión **desde la URL Vercel fuera de LAN** |

Sin `ETIQUETAS_API_ORIGIN`: la web en Vercel carga, pero `/api` responde 503 hasta configurar túnel HTTPS a la PC.

## 6. Tests antes de merge

```powershell
# API etiquetas (ejemplo)
cd services\etiquetas-api
.\.venv\Scripts\python.exe -m unittest test_etiquetas test_catalogo_cache -v

# Build frontend
cd ..\etiquetas-web
npm run build
```

CI en GitHub corre tests del API en cada push a `main` (`.github/workflows/ci.yml`).
