import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  actualizarPedido,
  actualizarReunion,
  agregarNovedad,
  crearPedido,
  eliminarPedido,
  fetchPedido,
  fetchPedidosReunion,
  fetchReunion,
  fetchReuniones,
  finalizarPedido,
  limpiarConsultas,
  reactivarPedido,
  reordenarPedidos,
  type Pedido,
  type PedidoPatch,
  type Reunion,
} from "../../api/minutaClient";
import { useAuth } from "../../auth/AuthContext";
import {
  cargarSesionLocal,
  guardarSesionLocal,
  sesionInicial,
  type MinutaSesionLocal,
} from "./types";

export function useMinutaSession(reunionId: number) {
  const { usuario } = useAuth();
  const scope = (usuario?.email ?? "anon").toLowerCase();
  const [reunion, setReunion] = useState<Reunion | null>(null);
  const [sesion, setSesion] = useState<MinutaSesionLocal>(() =>
    cargarSesionLocal(scope, reunionId) ?? sesionInicial(reunionId),
  );
  const [pedidosRaw, setPedidosRaw] = useState<Pedido[]>([]);
  const [reunionesEnviadas, setReunionesEnviadas] = useState<Reunion[]>([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandidoId, setExpandidoId] = useState<number | null>(null);
  const debounceConsultas = useRef<Record<number, ReturnType<typeof setTimeout>>>({});

  useEffect(() => {
    guardarSesionLocal(scope, reunionId, sesion);
  }, [scope, reunionId, sesion]);

  /** Pedidos con overlays de cache local (excepto consultas que ya van a DB). */
  const pedidos = useMemo(() => {
    return pedidosRaw.map((p) => {
      const patch = sesion.borradoresCampos[p.id];
      if (!patch) return p;
      const { consultas: _c, ...rest } = patch;
      return { ...p, ...rest };
    });
  }, [pedidosRaw, sesion.borradoresCampos]);

  const pedidosActivos = useMemo(
    () => pedidos.filter((p) => Number(p.activo) === 1),
    [pedidos],
  );
  const pedidosFinalizados = useMemo(
    () => pedidos.filter((p) => Number(p.activo) !== 1),
    [pedidos],
  );

  const recargar = useCallback(async (opciones?: { silencioso?: boolean }) => {
    if (!opciones?.silencioso) setCargando(true);
    setError(null);
    try {
      const r = await fetchReunion(reunionId);
      setReunion(r);
      const local = cargarSesionLocal(scope, reunionId);
      setSesion((s) => ({
        ...s,
        reunionId,
        fecha: local?.fecha || r.fecha || s.fecha,
        sectoresComprometidos:
          local?.sectoresComprometidos ||
          r.sectores_comprometidos ||
          r.sector ||
          s.sectoresComprometidos,
        notasGenerales: local?.notasGenerales ?? r.notas_generales ?? s.notasGenerales,
        borradoresNovedad: local?.borradoresNovedad ?? s.borradoresNovedad,
        borradoresCampos: local?.borradoresCampos ?? s.borradoresCampos,
        vistosEnReunion: local?.vistosEnReunion ?? s.vistosEnReunion,
        destinatarios: local?.destinatarios ?? s.destinatarios,
      }));
      const [lista, enviadas] = await Promise.all([
        fetchPedidosReunion(reunionId, false),
        fetchReuniones({ sector: r.sector, soloEnviadas: true, limite: 30 }),
      ]);
      setPedidosRaw(lista);
      setReunionesEnviadas(enviadas.filter((x) => x.id !== reunionId));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error al cargar reunión.");
    } finally {
      setCargando(false);
    }
  }, [reunionId, scope]);

  useEffect(() => {
    void recargar();
  }, [recargar]);

  const setSesionParcial = useCallback(
    (patch: Partial<MinutaSesionLocal>) => {
      setSesion((s) => {
        const next = { ...s, ...patch };
        guardarSesionLocal(scope, reunionId, next);
        return next;
      });
    },
    [scope, reunionId],
  );

  const setNotasGenerales = useCallback(
    (notasGenerales: string) => setSesionParcial({ notasGenerales }),
    [setSesionParcial],
  );

  const setDestinatarios = useCallback(
    (destinatarios: string[]) => setSesionParcial({ destinatarios }),
    [setSesionParcial],
  );

  const toggleDestinatario = useCallback(
    (email: string) => {
      setSesion((s) => {
        const set = new Set(s.destinatarios);
        if (set.has(email)) set.delete(email);
        else set.add(email);
        const next = { ...s, destinatarios: [...set] };
        guardarSesionLocal(scope, reunionId, next);
        return next;
      });
    },
    [scope, reunionId],
  );

  const setBorradorNovedad = useCallback(
    (pedidoId: number, texto: string) => {
      setSesion((s) => {
        const next = {
          ...s,
          borradoresNovedad: { ...s.borradoresNovedad, [pedidoId]: texto },
        };
        guardarSesionLocal(scope, reunionId, next);
        return next;
      });
    },
    [scope, reunionId],
  );

  /** Campos en cache + persistencia inmediata a DB para no perder datos (fix 3 vacíos). */
  const guardarCampoPedido = useCallback(
    (id: number, patch: PedidoPatch) => {
      // Optimista en UI
      setPedidosRaw((list) =>
        list.map((p) => (p.id === id ? { ...p, ...patch } as Pedido : p)),
      );
      // Consultas con debounce (ya estaba)
      if ("consultas" in patch && Object.keys(patch).length === 1) {
        if (debounceConsultas.current[id]) clearTimeout(debounceConsultas.current[id]);
        debounceConsultas.current[id] = setTimeout(() => {
          void actualizarPedido(id, { consultas: patch.consultas }).catch(() => {});
        }, 400);
        return;
      }
      // Para pedido/n_pedido/oc/etc. también persistir inmediato + guardar en cache por si falla
      const patchSinConsultas = { ...patch };
      // Si solo es consultas ya lo manejamos arriba
      if ("consultas" in patchSinConsultas && Object.keys(patchSinConsultas).length === 1) return;
      // Guardar en cache local por si hay error de red
      setSesion((s) => {
        const prev = s.borradoresCampos[id] ?? {};
        const next = {
          ...s,
          borradoresCampos: { ...s.borradoresCampos, [id]: { ...prev, ...patch } },
        };
        guardarSesionLocal(scope, reunionId, next);
        return next;
      });
      // Persistir a DB inmediato (sin debounce, para que el mail lo vea)
      void actualizarPedido(id, patch).catch(() => {});
    },
    [scope, reunionId],
  );

  const reordenarLocal = useCallback(
    (idsOrdenados: number[]) => {
      setPedidosRaw((list) => {
        const byId = new Map(list.map((p) => [p.id, p]));
        const ordenados = idsOrdenados
          .map((id, idx) => {
            const p = byId.get(id);
            return p ? { ...p, orden: idx } : undefined;
          })
          .filter((p): p is Pedido => Boolean(p));
        const restantes = list
          .filter((p) => !idsOrdenados.includes(p.id))
          .map((p, i) => ({ ...p, orden: idsOrdenados.length + i }));
        return [...ordenados, ...restantes];
      });
      void reordenarPedidos(reunionId, idsOrdenados).catch(() => {});
    },
    [reunionId],
  );

  const addPedido = useCallback(async () => {
    if (!reunion) return;
    try {
      const p = await crearPedido({
        reunion_id: reunionId,
        sector: reunion.sector,
        fecha: sesion.fecha,
      });
      setPedidosRaw((list) => [p, ...list]);
      setExpandidoId(p.id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "No se pudo crear el pedido.");
    }
  }, [reunion, reunionId, sesion.fecha]);

  const ejecutarFinalizar = useCallback(async (pedidoId: number) => {
    try {
      const p = await finalizarPedido(pedidoId, { fecha: sesion.fecha });
      setPedidosRaw((list) => list.map((x) => (x.id === pedidoId ? { ...x, ...p, activo: 0 } : x)));
      setSesion((s) => {
        const nextNov = { ...s.borradoresNovedad };
        delete nextNov[pedidoId];
        return { ...s, borradoresNovedad: nextNov };
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error al finalizar.");
      throw e;
    }
  }, [sesion.fecha]);

  const ejecutarReactivar = useCallback(async (pedidoId: number) => {
    try {
      const p = await reactivarPedido(pedidoId);
      setPedidosRaw((list) => list.map((x) => (x.id === pedidoId ? { ...x, ...p, activo: 1 } : x)));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error al reactivar.");
      throw e;
    }
  }, []);

  const ejecutarEliminar = useCallback(async (pedidoId: number) => {
    try {
      await eliminarPedido(pedidoId);
      setPedidosRaw((list) => list.filter((p) => p.id !== pedidoId));
      setSesion((s) => {
        const nextNov = { ...s.borradoresNovedad };
        const nextCam = { ...s.borradoresCampos };
        const nextVistos = { ...s.vistosEnReunion };
        delete nextNov[pedidoId];
        delete nextCam[pedidoId];
        delete nextVistos[pedidoId];
        return {
          ...s,
          borradoresNovedad: nextNov,
          borradoresCampos: nextCam,
          vistosEnReunion: nextVistos,
        };
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error al eliminar.");
      throw e;
    }
  }, []);

  /** Al enviar: persiste campos/novedades cacheados. No aborta si un id local ya no existe. */
  const persistirAlEnviar = useCallback(async () => {
    const avisos: string[] = [];
    const idsEnReunion = new Set(pedidosRaw.map((p) => p.id));

    const esFaltante = (err: unknown) =>
      err instanceof Error && /no encontrado/i.test(err.message);

    for (const [pidStr, patch] of Object.entries(sesion.borradoresCampos)) {
      const pid = Number(pidStr);
      if (!Number.isFinite(pid)) continue;
      const { consultas: _c, ...rest } = patch;
      if (Object.keys(rest).length === 0) continue;
      try {
        await actualizarPedido(pid, rest);
      } catch (e) {
        if (esFaltante(e)) {
          avisos.push(`Ítem #${pid} (campos): no está en el servidor, se omitió.`);
          continue;
        }
        throw e;
      }
    }

    for (const [pidStr, texto] of Object.entries(sesion.borradoresNovedad)) {
      const pid = Number(pidStr);
      const t = texto.trim();
      if (!t || !Number.isFinite(pid)) continue;
      // Preferir ids de esta reunión; igual intentar otros por si el ítem vive en Histórico.
      try {
        await agregarNovedad(pid, {
          fecha_reunion: sesion.fecha,
          texto: t,
        });
      } catch (e) {
        if (esFaltante(e)) {
          if (!idsEnReunion.has(pid)) {
            avisos.push(`Ítem #${pid} (novedad): no encontrado; va solo en el mail local.`);
          } else {
            avisos.push(`Ítem #${pid} (novedad): no encontrado en servidor.`);
          }
          continue;
        }
        throw e;
      }
    }

    await actualizarReunion(reunionId, {
      notas_generales: sesion.notasGenerales,
      sectores_comprometidos: sesion.sectoresComprometidos,
      fecha: sesion.fecha,
      email_enviado_en: new Date().toISOString(),
    });
    if (reunionId) {
      await limpiarConsultas(reunionId).catch(() => {});
    }
    return avisos;
  }, [sesion, reunionId, pedidosRaw]);

  const expandirPedido = useCallback(async (id: number | null) => {
    setExpandidoId(id);
    if (id == null) return;
    try {
      const detalle = await fetchPedido(id);
      setPedidosRaw((list) =>
        list.map((p) =>
          p.id === id
            ? { ...p, novedades: detalle.novedades, movimientos: detalle.movimientos }
            : p,
        ),
      );
    } catch {
      /* historial no crítico */
    }
  }, []);

  const setVistoPedido = useCallback((pedidoId: number, visto: boolean) => {
    setSesion((s) => ({
      ...s,
      vistosEnReunion: { ...s.vistosEnReunion, [pedidoId]: visto },
    }));
  }, []);

  const resetBorradoresTrasEnvio = useCallback(() => {
    setSesionParcial({
      destinatarios: [],
      borradoresNovedad: {},
      borradoresCampos: {},
      vistosEnReunion: {},
      notasGenerales: "",
    });
  }, [setSesionParcial]);

  return {
    reunion,
    sesion,
    pedidosActivos,
    pedidosFinalizados,
    reunionesEnviadas,
    cargando,
    error,
    setError,
    expandidoId,
    expandirPedido,
    setNotasGenerales,
    setDestinatarios,
    toggleDestinatario,
    setBorradorNovedad,
    setVistoPedido,
    guardarCampoPedido,
    reordenarLocal,
    addPedido,
    ejecutarFinalizar,
    ejecutarReactivar,
    ejecutarEliminar,
    persistirAlEnviar,
    setSesionParcial,
    resetBorradoresTrasEnvio,
    recargar,
  };
}
