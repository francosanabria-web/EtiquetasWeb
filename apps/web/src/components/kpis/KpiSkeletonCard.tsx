type Props = { lines?: number; height?: number };

export default function KpiSkeletonCard({ lines = 3, height }: Props) {
  return (
    <div className="kpi-skeleton-card" style={height ? { minHeight: height } : undefined}>
      {Array.from({ length: lines }).map((_, i) => (
        <div key={i} className="kpi-skeleton-line" style={{ width: i === 0 ? "40%" : i === lines - 1 ? "70%" : "90%" }} />
      ))}
    </div>
  );
}

export function KpiSkeletonGrid({ count = 4 }: { count?: number }) {
  return (
    <div className="kpi-grid-2">
      {Array.from({ length: count }).map((_, i) => (
        <KpiSkeletonCard key={i} height={220} />
      ))}
    </div>
  );
}
