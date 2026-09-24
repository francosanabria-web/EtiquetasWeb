# Stack — actual y objetivo

**Última actualización:** 2026-06-26

## Sistema operativo

| Entorno | SO |
|---------|-----|
| PC pañol (escritorio + servicios LAN) | **Windows 10/11** |
| Desarrollo | Windows 10 (usuario Mantenimiento) |

## Stack actual (producción + desarrollo)

| Capa | Actual | Ubicación / notas |
|------|--------|-------------------|
| App producción | Python 3.14 + Tkinter `.exe` | `almacen_gui.py` / PyInstaller |
| Datos maestros | Excel `.xlsx` en `G:\...\pañol v5.0\` | master_codes, master_salidas |
| Espejo móvil | Firebase Firestore | sistemapanol-a1bd4 |
| App consulta móvil | Vite 6 + React 19 + TS + Firebase JS 12 | AppPanolWeb |
| Etiquetas LAN | FastAPI + SQLite + React | AppWebSalidas/services |
| Minutas LAN | FastAPI + SQLite + React | AppWebSalidas/services |
| Minuta shell | React 19 + email_service | apps/web + backend |
| Cola impresión | SQLite `cola.db` | etiquetas-api |
| Mail | smtplib Gmail :587 | escritorio + email_service |
| CI | GitHub Actions | unittest etiquetas + minutas |
| Repo web | Git + GitHub | EtiquetasWeb.git |

## Stack objetivo (migración)

| Capa | Objetivo |
|------|----------|
| Base central | **MariaDB** (PC Windows local) |
| Backend | Servicios Python (FastAPI/Starlette) por dominio |
| Frontend | Shell React (`apps/web`) + AppPanolWeb sin cambios (fase 1) |
| Sync móvil | Backend → Firestore (`merge=True`, preservar `alias`) |
| Auth | Firebase Auth + roles (reemplazar demo) |
| Escritorio | Paralelo 7 días → retirar `.exe` |
| Excel | Import/export, no fuente de verdad |

## Herramientas

| Herramienta | Uso |
|-------------|-----|
| **HeidiSQL** | Admin MariaDB (planificado) |
| **PyInstaller** | Empaquetar escritorio |
| **Firebase CLI** | Deploy AppPanolWeb / rules |
| **Vite** | Build frontend (shell, módulos, AppPanolWeb) |
| **uvicorn** | Servir APIs Python |
| **npm** | Gestión deps frontend |
| **Git / GitHub** | Monorepo AppWebSalidas |
| **Obsidian** | Documentación viva (este vault) |
| **PowerShell** | Supervisores LAN (`supervisor_*.ps1`) |

## Python

| Contexto | Versión |
|----------|---------|
| Escritorio + dev local | **3.14** |
| Nota | pydantic/FastAPI en 3.14 requiere wheels; email_service usa Starlette por esto |

## Puertos LAN (convención)

| Puerto | Servicio |
|--------|----------|
| 5173 | etiquetas-web |
| 5175 | minutas-web |
| 5180 | shell apps/web |
| 8010 | etiquetas-api |
| 8012 | minutas-api |
| 8020 | email_service |

## ⚠️ Pendiente de verificar

- Versión MariaDB a instalar en PC pañol
- Si CockroachDB del doc `ARQUITECTURA_DATOS.md` queda descartado formalmente
