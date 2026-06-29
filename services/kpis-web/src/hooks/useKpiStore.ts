import { useCallback, useEffect, useMemo, useState } from "react";
import {
  agruparPor,
  calcularResumen,
  filtrarRegistros,
  rangoFechasDefault,
  seriePorFecha,
  transformarFilas,
  valoresUnicos,
} from "../lib/kpiEngine";
import { obtenerMatrizHoja } from "../lib/excelParser";
import { crearConfigInicial, configValida } from "../lib/columnMapper";
import {
  cargarDataset,
  guardarDataset,
  limpiarCache,
  type DatasetCache,
} from "../lib/cache";
import type {
  ConfigImportacion,
  FiltrosDashboard,
  MetaImportacion,
  RegistroGasto,
  ResultadoParseo,
  VistaActiva,
} from "../types/kpi";

export type EstadoKpi = {
  cargando: boolean;
  registros: RegistroGasto[];
  config: ConfigImportacion | null;
  meta: MetaImportacion | null;
  filtros: FiltrosDashboard;
  vista: VistaActiva;
  parseo: ResultadoParseo | null;
  archivoPendiente: File | null;
  error: string | null;
  mensaje: string | null;
};

export function useKpiStore() {
  const [cargando, setCargando] = useState(true);
  const [registros, setRegistros] = useState<RegistroGasto[]>([]);
  const [config, setConfig] = useState<ConfigImportacion | null>(null);
  const [meta, setMeta] = useState<MetaImportacion | null>(null);
  const [filtros, setFiltros] = useState<FiltrosDashboard>({
    fechaDesde: "",
    fechaHasta: "",
    lineas: [],
    obras: [],
  });
  const [vista, setVista] = useState<VistaActiva>("dashboard");
  const [parseo, setParseo] = useState<ResultadoParseo | null>(null);
  const [archivoPendiente, setArchivoPendiente] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [mensaje, setMensaje] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const cache = await cargarDataset();
        if (cache) {
          setRegistros(cache.registros);
          setConfig(cache.config);
          setMeta(cache.meta);
          const rango = rangoFechasDefault(cache.registros);
          setFiltros((f) => ({
            ...f,
            fechaDesde: rango.desde,
            fechaHasta: rango.hasta,
          }));
          setMensaje("Datos restaurados desde caché local.");
        }
      } catch {
        setError("No se pudo leer la caché local.");
      } finally {
        setCargando(false);
      }
    })();
  }, []);

  const registrosFiltrados = useMemo(
    () => filtrarRegistros(registros, filtros),
    [registros, filtros]
  );

  const resumen = useMemo(
    () => calcularResumen(registrosFiltrados),
    [registrosFiltrados]
  );

  const porLinea = useMemo(
    () => agruparPor(registrosFiltrados, "linea").slice(0, 12),
    [registrosFiltrados]
  );

  const porObra = useMemo(
    () => agruparPor(registrosFiltrados, "obra").slice(0, 10),
    [registrosFiltrados]
  );

  const porCategoria = useMemo(
    () => agruparPor(registrosFiltrados, "categoria").slice(0, 8),
    [registrosFiltrados]
  );

  const serie = useMemo(
    () => seriePorFecha(registrosFiltrados),
    [registrosFiltrados]
  );

  const lineasDisponibles = useMemo(
    () => valoresUnicos(registros, "linea"),
    [registros]
  );

  const obrasDisponibles = useMemo(
    () => valoresUnicos(registros, "obra"),
    [registros]
  );

  const persistir = useCallback(async (data: DatasetCache) => {
    await guardarDataset(data);
    setRegistros(data.registros);
    setConfig(data.config);
    setMeta(data.meta);
    const rango = rangoFechasDefault(data.registros);
    setFiltros({
      fechaDesde: rango.desde,
      fechaHasta: rango.hasta,
      lineas: [],
      obras: [],
    });
  }, []);

  const procesarConConfig = useCallback(
    async (file: File, cfg: ConfigImportacion) => {
      if (!configValida(cfg)) {
        setError("Completá al menos Fecha e Importe en el mapeo de columnas.");
        return;
      }
      setCargando(true);
      setError(null);
      try {
        const buffer = await file.arrayBuffer();
        const { filas } = obtenerMatrizHoja(buffer, cfg.hoja, cfg.filaEncabezado);
        const { validos, descartados } = transformarFilas(filas, cfg);
        if (!validos.length) {
          setError(
            "No se encontraron filas válidas. Revisá el mapeo de columnas y el formato de fecha/importe."
          );
          return;
        }
        const metaNueva: MetaImportacion = {
          nombreArchivo: file.name,
          importadoEn: new Date().toISOString(),
          filasValidas: validos.length,
          filasDescartadas: descartados,
        };
        await persistir({ registros: validos, config: cfg, meta: metaNueva });
        setParseo(null);
        setArchivoPendiente(null);
        setVista("dashboard");
        setMensaje(
          `Importados ${validos.length} registros${descartados ? ` (${descartados} descartados)` : ""}.`
        );
      } catch (e) {
        setError(e instanceof Error ? e.message : "Error al procesar el archivo.");
      } finally {
        setCargando(false);
      }
    },
    [persistir]
  );

  const iniciarImportacion = useCallback(
    (file: File, resultado: ResultadoParseo) => {
      setArchivoPendiente(file);
      setParseo(resultado);
      setError(null);
      const hoja = resultado.hojas[0];
      if (!hoja) {
        setError("El archivo no contiene hojas legibles.");
        return;
      }
      const cfgGuardada = config;
      if (
        cfgGuardada &&
        cfgGuardada.hoja === hoja.nombre &&
        configValida(cfgGuardada)
      ) {
        void procesarConConfig(file, cfgGuardada);
        return;
      }
      const cfg = crearConfigInicial(hoja.nombre, hoja.encabezados);
      setConfig(cfg);
      setVista("config");
    },
    [config, procesarConConfig]
  );

  const confirmarMapeo = useCallback(() => {
    if (!archivoPendiente || !config) return;
    void procesarConConfig(archivoPendiente, config);
  }, [archivoPendiente, config, procesarConConfig]);

  const borrarCache = useCallback(async () => {
    if (!confirm("¿Eliminar datos y configuración guardados en este navegador?")) return;
    await limpiarCache();
    setRegistros([]);
    setConfig(null);
    setMeta(null);
    setParseo(null);
    setArchivoPendiente(null);
    setFiltros({ fechaDesde: "", fechaHasta: "", lineas: [], obras: [] });
    setMensaje("Caché eliminada.");
  }, []);

  return {
    cargando,
    registros,
    registrosFiltrados,
    config,
    setConfig,
    meta,
    filtros,
    setFiltros,
    vista,
    setVista,
    parseo,
    archivoPendiente,
    error,
    setError,
    mensaje,
    setMensaje,
    resumen,
    porLinea,
    porObra,
    porCategoria,
    serie,
    lineasDisponibles,
    obrasDisponibles,
    iniciarImportacion,
    confirmarMapeo,
    borrarCache,
  };
}
