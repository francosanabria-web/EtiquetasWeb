import { collection, getDocs } from "firebase/firestore";
import { db } from "./firebase";

/** Artículo del catálogo Firestore (misma forma que AppPanolWeb). */
export type ArticuloCatalogo = {
  id: string;
  codigo?: string;
  desc?: string;
  alias?: string;
  stock?: string | number;
  ubicacion?: string;
};

/** Máximo de resultados mostrados por búsqueda (filtrado en cliente). */
export const MAX_SEARCH_RESULTS = 100;

let memoryCatalog: ArticuloCatalogo[] | null = null;
let catalogLoadPromise: Promise<ArticuloCatalogo[]> | null = null;

function snapToLista(snap: Awaited<ReturnType<typeof getDocs>>): ArticuloCatalogo[] {
  const lista: ArticuloCatalogo[] = [];
  snap.forEach((d) => {
    const data = d.data() as Record<string, unknown>;
    lista.push({ id: d.id, ...data } as ArticuloCatalogo);
  });
  return lista;
}

export function getCatalogFromMemory(): ArticuloCatalogo[] {
  return memoryCatalog ?? [];
}

export function isCatalogLoaded(): boolean {
  return memoryCatalog !== null && memoryCatalog.length > 0;
}

/**
 * Carga catálogo Firestore `articulos` (caché persistente IndexedDB).
 * Misma estrategia que AppPanolWeb: getDocs + filtro en cliente.
 */
export async function ensureCatalogLoaded(): Promise<ArticuloCatalogo[]> {
  if (memoryCatalog) return memoryCatalog;
  if (catalogLoadPromise) return catalogLoadPromise;

  catalogLoadPromise = (async () => {
    const col = collection(db, "articulos");
    const snap = await getDocs(col);
    memoryCatalog = snapToLista(snap);
    return memoryCatalog;
  })();

  try {
    return await catalogLoadPromise;
  } finally {
    catalogLoadPromise = null;
  }
}

export function filterArticulos(
  catalog: ArticuloCatalogo[],
  query: string,
): { items: ArticuloCatalogo[]; totalMatches: number } {
  const q = query.trim();
  if (!q) return { items: [], totalMatches: 0 };

  const palabras = q.toLowerCase().split(/\s+/).filter(Boolean);
  const items: ArticuloCatalogo[] = [];
  let totalMatches = 0;

  for (const item of catalog) {
    const codigo = item.codigo ? item.codigo.toLowerCase() : "";
    const desc = item.desc ? item.desc.toLowerCase() : "";
    const alias = item.alias ? item.alias.toLowerCase() : "";
    const textoCompleto = `${codigo} ${desc} ${alias}`;
    if (!palabras.every((palabra) => textoCompleto.includes(palabra))) continue;

    totalMatches += 1;
    if (items.length < MAX_SEARCH_RESULTS) items.push(item);
  }

  return { items, totalMatches };
}
