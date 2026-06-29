import type { SesionResumen } from "../types/minuta";

type Props = {
  sesiones: SesionResumen[];
  actualId: number | null;
  onSeleccionar: (id: number) => void;
};

export default function HistorialPanel({ sesiones, actualId, onSeleccionar }: Props) {
  const pasadas = sesiones.filter((s) => s.id !== actualId).slice(0, 8);
  if (!pasadas.length) return null;

  return (
    <aside className="panel historial">
      <h3>Reuniones anteriores</h3>
      <ul>
        {pasadas.map((s) => (
          <li key={s.id}>
            <button type="button" className="hist-btn" onClick={() => onSeleccionar(s.id)}>
              <span>{s.semana_iso}</span>
              <span className="muted">{s.fecha}</span>
              <span className={`badge mini estado-${s.estado}`}>{s.estado}</span>
            </button>
          </li>
        ))}
      </ul>
    </aside>
  );
}
