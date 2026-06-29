import type { ConfigImportacion, MetaImportacion, RegistroGasto } from "../types/kpi";

const CONFIG_KEY = "kpis-panol-config-v1";
const DB_NAME = "kpis-panol-db";
const DB_VERSION = 1;
const STORE = "dataset";

export type DatasetCache = {
  registros: RegistroGasto[];
  meta: MetaImportacion;
  config: ConfigImportacion;
};

function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onerror = () => reject(req.error);
    req.onsuccess = () => resolve(req.result);
    req.onupgradeneeded = () => {
      req.result.createObjectStore(STORE);
    };
  });
}

export async function guardarDataset(data: DatasetCache): Promise<void> {
  localStorage.setItem(CONFIG_KEY, JSON.stringify(data.config));
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE, "readwrite");
    tx.objectStore(STORE).put(data, "actual");
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}

export async function cargarDataset(): Promise<DatasetCache | null> {
  const cfgRaw = localStorage.getItem(CONFIG_KEY);
  if (!cfgRaw) return null;

  let config: ConfigImportacion;
  try {
    config = JSON.parse(cfgRaw) as ConfigImportacion;
  } catch {
    return null;
  }

  const db = await openDb();
  const registros = await new Promise<RegistroGasto[] | null>((resolve, reject) => {
    const tx = db.transaction(STORE, "readonly");
    const req = tx.objectStore(STORE).get("actual");
    req.onsuccess = () => {
      const val = req.result as DatasetCache | undefined;
      resolve(val?.registros ?? null);
    };
    req.onerror = () => reject(req.error);
  });

  if (!registros?.length) return null;

  const metaRaw = localStorage.getItem(`${CONFIG_KEY}-meta`);
  let meta: MetaImportacion = {
    nombreArchivo: "Caché local",
    importadoEn: new Date().toISOString(),
    filasValidas: registros.length,
    filasDescartadas: 0,
  };
  if (metaRaw) {
    try {
      meta = JSON.parse(metaRaw) as MetaImportacion;
    } catch {
      /* usar default */
    }
  }

  return { registros, meta, config };
}

export async function guardarConfig(config: ConfigImportacion): Promise<void> {
  localStorage.setItem(CONFIG_KEY, JSON.stringify(config));
}

export async function guardarMeta(meta: MetaImportacion): Promise<void> {
  localStorage.setItem(`${CONFIG_KEY}-meta`, JSON.stringify(meta));
}

export async function limpiarCache(): Promise<void> {
  localStorage.removeItem(CONFIG_KEY);
  localStorage.removeItem(`${CONFIG_KEY}-meta`);
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE, "readwrite");
    tx.objectStore(STORE).delete("actual");
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}

export function cargarConfig(): ConfigImportacion | null {
  const raw = localStorage.getItem(CONFIG_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as ConfigImportacion;
  } catch {
    return null;
  }
}
