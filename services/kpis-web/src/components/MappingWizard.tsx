import type { ConfigImportacion } from "../types/kpi";
import { CAMPOS_DATO, ETIQUETAS_CAMPO } from "../types/kpi";
import { configValida } from "../lib/columnMapper";
import type { ResultadoParseo } from "../types/kpi";

type Props = {
  config: ConfigImportacion;
  parseo: ResultadoParseo;
  onChange: (cfg: ConfigImportacion) => void;
  onConfirmar: () => void;
  onCancelar: () => void;
};

export default function MappingWizard({
  config,
  parseo,
  onChange,
  onConfirmar,
  onCancelar,
}: Props) {
  const hoja = parseo.hojas.find((h) => h.nombre === config.hoja) ?? parseo.hojas[0];
  const encabezados = hoja?.encabezados ?? [];
  const valido = configValida(config);

  return (
    <section className="panel mapping">
      <header className="panel-head">
        <div>
          <h2>Traducir columnas del Excel</h2>
          <p className="sub">
            Indicá qué columna corresponde a cada dato. Esta configuración queda guardada para futuras importaciones.
          </p>
        </div>
      </header>

      <div className="mapping-grid">
        <label>
          Hoja
          <select
            value={config.hoja}
            onChange={(e) => onChange({ ...config, hoja: e.target.value })}
          >
            {parseo.hojas.map((h) => (
              <option key={h.nombre} value={h.nombre}>
                {h.nombre} ({h.totalFilas} filas)
              </option>
            ))}
          </select>
        </label>

        {CAMPOS_DATO.map((campo) => (
          <label key={campo}>
            {ETIQUETAS_CAMPO[campo]}
            {campo === "fecha" || campo === "importe" ? " *" : ""}
            <select
              value={config.mapeo[campo] ?? ""}
              onChange={(e) =>
                onChange({
                  ...config,
                  mapeo: {
                    ...config.mapeo,
                    [campo]: e.target.value || undefined,
                  },
                })
              }
            >
              <option value="">— Sin asignar —</option>
              {encabezados.map((col) => (
                <option key={col} value={col}>
                  {col}
                </option>
              ))}
            </select>
          </label>
        ))}
      </div>

      {hoja && hoja.filasPreview.length > 0 && (
        <div className="preview-table-wrap">
          <h4>Vista previa</h4>
          <table className="data-table compact">
            <thead>
              <tr>
                {encabezados.slice(0, 6).map((h) => (
                  <th key={h}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {hoja.filasPreview.slice(0, 4).map((fila, i) => (
                <tr key={i}>
                  {encabezados.slice(0, 6).map((h) => (
                    <td key={h}>{String(fila[h] ?? "")}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="actions-row">
        <button type="button" className="btn-ghost" onClick={onCancelar}>
          Cancelar
        </button>
        <button type="button" className="btn-primary" disabled={!valido} onClick={onConfirmar}>
          Aplicar e importar
        </button>
      </div>
    </section>
  );
}
