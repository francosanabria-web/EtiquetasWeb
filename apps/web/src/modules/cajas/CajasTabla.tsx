/**
 * CajasTabla — Componente de tabla de datos para el módulo Cajas de Herramientas.
 */

import type { Caja, Herramienta } from "../../api/cajasClient";

type CajasProps = {
  cajas: Caja[];
  herramientas: Herramienta[];
  loading: boolean;
  selectedCajaId: number | null;
  selectedHerramientaId: number | null;
  onSelectCaja: (c: Caja) => void;
  onSelectHerramienta: (h: Herramienta) => void;
};

export default function CajasTabla({ cajas, herramientas, loading, selectedCajaId, selectedHerramientaId, onSelectCaja, onSelectHerramienta }: CajasProps) {
  if (loading) {
    return <p className="sol-hint">Cargando cajas…</p>;
  }

  if (cajas.length === 0 && herramientas.length === 0) {
    return <p className="sol-hint">Sin resultados.</p>;
  }

  return (
    <table className="sol-table">
      <thead>
        <tr>
          <th>Codigo</th>
          <th>Descripcion</th>
          <th>Ubicacion</th>
          <th>Activa</th>
          <th>Tipo</th>
        </tr>
      </thead>
      <tbody>
        {cajas.map((c) => (
          <tr
            key={c.id}
            className={selectedCajaId === c.id ? "selected" : ""}
            onClick={() => onSelectCaja(c)}
          >
            <td><strong>{c.codigo}</strong></td>
            <td>{c.descripcion ?? "—"}</td>
            <td>{c.ubicacion ?? "—"}</td>
            <td><span className={`sol-estado sol-estado-${c.activa ? "cumplido" : "cancelado"}`}>{c.activa ? "Sí" : "No"}</span></td>
            <td>Caja</td>
          </tr>
        ))}
        {herramientas.map((h) => (
          <tr
            key={h.id}
            className={selectedHerramientaId === h.id ? "selected" : ""}
            onClick={() => onSelectHerramienta(h)}
          >
            <td><strong>{h.codigo}</strong></td>
            <td>{h.descripcion ?? "—"}</td>
            <td>{h.unidad}</td>
            <td>—</td>
            <td>Herramienta</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
