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
