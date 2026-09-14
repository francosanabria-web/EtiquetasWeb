import KpiNamedBarList from "./KpiNamedBarList";
import type { BarItem } from "./KpiBarChart";

type Props = {
  data: BarItem[];
  height?: number;
};

/** @deprecated Usar KpiNamedBarList. Mantiene compat. para Gasto por sector. */
export default function KpiSectorBarList({ data, height }: Props) {
  return <KpiNamedBarList data={data} height={height} ariaLabel="Gasto por sector" />;
}
