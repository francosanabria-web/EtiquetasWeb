import { useMemo } from "react";
import {
  IMPORTANCIAS,
  labelEstado,
  labelImportancia,
  type EstadoItem,
  type Pedido,
} from "../../api/minutaClient";
import { fechaHoyIso, fmtFecha } from "./types";

/** % de avance según el estado actual del pedido (decisión de producto). */
const AVANCE_ESTADO: Record<EstadoItem, number> = {
  sin_oc: 25,
  en_proceso: 50,
  parcial: 75,
  completado: 100,
};

type Props = {
  pedidos: Pedido[];
};

export default function VistaIndicadores({ pedidos }: Props) {
  const hoy = fechaHoyIso();

  const { global, contadores } = useMemo(() => {
    const contadores: Partial<Record<EstadoItem, number>> = {};
    if (pedidos.length === 0) {
      return { global: 100, contadores };
    }
    let suma = 0;
    for (const p of pedidos) {
      const estado = p.estado;
      contadores[estado] = (contadores[estado] ?? 0) + 1;
      suma += AVANCE_ESTADO[estado] ?? 0;
    }
    return { global: Math.round(suma / pedidos.length), contadores };
  }, [pedidos]);

  const grupos = useMemo(() => {
    const grupos: { importancia: Pedido["importancia"]; pedidos: Pedido[] }[] = Array.from(
      IMPORTANCIAS,
      (i) => ({ importancia: i.value, pedidos: [] }),
    );

    for (const p of pedidos) {
      const grp = grupos.find((g) => g.importancia === p.importancia) ?? grupos[grupos.length - 1];
      grp.pedidos.push(p);
    }

    for (const grp of grupos) {
      // Con fecha esperada primero (orden por fecha), sin fecha al final.
      grp.pedidos.sort((a, b) => {
        const aF = a.fecha_esperada ? a.fecha_esperada.trim() : "";
        const bF = b.fecha_esperada ? b.fecha_esperada.trim() : "";
        if (aF && bF) {
          const cmp = aF.localeCompare(bF);
          if (cmp !== 0) return cmp;
        } else if (aF && !bF) {
          return -1;
        } else if (!aF && bF) {
          return 1;
        }
        return (Number(b.id) || 0) - (Number(a.id) || 0);
      });
    }

    return grupos.filter((g) => g.pedidos.length > 0);
  }, [pedidos]);

  return (
    <section className="minuta-section">
      <div className="minuta-section-head">
        <h2>Indicadores de cumplimiento</h2>
      </div>

      <div className="minuta-ind-resumen">
        <div className="minuta-ind-global">
          <span className="minuta-ind-global-num">{global}%</span>
          <span className="minuta-ind-global-label">Cumplimiento general</span>
          <div className="minuta-ind-bar">
            <div
              className="minuta-ind-bar-fill"
              style={{ width: `${global}%` }}
              aria-hidden="true"
            />
          </div>
        </div>
        <ul className="minuta-ind-contadores">
          {(Object.keys(AVANCE_ESTADO) as EstadoItem[]).map((estado) => (
            <li key={estado} className={`minuta-ind-contador minuta-ind-estado-${estado}`}>
              <span className="minuta-ind-contador-n">{contadores[estado] ?? 0}</span>{" "}
              {labelEstado(estado)}
            </li>
          ))}
        </ul>
      </div>

      {grupos.length === 0 && (
        <p className="minuta-hint">No hay pedidos activos para mostrar indicadores.</p>
      )}

      {grupos.map((grp) => (
        <details
          key={grp.importancia}
          className="minuta-ind-grupo"
          {...(grp.importancia === "critico" ? { open: true } : {})}
        >
          <summary className={`minuta-ind-grupo-title minuta-imp-${grp.importancia}`}>
            <span className="minuta-ind-grupo-name">
              {labelImportancia(grp.importancia)}
            </span>
            <span className="minuta-ind-grupo-count">{grp.pedidos.length}</span>
          </summary>
          <ul className="minuta-ind-lista">
            {grp.pedidos.map((p) => {
              const avance = AVANCE_ESTADO[p.estado] ?? 0;
              const conFecha = Boolean(p.fecha_esperada && p.fecha_esperada.trim());
              const vencido = conFecha && (p.fecha_esperada as string).trim() < hoy;
              const numero = p.n_pedido || `#${p.id}`;
              const descripcion = p.pedido?.trim();
              return (
                <li key={p.id} className="minuta-ind-item">
                  <div className="minuta-ind-item-head">
                    <span className="minuta-ind-item-label">
                      {numero}
                      {descripcion && (
                        <span className="minuta-ind-item-desc">{descripcion}</span>
                      )}
                    </span>
                    <span className={`minuta-ind-avance-num minuta-ind-estado-${p.estado}`}>
                      {avance}%
                    </span>
                  </div>
                  <div className="minuta-ind-bar">
                    <div
                      className={`minuta-ind-bar-fill minuta-ind-estado-${p.estado}`}
                      style={{ width: `${avance}%` }}
                      aria-hidden="true"
                    />
                  </div>
                  <div className="minuta-ind-item-meta">
                    <span className={`minuta-ind-avance-estado minuta-ind-estado-${p.estado}`}>
                      {labelEstado(p.estado)}
                    </span>
                    {conFecha ? (
                      <span
                        className={vencido ? "minuta-ind-vencido" : "minuta-ind-a-tiempo"}
                        title={
                          vencido
                            ? "Vencido respecto de la fecha esperada"
                            : "A tiempo respecto de la fecha esperada"
                        }
                      >
                        {vencido ? "Vencido" : "A tiempo"} · esperado{" "}
                        {fmtFecha(p.fecha_esperada as string)}
                      </span>
                    ) : (
                      <span className="minuta-ind-sin-fecha">Sin fecha esperada</span>
                    )}
                  </div>
                </li>
              );
            })}
          </ul>
        </details>
      ))}
    </section>
  );
}
