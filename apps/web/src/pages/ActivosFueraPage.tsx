import { useCallback, useEffect, useState } from "react";
import { useAuth } from "../auth/AuthContext";
import { permisoDe } from "../config/navegacion";
import { fetchActivosResumen, type ActivosResumen } from "../api/activosClient";
import ActivosPanel from "../components/activos/ActivosPanel";

export default function ActivosFueraPage() {
  const { usuario, token } = useAuth();
  const [data, setData] = useState<ActivosResumen | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const puedeEscribir = permisoDe(usuario, "activos") === "escritura";

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setData(await fetchActivosResumen(token ?? undefined));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error al cargar activos fuera de planta.");
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <div className="page-content act-page-wide">
      <header className="page-header">
        <h1>Activos fuera de planta</h1>
        <p className="sub">Seguimiento de reparaciones, remitos y estado por sector.</p>
      </header>
      <ActivosPanel
        data={data}
        loading={loading}
        error={error}
        puedeEscribir={puedeEscribir}
        token={token}
        onRetry={() => void load()}
        onRefreshed={() => void load()}
      />
    </div>
  );
}
