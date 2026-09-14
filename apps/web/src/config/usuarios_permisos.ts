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
    usuarios: "escritura",
    personal: "escritura",
    cajas: "escritura",
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
    usuarios: "sin_acceso",
    personal: "escritura",
    cajas: "escritura",
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
    usuarios: "sin_acceso",
    personal: "escritura",
    cajas: "consulta",
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
    usuarios: "sin_acceso",
    personal: "consulta",
    cajas: "consulta",
  },
};

