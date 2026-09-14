/**
 * PersonalTabla — Componente de tabla de datos para el módulo Personal.
 */

import type { Personal } from "../../api/personalClient";

type Props = {
  items: Personal[];
  loading: boolean;
  selectedId: number | null;
  onSelect: (p: Personal) => void;
};

export default function PersonalTabla({ items, loading, selectedId, onSelect }: Props) {
  if (loading) {
    return <p className="sol-hint">Cargando personal…</p>;
  }

  if (items.length === 0) {
    return <p className="sol-hint">Sin resultados.</p>;
  }

  const tipoLabel: Record<string, string> = {
    tecnico: "Técnico",
    supervisor: "Supervisor",
    produccion: "Producción",
    generico: "Genérico",
    panol: "Pañol",
  };

  return (
    <table className="sol-table">
      <thead>
        <tr>
          <th>Nombre</th>
          <th>Legajo</th>
          <th>Email</th>
          <th>Área</th>
          <th>Tipo</th>
          <th>Activo</th>
        </tr>
      </thead>
      <tbody>
        {items.map((p) => (
          <tr
            key={p.id}
            className={selectedId === p.id ? "selected" : ""}
            onClick={() => onSelect(p)}
          >
            <td><strong>{p.nombre}</strong></td>
            <td>{p.legajo ?? "—"}</td>
            <td>{p.email ?? "—"}</td>
            <td>{p.area_id ?? "—"}</td>
            <td>{tipoLabel[p.tipo] ?? p.tipo}</td>
            <td>
              <span className={`sol-estado sol-estado-${p.activo ? "cumplido" : "cancelado"}`}>
                {p.activo ? "Activo" : "Inactivo"}
              </span>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
