# Checklist — nuevo módulo (misma lógica que etiquetas)

Copiá este flujo para cada módulo nuevo del pañol.

## 1. Estructura en el monorepo

```
services/<nombre>-web/          ← frontend Vite + React (LAN si es uso interno)
services/<nombre>-api/          ← opcional: FastAPI si necesita backend propio
```

Referencia: `services/etiquetas-web/` + `services/etiquetas-api/`.

Archivos mínimos frontend:

- `package.json`, `vite.config.ts`, `tsconfig.json`, `index.html`
- `.env.example` + `.gitignore` (incluir `.env.local`)
- `src/` (App, api.ts, types)

Solo agregar `vercel.json` si el módulo **debe** publicarse en internet (ej. portal público). Etiquetas y la mayoría del pañol: **solo LAN**.

## 2. Desarrollo local

```powershell
cd services\<nombre>-web
npm install
copy .env.example .env.local   # editar URLs (IP LAN)
npm run dev:lan                # accesible desde otras PCs
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

Merge a `main` cuando esté probado → `docs/FLUJO_DESARROLLO.md`.

## 4. Despliegue

| Tipo | Dónde | Cómo |
|------|-------|------|
| **Uso interno pañol** (etiquetas, salidas, etc.) | PC servidor o LAN | Supervisor / `npm run dev:lan` + API local |
| **App pública** (shell, móvil) | Vercel u otro hosting | Proyecto aparte; ver README del módulo |

Etiquetas: **no Vercel**. Acceso vía `http://IP-PC:5173` con supervisor en la PC impresora.

## 5. Etiquetas — estado actual (referencia)

| Pieza | Estado |
|-------|--------|
| GitHub `main` | Código fuente |
| LAN supervisor | API :8010, web :5173, print-agent |
| Acceso | localhost o IP PC impresora (ej. 10.1.102.8) |

## 6. Tests antes de merge

```powershell
cd services\etiquetas-api
.\.venv\Scripts\python.exe -m unittest test_etiquetas test_catalogo_cache -v

cd ..\etiquetas-web
npm run build
```

CI en GitHub: `.github/workflows/ci.yml` (tests API en push a `main`).
