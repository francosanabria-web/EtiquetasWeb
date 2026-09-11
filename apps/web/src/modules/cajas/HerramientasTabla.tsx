/**
 * HerramientasTabla — Tabla de herramientas con codigo, categoria, unidad.
 */

import type { Herramienta } from "../../api/cajasClient";

type Props = {
  herramientas: Herramienta[];
  loading: boolean;
};

export default function HerramientasTabla({ herramientas, loading }: Props) {
  if (loading) {
    return <p className="sol-hint">Cargando herramientas…</p>;
  }

  if (herramientas.length === 0) {
    return <p className="sol-hint">Sin herramientas.</p>;
  }

  return (
    <table className="sol-table">
      <thead>
        <tr>
          <th>Codigo</th>
          <th>Descripcion</th>
          <th>Categoria</th>
          <th>Unidad</th>
          <th>Articulo</th>
        </tr>
      </thead>
      <tbody>
        {herramientas.map((h) => (
          <tr key={h.id}>
            <td><strong>{h.codigo}</strong></td>
            <td>{h.descripcion ?? "—"}</td>
            <td>{h.categoria}</td>
            <td>{h.unidad}</td>
            <td>{h.articulo_codigo ?? "—"}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
