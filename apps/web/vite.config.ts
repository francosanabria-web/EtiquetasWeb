import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

/** Proxy — timeout largo: KPIs lee Excel en G: (red) */
const proxyOpts = { changeOrigin: true, timeout: 120_000, proxyTimeout: 120_000 };

const proxyEmail = {
  "/api/email": {
    target: "http://127.0.0.1:8020",
    ...proxyOpts,
  },
};

const proxyMinuta = {
  "/api/minuta": {
    target: "http://127.0.0.1:8013",
    ...proxyOpts,
  },
};

const proxyKpis = {
  "/api/kpis": {
    target: "http://127.0.0.1:8001",
    ...proxyOpts,
  },
};

const proxySolicitudes = {
  "/api/solicitudes": {
    target: "http://127.0.0.1:8014",
    ...proxyOpts,
  },
};

const proxyUsuarios = {
  "/api/usuarios": {
    target: "http://127.0.0.1:8015",
    ...proxyOpts,
  },
};

const proxyActivos = {
  "/api/activos": {
    target: "http://127.0.0.1:8016",
    ...proxyOpts,
  },
};

const proxyReportes = {
  "/api/reportes": {
    target: "http://127.0.0.1:8017",
    ...proxyOpts,
  },
};

const proxySalidas = {
  "/api/salidas": {
    target: "http://127.0.0.1:8018",
    ...proxyOpts,
  },
};

const proxyPersonal = {
  "/api/personal": {
    target: "http://127.0.0.1:8019",
    ...proxyOpts,
  },
  "/api/areas": {
    target: "http://127.0.0.1:8019",
    ...proxyOpts,
  },
};

const proxyCajas = {
  "/api/cajas": {
    target: "http://127.0.0.1:8021",
    ...proxyOpts,
  },
};

const serverOpts = {
  host: true,
  port: 5180,
  allowedHosts: true as const,
  proxy: {
    ...proxyEmail,
    ...proxyMinuta,
    ...proxyKpis,
    ...proxySolicitudes,
    ...proxyUsuarios,
    ...proxyActivos,
    ...proxyReportes,
    ...proxySalidas,
    ...proxyPersonal,
    ...proxyCajas,
  },
};

export default defineConfig({
  plugins: [react()],
  server: serverOpts,
  preview: serverOpts,
});
