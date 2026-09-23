export type Rol = "admin" | "panol" | "supervisor" | "jefatura";

export type NivelPermiso = "sin_acceso" | "consulta" | "escritura";

export type ModuloId =
  | "inicio"
  | "salidas"
  | "reportes"
  | "activos"
  | "etiquetas"
  | "minuta"
  | "kpis"
  | "solicitudes"
  | "buscador"
  | "usuarios"
  | "personal"
  | "cajas"
  | "actualizacion";

export type PermisosUsuario = Record<ModuloId, NivelPermiso>;

export type Usuario = {
  id: number;
  usuario: string;
  nombre: string;
  email: string;
  rol: Rol;
  activo?: boolean;
  permisos: PermisosUsuario;
};

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

export type TipoAcceso = "interno" | "externo" | "proximo";

// TODO: migrar a lucide-react cuando se actualice el contrato del icono (out of scope Fase 2)
// Se mantiene emoji (🧰 etc.) para consistencia con .nav-icon y .mod-icon centrados. Ver HubVisualPolish spec.
export type ModuloNav = {
  id: ModuloId;
  titulo: string;
  descripcion: string;
  // icono emoji — TODO: migrar a lucide-react cuando se actualice el contrato del icono (out of scope Fase 2)
  icono: string;
  /** Ruta interna del shell (react-router). */
  ruta?: string;
  /** URL externa (LAN o Vercel). */
  href?: string;
  tipo: TipoAcceso;
  roles: Rol[];
  /** Si aparece en el menú lateral. KPIs sí, buscador solo en inicio. */
  enSidebar: boolean;
};

const ETIQUETAS =
  import.meta.env.VITE_ETIQUETAS_URL ?? "http://localhost:5173";
const BUSCADOR =
  import.meta.env.VITE_BUSCADOR_URL ?? "https://apppanol.vercel.app";

/** Catálogo central — fuente única para menú lateral y cards de inicio. */
export const MODULOS: ModuloNav[] = [
  {
    id: "inicio",
    titulo: "Inicio",
    descripcion: "Panel principal y accesos rápidos.",
    icono: "🏠",
    ruta: "/",
    tipo: "interno",
    roles: ["admin", "panol", "supervisor", "jefatura"],
    enSidebar: true,
  },
  {
    id: "salidas",
    titulo: "Salidas",
    descripcion: "Registrar egresos de material del pañol (carga pendiente + finalizar).",
    icono: "📤",
    ruta: "/salidas",
    tipo: "interno",
    roles: ["admin", "panol"],
    enSidebar: true,
  },
  {
    id: "reportes",
    titulo: "Reportes",
    descripcion: "Consultas operativas de movimientos, filtros y export CSV.",
    icono: "📊",
    ruta: "/reportes",
    tipo: "interno",
    roles: ["admin", "panol", "jefatura"],
    enSidebar: true,
  },
  {
    id: "activos",
    titulo: "Activos fuera de planta",
    descripcion: "Seguimiento de equipos y repuestos fuera de planta.",
    icono: "🏭",
    ruta: "/activos",
    tipo: "interno",
    roles: ["admin", "panol", "supervisor", "jefatura"],
    enSidebar: true,
  },
  {
    id: "etiquetas",
    titulo: "Etiquetas",
    descripcion: "Imprimir rótulos y etiquetas desde la red local.",
    icono: "🏷️",
    href: ETIQUETAS,
    tipo: "externo",
    roles: ["admin", "panol"],
    enSidebar: true,
  },
  {
    id: "minuta",
    titulo: "Minuta de Reunión",
    descripcion: "Anotar temas en reunión y enviar minuta por correo.",
    icono: "📝",
    ruta: "/minuta",
    tipo: "interno",
    roles: ["admin", "panol", "supervisor", "jefatura"],
    enSidebar: true,
  },
  {
    id: "solicitudes",
    titulo: "Solicitud de pedidos",
    descripcion: "Pedidos Normal/Urgente y TR, con PDF para Compras.",
    icono: "🧾",
    ruta: "/solicitudes",
    tipo: "interno",
    roles: ["admin", "panol", "supervisor", "jefatura"],
    enSidebar: true,
  },
  {
    id: "kpis",
    titulo: "KPIs",
    descripcion: "Indicadores de gestión del pañol.",
    icono: "📈",
    ruta: "/kpis",
    tipo: "interno",
    roles: ["admin", "jefatura"],
    enSidebar: true,
  },
  {
    id: "usuarios",
    titulo: "Usuarios",
    descripcion: "Alta de usuarios, contraseñas y permisos por módulo.",
    icono: "👥",
    ruta: "/usuarios",
    tipo: "interno",
    roles: ["admin"],
    enSidebar: true,
  },
  {
    id: "personal",
    titulo: "Personal",
    descripcion: "Gestión de personal y áreas organizacionales.",
    icono: "👤",
    ruta: "/admin/personal",
    tipo: "interno",
    roles: ["admin", "panol"],
    enSidebar: true,
  },
  {
    id: "cajas",
    titulo: "Cajas de Herramientas",
    descripcion: "Caja ideal, inventario por técnico y KPIs de cumplimiento.",
    icono: "🧰",
    ruta: "/admin/cajas",
    tipo: "interno",
    roles: ["admin", "panol", "supervisor", "jefatura"],
    enSidebar: true,
  },
  {
    id: "actualizacion",
    titulo: "Actualización y datos",
    descripcion: "Actualizar maestro de stock desde Excel (valorizado/detallado)",
    icono: "🔄",
    ruta: "/actualizacion",
    tipo: "interno",
    roles: ["admin", "panol"],
    enSidebar: true,
  },
  {
    id: "buscador",
    titulo: "Buscador",
    descripcion: "Consultar alias, stock y ubicaciones (app en Vercel).",
    icono: "🔎",
    href: BUSCADOR,
    tipo: "externo",
    roles: ["admin", "panol", "supervisor", "jefatura"],
    enSidebar: false,
  },
];

/** Nivel de permiso efectivo del usuario para un módulo. */
export function permisoDe(usuario: Usuario | null, modulo: ModuloId): NivelPermiso {
  if (!usuario) return "sin_acceso";
  return usuario.permisos?.[modulo] ?? "sin_acceso";
}

/** Módulos que el usuario puede ver (permiso ≠ sin_acceso). */
export function modulosVisibles(usuario: Usuario | null): ModuloNav[] {
  return MODULOS.filter((m) => permisoDe(usuario, m.id) !== "sin_acceso");
}

export function modulosSidebar(usuario: Usuario | null): ModuloNav[] {
  return modulosVisibles(usuario).filter((m) => m.enSidebar);
}

export function modulosInicio(usuario: Usuario | null): ModuloNav[] {
  return modulosVisibles(usuario).filter((m) => m.id !== "inicio");
}
