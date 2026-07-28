import { useCallback, useEffect, useState } from "react";
import { fetchActivos, type ActivosResumen } from "../api/kpisClient";
import ActivosSection from "../components/kpis/ActivosSection";

export default function ActivosFueraPage() {
  const [data, setData] = useState<ActivosResumen | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setData(await fetchActivos());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error al cargar activos fuera de planta.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <div className="page-content">
      <header className="page-header">
        <h1>Activos fuera de planta</h1>
        <p className="sub">Seguimiento de reparaciones, remitos y estado por sector.</p>
      </header>
      <ActivosSection data={data} loading={loading} error={error} onRetry={() => void load()} />
    </div>
  );
}

