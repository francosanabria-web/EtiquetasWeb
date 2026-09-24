# Usuarios / Accesos

**Estado:** 🔄 En desarrollo (MVP funcional)  
**Última actualización:** 2026-07-29

## Qué hace

Login real y gestión de accesos del portal, **en la red interna** (la app no se expone a internet; el buscador externo queda aparte). El admin gestiona desde la app: alta/baja de usuarios, **usuario y contraseña**, y **permisos por usuario y por módulo**.

## Decisiones

- **Fuente de datos:** SQLite local en la PC de pañol (`backend/usuarios/data/usuarios.db`), hasta el traspaso a la base de datos central (MariaDB/HeidiSQL).
- **Contraseñas:** PBKDF2-HMAC-SHA256 + salt por usuario (nunca en texto plano).
- **Sesión:** token opaco con vencimiento (12 h), tabla `sesiones`.
- **Permisos:** matriz por usuario `módulo → sin_acceso | consulta | escritura`, sembrada de la **plantilla del rol** al crear y editable a mano.
- **Usuario:** formato corto (`fsanabria`, `panol`). Cada usuario tiene además un `email` (`usuario@panol.local`) que se usa como identidad en minuta/solicitudes.
- **Alcance MVP:** login + gestión + permisos aplicados en la UI. Los servicios (minuta, solicitudes, kpis…) todavía confían en la LAN; exigir token en todos es fase posterior.

## Roles y plantillas

`admin`, `panol`, `supervisor`, `jefatura`. Las plantillas reflejan el mapa previo de permisos por rol. El módulo **Usuarios** solo lo ve el admin. Salvaguarda: siempre debe quedar **al menos un admin activo** (no se puede borrar/desactivar/bajar de rol el último).

## Flujo de uso

1. Login con usuario + contraseña.
2. El portal muestra solo los módulos con permiso ≠ `sin_acceso` (sidebar + inicio) y bloquea el acceso por URL a los módulos sin permiso.
3. **Cambiar mi contraseña:** botón en la barra lateral (cualquier usuario).
4. **Admin → Usuarios:** lista, alta, edición (nombre, rol, activo, matriz de permisos), resetear contraseña, eliminar.

## Rutas de código

| Capa | Path |
|------|------|
| Backend | `backend/usuarios/` (Starlette :8015, `main.py` / `db.py` / `config.py`) |
| Cliente | `apps/web/src/api/usuariosClient.ts` |
| Auth | `apps/web/src/auth/AuthContext.tsx` + `RequireAuth.tsx` + `RequirePermiso.tsx` |
| UI admin | `apps/web/src/modules/usuarios/UsuariosPage.tsx` |
| Permisos | `apps/web/src/config/navegacion.ts` (`permisoDe`, `modulosVisibles`) |
| Arranque | `scripts/_start_usuarios.bat` (incluido en `INICIAR_TODO.bat`) |

## Migración desde el demo

Al primer arranque se **siembran los 4 usuarios previos** con usuarios cortos (`admin`, `panol`, `supervisor`, `jefatura`) y sus contraseñas de antes, para no cortar el servicio. Se quitó el cartel de credenciales demo del login. **Recomendado:** cambiar esas contraseñas después del primer ingreso.

## Pendientes

- Exigir el token de sesión en el resto de los servicios (hoy confían en la LAN).
- Migrar `usuarios.db` a la base central junto con el resto de los datos.
- Auditoría de cambios (quién creó/editó/borró y cuándo).
