import type { ModuloId, Rol } from "./navegacion";

export type PermisoModulo = "consulta" | "escritura";

export type PermisosPorRol = Record<ModuloId, PermisoModulo | "sin_acceso">;

/**
 * Archivo editable para alta de usuarios y permisos.
 * Ajustar este mapa para cambiar accesos por rol.
 */
export const PERMISOS_ROL: Record<Rol, PermisosPorRol> = {
  admin: {
    inicio: "escritura",
    salidas: "escritura",
    reportes: "escritura",
    activos: "escritura",
    etiquetas: "escritura",
    minuta: "escritura",
    kpis: "escritura",
    solicitudes: "escritura",
    buscador: "escritura",
  },
  panol: {
    inicio: "escritura",
    salidas: "escritura",
    reportes: "escritura",
    activos: "escritura",
    etiquetas: "escritura",
    minuta: "escritura",
    kpis: "escritura",
    solicitudes: "escritura",
    buscador: "escritura",
  },
  supervisor: {
    inicio: "consulta",
    salidas: "sin_acceso",
    reportes: "sin_acceso",
    activos: "escritura",
    etiquetas: "sin_acceso",
    minuta: "escritura",
    kpis: "sin_acceso",
    solicitudes: "escritura",
    buscador: "consulta",
  },
  jefatura: {
    inicio: "consulta",
    salidas: "sin_acceso",
    reportes: "consulta",
    activos: "escritura",
    etiquetas: "sin_acceso",
    minuta: "escritura",
    kpis: "consulta",
    solicitudes: "consulta",
    buscador: "consulta",
  },
};

