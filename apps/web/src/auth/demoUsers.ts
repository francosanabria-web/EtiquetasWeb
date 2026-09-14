import type { PermisosUsuario, Rol, Usuario } from "../config/navegacion";
import { PERMISOS_ROL } from "../config/usuarios_permisos";

/**
 * Usuarios de demostración hasta conectar Firebase Auth / backend de cuentas.
 * NO usar en producción: reemplazar por autenticación real.
 */
function demoUsuario(
  id: number,
  usuario: string,
  nombre: string,
  email: string,
  clave: string,
  rol: Rol
): Usuario & { clave: string } {
  return {
    id,
    usuario,
    nombre,
    email,
    clave,
    rol,
    activo: true,
    permisos: PERMISOS_ROL[rol] as PermisosUsuario,
  };
}

export const USUARIOS_DEMO: Array<Usuario & { clave: string }> = [
  demoUsuario(1, "admin", "Administrador", "admin@panol.local", "admin123", "admin"),
  demoUsuario(2, "panol", "Pañol", "panol@panol.local", "panol123", "panol"),
  demoUsuario(3, "supervisor", "Supervisor", "supervisor@panol.local", "supervisor123", "supervisor"),
  demoUsuario(4, "jefatura", "Jefatura", "jefatura@panol.local", "jefatura123", "jefatura"),
];

export function autenticarDemo(email: string, clave: string): Usuario | null {
  const q = email.trim().toLowerCase();
  const found = USUARIOS_DEMO.find(
    (u) => u.email.toLowerCase() === q && u.clave === clave
  );
  if (!found) return null;
  const { clave: _, ...usuario } = found;
  return usuario;
}

export function etiquetaRol(rol: Rol): string {
  switch (rol) {
    case "admin":
      return "Administrador";
    case "panol":
      return "Pañol";
    case "supervisor":
      return "Supervisor";
    case "jefatura":
      return "Jefatura / Gerencia";
  }
}
