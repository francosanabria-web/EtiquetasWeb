# Flujo de desarrollo seguro (probar antes de commitear)

## Regla de oro

| Rama | Qué es | Etiquetas (LAN) |
|------|--------|-----------------|
| `main` | Código estable en GitHub | Actualizar PC impresora cuando mergees |
| `feature/...` | Trabajo en curso | Probar local; no afecta otras PCs hasta pull en servidor |

**No desarrolles directo en `main` si querés probar sin mezclar cambios a medias.**

---

## Empezar un cambio

```powershell
cd C:\Users\Mantenimiento\Desktop\AppWebSalidas

git status
git checkout main
git pull
git checkout -b feature/etiquetas-mis-cambios

# ... editás, probás localmente ...
```

Pausar y cambiar de tema:

```powershell
git stash push -m "etiquetas WIP"
git checkout main
git checkout -b feature/otro-modulo

# Volver después:
git checkout feature/etiquetas-mis-cambios
git stash pop
```

---

## Probar en local (red del pañol)

| Módulo | Comando | URL |
|--------|---------|-----|
| Etiquetas web | `cd services\etiquetas-web` → `npm run dev:lan` | http://localhost:5173 o http://IP:5173 |
| Etiquetas API | supervisor o `.venv\...\uvicorn` | http://localhost:8010 |
| Shell | `cd apps\web` → `npm run dev` | http://localhost:5180 |

- Config local: **`.env.local`** (en `.gitignore`).
- Otros equipos usan la IP de la PC impresora; ver `COMO_IMPRIMIR.txt`.

---

## Cuando el cambio está probado

```powershell
git checkout feature/tu-rama
git add <archivos relevantes>
git commit -m "feat: descripción clara"
git push -u origin feature/tu-rama
```

Merge a `main`:

```powershell
git checkout main
git pull
git merge feature/tu-rama
git push
```

En la **PC impresora**: `git pull` en el repo y reiniciar supervisor si cambió código.

---

## Qué NO commitear nunca

- `serviceAccountKey.json`
- `.env.local` / credenciales
- `*.db`, `catalogo_cache.db`, `node_modules/`, `.venv/`

---

## Resumen rápido

1. Rama **`feature/...`** por tarea.
2. **Probar local** con supervisor / `npm run dev:lan`.
3. **`git stash`** si cambiás de tema sin commit.
4. **`git push` a `main`** cuando el código esté listo; luego actualizar la PC servidor.
