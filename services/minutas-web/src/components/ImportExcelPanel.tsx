import { useRef, useState } from "react";
import type { ResumenImport } from "../types/minuta";
import { exportarExcel, descargarBlob, importarNovedades } from "../api/client";

type Props = {
  onImportado: (res: ResumenImport) => void;
  onImportar: (file: File) => Promise<ResumenImport>;
  disabled?: boolean;
  sesionId?: number;
  selectedRefs?: string[];
  onNovedadesImportado?: () => void;
};

export default function ImportExcelPanel({ onImportado, onImportar, disabled, sesionId, selectedRefs, onNovedadesImportado }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const inputNovedadesRef = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [ultimo, setUltimo] = useState<ResumenImport | null>(null);
  const [exportBusy, setExportBusy] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);
  const [novedadesBusy, setNovedadesBusy] = useState(false);
  const [novedadesMsg, setNovedadesMsg] = useState<string | null>(null);

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

  async function handleExportar() {
    if (!sesionId || disabled) return;
    setExportBusy(true);
    setExportError(null);
    try {
      const blob = await exportarExcel(sesionId, { refs: selectedRefs });
      // Try to get filename from blob? Use simple naming
      const filename = `Minuta_${sesionId}.xlsx`;
      descargarBlob(blob, filename);
    } catch (e) {
      setExportError(e instanceof Error ? e.message : "Error al exportar");
    } finally {
      setExportBusy(false);
    }
  }

  async function handleNovedades(file: File | null) {
    if (!file || !sesionId) return;
    setNovedadesBusy(true);
    setNovedadesMsg(null);
    setError(null);
    try {
      const res = await importarNovedades(sesionId, file);
      const msg = `Novedades: ${res.procesadas} nuevas, ${res.omitidas_duplicadas} duplicadas omitidas, ${res.pendientes_consulta} en consulta, ${res.no_reconocidas} no reconocidas.`;
      setNovedadesMsg(msg);
      if (onNovedadesImportado) onNovedadesImportado();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error al importar novedades");
    } finally {
      setNovedadesBusy(false);
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

      {sesionId && (
        <div className="export-actions" style={{ marginTop: 16, display: "flex", gap: 8, flexWrap: "wrap" }}>
          <button
            type="button"
            className="btn-primary"
            disabled={disabled || exportBusy || !sesionId}
            onClick={() => void handleExportar()}
          >
            {exportBusy ? "Exportando…" : "Exportar Excel"}
          </button>
          <button
            type="button"
            className="btn-ghost"
            disabled={disabled || novedadesBusy || !sesionId}
            onClick={() => inputNovedadesRef.current?.click()}
          >
            {novedadesBusy ? "Importando…" : "Importar Novedades"}
          </button>
          <input
            ref={inputNovedadesRef}
            type="file"
            accept=".xlsx,.xlsm,.xls"
            hidden
            onChange={(e) => void handleNovedades(e.target.files?.[0] ?? null)}
          />
        </div>
      )}
      {exportError && <p className="field-error">{exportError}</p>}
      {novedadesMsg && <p className="import-meta">{novedadesMsg}</p>}
      <p className="sub" style={{ marginTop: 8 }}>
        Exportar respeta filas y columnas (orden fila_excel). La columna Novedades es la única editable (hoja protegida).
      </p>
    </section>
  );
}
