import type { VercelRequest, VercelResponse } from "@vercel/node";

/**
 * Proxy serverless: el frontend en Vercel (HTTPS) llama a /api/* en el mismo
 * origen y esta función reenvía a etiquetas-api (LAN vía túnel HTTPS o URL pública).
 * Evita mixed-content (HTTPS → HTTP) y CORS en el navegador.
 *
 * Variable en Vercel (solo servidor): ETIQUETAS_API_ORIGIN
 *   Ej: https://etiquetas-api.tudominio.com  (sin barra final)
 */
export default async function handler(req: VercelRequest, res: VercelResponse) {
  const origin = process.env.ETIQUETAS_API_ORIGIN?.replace(/\/$/, "");
  if (!origin) {
    res.status(503).json({
      detail:
        "ETIQUETAS_API_ORIGIN no está configurada en Vercel. " +
        "Apuntala a la API accesible desde internet (túnel HTTPS o hosting).",
    });
    return;
  }

  const segs = req.query.path;
  const pathPart = Array.isArray(segs) ? segs.join("/") : segs ?? "";
  const qs = req.url?.includes("?") ? req.url.slice(req.url.indexOf("?")) : "";
  const target = `${origin}/${pathPart}${qs}`;

  const headers: Record<string, string> = {};
  const ct = req.headers["content-type"];
  if (typeof ct === "string") headers["Content-Type"] = ct;

  const init: RequestInit = { method: req.method, headers };

  if (req.method && !["GET", "HEAD"].includes(req.method) && req.body) {
    init.body =
      typeof req.body === "string" ? req.body : JSON.stringify(req.body);
  }

  try {
    const upstream = await fetch(target, init);
    const body = await upstream.text();
    res.status(upstream.status);
    const skip = new Set(["transfer-encoding", "connection", "keep-alive"]);
    upstream.headers.forEach((value, key) => {
      if (!skip.has(key.toLowerCase())) res.setHeader(key, value);
    });
    res.send(body);
  } catch {
    res.status(502).json({
      detail: `No se pudo contactar la API en ${origin}. ¿Está encendida y accesible?`,
    });
  }
}
