# Flujo de desarrollo seguro (probar antes de commitear)

## Regla de oro

| Rama | Qué es | Vercel |
|------|--------|--------|
| `main` | Producción estable | Deploy automático al hacer push |
| `feature/...` | Trabajo en curso | No se despliega hasta merge a `main` |

**Nunca desarrolles directo en `main` si querés probar sin publicar.**

---

## Empezar un cambio (ej. etiquetas, pausado por otro módulo)

```powershell
cd C:\Users\Mantenimiento\Desktop\AppWebSalidas

# Ver en qué rama estás
git status

# Crear rama para el cambio futuro de etiquetas
git checkout main
git pull
git checkout -b feature/etiquetas-mis-cambios

# ... editás, probás localmente ...
# NO hace falta commitear todavía
```

Cuando quieras **pausar** y trabajar en otra cosa:

```powershell
# Opción A: guardar cambios sin commit (recomendado)
git stash push -m "etiquetas WIP"
git checkout main
git checkout -b feature/otro-modulo

# Volver después a etiquetas:
git checkout feature/etiquetas-mis-cambios
git stash pop
```

```powershell
# Opción B: commit en la rama feature (también válido)
git add ...
git commit -m "WIP: ..."
git checkout main
# La rama feature queda guardada en GitHub si hiciste push de la rama
```

---

## Probar en local (sin tocar Vercel)

| Módulo | Comando | URL local |
|--------|---------|-----------|
| Etiquetas web | `cd services\etiquetas-web` → `npm run dev` | http://localhost:5173 |
| Etiquetas API | supervisor o `.venv\...\uvicorn` | http://localhost:8010 |
| Shell | `cd apps\web` → `npm run dev` | http://localhost:5180 |

- Config local: **`.env.local`** (está en `.gitignore`, no se sube a GitHub).
- Vercel **no se entera** de tus cambios hasta que hagas `git push` a `main`.

---

## Cuando el cambio está probado

```powershell
git checkout feature/tu-rama
git add <archivos relevantes>
git commit -m "feat: descripción clara"
git push -u origin feature/tu-rama
```

Merge a `main` (cuando estés listo para producción):

```powershell
git checkout main
git pull
git merge feature/tu-rama
git push
```

→ Vercel redeploya solo en ese push a `main`.

---

## Qué NO commitear nunca

- `serviceAccountKey.json`
- `.env.local` / credenciales
- `*.db`, `catalogo_cache.db`, `node_modules/`, `.venv/`

Ya están en `.gitignore`.

---

## Resumen rápido

1. **Rama `feature/...`** para cada tarea.
2. **Probar local** con `npm run dev` / supervisor.
3. **`git stash`** si tenés que cambiar de tema sin commit.
4. **Push a `main`** solo cuando querés que Vercel lo publique.
