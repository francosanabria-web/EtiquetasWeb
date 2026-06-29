import { formatearMoneda } from "../lib/kpiEngine";

type Props = {
  titulo: string;
  valor: string;
  detalle?: string;
  accent?: "blue" | "teal" | "amber" | "violet";
};

export default function KpiCard({ titulo, valor, detalle, accent = "blue" }: Props) {
  return (
    <article className={`kpi-card accent-${accent}`}>
      <span className="kpi-label">{titulo}</span>
      <strong className="kpi-value">{valor}</strong>
      {detalle && <span className="kpi-detail">{detalle}</span>}
    </article>
  );
}

export function KpiCardMoneda({
  titulo,
  monto,
  detalle,
  accent,
}: {
  titulo: string;
  monto: number;
  detalle?: string;
  accent?: Props["accent"];
}) {
  return (
    <KpiCard titulo={titulo} valor={formatearMoneda(monto)} detalle={detalle} accent={accent} />
  );
}
