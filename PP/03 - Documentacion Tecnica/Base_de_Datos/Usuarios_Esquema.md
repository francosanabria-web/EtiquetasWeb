# Usuarios / Accesos — Esquema (SQLite)

**Última actualización:** 2026-07-29

Base local en la PC de pañol: `backend/usuarios/data/usuarios.db` (env `USUARIOS_DB_PATH`). No se versiona. Es una etapa previa a la migración a la base central (MariaDB/HeidiSQL).

## Tabla `usuarios`

| Columna | Tipo | Notas |
|---------|------|-------|
| `id` | INTEGER PK | autoincrement |
| `usuario` | TEXT UNIQUE | nombre de login corto (minúsculas) |
| `nombre` | TEXT | nombre visible |
| `email` | TEXT | identidad (`usuario@panol.local` por defecto); usado por minuta/solicitudes |
| `hash` | TEXT | PBKDF2-HMAC-SHA256 (hex) |
| `salt` | TEXT | salt por usuario (hex) |
| `rol_base` | TEXT | `admin` / `panol` / `supervisor` / `jefatura` |
| `activo` | INTEGER | 1 / 0 |
| `creado_en` / `actualizado_en` | TEXT | ISO UTC |

## Tabla `permisos`

| Columna | Tipo | Notas |
|---------|------|-------|
| `usuario_id` | INTEGER FK → usuarios(id) | ON DELETE CASCADE |
| `modulo` | TEXT | id del módulo (inicio, salidas, reportes, activos, etiquetas, minuta, kpis, solicitudes, buscador, usuarios) |
| `nivel` | TEXT | `sin_acceso` / `consulta` / `escritura` |
| PK | (usuario_id, modulo) | |

## Tabla `sesiones`

| Columna | Tipo | Notas |
|---------|------|-------|
| `token` | TEXT PK | opaco (`secrets.token_urlsafe`) |
| `usuario_id` | INTEGER FK | ON DELETE CASCADE |
| `creado_en` | TEXT | ISO UTC |
| `vence_en` | TEXT | ISO UTC (12 h por defecto) |

## Seguridad

- Hash PBKDF2 con 200.000 iteraciones; verificación con `hmac.compare_digest`.
- La gestión (crear/editar/borrar/resetear) exige sesión de un usuario `admin`.
- Salvaguarda: siempre debe quedar al menos un admin activo.
