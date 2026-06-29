import { useCallback, useEffect, useState } from "react";
import {
  ApiError,
  getSesionActual,
  iniciarSesion,
  listarSesiones,
} from "../api/client";
import type { SesionDetalle, SesionResumen } from "../types/minuta";

export function useMinutaSession() {
  const [sesion, setSesion] = useState<SesionDetalle | null>(null);
  const [historial, setHistorial] = useState<SesionResumen[]>([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [apiOk, setApiOk] = useState(true);

  const refrescar = useCallback(async () => {
    setError(null);
    try {
      const [actual, lista] = await Promise.all([
        getSesionActual(),
        listarSesiones(),
      ]);
      setSesion(actual);
      setHistorial(lista);
      setApiOk(true);
    } catch (e) {
      setApiOk(false);
      setError(e instanceof ApiError ? e.message : "Error al cargar la sesión.");
    } finally {
      setCargando(false);
    }
  }, []);

  useEffect(() => {
    void refrescar();
  }, [refrescar]);

  const iniciar = useCallback(
    async (responsable: string) => {
      setCargando(true);
      setError(null);
      try {
        const s = await iniciarSesion({
          responsable: responsable.trim() || undefined,
        });
        setSesion(s);
        await refrescar();
      } catch (e) {
        setError(e instanceof ApiError ? e.message : "No se pudo iniciar la reunión.");
      } finally {
        setCargando(false);
      }
    },
    [refrescar]
  );

  return {
    sesion,
    setSesion,
    historial,
    cargando,
    error,
    setError,
    apiOk,
    refrescar,
    iniciar,
  };
}
