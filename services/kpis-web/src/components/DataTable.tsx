import type { RegistroGasto } from "../types/kpi";
import { formatearFecha, formatearMoneda } from "../lib/kpiEngine";

type Props = {
  registros: RegistroGasto[];
  maxFilas?: number;
};

export default function DataTable({ registros, maxFilas = 200 }: Props) {
  const filas = registros.slice(0, maxFilas);

  return (
    <div className="table-wrap">
      <table className="data-table">
        <thead>
          <tr>
            <th>Fecha</th>
            <th>Línea</th>
            <th>Obra</th>
            <th>Concepto</th>
            <th>Categoría</th>
            <th className="num">Importe</th>
          </tr>
        </thead>
        <tbody>
          {filas.map((r) => (
            <tr key={r.id}>
              <td>{formatearFecha(r.fecha)}</td>
              <td>{r.linea}</td>
              <td>{r.obra}</td>
              <td>{r.concepto || "—"}</td>
              <td>{r.categoria}</td>
              <td className="num">{formatearMoneda(r.importe)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {registros.length > maxFilas && (
        <p className="table-note">
          Mostrando {maxFilas} de {registros.length} registros. Acotá con filtros para ver el detalle completo.
        </p>
      )}
      {!registros.length && (
        <p className="empty">No hay registros con los filtros actuales.</p>
      )}
    </div>
  );
}
