export type Urgencia = "baja" | "media" | "alta" | "critica";
export type EstadoEntrega = "pendiente" | "parcial" | "completo";
export type EstadoSesion = "abierta" | "cerrada" | "enviada";

export type EntregaParcial = {
  id: number;
  solicitud_id: number;
  fecha: string;
  cantidad: number;
  observacion: string | null;
  creado_en: string;
};

export type Actualizacion = {
  id: number;
  sesion_id: number;
  solicitud_id: number | null;
  texto: string;
  autor: string | null;
  creado_en: string;
};

export type Solicitud = {
  id: number;
  sesion_origen_id: number;
  numero_referencia: string;
  solicitante: string;
  urgencia: Urgencia;
  cantidad_items: number;
  descripcion: string | null;
  estado_entrega: EstadoEntrega;
  cerrado: boolean;
  entregas: EntregaParcial[];
  actualizaciones: Actualizacion[];
  creado_en: string;
  actualizado_en: string;
};

export type Tema = {
  id: number;
  sesion_origen_id: number;
  titulo: string;
  descripcion: string | null;
  resuelto: boolean;
  creado_en: string;
  actualizado_en: string;
};

export type SesionResumen = {
  id: number;
  fecha: string;
  semana_iso: string;
  estado: EstadoSesion;
  responsable: string | null;
  notas_generales: string | null;
  email_enviado_en: string | null;
  creado_en: string;
  actualizado_en: string;
};

export type SesionDetalle = SesionResumen & {
  solicitudes: Solicitud[];
  temas: Tema[];
  actualizaciones: Actualizacion[];
};

export type SolicitudForm = {
  numero_referencia: string;
  solicitante: string;
  urgencia: Urgencia;
  cantidad_items: string;
  descripcion: string;
};

export type EntregaForm = {
  fecha: string;
  cantidad: string;
  observacion: string;
};

export type TemaForm = {
  titulo: string;
  descripcion: string;
};

export type FilaPedido = {
  id: number;
  ref_pedido: string;
  fila_excel: number;
  fecha_solicitud: string;
  cant_articulos_pedido?: string;
  num_odoo?: string;
  num_solicitud?: string;
  solicitante: string;
  tipo_solicitud: string;
  maquina_linea: string;
  almacenista: string;
  codigo: string;
  descripcion: string;
  cantidad: string;
  unidad: string;
  precio: string;
  total: string;
  moneda: string;
  proveedor: string;
  oc_rq: string;
  fecha_oc: string;
  comprador: string;
  fecha_envio_compras: string;
  estado_item: string;
  estado_solicitud: string;
  elegible: boolean;
  cumplida: boolean;
  seleccionada: boolean;
  notas?: NotaFila[];
};

export type PedidoGrupo = {
  ref_pedido: string;
  fecha_solicitud: string;
  solicitante: string;
  tipo_solicitud: string;
  maquina_linea: string;
  estado_solicitud: string;
  num_odoo?: string;
  num_solicitud?: string;
  almacenista?: string;
  filas: FilaPedido[];
  seleccionada: boolean;
  cantidad_filas: number;
};

export type ResumenImport = {
  importacion_id: number;
  hoja: string;
  nombre_archivo: string;
  importado_en: string;
  resumen: {
    total_filas: number;
    elegibles: number;
    cumplidas: number;
    pedidos_elegibles: number;
    pedidos_total: number;
  };
};

export type NotaFila = {
  id: number;
  sesion_id: number;
  fila_id: number;
  texto: string;
  autor: string | null;
  creado_en: string;
};

export type ExportRow = {
  cant_articulos_pedido: string;
  solicitante: string;
  tipo_solicitud: string;
  maquina_linea: string;
  fecha_solicitud: string;
  num_odoo: string;
  almacenista: string;
  num_solicitud: string;
  codigo: string;
  descripcion: string;
  cantidad: string;
  unidad: string;
  precio: string;
  total: string;
  moneda: string;
  proveedor: string;
  oc_rq: string;
  fecha_oc: string;
  comprador: string;
  fecha_envio_compras: string;
  estado_item: string;
  estado_solicitud: string;
  novedades: string;
};

export const URGENCIA_OPCIONES: { value: Urgencia; label: string }[] = [
  { value: "baja", label: "Baja" },
  { value: "media", label: "Media" },
  { value: "alta", label: "Alta" },
  { value: "critica", label: "Crítica" },
];

export const URGENCIA_LABEL: Record<Urgencia, string> = {
  baja: "Baja",
  media: "Media",
  alta: "Alta",
  critica: "Crítica",
};

export const ESTADO_ENTREGA_LABEL: Record<EstadoEntrega, string> = {
  pendiente: "Pendiente",
  parcial: "Entrega parcial",
  completo: "Completo",
};
