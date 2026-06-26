export type TipoEtiqueta = "simple" | "codigo";

export type CatalogoItem = {
  codigo: string;
  descripcion: string;
  ubicacion: string;
};

export type PedidoCreado = {
  id: number;
  estado: string;
};

export type Pedido = {
  id: number;
  tipo: TipoEtiqueta;
  texto_libre: string | null;
  codigo: string | null;
  descripcion: string | null;
  ubicacion: string | null;
  qr_data: string | null;
  cantidad: number;
  solicitado_por: string | null;
  estado: string;
  intentos: number;
  error_msg: string | null;
  creado_en: string;
  actualizado_en: string;
};

export type NuevaEtiqueta =
  | {
      tipo: "simple";
      texto_libre: string;
      cantidad: number;
      escala_fuente?: number;
      solicitado_por?: string;
    }
  | {
      tipo: "codigo";
      codigo: string;
      descripcion: string;
      ubicacion: string;
      qr_data: string;
      cantidad: number;
      solicitado_por?: string;
    };
