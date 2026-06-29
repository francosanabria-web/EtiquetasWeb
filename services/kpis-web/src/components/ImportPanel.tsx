import { useRef, useState } from "react";
import { leerArchivoExcel } from "../lib/excelParser";
import type { ResultadoParseo } from "../types/kpi";

type Props = {
  onArchivo: (file: File, parseo: ResultadoParseo) => void;
  deshabilitado?: boolean;
};

export default function ImportPanel({ onArchivo, deshabilitado }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [arrastrando, setArrastrando] = useState(false);
  const [procesando, setProcesando] = useState(false);

  async function manejar(file: File | null) {
    if (!file || deshabilitado) return;
    const ext = file.name.toLowerCase();
    if (!ext.endsWith(".xlsx") && !ext.endsWith(".xls") && !ext.endsWith(".csv")) {
      alert("Formato no soportado. Usá .xlsx, .xls o .csv");
      return;
    }
    setProcesando(true);
    try {
      const parseo = await leerArchivoExcel(file);
      onArchivo(file, parseo);
    } catch {
      alert("No se pudo leer el archivo Excel.");
    } finally {
      setProcesando(false);
    }
  }

  return (
    <section
      className={`import-zone${arrastrando ? " drag" : ""}${deshabilitado ? " disabled" : ""}`}
      onDragOver={(e) => {
        e.preventDefault();
        setArrastrando(true);
      }}
      onDragLeave={() => setArrastrando(false)}
      onDrop={(e) => {
        e.preventDefault();
        setArrastrando(false);
        void manejar(e.dataTransfer.files[0] ?? null);
      }}
      onClick={() => !deshabilitado && inputRef.current?.click()}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => e.key === "Enter" && inputRef.current?.click()}
    >
      <input
        ref={inputRef}
        type="file"
        accept=".xlsx,.xls,.csv"
        hidden
        onChange={(e) => void manejar(e.target.files?.[0] ?? null)}
      />
      <div className="import-icon">📊</div>
      <h3>{procesando ? "Leyendo planilla…" : "Importar planilla Excel"}</h3>
      <p>Arrastrá el archivo acá o hacé clic para elegirlo.</p>
      <p className="hint">Gastos por fecha, línea, obra, etc. La configuración de columnas se guarda automáticamente.</p>
    </section>
  );
}
