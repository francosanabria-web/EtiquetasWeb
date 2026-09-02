import { useRef, useState } from "react";
import type { ResumenImport } from "../types/minuta";

type Props = {
  onImportado: (res: ResumenImport) => void;
  onImportar: (file: File) => Promise<ResumenImport>;
  disabled?: boolean;
};

export default function ImportExcelPanel({ onImportado, onImportar, disabled }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [ultimo, setUltimo] = useState<ResumenImport | null>(null);

  async function procesar(file: File | null) {
    if (!file || disabled) return;
    setBusy(true);
    setError(null);
    try {
      const res = await onImportar(file);
      setUltimo(res);
      onImportado(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error al importar");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="panel import-excel">
      <h3>1. Importar Excel de pedidos</h3>
      <p className="sub">
        Planilla diaria del pañol. Se detectan pendientes por columnas W/X (estado ítem / solicitud).
      </p>
      <div
        className="import-drop"
        onClick={() => !disabled && inputRef.current?.click()}
        role="button"
        tabIndex={0}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".xlsx,.xlsm,.xls"
          hidden
          onChange={(e) => void procesar(e.target.files?.[0] ?? null)}
        />
        {busy ? "Importando…" : "Elegir o arrastrar archivo .xlsx"}
      </div>
      {error && <p className="field-error">{error}</p>}
      {ultimo && (
        <p className="import-meta">
          <strong>{ultimo.nombre_archivo}</strong> — hoja «{ultimo.hoja}» —{" "}
          {ultimo.resumen.pedidos_elegibles} pedidos elegibles / {ultimo.resumen.total_filas} filas
        </p>
      )}
    </section>
  );
}
