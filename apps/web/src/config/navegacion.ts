export type Rol = "admin" | "panol" | "supervisor" | "jefatura";

export type Usuario = {
  id: string;
  nombre: string;
  email: string;
  rol: Rol;
};

export type ModuloId =
  | "inicio"
  | "salidas"
  | "reportes"
  | "activos"
  | "etiquetas"
  | "minuta"
  | "kpis"
  | "solicitudes"
  | "buscador";

export type TipoAcceso = "interno" | "externo" | "proximo";

export type ModuloNav = {
  id: ModuloId;
  titulo: string;
  descripcion: string;
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
    descripcion: "Registrar solicitudes y salidas de material del pañol.",
    icono: "📤",
    ruta: "/salidas",
    tipo: "interno",
    roles: ["admin", "panol"],
    enSidebar: true,
  },
  {
    id: "reportes",
    titulo: "Reportes",
    descripcion: "Informes y exportaciones para jefatura y gerencia.",
    icono: "📊",
    ruta: "/reportes",
    tipo: "interno",
    roles: ["admin", "jefatura"],
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

export function modulosParaRol(rol: Rol): ModuloNav[] {
  return MODULOS.filter((m) => m.roles.includes(rol));
}

export function modulosSidebar(rol: Rol): ModuloNav[] {
  return modulosParaRol(rol).filter((m) => m.enSidebar);
}

export function modulosInicio(rol: Rol): ModuloNav[] {
  return modulosParaRol(rol).filter((m) => m.id !== "inicio");
}
