import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Servidor de desarrollo accesible desde la red local (tablets/otras PCs).
export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
  },
});
