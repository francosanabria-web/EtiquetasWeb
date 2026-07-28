import type { Rol, Usuario } from "../config/navegacion";

/**
 * Usuarios de demostración hasta conectar Firebase Auth / backend de cuentas.
 * NO usar en producción: reemplazar por autenticación real.
 */
export const USUARIOS_DEMO: Array<Usuario & { clave: string }> = [
  {
    id: "1",
    nombre: "Administrador",
    email: "admin@panol.local",
    clave: "admin123",
    rol: "admin",
  },
  {
    id: "2",
    nombre: "Pañol",
    email: "panol@panol.local",
    clave: "panol123",
    rol: "panol",
  },
  {
    id: "3",
    nombre: "Supervisor",
    email: "supervisor@panol.local",
    clave: "supervisor123",
    rol: "supervisor",
  },
  {
    id: "4",
    nombre: "Jefatura",
    email: "jefatura@panol.local",
    clave: "jefatura123",
    rol: "jefatura",
  },
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
