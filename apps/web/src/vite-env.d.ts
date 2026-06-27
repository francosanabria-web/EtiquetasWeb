/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_ETIQUETAS_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
