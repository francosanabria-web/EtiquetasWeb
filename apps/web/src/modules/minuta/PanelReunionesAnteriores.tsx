import { Link } from "react-router-dom";
import type { Reunion } from "../../api/minutaClient";
import { fmtFecha } from "./types";

type Props = {
  reuniones: Reunion[];
  sector: string;
  fechaActual: string;
};

/** Solo reuniones con mail enviado. */
export default function PanelReunionesAnteriores({
  reuniones,
  sector,
  fechaActual,
}: Props) {
  const previas = reuniones
    .filter((r) => r.email_enviado_en && r.fecha !== fechaActual)
    .slice(0, 12);

  return (
    <section className="minuta-section minuta-historial-panel">
      <h2>Reuniones anteriores{sector ? ` — ${sector}` : ""}</h2>
      {previas.length === 0 ? (
        <p className="minuta-hint">Aún no hay reuniones con mail enviado.</p>
      ) : (
        <ul className="minuta-reuniones-list">
          {previas.map((r) => (
            <li key={r.id}>
              <Link to={`/minuta/${r.id}`} className="minuta-reunion-link">
                {r.titulo || fmtFecha(r.fecha)} — {fmtFecha(r.fecha)}
              </Link>
              <span className="minuta-enviada-badge">Mail enviado</span>
              {r.notas_generales && (
                <p className="minuta-reunion-notas">{r.notas_generales}</p>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
