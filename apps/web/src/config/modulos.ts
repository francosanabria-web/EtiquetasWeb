export type Rol = "admin" | "panolero" | "consulta";

export type Usuario = {
  id: string;
  nombre: string;
  email: string;
  rol: Rol;
};

export type ModuloId = "etiquetas" | "panol" | "salidas" | "inventario";

export type ModuloDef = {
  id: ModuloId;
  titulo: string;
  descripcion: string;
  icono: string;
  /** Ruta interna del shell o URL externa (módulos legacy / otro puerto). */
  ruta: string;
  externo?: boolean;
  roles: Rol[];
  disponible: boolean;
};

/** Catálogo de módulos del sistema. Se amplía a medida que desarrollamos. */
export const MODULOS: ModuloDef[] = [
  {
    id: "etiquetas",
    titulo: "Etiquetas",
    descripcion: "Imprimir rótulos y etiquetas de código desde la red.",
    icono: "🏷️",
    ruta: import.meta.env.VITE_ETIQUETAS_URL ?? "http://localhost:5173",
    externo: true,
    roles: ["admin", "panolero"],
    disponible: true,
  },
  {
    id: "panol",
    titulo: "Pañol — Buscador",
    descripcion: "Consultar alias, stock y conteos internos (app todo-en-uno).",
    icono: "🔎",
    ruta: "/modulos/panol",
    roles: ["admin", "panolero", "consulta"],
    disponible: false,
  },
  {
    id: "salidas",
    titulo: "Salidas de pañol",
    descripcion: "Registrar solicitudes y salidas de material.",
    icono: "📤",
    ruta: "/modulos/salidas",
    roles: ["admin", "panolero"],
    disponible: false,
  },
  {
    id: "inventario",
    titulo: "Inventario",
    descripcion: "Controles de inventario y ajustes (próximo módulo).",
    icono: "📦",
    ruta: "/modulos/inventario",
    roles: ["admin"],
    disponible: false,
  },
];

export function modulosParaRol(rol: Rol): ModuloDef[] {
  return MODULOS.filter((m) => m.roles.includes(rol));
}

export function puedeUsarModulo(rol: Rol, id: ModuloId): boolean {
  const mod = MODULOS.find((m) => m.id === id);
  return !!mod && mod.roles.includes(rol) && mod.disponible;
}
