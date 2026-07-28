/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_ETIQUETAS_URL?: string;
  readonly VITE_EMAIL_API_URL?: string;
  readonly VITE_KPIS_API_URL?: string;
  readonly VITE_BUSCADOR_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
