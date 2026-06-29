import type { FiltrosDashboard } from "../types/kpi";

type Props = {
  filtros: FiltrosDashboard;
  lineas: string[];
  obras: string[];
  onChange: (f: FiltrosDashboard) => void;
  onReset: () => void;
};

export default function FilterBar({ filtros, lineas, obras, onChange, onReset }: Props) {
  return (
    <section className="filters">
      <label>
        Desde
        <input
          type="date"
          value={filtros.fechaDesde}
          onChange={(e) => onChange({ ...filtros, fechaDesde: e.target.value })}
        />
      </label>
      <label>
        Hasta
        <input
          type="date"
          value={filtros.fechaHasta}
          onChange={(e) => onChange({ ...filtros, fechaHasta: e.target.value })}
        />
      </label>
      <label>
        Línea
        <select
          value={filtros.lineas[0] ?? ""}
          onChange={(e) =>
            onChange({
              ...filtros,
              lineas: e.target.value ? [e.target.value] : [],
            })
          }
        >
          <option value="">Todas</option>
          {lineas.map((l) => (
            <option key={l} value={l}>
              {l}
            </option>
          ))}
        </select>
      </label>
      <label>
        Obra
        <select
          value={filtros.obras[0] ?? ""}
          onChange={(e) =>
            onChange({
              ...filtros,
              obras: e.target.value ? [e.target.value] : [],
            })
          }
        >
          <option value="">Todas</option>
          {obras.map((o) => (
            <option key={o} value={o}>
              {o}
            </option>
          ))}
        </select>
      </label>
      <button type="button" className="btn-ghost btn-sm" onClick={onReset}>
        Limpiar filtros
      </button>
    </section>
  );
}
